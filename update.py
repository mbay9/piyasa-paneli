#!/usr/bin/env python3
"""Piyasa Komuta Paneli - gece veri güncelleyici (v2, doğruluk öncelikli).

GitHub Actions üzerinde çalışır ve data.json üretir.

Kaynaklar
  - Fiyat/hacim: Yahoo Finance halka açık grafik verisi (yfinance) - resmi borsa verisi DEĞİL.
    Bu yüzden S&P 500, Nasdaq Composite ve VIX kapanışları FRED (resmi) ile çapraz doğrulanır.
  - S&P 500 hisse listesi: iShares IVV resmi holdings CSV (yedek: datasets/s-and-p-500-companies)
  - Getiri eğrisi: U.S. Treasury günlük par getiri eğrisi, FRED DGS2/DGS10 ile çapraz doğrulanır

Koruma kuralları (veri uydurmak yerine çalışmayı durdurur, eski sayfa yerinde kalır)
  - Piyasa kapanışından önce (New York 16:30) alınan günlük veri reddedilir
  - Hisse verisi kapsamı %95'in altındaysa durur
  - Yahoo, FRED ile aynı tarihte %1'den fazla ayrışırsa durur
"""
import io
import json
import math
import os
import sys
import time
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

SCRIPT_VERSION = "3"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,text/plain,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# (kısa ad, Yahoo sembolü, açıklama, 7/24 işlem görür mü)
INDEXES = [
    ("SPX", "^GSPC", "S&P 500", False),
    ("NASDAQ", "^IXIC", "Nasdaq Composite", False),
    ("RUT", "^RUT", "Russell 2000", False),
    ("VIX", "^VIX", "CBOE Volatility Index", False),
    ("DXY", "DX-Y.NYB", "ABD Dolar Endeksi", False),
    ("GOLD", "GC=F", "Altın vadeli (ön ay)", False),
    ("SILVER", "SI=F", "Gümüş vadeli (ön ay)", False),
    ("BTC", "BTC-USD", "Bitcoin", True),
]
ETFS = [
    ("SPY", "SPDR S&P 500 ETF"),
    ("QQQ", "Invesco QQQ (Nasdaq-100)"),
    ("IWM", "iShares Russell 2000 ETF"),
    ("RSP", "Invesco S&P 500 Equal Weight ETF"),
    ("QQQE", "Direxion Nasdaq-100 Equal Weighted ETF"),
]
SECTORS = [
    ("XLK", "Technology"), ("XLF", "Financials"), ("XLI", "Industrials"),
    ("XLP", "Consumer Staples"), ("XLE", "Energy"), ("XLV", "Health Care"),
    ("XLB", "Materials"), ("XLRE", "Real Estate"), ("XLC", "Communication Services"),
    ("XLY", "Consumer Discretionary"), ("XLU", "Utilities"),
]
PAIRS = [
    ("RSP", "SPY", "S&P 500: eşit ağırlık (RSP) / piyasa değeri ağırlıklı (SPY)"),
    ("QQQE", "QQQ", "Nasdaq-100: eşit ağırlık (QQQE) / piyasa değeri ağırlıklı (QQQ)"),
]
# (panel adı, Yahoo sembolü, FRED serisi, izin verilen fark %)
PRICE_VERIFY = [
    ("SPX", "^GSPC", "SP500", 0.10),
    ("NASDAQ", "^IXIC", "NASDAQCOM", 0.10),
    ("VIX", "^VIX", "VIXCLS", 0.50),
]
MIN_COVERAGE = 0.95        # altında çalışma durur
GOOD_COVERAGE = 0.98       # altında veri kalitesi düşer
HARD_DIFF_PCT = 1.0        # Yahoo-FRED farkı bunu aşarsa çalışma durur
ISHARES_URL = ("https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
               "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund")
DATASETS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
AI_ETFS = [
    ("SOXX", "iShares Semiconductor ETF"),
    ("SMH", "VanEck Semiconductor ETF"),
    ("DRAM", "Roundhill Memory ETF"),
]
SOXX_URL = ("https://www.ishares.com/us/products/239705/ishares-semiconductor-etf/"
            "1467271812596.ajax?fileType=csv&fileName=SOXX_holdings&dataType=fund")
# Resmi liste okunamazsa kullanılan, elle derlenmiş yapay zeka / yarı iletken çekirdek listesi
AI_CORE = {
    "NVDA": "Yapay zeka çipleri", "AVGO": "Ağ ve özel çip", "AMD": "CPU / GPU", "TSM": "Foundry",
    "ASML": "Litografi", "AMAT": "Ekipman", "LRCX": "Ekipman", "KLAC": "Ekipman", "MU": "Bellek",
    "MRVL": "Özel çip / ağ", "QCOM": "Mobil çip", "INTC": "CPU / foundry", "TXN": "Analog",
    "ADI": "Analog", "MPWR": "Güç yarı iletkenleri", "ARM": "Mimari lisansı", "ON": "Güç / otomotiv",
    "NXPI": "Otomotiv / gömülü", "MCHP": "Mikrodenetleyici", "TER": "Test ekipmanı",
    "WDC": "Depolama", "STX": "Depolama", "SNDK": "NAND bellek", "SMCI": "AI sunucuları",
    "ANET": "AI ağ donanımı", "VRT": "Veri merkezi altyapısı", "SNPS": "Çip tasarım yazılımı",
    "CDNS": "Çip tasarım yazılımı", "000660.KS": "Bellek (SK hynix)", "005930.KS": "Bellek (Samsung)",
}
AI_MEMORY = {"MU", "WDC", "STX", "SNDK", "000660.KS", "005930.KS"}
TICKER_FIX = {"BRKB": "BRK-B", "BFB": "BF-B"}


