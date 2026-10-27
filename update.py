#!/usr/bin/env python3
"""Piyasa Komuta Paneli - gece veri güncelleyici (v2, doğruluk öncelikli).

GitHub Actions üzerinde çalışır ve data.json üretir.

Kaynaklar
  - Fiyat/hacim: Yahoo Finance halka açık grafik verisi (yfinance) - resmi borsa verisi DEĞİL.
    Bu yüzden VIX kapanışı Cboe'nin resmi dosyasıyla, S&P 500 ve Nasdaq Composite ise SPY ve QQQ ile çapraz doğrulanır.
  - S&P 500 hisse listesi: iShares IVV resmi holdings CSV (yedek: datasets/s-and-p-500-companies)
  - Getiri eğrisi: U.S. Treasury günlük par getiri eğrisi (resmi kaynağın kendisi)

Koruma kuralları (veri uydurmak yerine çalışmayı durdurur, eski sayfa yerinde kalır)
  - Piyasa kapanışından önce (New York 16:30) alınan günlük veri reddedilir
  - Hisse verisi kapsamı %95'in altındaysa durur
  - Yahoo, resmi dosyayla (VIX) aynı tarihte %1'den fazla ayrışırsa durur
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
    ("BTC", "BTC-USD", "Bitcoin", True),
    # Asya borsaları kendi saatinde kapanır; ABD referans gününe göre "eski" sayılmaz
    ("KOSPI", "^KS11", "KOSPI (Güney Kore)", True),
    ("NIKKEI", "^N225", "Nikkei 225 (Japonya)", True),
]
ETFS = [
    ("SPY", "SPDR S&P 500 ETF"),
    ("QQQ", "Invesco QQQ (Nasdaq-100)"),
    ("IWM", "iShares Russell 2000 ETF"),
    ("RSP", "Invesco S&P 500 Equal Weight ETF"),
    ("QQQE", "Direxion Nasdaq-100 Equal Weighted ETF"),
    ("RWJ", "Invesco S&P SmallCap 600 Revenue ETF"),
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
# (panel adı, Yahoo sembolü, izin verilen fark %). Yalnız VIX için resmi günlük dosya (Cboe) runner'dan alınabiliyor.
PRICE_VERIFY = [("VIX", "^VIX", 0.50)]
MIN_COVERAGE = 0.95        # altında çalışma durur
GOOD_COVERAGE = 0.98       # altında veri kalitesi düşer
HARD_DIFF_PCT = 1.0        # Yahoo-resmi dosya farkı bunu aşarsa çalışma durur
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


def http_get(url, tries=3, timeout=30, headers=None):
    last = None
    for i in range(tries):
        t0 = time.time()
        try:
            resp = requests.get(url, headers=headers or HEADERS, timeout=(10, timeout))
            if resp.status_code == 200 and resp.text:
                return resp
            last = f"HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        log(f"  http deneme {i + 1}/{tries} başarısız ({int(time.time() - t0)}s): {url[:60]} -> {last[:100]}")
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
    for n in (50, 100, 200):
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
    hi = float(c.iloc[-252:].max())
    out["from_high"] = r((c.iloc[-1] / hi - 1) * 100) if hi > 0 else None
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
    for n in (50, 100, 200):
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


def sector_participation(frames):
    """Sektör ETF'lerinin kaçı kendi 50 günlük ortalamasının üstünde (fiyat bazlı vekil, bileşen genişliği değildir)."""
    cols = {}
    for sym, _ in SECTORS:
        if sym in frames:
            c = frames[sym]["Close"].astype(float)
            cols[sym] = c
    if len(cols) < 6:
        return None
    df = pd.DataFrame(cols).dropna(how="all")
    ma = df.rolling(50, min_periods=50).mean()
    valid = ma.notna() & df.notna()
    above = (df > ma) & valid
    cnt = valid.sum(axis=1)
    pct = (above.sum(axis=1) / cnt.replace(0, np.nan) * 100).dropna()
    pct = pct[cnt.loc[pct.index] >= 6].iloc[-60:]
    if len(pct) < 10:
        return None
    return {"count": int(cnt.loc[pct.index[-1]]), "above": int(above.sum(axis=1).loc[pct.index[-1]]),
            "pct": r(pct.iloc[-1], 0),
            "d5": r(pct.iloc[-1] - pct.iloc[-6], 0) if len(pct) > 5 else None,
            "dates": [d.strftime("%Y-%m-%d") for d in pct.index], "series": [r(x, 1) for x in pct.tolist()]}


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
                     "above50": above50, "above100": m.get("above100"), "above200": m.get("above200"),
                     "dist50": m.get("dist50"), "dist100": m.get("dist100"), "dist200": m.get("dist200"),
                     "from_high": m.get("from_high"), "trend": m.get("trend"), "status": status,
                     "vol_vs20": m["vol_vs20"], "vol_vs50": m.get("vol_vs50"), "spark": m.get("spark")})
    rows.sort(key=lambda x: (x["rel20"] is None, -(x["rel20"] or 0)))
    return rows


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