# ---------------------------------------------------------------- yardımcılar
def log(*a):
    print(*a, file=sys.stderr, flush=True)


def r(x, nd=2):
    """Sayıyı yuvarla; NaN/inf/None -> None (JSON güvenli)."""
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return round(x, nd)


def tr(x, nd=1):
    """Türkçe sayı biçimi: 1.234,5"""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def http_get(url, tries=3, timeout=60, headers=None):
    last = None
    for i in range(tries):
        try:
            resp = requests.get(url, headers=headers or HEADERS, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return resp
            last = f"HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        if i < tries - 1:
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url[:70]}... alınamadı: {last}")


def pct_change(s, n):
    if len(s) <= n:
        return None
    base = s.iloc[-1 - n]
    if not base:
        return None
    return (s.iloc[-1] / base - 1) * 100


def trend_label(close, s50, s200):
    if s50 is None or s200 is None or not math.isfinite(s50) or not math.isfinite(s200):
        return "Belirsiz"
    if close > s50 > s200:
        return "Yükseliş"
    if close < s50 < s200:
        return "Düşüş"
    return "Yatay / karışık"


def metrics(d, use_volume=True):
    """d: Close ve Volume sütunlu DataFrame (tarih indeksli)."""
    c = d["Close"].astype(float)
    v = d["Volume"].astype(float) if (use_volume and "Volume" in d) else pd.Series(dtype=float)
    out = {"date": c.index[-1].strftime("%Y-%m-%d"), "close": r(c.iloc[-1], 4)}
    out["d1"] = r(pct_change(c, 1))
    out["d5"] = r(pct_change(c, 5))
    out["d20"] = r(pct_change(c, 20))
    smas = {}
    for n in (20, 50, 200):
        if len(c) >= n:
            m = float(c.rolling(n).mean().iloc[-1])
            smas[n] = m
            out[f"sma{n}"] = r(m, 4)
            out[f"above{n}"] = bool(c.iloc[-1] > m)
            out[f"dist{n}"] = r((c.iloc[-1] / m - 1) * 100)
        else:
            smas[n] = None
            out[f"sma{n}"] = None
            out[f"above{n}"] = None
            out[f"dist{n}"] = None
    out["trend"] = trend_label(float(c.iloc[-1]), smas[50], smas[200])
    out["vol"] = None
    out["vol_vs20"] = None
    out["vol_vs50"] = None
    if len(v) >= 51 and v.iloc[-1] > 0:
        a20 = v.iloc[-21:-1].mean()
        a50 = v.iloc[-51:-1].mean()
        out["vol"] = int(v.iloc[-1])
        if a20 > 0:
            out["vol_vs20"] = r((v.iloc[-1] / a20 - 1) * 100, 1)
        if a50 > 0:
            out["vol_vs50"] = r((v.iloc[-1] / a50 - 1) * 100, 1)
    out["spark"] = [r(x, 4) for x in c.iloc[-30:].tolist()]
    return out


def breadth_series(closes, n):
    """closes: tarih x hisse DataFrame. n günlük MA üstündeki hisselerin yüzdesi."""
    ma = closes.rolling(n, min_periods=n).mean()
    valid = ma.notna() & closes.notna()
    above = (closes > ma) & valid
    cnt = valid.sum(axis=1)
    pct = above.sum(axis=1) / cnt.replace(0, np.nan) * 100
    return pct, cnt, above.sum(axis=1)


def breadth_block(closes):
    out = {}
    for n in (20, 50, 200):
        pct, cnt, ab = breadth_series(closes, n)
        pct = pct.dropna()
        if pct.empty:
            out[f"ma{n}"] = None
            continue
        out[f"ma{n}"] = {
            "pct": r(pct.iloc[-1], 1),
            "above": int(ab.loc[pct.index[-1]]),
            "total": int(cnt.loc[pct.index[-1]]),
            "d1": r(pct.iloc[-1] - pct.iloc[-2], 1) if len(pct) > 1 else None,
            "d5": r(pct.iloc[-1] - pct.iloc[-6], 1) if len(pct) > 5 else None,
            "spark": [r(x, 1) for x in pct.iloc[-60:].tolist()],
        }
    if len(closes) >= 200:
        hi = closes.rolling(252, min_periods=200).max()
        lo = closes.rolling(252, min_periods=200).min()
        last = closes.iloc[-1]
        out["new_highs"] = int((last >= hi.iloc[-1]).sum())
        out["new_lows"] = int((last <= lo.iloc[-1]).sum())
    else:
        out["new_highs"] = None
        out["new_lows"] = None
    return out


def pair_block(a_name, b_name, label, frames):
    if a_name not in frames or b_name not in frames:
        return {"label": label, "a": a_name, "b": b_name, "available": False}
    a = frames[a_name]["Close"].astype(float)
    b = frames[b_name]["Close"].astype(float)
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    ratio = a / b
    out = {"label": label, "a": a_name, "b": b_name, "available": True,
           "date": idx[-1].strftime("%Y-%m-%d"),
           "ratio": r(ratio.iloc[-1], 4),
           "ratio_d1": r(pct_change(ratio, 1)),
           "ratio_d5": r(pct_change(ratio, 5)),
           "ratio_d20": r(pct_change(ratio, 20))}
    for n, key in ((5, "ret5"), (20, "ret20"), (60, "ret60")):
        ra, rb = pct_change(a, n), pct_change(b, n)
        out[f"{key}_a"] = r(ra)
        out[f"{key}_b"] = r(rb)
        out[f"{key}_diff"] = r(ra - rb) if ra is not None and rb is not None else None
    if len(ratio) >= 50:
        out["ratio_above50"] = bool(ratio.iloc[-1] > ratio.rolling(50).mean().iloc[-1])
    else:
        out["ratio_above50"] = None
    diff = out["ret20_diff"]
    if diff is None:
        out["verdict"] = "Belirsiz"
    elif diff <= -1:
        out["verdict"] = "DAR"
    elif diff >= 1:
        out["verdict"] = "GENİŞ"
    else:
        out["verdict"] = "DENGELİ"
    out["spark"] = [r(x, 4) for x in ratio.iloc[-60:].tolist()]
    return out


def sector_block(frames):
    if "SPY" not in frames:
        return []
    spy20 = pct_change(frames["SPY"]["Close"].astype(float), 20)
    rows = []
    for sym, name in SECTORS:
        if sym not in frames:
            continue
        m = metrics(frames[sym])
        rel = None if spy20 is None or m["d20"] is None else m["d20"] - spy20
        above50 = m.get("above50")
        if rel is None or above50 is None:
            status = "Belirsiz"
        elif rel > 0 and above50:
            status = "Lider"
        elif rel > 0:
            status = "Toparlanıyor"
        elif above50:
            status = "Zayıflıyor"
        else:
            status = "Geride"
        rows.append({"symbol": sym, "name": name, "date": m["date"], "close": m["close"],
                     "d1": m["d1"], "d5": m["d5"], "d20": m["d20"], "rel20": r(rel),
                     "above50": above50, "above200": m.get("above200"), "status": status,
                     "vol_vs20": m["vol_vs20"]})
    rows.sort(key=lambda x: (x["rel20"] is None, -(x["rel20"] or 0)))
    return rows


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def regime(idx_metrics, vix, curve_spread, sectors, dxy):
    """Basit, açık kurallı rejim skoru (0-100). Resmi veri değil, model çıktısıdır."""
    parts = []
    vals = []
    for k in ("SPX", "NASDAQ", "RUT"):
        m = idx_metrics.get(k)
        if m:
            flags = [m.get("above20"), m.get("above50"), m.get("above200")]
            flags = [f for f in flags if f is not None]
            if flags:
                vals.append(sum(1 for f in flags if f) / len(flags) * 100)
    if vals:
        parts.append(("Endeks trendi", r(sum(vals) / len(vals), 0), f"{len(vals)}/3 endeks, 20/50/200 MA üstü oranı"))
    if vix is not None:
        parts.append(("Volatilite", r(clamp((30 - vix) / 18 * 100), 0), f"VIX {tr(vix, 2)}"))
    if curve_spread is not None:
        parts.append(("Getiri eğrisi", r(clamp((curve_spread + 0.5) / 1.5 * 100), 0), f"10Y-2Y {'+' if curve_spread >= 0 else '−'}{tr(abs(curve_spread), 2)} puan"))
    sec = [s for s in sectors if s["above50"] is not None]
    if sec:
        n_up = sum(1 for s in sec if s["above50"])
        parts.append(("Sektör breadth", r(n_up / len(sec) * 100, 0), f"{n_up}/{len(sec)} sektör ETF'i 50G MA üzerinde"))
    if dxy and dxy.get("above50") is not None:
        parts.append(("Dolar", 70 if not dxy["above50"] else 30, "DXY 50G MA altında" if not dxy["above50"] else "DXY 50G MA üzerinde"))
    if not parts:
        return None
    score = sum(p[1] for p in parts) / len(parts)
    label = "RISK_ON" if score >= 65 else ("RISK_OFF" if score < 40 else "NÖTR")
    return {"score": r(score, 0), "label": label,
            "components": [{"name": n, "score": s, "note": t} for n, s, t in parts],
            "note": "Kural tabanlı model: bileşenlerin eşit ağırlıklı ortalaması. Resmi veri değildir."}


# ------------------------------------------------------------------ hisse listesi
def yahoo_symbol(t):
    t = str(t).strip().upper()
    t = TICKER_FIX.get(t, t)
    return t.replace(".", "-")


def parse_ishares(txt):
    lines = txt.lstrip("﻿").splitlines()
    start = next((i for i, ln in enumerate(lines[:80]) if ln.replace('"', "").startswith("Ticker,")), None)
    if start is None:
        raise ValueError("Ticker başlığı bulunamadı; yanıtın başı: " + txt[:160].replace("\n", " "))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), on_bad_lines="skip")
    df = df[df["Asset Class"].astype(str).str.strip() == "Equity"]
    tick = [yahoo_symbol(t) for t in df["Ticker"].dropna() if str(t).strip() not in ("-", "")]
    return sorted(set(tick))


def get_universe():
    ish = ds = None
    try:
        ish = parse_ishares(http_get(ISHARES_URL).text)
    except Exception as e:  # noqa: BLE001
        log("iShares listesi alınamadı:", repr(e))
    try:
        df = pd.read_csv(io.StringIO(http_get(DATASETS_URL).text))
        ds = sorted(set(yahoo_symbol(t) for t in df["Symbol"]))
    except Exception as e:  # noqa: BLE001
        log("Yedek hisse listesi alınamadı:", repr(e))
    ok = lambda x: x is not None and 480 <= len(x) <= 520  # noqa: E731
    if ok(ish):
        tickers, source, official = ish, "iShares IVV holdings CSV (resmi)", True
    elif ok(ds):
        tickers, source, official = ds, "datasets/s-and-p-500-companies (GitHub, resmi değil)", False
    else:
        return None
    check = None
    if ok(ish) and ok(ds):
        a, b = set(ish), set(ds)
        check = {"ishares": len(a), "datasets": len(b), "common": len(a & b),
                 "only_ishares": sorted(a - b)[:12], "only_datasets": sorted(b - a)[:12]}
    return {"tickers": tickers, "source": source, "official": official, "check": check}