REGIME_VERSION = "SP500-trend-v2"
TREND_MA, TREND_BAND, TREND_CONFIRM = 200, 0.015, 2


def regime(spx_close, vix_close, closes, n_total, ref_date):
    """S&P 500 trend rejimi. Kural: 200 gunluk ortalamanin %1,5 uzerinde 2 kapanis = RISK_ON, %1,5 altinda 2 kapanis = RISK_OFF,
    aradayken onceki durum korunur. Gecmis testte (1993-2026) en buyuk dusus -55'ten -20'ye indi. VIX ve genislik yalnizca bilgidir, puanlanmaz."""
    dq = {"sources": ["S&P 500 (^GSPC) gunluk kapanis: Yahoo Finance, resmi degil, fiyat endeksi"], "missing_data": [], "stale_data": [], "warnings": []}
    out = {"as_of_date": None, "market_regime": "INSUFFICIENT_DATA", "state_since": None, "days_in_state": None, "close": None,
           "sma200": None, "distance_pct": None, "lower_band": None, "upper_band": None,
           "context": {"vix": None, "vix_percentile": None, "breadth_pct200": None, "breadth_valid": None, "breadth_total": n_total},
           "data_quality": dq, "methodology_version": REGIME_VERSION}
    s = spx_close.dropna()
    if len(s) < TREND_MA + 60:
        dq["missing_data"].append(f"S&P 500 gecmisi yetersiz ({len(s)} gun)")
        return out
    last = s.index[-1]
    if last.strftime("%Y-%m-%d") != ref_date:
        dq["stale_data"].append(f"S&P 500 uzun gecmis son verisi {last.strftime('%Y-%m-%d')}, referans {ref_date}")
        return out
    ma = s.rolling(TREND_MA).mean()
    on, since, flips, up, dn, hist = None, None, 0, 0, 0, []
    for d, c, m in zip(s.index, s.values, ma.values):
        if np.isnan(m):
            continue
        up = up + 1 if c > m * (1 + TREND_BAND) else 0
        dn = dn + 1 if c < m * (1 - TREND_BAND) else 0
        if on is None:
            on = bool(c > m)
            continue
        new = True if up >= TREND_CONFIRM else (False if dn >= TREND_CONFIRM else on)
        if new != on:
            on, since, flips = new, d, flips + 1
            hist.append({"date": d.strftime("%Y-%m-%d"), "to": "RISK_ON" if new else "RISK_OFF"})
    close, m = float(s.iloc[-1]), float(ma.iloc[-1])
    out.update({"as_of_date": ref_date, "market_regime": "RISK_ON" if on else "RISK_OFF", "close": r(close, 2), "sma200": r(m, 2),
                "distance_pct": r((close / m - 1) * 100, 2), "lower_band": r(m * (1 - TREND_BAND), 2), "upper_band": r(m * (1 + TREND_BAND), 2)})
    out["recent_flips"] = hist[-4:][::-1]
    if since is not None:
        out["state_since"] = since.strftime("%Y-%m-%d")
        out["days_in_state"] = int((s.index > since).sum())
    else:
        dq["warnings"].append("Durum degisimi mevcut gecmiste yok, baslangic tarihi bilinmiyor")

    ctx = out["context"]
    vs = vix_close.dropna()
    vs = vs[vs.index <= last].tail(252) if len(vs) else vs
    if len(vs) >= 252 and vs.index[-1] == last:
        ctx["vix"] = r(float(vs.iloc[-1]), 2)
        ctx["vix_percentile"] = r(float((vs <= vs.iloc[-1]).sum()) / len(vs) * 100, 0)
    if closes is not None and n_total:
        c2 = closes[closes.index <= last]
        if len(c2) >= 200 and c2.index[-1] == last:
            pct, cnt, _ab = breadth_series(c2, 200)
            pct = pct.dropna()
            if len(pct) and pct.index[-1] == last:
                valid = int(cnt.loc[last])
                if valid / n_total >= MIN_COVERAGE:
                    ctx["breadth_pct200"], ctx["breadth_valid"] = r(pct.iloc[-1], 1), valid
    return out


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