# ------------------------------------------------------------------ fiyat verisi
def _download_chunk(chunk, period, hard_timeout=150):
    """yfinance bazen sonsuza dek takılır: ayrı (daemon) iş parçacığında çalıştırıp süre aşımında vazgeçer."""
    import threading
    box = {}

    def work():
        box["r"] = _download_chunk_inner(chunk, period)

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(hard_timeout)
    if th.is_alive():
        log(f"UYARI: {len(chunk)} sembollük indirme {hard_timeout}s içinde dönmedi, atlandı: {chunk[:5]}...")
        return {}
    return box.get("r", {})


def _download_chunk_inner(chunk, period):
    import yfinance as yf  # geç import: testlerde gerekmez
    frames = {}
    try:
        df = yf.download(chunk, period=period, interval="1d", auto_adjust=True,
                         group_by="ticker", threads=True, progress=False, timeout=30)
    except Exception as e:  # noqa: BLE001
        log("indirme hatası:", repr(e))
        return frames
    if df is None or df.empty:
        return frames
    if len(chunk) == 1:
        df = pd.concat({chunk[0]: df}, axis=1)
    for t in chunk:
        try:
            d = df[t][["Close", "Volume"]].dropna(subset=["Close"]).copy()
        except KeyError:
            continue
        d["Volume"] = d["Volume"].fillna(0)
        d = d[d["Close"] > 0]
        d.index = pd.to_datetime(d.index).tz_localize(None)
        d = d[~d.index.duplicated(keep="last")].sort_index()
        if len(d):
            frames[t] = d
    return frames


def download(tickers, period="2y", batch=60, tries=3, max_seconds=420):
    """Yeniden deneyerek indirir. (frames, eksik_semboller) döndürür."""
    frames = {}
    pending = list(tickers)
    t0 = time.time()
    for attempt in range(tries):
        if not pending:
            break
        size = batch if attempt == 0 else 15
        for i in range(0, len(pending), size):
            if time.time() - t0 > max_seconds:
                log(f"UYARI: indirme süre sınırına ({max_seconds}s) ulaştı, {len(pending)} sembol eksik kaldı")
                return frames, [t for t in tickers if t not in frames]
            frames.update(_download_chunk(pending[i:i + size], period))
            log(f"  indirme: {len(frames)}/{len(tickers)} ({int(time.time() - t0)}s)")
            time.sleep(0.3)
        pending = [t for t in tickers if t not in frames]
        if pending and attempt < tries - 1:
            log(f"{len(pending)} sembol eksik, yeniden deneniyor (deneme {attempt + 2}/{tries})")
            time.sleep(5)
    return frames, pending


def ensure_market_closed(ref_date, now_utc=None):
    """Kapanıştan önce alınan (yarım) günlük mumu reddeder."""
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    ny = now.astimezone(ZoneInfo("America/New_York"))
    if ref_date == ny.strftime("%Y-%m-%d") and (ny.hour, ny.minute) < (16, 30) and not os.environ.get("ALLOW_PARTIAL"):
        raise SystemExit(f"HATA: New York saati {ny:%H:%M}, {ref_date} günlük verisi henüz tamamlanmamış olabilir. "
                         "Güncelleme iptal (eski sayfa korunur). Zorlamak için ALLOW_PARTIAL=1.")


def sanity_warnings(frames, ref_date):
    warns = []
    for t, f in frames.items():
        c = f["Close"]
        if len(c) > 1 and t != "BTC-USD":
            d1 = pct_change(c, 1)
            if d1 is not None and abs(d1) > 25:
                warns.append(f"{t}: tek günde %{tr(abs(d1), 1)} {'artış' if d1 > 0 else 'düşüş'}, veri hatası olabilir")
        if t in ("^GSPC", "^IXIC", "^RUT", "^VIX", "SPY", "QQQ", "IWM", "RSP", "QQQE"):
            lag = (pd.Timestamp(ref_date) - c.index[-1]).days
            if lag > 4:
                warns.append(f"{t}: son veri {lag} gün eski")
    return warns


# ---------------------------------------------------------------- resmi doğrulama
def fred_series(sid, days=60):
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    resp = http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}")
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = ["date", "v"]
    df["date"] = pd.to_datetime(df["date"])
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    return df.dropna().set_index("date")["v"]


def compare_series(y, f, tol, ref_date, rel=True):
    """Son 5 ortak günde karşılaştırır. rel=True ise yüzde fark, değilse mutlak fark."""
    common = y.index.intersection(f.index)
    if len(common) == 0:
        return {"status": "unavailable", "note": "ortak tarih yok"}
    days = common[-5:]
    diffs = []
    for d in days:
        yv, fv = float(y.loc[d]), float(f.loc[d])
        diffs.append((yv / fv - 1) * 100 if rel else yv - fv)
    worst = max(diffs, key=abs)
    last = diffs[-1]
    hard = HARD_DIFF_PCT if rel else 0.05
    status = "ok" if abs(worst) <= tol else ("warn" if abs(worst) <= hard else "bad")
    d_last = days[-1]
    return {"status": status, "date": d_last.strftime("%Y-%m-%d"),
            "yahoo": r(y.loc[d_last], 4), "official": r(f.loc[d_last], 4),
            "diff": r(last, 3), "worst_diff": r(worst, 3), "days_checked": len(days),
            "covers_ref": d_last.strftime("%Y-%m-%d") == ref_date,
            "latest_official": f.index[-1].strftime("%Y-%m-%d")}


def verify_prices(frames, ref_date):
    out = []
    for key, ysym, sid, tol in PRICE_VERIFY:
        item = {"id": key, "fred": sid, "tol_pct": tol, "kind": "price"}
        try:
            if ysym not in frames:
                raise RuntimeError("Yahoo verisi yok")
            item.update(compare_series(frames[ysym]["Close"], fred_series(sid), tol, ref_date, rel=True))
        except Exception as e:  # noqa: BLE001
            item.update(status="unavailable", note=str(e)[:140])
        out.append(item)
    return out


def verify_yields(ydf, ysrc, ref_date):
    out = []
    for col, sid, name in (("y2", "DGS2", "US2Y"), ("y10", "DGS10", "US10Y")):
        item = {"id": name, "fred": sid, "tol_pct": 0.011, "kind": "yield"}
        if ydf is None or "Treasury" not in (ysrc or ""):
            item.update(status="unavailable", note="Treasury verisi yok veya kaynak zaten FRED")
        else:
            try:
                item.update(compare_series(ydf[col].astype(float), fred_series(sid), 0.011, ref_date, rel=False))
            except Exception as e:  # noqa: BLE001
                item.update(status="unavailable", note=str(e)[:140])
        out.append(item)
    return out


# ---------------------------------------------------------------------- getiri
def get_yields():
    """2Y/10Y getiri: Treasury CSV, yedek FRED."""
    year = dt.date.today().year
    try:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
               f"&field_tdr_date_value={year}&page&_format=csv")
        df = pd.read_csv(io.StringIO(http_get(url).text))
        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
        df = df.sort_values("Date").dropna(subset=["2 Yr", "10 Yr"])
        if len(df) >= 6:
            return (df.set_index("Date")[["2 Yr", "10 Yr"]].rename(columns={"2 Yr": "y2", "10 Yr": "y10"}),
                    "U.S. Treasury günlük par getiri eğrisi")
    except Exception as e:  # noqa: BLE001
        log("Treasury alınamadı:", repr(e))
    try:
        cols = {}
        for sid, key in (("DGS2", "y2"), ("DGS10", "y10")):
            cols[key] = fred_series(sid, days=90).rename(key)
        df = pd.concat(cols.values(), axis=1).dropna()
        if len(df) >= 6:
            return df, "FRED DGS2 / DGS10 (yedek)"
    except Exception as e:  # noqa: BLE001
        log("FRED getiri alınamadı:", repr(e))
    return None, None


def yield_block(df, source):
    if df is None:
        return {"available": False}
    s2, s10 = df["y2"].astype(float), df["y10"].astype(float)
    spread = s10 - s2

    def bp(s, n):
        return r((s.iloc[-1] - s.iloc[-1 - n]) * 100, 0) if len(s) > n else None

    return {
        "available": True, "source": source, "date": df.index[-1].strftime("%Y-%m-%d"),
        "y2": {"value": r(s2.iloc[-1]), "d1_bp": bp(s2, 1), "d5_bp": bp(s2, 5), "spark": [r(x) for x in s2.iloc[-30:]]},
        "y10": {"value": r(s10.iloc[-1]), "d1_bp": bp(s10, 1), "d5_bp": bp(s10, 5), "spark": [r(x) for x in s10.iloc[-30:]]},
        "spread": {"value": r(spread.iloc[-1]), "d1_bp": bp(spread, 1), "d5_bp": bp(spread, 5), "spark": [r(x) for x in spread.iloc[-30:]]},
    }