def cboe_vix():
    """VIX günlük kapanışı: Cboe'nin kendi resmi tarihsel dosyası."""
    resp = http_get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", tries=2, timeout=30)
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = [c.strip().upper() for c in df.columns]
    df["DATE"] = pd.to_datetime(df["DATE"])
    df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")
    return df.dropna(subset=["CLOSE"]).set_index("DATE")["CLOSE"].tail(30)


def verify_prices(frames, ref_date):
    """VIX, Cboe'nin resmi dosyasıyla doğrulanır. SPX ve NASDAQ için resmi günlük dosya alınamıyor; onlar verify_proxies ile SPY ve QQQ'ya karşı kontrol edilir."""
    out = []
    for key, ysym, tol in PRICE_VERIFY:
        item = {"id": key, "source": "Cboe VIX_History", "tol_pct": tol, "kind": "price"}
        try:
            if ysym not in frames:
                raise RuntimeError("Yahoo verisi yok")
            item.update(compare_series(frames[ysym]["Close"], cboe_vix(), tol, ref_date, rel=True))
        except Exception as e:  # noqa: BLE001
            item.update(status="unavailable", note=str(e)[:140])
        out.append(item)
    return out


# ---------------------------------------------------------------------- getiri
def get_yields():
    """2Y/10Y getiri: U.S. Treasury günlük par getiri eğrisi (resmi dosyanın kendisi)."""
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
        if m.get("above200") is False and m["dist200"] <= -1.5:
            add("bad", f"{key} 200G ALTINDA", f"{key} 200 günlük ortalamanın %{tr(abs(m['dist200']), 1)} altında (%1,5'lik bandın dışında).")
        elif m.get("above200") is False:
            add("warn", f"{key} 200G'YE YAKIN", f"{key} 200 günlük ortalamanın %{tr(abs(m['dist200']), 1)} altında, %1,5'lik band içinde.")
        elif m.get("above50") is False:
            add("warn", f"{key} 50G ALTINDA", f"{key} 50 günlük ortalamanın %{tr(abs(m['dist50']), 1)} altında.")
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
            add("warn", f"{v['id']} DOĞRULAMA", f"{v['id']} ile {v.get('source', 'resmi kaynak')} arasında {unit}{tr(abs(v['worst_diff']), 2)}{tail} fark var, izin verilen {unit}{tr(v['tol_pct'], 2)}{tail}.")
    if universe and not universe["official"]:
        add("info", "HİSSE LİSTESİ", "S&P 500 hisse listesi resmi kaynaktan alınamadı, GitHub'daki topluluk listesi kullanıldı.")
    return notes