# ----------------------------------------------------------------- risk notları
def build_notes(idx, etf, breadth, pairs, yields, sectors, verification, universe):
    notes = []

    def add(level, title, text):
        notes.append({"level": level, "title": title, "text": text})

    vix = idx.get("VIX")
    if vix:
        v = vix["close"]
        if v < 15:
            add("ok", "VIX DÜŞÜK", f"VIX {tr(v, 2)}: 15 altı, piyasa sakin.")
        elif v < 20:
            add("ok", "VIX NORMAL", f"VIX {tr(v, 2)}: 15-20 arası, normal bölge.")
        elif v < 30:
            add("warn", "VIX YÜKSEK", f"VIX {tr(v, 2)}: 20-30 arası, gerginlik var.")
        else:
            add("bad", "VIX ÇOK YÜKSEK", f"VIX {tr(v, 2)}: 30 üstü, stres bölgesi.")
        if vix.get("d5") is not None:
            if vix["d5"] >= 15:
                add("warn", "VIX SIÇRADI", f"VIX 5 işlem gününde %{tr(vix['d5'], 1)} arttı.")
            elif vix["d5"] <= -15:
                add("ok", "VIX GEVŞEDİ", f"VIX 5 işlem gününde %{tr(abs(vix['d5']), 1)} düştü.")
    for key in ("SPX", "NASDAQ", "RUT"):
        m = idx.get(key)
        if not m:
            continue
        if m.get("above200") is False:
            add("bad", f"{key} 200G ALTINDA", f"{key} 200 günlük ortalamanın %{tr(abs(m['dist200']), 1)} altında.")
        elif m.get("above50") is False:
            add("warn", f"{key} 50G ALTINDA", f"{key} 50 günlük ortalamanın %{tr(abs(m['dist50']), 1)} altında.")
    sp = etf.get("SPY")
    if sp and sp.get("vol_vs20") is not None:
        vv = sp["vol_vs20"]
        yon = "üstünde" if vv >= 0 else "altında"
        if vv >= 30:
            add("info", "HACİM YÜKSEK", f"SPY hacmi 20 günlük ortalamanın %{tr(abs(vv), 0)} {yon}.")
        elif vv <= -25:
            add("info", "HACİM DÜŞÜK", f"SPY hacmi 20 günlük ortalamanın %{tr(abs(vv), 0)} {yon}.")
        else:
            add("info", "HACİM NORMAL", f"SPY hacmi 20 günlük ortalamanın %{tr(abs(vv), 0)} {yon}.")
    b50 = (breadth.get("ma50") or {}).get("pct")
    b200 = (breadth.get("ma200") or {}).get("pct")
    if b50 is not None:
        if b50 < 30:
            add("bad", "BREADTH ZAYIF", f"S&P 500 hisselerinin sadece %{tr(b50, 0)}'i 50G MA üstünde.")
        elif b50 < 50:
            add("warn", "BREADTH ORTA-ZAYIF", f"S&P 500 hisselerinin %{tr(b50, 0)}'i 50G MA üstünde.")
        else:
            add("ok", "BREADTH SAĞLAM", f"S&P 500 hisselerinin %{tr(b50, 0)}'i 50G MA üstünde.")
    if b200 is not None and b200 < 40:
        add("warn", "UZUN VADE ZAYIF", f"Hisselerin sadece %{tr(b200, 0)}'i 200G MA üstünde.")
    for p in pairs:
        if not p.get("available") or p.get("ret20_diff") is None:
            continue
        a, b, d = p["a"], p["b"], p["ret20_diff"]
        if p["verdict"] == "DAR":
            add("warn", f"{a}/{b} DAR", f"{a}, {b}'nin 20 günde {tr(abs(d), 1)} puan gerisinde: yükseliş az sayıda büyük hisseyle taşınıyor.")
        elif p["verdict"] == "GENİŞ":
            add("ok", f"{a}/{b} GENİŞ", f"{a}, {b}'nin 20 günde {tr(d, 1)} puan önünde: eşit ağırlıklı endeks de yükseliyor.")
        else:
            add("info", f"{a}/{b} DENGELİ", f"{a} ile {b} 20 günde yakın seyretti ({'+' if d >= 0 else '−'}{tr(abs(d), 1)} puan).")
    y = yields.get("spread") if yields.get("available") else None
    if y and y["value"] is not None:
        if y["value"] < 0:
            add("bad", "TERS EĞRİ", f"10Y-2Y farkı −{tr(abs(y['value']), 2)} puan: eğri ters.")
        else:
            add("ok", "EĞRİ POZİTİF", f"10Y-2Y farkı +{tr(y['value'], 2)} puan.")
    lead = [s["symbol"] for s in sectors if s["status"] == "Lider"][:3]
    lag = [s["symbol"] for s in sectors if s["status"] == "Geride"][-3:]
    if lead:
        add("info", "SEKTÖR LİDERLERİ", "SPY'a göre güçlü ve 50G üstünde: " + ", ".join(lead) + ("; geride kalanlar: " + ", ".join(lag) if lag else "."))
    elif sectors:
        add("warn", "LİDER SEKTÖR YOK", "Hiçbir sektör hem SPY'dan güçlü hem 50G üstünde değil.")
    for v in verification:
        if v["status"] == "warn":
            unit = "%" if v.get("kind") == "price" else ""
            tail = "" if v.get("kind") == "price" else " puan"
            add("warn", f"{v['id']} DOĞRULAMA", f"{v['id']} ile {v['fred']} (FRED, resmi) arasında {unit}{tr(abs(v['worst_diff']), 2)}{tail} fark var, izin verilen {unit}{tr(v['tol_pct'], 2)}{tail}.")
    if universe and not universe["official"]:
        add("info", "HİSSE LİSTESİ", "S&P 500 hisse listesi resmi kaynaktan alınamadı, GitHub'daki topluluk listesi kullanıldı.")
    return notes


def data_quality(universe, coverage, verification, warnings):
    level, reasons = 3, []
    if not universe or not universe["official"]:
        level = min(level, 2)
        reasons.append("Hisse listesi resmi kaynaktan alınamadı")
    if coverage and coverage["ratio"] < GOOD_COVERAGE:
        level = min(level, 2)
        reasons.append(f"Hisse kapsamı %{tr(coverage['ratio'] * 100, 1)}")
    oks = [v for v in verification if v["status"] == "ok"]
    if not oks:
        level = 1
        reasons.append("Hiçbir fiyat resmi kaynakla doğrulanamadı")
    else:
        if any(v["status"] == "unavailable" for v in verification):
            level = min(level, 2)
            reasons.append("Bazı seriler resmi kaynakla doğrulanamadı")
        if any(v["status"] == "warn" for v in verification):
            level = min(level, 2)
            reasons.append("Bazı serilerde Yahoo ile resmi veri arasında küçük fark var")
        if not all(v.get("covers_ref") for v in oks):
            reasons.append("Resmi kaynak son günü henüz yayınlamadı, bir önceki güne kadar doğrulandı (sabah yenilenir)")
    if warnings:
        level = min(level, 2)
        reasons.append(f"{len(warnings)} veri uyarısı")
    return {"level": {3: "YÜKSEK", 2: "ORTA", 1: "DÜŞÜK"}[level], "reasons": reasons}