def verify_proxies(frames, ref_date, tol=0.5):
    """Resmi kaynak yokken: endeksin günlük getirisi ile aynı endeksi izleyen ETF'in getirisi uyuşmalı."""
    out = []
    for idx_sym, etf_sym, name in (("^GSPC", "SPY", "SPX"), ("^IXIC", "QQQ", "NASDAQ")):
        item = {"id": name, "etf": etf_sym, "kind": "proxy"}
        try:
            a, b = frames[idx_sym]["Close"], frames[etf_sym]["Close"]
            a, b = a[a.index <= pd.Timestamp(ref_date)], b[b.index <= pd.Timestamp(ref_date)]
            if a.index[-1] != b.index[-1] or len(a) < 2 or len(b) < 2:
                raise RuntimeError("tarihler uyuşmuyor")
            ra, rb = pct_change(a, 1), pct_change(b, 1)
            diff = abs(ra - rb)
            item.update(date=a.index[-1].strftime("%Y-%m-%d"), index_d1=r(ra, 3), etf_d1=r(rb, 3), diff=r(diff, 3),
                        status="ok" if diff <= tol else "bad")
        except Exception as e:  # noqa: BLE001
            item.update(status="unavailable", note=str(e)[:120])
        out.append(item)
    return out


def data_quality(universe, coverage, verification, warnings, proxies=None):
    level, reasons = 3, []
    if not universe or not universe["official"]:
        level = min(level, 2)
        reasons.append("Hisse listesi resmi kaynaktan alınamadı")
    if coverage and coverage["ratio"] < GOOD_COVERAGE:
        level = min(level, 2)
        reasons.append(f"Hisse kapsamı %{tr(coverage['ratio'] * 100, 1)}")
    vix_ok = any(v["status"] == "ok" for v in verification)
    prox_ok = bool(proxies) and all(p["status"] == "ok" for p in proxies)
    if not vix_ok and not prox_ok:
        level = 1
        reasons.append("Hiçbir fiyat bağımsız kaynakla doğrulanamadı")
    else:
        if not vix_ok:
            level = min(level, 2)
            reasons.append("VIX, Cboe resmi dosyasıyla doğrulanamadı")
        elif any(v["status"] == "warn" for v in verification):
            level = min(level, 2)
            reasons.append("VIX'te Yahoo ile Cboe dosyası arasında küçük fark var")
        elif not all(v.get("covers_ref") for v in verification if v["status"] == "ok"):
            reasons.append("Cboe dosyası son günü henüz yayınlamadı, bir önceki güne kadar doğrulandı (sabah yenilenir)")
        if not prox_ok:
            level = min(level, 2)
            reasons.append("S&P 500 ve Nasdaq, SPY ve QQQ ile çapraz doğrulanamadı")
    if warnings:
        level = min(level, 2)
        reasons.append(f"{len(warnings)} veri uyarısı")
    return {"level": {3: "YÜKSEK", 2: "ORTA", 1: "DÜŞÜK"}[level], "reasons": reasons}


# ----------------------------------------------------------------------- ana akış
# ------------------------------------------------------------------ yapay zeka bölümü
def load_holdings():
    """Resmi ETF bileşen dosyaları (holdings.json): {ETF: {asof, source, items:[{symbol,name,weight}]}}"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdings.json")
    with open(path, encoding="utf-8") as f:
        h = json.load(f)
    uni = {}
    for etf, blk in h.items():
        for it in blk["items"]:
            e = uni.setdefault(it["symbol"], {"name": it["name"], "w": {}})
            e["w"][etf] = it.get("weight", 0)
    h.pop("WATCH", None)  # izleme listesi ETF bileşeni değil: ETF içi görünüme girmez, hisse tablosuna ve genişliğe girer
    return h, uni


def volume_trend(f):
    """Hacim eğilimi: son 5 günün ortalaması / son 20 günün ortalaması. +-%20 eşik. Hacim yoksa None."""
    if "Volume" not in f or len(f) < 25:
        return None, None
    v = f["Volume"].astype(float)
    a20 = float(v.iloc[-20:].mean())
    a5 = float(v.iloc[-5:].mean())
    if not a20 > 0 or (v.iloc[-20:] > 0).sum() < 15:
        return None, None
    ch = (a5 / a20 - 1) * 100
    return r(ch, 1), ("Artıyor" if ch >= 20 else ("Azalıyor" if ch <= -20 else "Normal"))


def market_caps(symbols, closes, budget=240):
    """Piyasa değeri (USD) = Yahoo hisse adedi x referans günü kapanışı x USD kuru. Alınamayan hisse için değer yok (None)."""
    import yfinance as yf
    t0 = time.time()
    info = {}
    for s in symbols:
        if time.time() - t0 > budget:
            log("UYARI: piyasa değeri süre sınırına ulaştı")
            break
        try:
            fi = yf.Ticker(s).fast_info
            n, cur = fi["shares"], fi["currency"]
            if n and cur:
                info[s] = (float(n), str(cur))
        except Exception as e:  # noqa: BLE001
            log(f"  piyasa değeri alınamadı {s}: {repr(e)[:80]}")
    fx = {}
    need = sorted({c for _, c in info.values() if c != "USD"})
    if need:
        ff, _ = download([f"{c}USD=X" for c in need], period="1mo", tries=2, max_seconds=60)
        for c in need:
            f = ff.get(f"{c}USD=X")
            if f is not None and len(f):
                fx[c] = float(f["Close"].iloc[-1])
    out = {}
    for s, (n, cur) in info.items():
        rate = 1.0 if cur == "USD" else fx.get(cur)
        close = closes.get(s)
        if rate is None or close is None:
            continue
        cap = n * close * rate
        if 1e7 < cap < 1e14:
            out[s] = round(cap / 1e6, 0) * 1e6
    return out


def ai_block(ref_date, spy, qqq):
    out = {"available": False}
    try:
        holdings, uni = load_holdings()
        etf_frames, miss_etf = download([t for t, _ in AI_ETFS], tries=2, max_seconds=90)
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
        hi = c.iloc[-252:].max()
        m.update({"symbol": t, "name": name, "available": True, "d60": r(pct_change(c, 60)), "rel": rel,
                  "from_high": r((c.iloc[-1] / hi - 1) * 100) if hi else None})
        etfs.append(m)
    spy20 = pct_change(spy["Close"][spy.index <= ref], 20)
    rows = []
    for t, f in stock_frames.items():
        f = f[f.index <= ref]
        if len(f) < 60 or f.index[-1] < ref - pd.Timedelta(days=4):
            continue
        m = metrics(f)
        c = f["Close"]
        hi = c.iloc[-252:].max()
        v5, vtr = volume_trend(f)
        rows.append({
            "symbol": t, "name": uni[t]["name"], "w": uni[t]["w"], "memory": "DRAM" in uni[t]["w"],
            "watch": set(uni[t]["w"]) == {"WATCH"},
            "close": m["close"], "date": m["date"], "d1": m["d1"], "d5": m["d5"], "d20": m["d20"],
            "rel20": r(m["d20"] - spy20) if (m["d20"] is not None and spy20 is not None) else None,
            "above50": m["above50"], "above100": m["above100"], "above200": m["above200"],
            "from_high": r((c.iloc[-1] / hi - 1) * 100) if hi else None,
            "vol_vs20": m["vol_vs20"], "vol5_vs20": v5, "vol_trend": vtr, "trend": m["trend"],
        })
    if len(rows) < 12:
        out["error"] = "Yeterli bileşen verisi alınamadı"
        out["etfs"] = etfs
        return out
    try:
        mc = market_caps([x["symbol"] for x in rows], {x["symbol"]: x["close"] for x in rows})
    except Exception as e:  # noqa: BLE001
        log("Piyasa değeri bölümü atlandı:", repr(e)[:120])
        mc = {}
    for x in rows:
        x["mcap"] = mc.get(x["symbol"])
    log(f"piyasa değeri: {len(mc)}/{len(rows)} hisse")
    n = len(rows)

    def share(rs, k):
        den = sum(1 for x in rs if x[k] is not None)
        return r(100 * sum(1 for x in rs if x[k]) / den, 1) if den else None

    d20s = [x["d20"] for x in rows if x["d20"] is not None]
    detail = {}
    for etf, blk in holdings.items():
        mem = [x for x in rows if etf in x["w"]]
        tot = sum(i["weight"] for i in blk["items"])
        wsum = sum(x["w"][etf] for x in mem)

        def wavg(k):
            v = [(x["w"][etf], x[k]) for x in mem if x[k] is not None]
            return r(sum(w * y for w, y in v) / sum(w for w, _ in v)) if v else None

        def wshare(k):
            den = sum(x["w"][etf] for x in mem if x[k] is not None)
            return r(100 * sum(x["w"][etf] for x in mem if x[k]) / den, 1) if den else None

        e20 = [x["d20"] for x in mem if x["d20"] is not None]
        own = next((e for e in etfs if e["symbol"] == etf and e["available"]), None)
        eq20 = r(float(np.mean(e20))) if e20 else None
        verdict = None
        if own and own.get("d20") is not None and eq20 is not None:
            diff = eq20 - own["d20"]
            verdict = "GENİŞ" if diff >= 1 else "DAR" if diff <= -1 else "DENGELİ"
        detail[etf] = {
            "asof": blk["asof"], "source": blk["source"], "listed": len(blk["items"]), "covered": len(mem),
            "covered_weight": r(100 * wsum / tot, 1) if tot else None,
            "w_d1": wavg("d1"), "w_d5": wavg("d5"), "w_d20": wavg("d20"), "eq_d20": eq20, "verdict": verdict,
            "above50_n": share(mem, "above50"), "above50_w": wshare("above50"),
            "above100_n": share(mem, "above100"), "above100_w": wshare("above100"),
            "above200_n": share(mem, "above200"), "above200_w": wshare("above200"),
            "top": [{"symbol": x["symbol"], "weight": x["w"][etf], "d1": x["d1"], "d20": x["d20"]}
                    for x in sorted(mem, key=lambda z: -z["w"][etf])[:5]],
        }
    by20 = sorted([x for x in rows if x["d20"] is not None], key=lambda x: x["d20"], reverse=True)
    memrows = [x for x in rows if x["memory"]]
    m20 = [x["d20"] for x in memrows if x["d20"] is not None]
    out.update({
        "available": True, "date": ref_date, "etfs": etfs, "detail": detail,
        "count": n, "requested": len(uni), "missing": miss[:15],
        "breadth": {"above50": share(rows, "above50"), "above100": share(rows, "above100"),
                    "above200": share(rows, "above200"),
                    "positive_d20": r(100 * sum(1 for d in d20s if d > 0) / len(d20s), 1) if d20s else None,
                    "near_high": r(100 * sum(1 for x in rows if x["from_high"] is not None and x["from_high"] > -5) / n, 1)},
        "memory": {"count": len(memrows), "avg_d20": r(float(np.mean(m20))) if m20 else None},
        "volume": {"rising": sum(1 for x in rows if x["vol_trend"] == "Artıyor"),
                   "falling": sum(1 for x in rows if x["vol_trend"] == "Azalıyor"),
                   "valid": sum(1 for x in rows if x["vol_trend"] is not None)},
        "leaders": [{k: x[k] for k in ("symbol", "name", "d1", "d20")} for x in by20[:6]],
        "laggards": [{k: x[k] for k in ("symbol", "name", "d1", "d20")} for x in by20[-6:][::-1]],
        "stocks": sorted(rows, key=lambda x: (-max(x["w"].values()), x["symbol"])),
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
                      "live": sym == "BTC-USD",  # 7/24 işlem görür: değer anlık, ABD kapanışı değil
                      "stale": (not h24) and m["date"] < ref_date})
            idx[key] = m
    etf_frames = {t: macro_frames[t] for t, _ in ETFS + SECTORS if t in macro_frames}
    etf = {t: dict(metrics(etf_frames[t]), symbol=t, name=n) for t, n in ETFS if t in etf_frames}

    universe = get_universe()
    breadth, coverage, closes = {}, None, None
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
    sector_part = sector_participation(etf_frames)
    ai = {"available": False}
    if "SPY" in etf_frames and "QQQ" in etf_frames:
        ai = ai_block(ref_date, etf_frames["SPY"], etf_frames["QQQ"])
        if not ai.get("available"):
            warnings.append("Yapay zeka bölümü eksik: " + str(ai.get("error")))
    ydf, ysrc = get_yields()
    yields = yield_block(ydf, ysrc)

    verification = verify_prices(macro_frames, ref_date)
    bad = [v for v in verification if v["status"] == "bad"]
    if bad:
        for v in bad:
            log(f"HATA: {v['id']} Yahoo={v.get('yahoo')} resmi={v.get('official')} ({v.get('date')}) fark={v.get('worst_diff')}; güncelleme iptal.")
        sys.exit(1)
    for v in verification:
        if v["id"] in idx:
            idx[v["id"]]["verify"] = {k: v.get(k) for k in ("status", "date", "diff", "source", "covers_ref")}

    spx_long = macro_frames["^GSPC"]["Close"]
    try:
        lf, _ = download(["^GSPC"], period="5y", tries=2)
        if "^GSPC" in lf and len(lf["^GSPC"]) > len(spx_long):
            spx_long = lf["^GSPC"]["Close"]
    except Exception as e:  # noqa: BLE001
        log("Uzun S&P 500 gecmisi alinamadi:", repr(e)[:160])
    reg = regime(spx_long, macro_frames["^VIX"]["Close"] if "^VIX" in macro_frames else pd.Series(dtype=float),
                 closes, len(universe["tickers"]) if universe else 0, ref_date)
    notes = build_notes(idx, etf, breadth, pairs, yields, sectors, verification, universe)
    proxies = verify_proxies(macro_frames, ref_date)
    if any(p["status"] == "bad" for p in proxies):
        log("HATA: endeks ile ETF getirileri tutarsız, güncelleme iptal:", proxies)
        sys.exit(1)
    dq = data_quality(universe, coverage, verification, warnings, proxies)

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
            "proxy_checks": proxies,
            "sources": [
                {"name": "Yahoo Finance halka açık grafik verisi (yfinance)", "official": False,
                 "use": "Fiyat, hacim, endeksler, ETF'ler. VIX resmi Cboe dosyasıyla, S&P 500 ve Nasdaq SPY ve QQQ ile çapraz kontrol edilir"},
                {"name": "Cboe VIX tarihsel dosyası", "official": True, "use": "VIX doğrulaması (son gün ertesi sabah yayınlanır)"},
                {"name": universe["source"] if universe else "Hisse listesi alınamadı",
                 "official": bool(universe and universe["official"]), "use": "S&P 500 bileşen listesi"},
                {"name": ysrc or "Getiri verisi alınamadı", "official": bool(ysrc and "Treasury" in ysrc),
                 "use": "2Y/10Y getiri"},
            ],
        },
        "indexes": idx, "etfs": etf, "breadth": breadth, "pairs": pairs,
        "sectors": sectors, "sector_participation": sector_part, "ai": ai, "yields": yields, "regime": reg, "notes": notes,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, indent=1)
    log(f"data.json yazıldı | referans kapanış: {ref_date} | kalite: {dq['level']} | "
        f"kapsam: {coverage['received'] if coverage else '-'}/{coverage['requested'] if coverage else '-'} | "
        f"doğrulama: " + ", ".join(f"{v['id']}={v['status']}" for v in verification))


if __name__ == "__main__":
    main()