# ----------------------------------------------------------------------- ana akış
# ------------------------------------------------------------------ yapay zeka bölümü
def get_ai_universe():
    """SOXX resmi holdings (iShares) + çekirdek liste. {ticker: {name, weight, official}}"""
    uni = {t: {"theme": th, "weight": None, "official": False} for t, th in AI_CORE.items()}
    source, official = "Elle derlenmiş çekirdek liste (resmi değil)", False
    try:
        txt = http_get(SOXX_URL).text
        lines = txt.lstrip("﻿").splitlines()
        start = next(i for i, ln in enumerate(lines[:80]) if ln.replace('"', "").startswith("Ticker,"))
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])), on_bad_lines="skip")
        df = df[df["Asset Class"].astype(str).str.strip() == "Equity"]
        got = 0
        for _, row in df.iterrows():
            t = yahoo_symbol(row["Ticker"])
            if t in ("-", "") or str(row["Ticker"]) == "nan":
                continue
            try:
                w = float(row.get("Weight (%)"))
            except (TypeError, ValueError):
                w = None
            e = uni.setdefault(t, {"theme": str(row.get("Name", "")).title()[:28], "weight": None, "official": True})
            e["weight"], e["official"] = r(w, 2), True
            got += 1
        if got >= 20:
            source, official = "iShares SOXX holdings CSV (resmi) + çekirdek liste", True
        else:
            raise ValueError(f"yalnızca {got} satır")
    except Exception as e:  # noqa: BLE001
        log("SOXX holdings alınamadı, çekirdek liste kullanılacak:", repr(e))
        for e_ in uni.values():
            e_["weight"], e_["official"] = None, False
    return uni, source, official


def ai_block(ref_date, spy, qqq):
    out = {"available": False}
    try:
        etf_frames, miss_etf = download([t for t, _ in AI_ETFS], tries=2, max_seconds=90)
        uni, source, official = get_ai_universe()
        stock_frames, miss = download(list(uni), batch=10, tries=2, max_seconds=180)
    except Exception as e:  # noqa: BLE001
        log("AI bölümü alınamadı:", repr(e))
        out["error"] = "Veri alınamadı"
        return out
    ref = pd.Timestamp(ref_date)
    etfs = []
    for t, name in AI_ETFS:
        f = etf_frames.get(t)
        if f is None or f.index[-1] < ref - pd.Timedelta(days=4):
            etfs.append({"symbol": t, "name": name, "available": False})
            continue
        f = f[f.index <= ref]
        m = metrics(f)
        c = f["Close"]
        rel = {}
        for lbl, base in (("spy", spy), ("qqq", qqq)):
            b = base["Close"][base.index <= ref]
            rel[lbl] = {n: r((pct_change(c, n) or 0) - (pct_change(b, n) or 0)) if len(c) > n and len(b) > n else None
                        for n in (20, 60)}
        ret60 = r(pct_change(c, 60))
        hi = c.iloc[-252:].max()
        m.update({"symbol": t, "name": name, "available": True, "d60": ret60, "rel": rel,
                  "from_high": r((c.iloc[-1] / hi - 1) * 100) if hi else None})
        etfs.append(m)
    rows, closes = [], {}
    for t, f in stock_frames.items():
        f = f[f.index <= ref]
        if len(f) < 60 or f.index[-1] < ref - pd.Timedelta(days=4):
            continue
        m = metrics(f)
        c = f["Close"]
        spy20 = pct_change(spy["Close"][spy.index <= ref], 20)
        hi = c.iloc[-252:].max()
        closes[t] = c
        rows.append({
            "symbol": t, "theme": uni[t]["theme"], "weight": uni[t]["weight"], "memory": t in AI_MEMORY,
            "close": m["close"], "d1": m["d1"], "d5": m["d5"], "d20": m["d20"],
            "rel20": r(m["d20"] - spy20) if (m["d20"] is not None and spy20 is not None) else None,
            "above20": m["above20"], "above50": m["above50"], "above200": m["above200"],
            "from_high": r((c.iloc[-1] / hi - 1) * 100) if hi else None,
            "vol_vs20": m["vol_vs20"], "trend": m["trend"],
        })
    if len(rows) < 8:
        out["error"] = "Yeterli bileşen verisi alınamadı"
        out["etfs"] = etfs
        return out
    n = len(rows)
    share = lambda k: r(100 * sum(1 for x in rows if x[k]) / max(1, sum(1 for x in rows if x[k] is not None)), 1)  # noqa: E731
    d20s = [x["d20"] for x in rows if x["d20"] is not None]
    eq20 = r(float(np.mean(d20s))) if d20s else None
    smh = next((e for e in etfs if e["symbol"] == "SMH" and e["available"]), None)
    verdict = None
    if smh and eq20 is not None and smh["d20"] is not None:
        diff = eq20 - smh["d20"]
        verdict = "GENİŞ" if diff >= 1 else "DAR" if diff <= -1 else "DENGELİ"
    by20 = sorted([x for x in rows if x["d20"] is not None], key=lambda x: x["d20"], reverse=True)
    mem = [x for x in rows if x["memory"]]
    mem20 = [x["d20"] for x in mem if x["d20"] is not None]
    out.update({
        "available": True, "date": ref_date, "source": source, "official": official,
        "etfs": etfs, "count": n, "requested": len(uni), "missing": miss[:15],
        "breadth": {"above20": share("above20"), "above50": share("above50"), "above200": share("above200"),
                    "positive_d20": r(100 * len(d20s and [d for d in d20s if d > 0]) / len(d20s), 1) if d20s else None,
                    "near_high": r(100 * sum(1 for x in rows if x["from_high"] is not None and x["from_high"] > -5) / n, 1)},
        "equal_weight_d20": eq20, "verdict": verdict,
        "memory": {"count": len(mem), "avg_d20": r(float(np.mean(mem20))) if mem20 else None},
        "leaders": by20[:6], "laggards": by20[-6:][::-1],
        "stocks": sorted(rows, key=lambda x: (x["weight"] is None, -(x["weight"] or 0), x["symbol"])),
    })
    return out


def main():
    now = dt.datetime.now(dt.timezone.utc)
    macro_frames, missing_macro = download([t for _, t, _, _ in INDEXES] + [t for t, _ in ETFS] + [t for t, _ in SECTORS])
    if "^GSPC" not in macro_frames:
        log("HATA: S&P 500 verisi alınamadı, güncelleme iptal.")
        sys.exit(1)
    ref_date = macro_frames["^GSPC"].index[-1].strftime("%Y-%m-%d")
    ensure_market_closed(ref_date, now)
    warnings = sanity_warnings(macro_frames, ref_date)
    if missing_macro:
        warnings.append("Eksik sembol: " + ", ".join(missing_macro))

    idx = {}
    for key, sym, name, h24 in INDEXES:
        if sym in macro_frames:
            m = metrics(macro_frames[sym], use_volume=False)  # Yahoo endeks/vadeli hacmi güvenilir değil
            m.update({"symbol": key, "yahoo": sym, "name": name, "h24": h24,
                      "stale": (not h24) and m["date"] < ref_date})
            idx[key] = m
    etf_frames = {t: macro_frames[t] for t, _ in ETFS + SECTORS if t in macro_frames}
    etf = {t: dict(metrics(etf_frames[t]), symbol=t, name=n) for t, n in ETFS if t in etf_frames}

    universe = get_universe()
    breadth, coverage = {}, None
    if universe:
        stock_frames, missing = download(universe["tickers"])
        ratio = len(stock_frames) / len(universe["tickers"])
        closes = pd.DataFrame({t: f["Close"] for t, f in stock_frames.items()}).sort_index()
        closes = closes[closes.index <= pd.Timestamp(ref_date)]
        late = int(closes.iloc[-1].isna().sum()) if len(closes) else 0
        coverage = {"requested": len(universe["tickers"]), "received": len(stock_frames),
                    "ratio": r(ratio, 3), "missing": missing[:25], "late": late}
        if ratio < MIN_COVERAGE:
            log(f"HATA: hisse verisi yetersiz ({len(stock_frames)}/{len(universe['tickers'])}), güncelleme iptal. Eksikler: {missing[:30]}")
            sys.exit(1)
        breadth = breadth_block(closes)
        breadth["date"] = closes.index[-1].strftime("%Y-%m-%d")
    else:
        log("UYARI: hisse listesi alınamadı, breadth hesaplanmadı.")
        warnings.append("Hisse listesi alınamadı, breadth hesaplanmadı")

    pairs = [pair_block(a, b, lbl, etf_frames) for a, b, lbl in PAIRS]
    sectors = sector_block(etf_frames)
    ai = {"available": False}
    if "SPY" in etf_frames and "QQQ" in etf_frames:
        ai = ai_block(ref_date, etf_frames["SPY"], etf_frames["QQQ"])
        if not ai.get("available"):
            warnings.append("Yapay zeka bölümü eksik: " + str(ai.get("error")))
    ydf, ysrc = get_yields()
    yields = yield_block(ydf, ysrc)

    verification = verify_prices(macro_frames, ref_date) + verify_yields(ydf, ysrc, ref_date)
    for v in verification:  # getiri farkı ikincil: durdurma, sadece uyar
        if v["kind"] == "yield" and v["status"] == "bad":
            v["status"] = "warn"
    bad = [v for v in verification if v["status"] == "bad"]
    if bad:
        for v in bad:
            log(f"HATA: {v['id']} Yahoo={v.get('yahoo')} resmi={v.get('official')} ({v.get('date')}) fark={v.get('worst_diff')}; güncelleme iptal.")
        sys.exit(1)
    for v in verification:
        if v["id"] in idx:
            idx[v["id"]]["verify"] = {k: v.get(k) for k in ("status", "date", "diff", "fred", "covers_ref")}

    spread_val = yields["spread"]["value"] if yields.get("available") else None
    vix_val = idx["VIX"]["close"] if "VIX" in idx else None
    reg = regime(idx, vix_val, spread_val, sectors, idx.get("DXY"))
    notes = build_notes(idx, etf, breadth, pairs, yields, sectors, verification, universe)
    dq = data_quality(universe, coverage, verification, warnings)

    out = {
        "meta": {
            "version": SCRIPT_VERSION,
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ref_date": ref_date,
            "universe_source": universe["source"] if universe else None,
            "universe_check": universe["check"] if universe else None,
            "coverage": coverage,
            "quality": dq,
            "warnings": warnings[:20],
            "verification": verification,
            "sources": [
                {"name": "Yahoo Finance halka açık grafik verisi (yfinance)", "official": False,
                 "use": "Fiyat, hacim, endeksler, ETF'ler (SPX, NASDAQ, VIX resmi FRED ile doğrulanır)"},
                {"name": universe["source"] if universe else "Hisse listesi alınamadı",
                 "official": bool(universe and universe["official"]), "use": "S&P 500 bileşen listesi"},
                {"name": ysrc or "Getiri verisi alınamadı", "official": bool(ysrc and "Treasury" in ysrc),
                 "use": "2Y/10Y getiri (FRED ile doğrulanır)"},
                {"name": "FRED (St. Louis Fed)", "official": True, "use": "S&P 500, Nasdaq, VIX ve getiri doğrulaması"},
            ],
        },
        "indexes": idx, "etfs": etf, "breadth": breadth, "pairs": pairs,
        "sectors": sectors, "ai": ai, "yields": yields, "regime": reg, "notes": notes,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, indent=1)
    log(f"data.json yazıldı | referans kapanış: {ref_date} | kalite: {dq['level']} | "
        f"kapsam: {coverage['received'] if coverage else '-'}/{coverage['requested'] if coverage else '-'} | "
        f"doğrulama: " + ", ".join(f"{v['id']}={v['status']}" for v in verification))


if __name__ == "__main__":
    main()
