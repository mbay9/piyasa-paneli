#!/usr/bin/env python3
"""Piyasa Komuta Paneli - gece veri güncelleyici (v2, doğruluk öncelikli).

GitHub Actions üzerinde çalışır ve data.json üretir.

Kaynaklar
  - Fiyat/hacim: Yahoo Finance halka açık grafik verisi (yfinance) - resmi borsa verisi DEĞİL.
    Bu yüzden VIX kapanışı Cboe'nin resmi dosyasıyla, S&P 500 SPY ile, Nasdaq Composite ONEQ ile çapraz doğrulanır.
  - S&P 500 hisse listesi: iShares IVV resmi holdings CSV (yedek: datasets/s-and-p-500-companies)

Koruma kuralları (veri uydurmak yerine çalışmayı durdurur, eski sayfa yerinde kalır)
  - Piyasa kapanışından önce (New York 16:30) alınan günlük veri reddedilir
  - Hisse verisi kapsamı %95'in altındaysa durur
  - Yahoo, resmi dosyayla (VIX) aynı tarihte %1'den fazla ayrışırsa durur
"""
import io
import json
import math
import os
import re
import sys
import time
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
from html.parser import HTMLParser

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
PROXY_ONLY = ["ONEQ"]      # yalnız Nasdaq Composite çapraz kontrolü için indirilir, sitede gösterilmez
MIN_COVERAGE = 0.95        # altında çalışma durur
HARD_DIFF_PCT = 1.0        # Yahoo-resmi dosya farkı bunu aşarsa çalışma durur
ISHARES_URL = ("https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
               "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund")
DATASETS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
AI_ETFS = [
    ("SOXX", "iShares Semiconductor ETF"),
    ("SMH", "VanEck Semiconductor ETF"),
    ("DRAM", "Roundhill Memory ETF"),
]
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


TREND_DAYS = 12


def confirmed_trend(c, days=TREND_DAYS, warm=120):
    """Trend etiketi: yeni etiket ancak art arda `days` kapanışta geçerliyse benimsenir, aksi halde önceki etiket sürer."""
    s50, s200 = c.rolling(50).mean(), c.rolling(200).mean()
    n = min(len(c), warm + days)
    labs = [trend_label(float(c.iloc[i]), float(s50.iloc[i]), float(s200.iloc[i])) for i in range(len(c) - n, len(c))]
    cur = labs[0]
    for i in range(days - 1, len(labs)):
        if all(x == labs[i] for x in labs[i - days + 1:i + 1]):
            cur = labs[i]
    return labs[-1] if "Belirsiz" in (cur, labs[-1]) else cur


def metrics(d):
    """d: Close sütunlu DataFrame (tarih indeksli)."""
    c = d["Close"].astype(float)
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
    out["trend"] = confirmed_trend(c)
    hi = float(c.iloc[-252:].max())
    out["from_high"] = r((c.iloc[-1] / hi - 1) * 100) if hi > 0 else None
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
                     "above50": above50, "above100": m.get("above100"), "above200": m.get("above200"),
                     "dist50": m.get("dist50"), "dist100": m.get("dist100"), "dist200": m.get("dist200"),
                     "from_high": m.get("from_high"), "trend": m.get("trend"), "status": status,
                     "spark": m.get("spark")})
    rows.sort(key=lambda x: (x["rel20"] is None, -(x["rel20"] or 0)))
    return rows


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
    if 0 < len(pending) <= 10 and time.time() - t0 < max_seconds:
        # toplu indirmede dönmeyen birkaç sembol için tek tek, ayrı yolla (Ticker.history) son bir deneme; nedeni de günlüğe yazılır
        import yfinance as yf
        for t in list(pending):
            try:
                h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True, timeout=30)
                d = h[["Close", "Volume"]].dropna(subset=["Close"]).copy()
                d["Volume"] = d["Volume"].fillna(0)
                d = d[d["Close"] > 0]
                d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
                d = d[~d.index.duplicated(keep="last")].sort_index()
                log(f"  tek tek deneme {t}: {len(d)} gün" + (f", son {d.index[-1]:%Y-%m-%d}" if len(d) else ""))
                if len(d):
                    frames[t] = d
            except Exception as e:  # noqa: BLE001
                log(f"  tek tek deneme {t} başarısız:", repr(e)[:200])
        pending = [t for t in tickers if t not in frames]
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
    """VIX, Cboe'nin resmi dosyasıyla doğrulanır. SPX ve NASDAQ için resmi günlük dosya alınamıyor; onlar verify_proxies ile SPY ve ONEQ'ya karşı kontrol edilir."""
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


def verify_proxies(frames, ref_date, tol=0.5):
    """Resmi kaynak yokken: endeksin günlük getirisi ile aynı endeksi izleyen ETF'in getirisi uyuşmalı."""
    out = []
    for idx_sym, etf_sym, name in (("^GSPC", "SPY", "SPX"), ("^IXIC", "ONEQ", "NASDAQ")):  # ONEQ Nasdaq Composite'i izler; QQQ Nasdaq-100'ü izler (farklı endeks)
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


# ----------------------------------------------------------------------- ana akış
# ------------------------------------------------------------------ yapay zeka bölümü
def load_stock_list():
    """Takip edilen AI hisse listesi (hisseler.json): {"items": [{"symbol", "name"}]}"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hisseler.json")
    with open(path, encoding="utf-8") as f:
        h = json.load(f)
    return {it["symbol"]: {"name": it["name"]} for it in h["items"]}


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
    return out, {s: c for s, (_, c) in info.items()}


def earnings_dates(symbols, ref_date, budget=120):
    """Yaklaşan bilanço tarihi (Yahoo takvimi). Tarih aralığı verilmişse tahmini sayılır. Alınamayan hisse atlanır.
    Önceki güncellemede onaylanmış, hâlâ gelecekteki tarihler yeniden sorulmaz. Sorgu ayrı iş parçacığında, sert süre sınırıyla çalışır."""
    import threading
    import yfinance as yf
    ref = pd.Timestamp(ref_date).date()
    lim = ref + dt.timedelta(days=45)
    prev = {}
    try:
        url = os.environ.get("LIVE_DATA_URL", "https://mbay9.github.io/piyasa-paneli/data.json")
        for x in json.loads(http_get(url, tries=2, timeout=30).text)["ai"]["stocks"]:
            if x.get("earn") and not x.get("earn_est") and x["earn"] >= ref.isoformat():
                prev[x["symbol"]] = (x["earn"], False)
    except Exception as e:  # noqa: BLE001
        log("Önceki bilanço tarihleri okunamadı:", repr(e)[:80])
    out = {s: prev[s] for s in symbols if s in prev}
    log(f"bilanço: {len(out)} onaylı tarih yeniden sorulmadı")

    def work():
        for s in symbols:
            if s in prev:
                continue
            try:
                cal = yf.Ticker(s).calendar or {}
                ds = []
                for d in cal.get("Earnings Date") or []:
                    d = d.date() if isinstance(d, dt.datetime) else d
                    if isinstance(d, dt.date) and ref <= d <= lim:
                        ds.append(d)
                ds.sort()
                if ds:
                    out[s] = (ds[0].isoformat(), len(ds) > 1)
            except Exception as e:  # noqa: BLE001
                log(f"  bilanço tarihi alınamadı {s}: {repr(e)[:80]}")

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(budget)
    if th.is_alive():
        log("UYARI: bilanço tarihleri süre sınırına ulaştı, eldekilerle devam")
    return dict(out)


SA_EX = {"KS": "krx", "SS": "sha", "T": "tyo", "TW": "tpe"}
FUND_KEYS = ("fcf", "nc", "fcu", "fcp", "fcd", "ncp", "ncd", "fet", "fck", "fnx")


def sa_base(s):
    if "." in s:
        c, x = s.rsplit(".", 1)
        return f"https://stockanalysis.com/quote/{SA_EX[x]}/{c}" if x in SA_EX else None
    return f"https://stockanalysis.com/stocks/{s.lower()}"


class _Rows(HTMLParser):
    """Tablo satırlarını hücre metinleri olarak toplar."""

    def __init__(self):
        super().__init__()
        self.rows, self._r, self._c = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._r = []
        elif tag in ("td", "th") and self._r is not None:
            self._c = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._c is not None and self._r is not None:
            self._r.append(" ".join("".join(self._c).split()))
            self._c = None
        elif tag == "tr" and self._r is not None:
            if self._r:
                self.rows.append(self._r)
            self._r = None

    def handle_data(self, d):
        if self._c is not None:
            self._c.append(d)


def sa_fetch(url, label):
    """stockanalysis.com tablosundan en güncel sütunun `label` satırı: (değer milyon, sütun başlığı, dönem sonu ISO, para birimi)."""
    html = http_get(url, tries=2, timeout=20).text
    p = _Rows()
    p.feed(html)
    u = re.search(r"Financials in (thousands|millions|billions) ([A-Z]{3})", html)
    mult = {"thousands": 1e-3, "millions": 1.0, "billions": 1e3}[u.group(1)] if u else 1.0
    val = per = None
    for row in p.rows:
        if len(row) > 1 and row[0] == label:
            val = row[1]
        if len(row) > 1 and row[0].startswith("Period Ending"):
            per = row[1]
    try:
        v = round(float(val.replace(",", "")) * mult, 2)
    except Exception:  # noqa: BLE001
        v = None
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", per or "")
    d = dt.datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat() if m else None
    head = p.rows[0][1] if p.rows and len(p.rows[0]) > 1 else None
    return v, head, d, (u.group(2) if u else None)


def fundamentals(symbols, ref_date, earn=None, budget=300):
    """FCF (Free Cash Flow) ve Net Cash (Debt): stockanalysis.com'da en son açıklanan bilançonun (son çeyrek) değeri, milyon, şirketin raporlama para biriminde.
    Bilanço takvimine bağlıdır: ilk kez bir kez çekilir; sonra yalnız hissenin bilanço tarihi geçince her gün kontrol edilir, yeni çeyrek gelince
    güncellenir ve bir sonraki bilançoya kadar tekrar sorgulanmaz. Alınamazsa eski değer korunur."""
    import threading
    earn = earn or {}
    ref = pd.Timestamp(ref_date).date()
    prev = {}
    try:
        url = os.environ.get("LIVE_DATA_URL", "https://mbay9.github.io/piyasa-paneli/data.json")
        for x in json.loads(http_get(url, tries=2, timeout=30).text)["ai"]["stocks"]:
            if re.match(r"Q\d", str(x.get("fcp") or "")) and (x.get("fcf") is not None or x.get("nc") is not None):
                prev[x["symbol"]] = {k: x.get(k) for k in FUND_KEYS}
    except Exception as e:  # noqa: BLE001
        log("Önceki temel veriler okunamadı:", repr(e)[:80])

    def day(v):
        try:
            return dt.date.fromisoformat(v)
        except Exception:  # noqa: BLE001
            return None

    out, todo = {}, []
    for s in symbols:
        v = dict(prev[s]) if s in prev else None
        if v is None:
            todo.append(s)  # ilk kez: bir kez çek
            continue
        en = day(earn.get(s))
        fnx = day(v.get("fnx"))
        if en and (fnx is None or fnx > ref):  # kayıtlı bilanço tarihi henüz gelmediyse güncel takvim geçerli
            fnx = en
            v["fnx"] = en.isoformat()
        out[s] = v
        ck = day(v.get("fck") or v.get("fet")) or dt.date.min
        pe = day(v.get("fcd"))
        if ck == ref:
            continue
        if fnx and fnx <= ref:  # bilanço açıklandı, yeni çeyrek gelene kadar her gün (30 günden sonra 3 günde bir)
            if (ref - fnx).days <= 30 or (ref - ck).days >= 3:
                todo.append(s)
        elif not fnx and pe and (ref - pe).days >= 100 and (ref - ck).days >= 7:  # bilanço tarihi bilinmiyorsa haftada bir güvenlik ağı
            todo.append(s)
    log(f"temel veriler: {len(symbols) - len(todo)} hisse güncel (bilanço bekleniyor), {len(todo)} kontrol edilecek")

    def work():
        fails = 0
        for s in todo:
            base = sa_base(s)
            if not base:
                continue
            try:
                f, fh, fd, fc = sa_fetch(base + "/financials/cash-flow-statement/?p=quarterly", "Free Cash Flow")
                time.sleep(0.4)
                n, nh, nd, nc = sa_fetch(base + "/financials/balance-sheet/?p=quarterly", "Net Cash (Debt)")
                time.sleep(0.4)
                fails = 0
                if f is None and n is None:
                    continue
                old = out.get(s)
                if old and fd == old.get("fcd") and nd == old.get("ncd"):
                    old["fck"] = ref.isoformat()  # yeni bilanço henüz yok: eski değer kalır, yarın yine bakılır
                    continue
                en = day(earn.get(s))
                new = {"fcf": f, "nc": n, "fcu": fc or nc, "fcp": fh, "fcd": fd, "ncp": nh, "ncd": nd,
                       "fck": ref.isoformat(), "fet": ref.isoformat(),
                       "fnx": en.isoformat() if en else None}
                if fd != nd:  # nakit akışı ve bilanço farklı çeyrekte: geride kalan yayımlanana kadar kontrole devam
                    new["fnx"] = (old or {}).get("fnx") or ref.isoformat()
                out[s] = new
            except Exception as e:  # noqa: BLE001
                fails += 1
                log(f"  temel veri alınamadı {s}: {repr(e)[:80]}")
                if fails >= 5:
                    log("UYARI: stockanalysis.com art arda hata verdi, temel veri sorguları durdu")
                    return

    th = threading.Thread(target=work, daemon=True)
    th.start()
    th.join(budget)
    if th.is_alive():
        log("UYARI: temel veriler süre sınırına ulaştı, eldekilerle devam")
    return dict(out)


def prev_ai():
    """Canlı siteden önceki güncellemenin AI bölümü: (tarih, {sembol: satır}, değişiklik bloğu). Alınamazsa (None, {}, None)."""
    try:
        url = os.environ.get("LIVE_DATA_URL", "https://mbay9.github.io/piyasa-paneli/data.json")
        j = json.loads(http_get(url, tries=2, timeout=30).text)
        a = j["ai"]
        rows = {x["symbol"]: x for x in a.get("stocks", [])}
        if (j.get("meta") or {}).get("trend_days") != TREND_DAYS:
            for x in rows.values():
                x["trend"] = None  # eski (1 günlük) etiketle kıyas yapma
        return a.get("date"), rows, a.get("changes")
    except Exception as e:  # noqa: BLE001
        log("Önceki AI verisi okunamadı:", repr(e)[:80])
        return None, {}, None


def build_changes(rows, ex, ref_date, pdate, prows, pchg):
    """Önceki kapanışa göre değişenler: trend etiketi, SMA 50 geçişi (trend değişmediyse), yeni 20 günlük kapanış zirvesi.
    Aynı gün yeniden çalışırsa trend/SMA değişimleri önceki bloktan korunur (kendi kendine kıyas boş kalmasın)."""
    ref = str(ref_date)
    items, since = [], None
    if pdate and pdate < ref:
        since = pdate
        for x in rows:
            p = prows.get(x["symbol"])
            if not p or p.get("date") != pdate or x["date"] != ref:
                continue
            if p.get("fcd") and x.get("fcd") and x["fcd"] > p["fcd"]:  # yeni bilanço dönemi (nakit akışı tablosu) yayımlandı
                it = {"s": x["symbol"], "k": "fund", "per": x.get("fcp"), "cur": x.get("fcu"), "f0": p.get("fcf"), "f1": x.get("fcf")}
                if p.get("ncd") and x.get("ncd") and x["ncd"] > p["ncd"]:
                    it.update({"n0": p.get("nc"), "n1": x.get("nc")})
                items.append(it)
            t0, t1 = p.get("trend"), x.get("trend")
            if t0 and t1 and "Belirsiz" not in (t0, t1) and t0 != t1:
                items.append({"s": x["symbol"], "k": "trend", "from": t0, "to": t1, "d1": x["d1"]})
            elif p.get("above50") is not None and x["above50"] is not None and p["above50"] != x["above50"]:
                items.append({"s": x["symbol"], "k": "sma50", "up": bool(x["above50"]), "close": x["close"],
                              "sma50": ex[x["symbol"]]["sma50"]})
    elif pdate == ref and pchg and pchg.get("since"):
        since = pchg["since"]
        items = [i for i in pchg.get("items", []) if i.get("k") != "hi20"]
    else:
        return None
    for x in rows:
        e = ex[x["symbol"]]
        if e["new_hi"] and x["date"] == ref:
            items.append({"s": x["symbol"], "k": "hi20", "prev_hi": e["prev_hi"]})
    return {"since": since, "items": items}


def ai_block(ref_date, spy, qqq):
    out = {"available": False}
    try:
        uni = load_stock_list()
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
    ex = {}
    for t, f in stock_frames.items():
        f = f[f.index <= ref]
        if len(f) < 60 or f.index[-1] < ref - pd.Timedelta(days=4):
            continue
        m = metrics(f)
        c = f["Close"]
        hi = c.iloc[-252:].max()
        cf = c.astype(float)
        new_hi, prev_hi = False, None
        if len(cf) >= 22:
            prev_hi = float(cf.iloc[-21:-1].max())
            new_hi = bool(cf.iloc[-1] > prev_hi and cf.iloc[-2] <= float(cf.iloc[-22:-2].max()))
        ex[t] = {"sma50": m["sma50"], "new_hi": new_hi, "prev_hi": r(prev_hi, 4) if prev_hi is not None else None}
        rows.append({
            "symbol": t, "name": uni[t]["name"],
            "close": m["close"], "date": m["date"], "d1": m["d1"], "d5": m["d5"], "d20": m["d20"],
            "rel20": r(m["d20"] - spy20) if (m["d20"] is not None and spy20 is not None) else None,
            "above50": m["above50"], "above100": m["above100"], "above200": m["above200"],
            "from_high": r((c.iloc[-1] / hi - 1) * 100) if hi else None,
            "trend": m["trend"],
        })
    if len(rows) < 12:
        out["error"] = "Yeterli bileşen verisi alınamadı"
        out["etfs"] = etfs
        return out
    try:
        mc, cu = market_caps([x["symbol"] for x in rows], {x["symbol"]: x["close"] for x in rows})
    except Exception as e:  # noqa: BLE001
        log("Piyasa değeri bölümü atlandı:", repr(e)[:120])
        mc, cu = {}, {}
    for x in rows:
        x["mcap"] = mc.get(x["symbol"])
        x["cur"] = cu.get(x["symbol"])
    log(f"piyasa değeri: {len(mc)}/{len(rows)} hisse")
    try:
        ed = earnings_dates([x["symbol"] for x in rows], ref_date)
    except Exception as e:  # noqa: BLE001
        log("Bilanço tarihleri bölümü atlandı:", repr(e)[:120])
        ed = {}
    for x in rows:
        x["earn"], x["earn_est"] = ed.get(x["symbol"], (None, False))
    log(f"bilanço tarihi: {len(ed)}/{len(rows)} hisse")
    try:
        fu = fundamentals([x["symbol"] for x in rows], ref_date, {x["symbol"]: x.get("earn") for x in rows})
    except Exception as e:  # noqa: BLE001
        log("Temel veriler bölümü atlandı:", repr(e)[:120])
        fu = {}
    for x in rows:
        x.update(fu.get(x["symbol"], {}))
    log(f"temel veriler: {sum(1 for x in rows if x.get('fcf') is not None)}/{len(rows)} hissede FCF")
    try:
        pdate, prows, pchg = prev_ai()
        chg = build_changes(rows, ex, ref_date, pdate, prows, pchg)
        if chg is not None:
            out["changes"] = chg
        log("değişenler:", "karşılaştırma yok" if chg is None else f"{len(chg['items'])} (önceki: {chg['since']})")
    except Exception as e:  # noqa: BLE001
        log("Değişenler bölümü atlandı:", repr(e)[:120])
    n = len(rows)

    def share(rs, k):
        den = sum(1 for x in rs if x[k] is not None)
        return r(100 * sum(1 for x in rs if x[k]) / den, 1) if den else None

    d20s = [x["d20"] for x in rows if x["d20"] is not None]
    out.update({
        "available": True, "date": ref_date, "etfs": etfs,
        "count": n, "requested": len(uni), "missing": miss[:15],
        "breadth": {"above50": share(rows, "above50"), "above100": share(rows, "above100"),
                    "above200": share(rows, "above200"),
                    "positive_d20": r(100 * sum(1 for d in d20s if d > 0) / len(d20s), 1) if d20s else None,
                    "near_high": r(100 * sum(1 for x in rows if x["from_high"] is not None and x["from_high"] > -5) / n, 1)},
        "stocks": sorted(rows, key=lambda x: x["symbol"]),
    })
    return out


def build_other_changes(cur, prev):
    """Ana göstergeler, ETF'ler, sektörler, genişlik ve AI ETF'leri için önceki güncellemeye göre değişenler.
    Her kalem a=bölüm (genel, genislik, sektor, ai) ile işaretlenir. Aynı gün yeniden çalışırsa önceki blok korunur."""
    ref = str(cur["meta"]["ref_date"])
    pref = (prev.get("meta") or {}).get("ref_date")
    if pref and str(pref) == ref:
        pc = prev.get("changes")
        return pc if pc and pc.get("since") else None
    if not pref or str(pref) > ref:
        return None
    items = []
    legacy = (prev.get("meta") or {}).get("trend_days") != TREND_DAYS

    def spark_hi(sp):
        if not sp or len(sp) < 22 or any(v is None for v in sp[-22:]):
            return None
        prior = max(sp[-21:-1])
        return prior if sp[-1] > prior and sp[-2] <= max(sp[-22:-2]) else None

    def level(area, x, p):
        if not x or not p or x.get("date") == p.get("date"):
            return
        s = x.get("symbol")
        t0, t1 = (None if legacy else p.get("trend")), x.get("trend")
        trend_flip = bool(t0 and t1 and "Belirsiz" not in (t0, t1) and t0 != t1)
        if trend_flip:
            items.append({"a": area, "s": s, "k": "trend", "from": t0, "to": t1, "d1": x.get("d1")})
        for n in (50, 100, 200):
            f0, f1 = p.get(f"above{n}"), x.get(f"above{n}")
            if f0 is None or f1 is None or f0 == f1 or (n == 50 and trend_flip):
                continue
            items.append({"a": area, "s": s, "k": "sma", "m": n, "up": bool(f1), "close": x.get("close"), "sma": x.get(f"sma{n}")})
        ph = spark_hi(x.get("spark"))
        if ph is not None:
            items.append({"a": area, "s": s, "k": "hi20", "prev_hi": ph})

    for k, x in (cur.get("indexes") or {}).items():
        level("genel", x, (prev.get("indexes") or {}).get(k))
    for k, x in (cur.get("etfs") or {}).items():
        level("genel", x, (prev.get("etfs") or {}).get(k))
    pmap = {x.get("symbol"): x for x in prev.get("sectors") or []}
    for x in cur.get("sectors") or []:
        p = pmap.get(x.get("symbol"))
        level("sektor", x, p)
        if p and x.get("date") != p.get("date") and p.get("status") and x.get("status") and p["status"] != x["status"]:
            items.append({"a": "sektor", "s": x["symbol"], "k": "status", "from": p["status"], "to": x["status"]})
    cai, pai = cur.get("ai") or {}, prev.get("ai") or {}
    pem = {x.get("symbol"): x for x in pai.get("etfs") or [] if x.get("available")}
    for x in cai.get("etfs") or []:
        if x.get("available"):
            level("ai", x, pem.get(x.get("symbol")))
    rg = {"RISK_ON": "Risk-on", "RISK_OFF": "Risk-off"}
    r0, r1 = (prev.get("regime") or {}).get("market_regime"), (cur.get("regime") or {}).get("market_regime")
    if r0 and r1 and r0 != r1:
        items.append({"a": "genel", "k": "regime", "from": rg.get(r0, r0), "to": rg.get(r1, r1)})
    pp = {x.get("label"): x for x in prev.get("pairs") or []}
    for x in cur.get("pairs") or []:
        p = pp.get(x.get("label"))
        if p and x.get("verdict") and p.get("verdict") and x["verdict"] != p["verdict"]:
            items.append({"a": "genislik", "n": x["label"], "k": "verdict", "from": p["verdict"], "to": x["verdict"]})

    def thr(area, name, v0, v1):
        if v0 is None or v1 is None or (v0 < 50) == (v1 < 50) or v0 == 50 or v1 == 50:
            return
        items.append({"a": area, "n": name, "k": "thr", "up": v1 > 50, "v": v1})

    for n in (50, 100, 200):
        thr("genislik", f"S&P 500: SMA {n} üstü hisse payı",
            ((prev.get("breadth") or {}).get(f"ma{n}") or {}).get("pct"), ((cur.get("breadth") or {}).get(f"ma{n}") or {}).get("pct"))
    for n in (50, 100, 200):
        thr("ai", f"AI hisseleri: SMA {n} üstü payı", (pai.get("breadth") or {}).get(f"above{n}"), (cai.get("breadth") or {}).get(f"above{n}"))
    return {"since": str(pref), "items": items}


def patch_asia_close(frames, syms=("^KS11", "^N225")):
    """Yahoo, kapanmış Asya seansının günlük mumunun kapanışını (close) saatlerce boş (null) bırakabiliyor: mum yalnız open/high/low ile gelir
    ve yfinance onu atar, gösterge bir gün geride kalır. Seans resmi kapanışını (15:30 yerel = 06:30 UTC) geçmişse ve Yahoo'nun son fiyatının
    zamanı kapanıştan sonraysa, o son fiyat kapanış olarak eklenir (kapanıştan sonra fiyat değişmez). Yahoo mumu doldurunca kendi değeri geçerli olur."""
    for sym in syms:
        f = frames.get(sym)
        if f is None or not len(f):
            continue
        try:
            j = json.loads(http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d", tries=2).text)["chart"]["result"][0]
            ts, q, meta = j["timestamp"], j["indicators"]["quote"][0], j["meta"]
            i = len(ts) - 1
            local = dt.datetime.fromtimestamp(ts[i] + int(meta.get("gmtoffset", 0)), dt.timezone.utc)
            day = pd.Timestamp(local.strftime("%Y-%m-%d"))
            if f.index[-1] >= day or q["close"][i] is not None or q["open"][i] is None:
                continue
            close_utc = dt.datetime(day.year, day.month, day.day, 6, 30, tzinfo=dt.timezone.utc).timestamp()
            price, rmt = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
            if not price or not rmt or rmt < close_utc:
                log(f"  {sym}: {day:%Y-%m-%d} mumunun kapanışı Yahoo'da henüz yok ve seans bitişi doğrulanamadı, eklenmedi")
                continue
            vol = q["volume"][i] or 0
            frames[sym] = pd.concat([f, pd.DataFrame({"Close": [float(price)], "Volume": [float(vol)]}, index=[day])])
            log(f"  {sym}: {day:%Y-%m-%d} günlük mumunun kapanışı Yahoo'da boş; kapanış sonrası son fiyat ({price}) kullanıldı")
        except Exception as e:  # noqa: BLE001
            log(f"  {sym}: kapanış yaması atlandı:", repr(e)[:120])


def partial_refresh(only):
    """Yalnız verilen göstergeler (ör. KOSPI,NIKKEI veya BTC): canlı data.json indirilir, bu göstergeler kendi kapanışına göre yenilenir,
    geri kalan her şey aynen kalır."""
    now = dt.datetime.now(dt.timezone.utc)
    url = os.environ.get("LIVE_DATA_URL", "https://mbay9.github.io/piyasa-paneli/data.json")
    d = json.loads(http_get(url, tries=3, timeout=30).text)
    keys = [x for x in INDEXES if x[0] in only]
    if not keys:
        log("HATA: bilinmeyen gösterge:", only)
        sys.exit(1)
    frames, _ = download([s for _, s, _, _ in keys] + ["^GSPC"])  # tek sembollü indirme desteklenmiyor: yanına her zaman ^GSPC eklenir
    patch_asia_close(frames, [x for x in ("^KS11", "^N225") if any(k[1] == x for k in keys)])
    n = 0
    skipped = 0
    for key, sym, name, h24 in keys:
        if sym not in frames:
            log(f"UYARI: {key} verisi alınamadı, eski değer kalıyor")
            continue
        f = frames[sym]
        if key == "BTC":  # 7/24 işlem görür: günlük kapanış UTC 00:00'dır, günü bitmemiş mumu at
            f = f[f.index < pd.Timestamp(now.strftime("%Y-%m-%d"))]
        m = metrics(f)
        old = d["indexes"].get(key)
        if old and old.get("date") and m["date"] < old["date"]:
            log(f"UYARI: {key} yeni veri ({m['date']}) eskisinden ({old['date']}) geri, değişmedi")
            skipped += 1
            continue
        m.update({"symbol": key, "yahoo": sym, "name": name, "h24": h24, "live": sym == "BTC-USD",
                  "stale": (not h24) and m["date"] < d["meta"]["ref_date"]})
        d["indexes"][key] = m
        n += 1
        log(f"{key}: {m['date']} kapanış {m['close']}")
    if n == 0 and skipped == 0:  # yeni veri yoksa hata değil: değişmeden yayınlanır
        log("HATA: hiçbir gösterge yenilenemedi.")
        sys.exit(1)
    d["meta"]["partial_refreshed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    d["meta"]["partial_refreshed"] = sorted(only)
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, allow_nan=False, indent=1)


def main():
    if "--only" in sys.argv:
        return partial_refresh(sys.argv[sys.argv.index("--only") + 1].split(","))
    now = dt.datetime.now(dt.timezone.utc)
    macro_frames, missing_macro = download([t for _, t, _, _ in INDEXES] + [t for t, _ in ETFS] + [t for t, _ in SECTORS] + PROXY_ONLY)
    patch_asia_close(macro_frames)
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
            f = macro_frames[sym]
            if not h24:  # DXY gibi: referans günden sonraki, bitmemiş çubuk alınmaz
                f = f[f.index <= pd.Timestamp(ref_date)]
            if sym == "BTC-USD":  # 7/24: günlük kapanış UTC 00:00, günü bitmemiş mum alınmaz
                f = f[f.index < pd.Timestamp(now.strftime("%Y-%m-%d"))]
            m = metrics(f)
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
    ai = {"available": False}
    if "SPY" in etf_frames and "QQQ" in etf_frames:
        ai = ai_block(ref_date, etf_frames["SPY"], etf_frames["QQQ"])
        if not ai.get("available"):
            warnings.append("Yapay zeka bölümü eksik: " + str(ai.get("error")))

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
    proxies = verify_proxies(macro_frames, ref_date)
    if any(p["status"] == "bad" for p in proxies):
        log("HATA: endeks ile ETF getirileri tutarsız, güncelleme iptal:", proxies)
        sys.exit(1)

    out = {
        "meta": {
            "version": SCRIPT_VERSION,
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ref_date": ref_date,
            "trend_days": TREND_DAYS,
            "universe_source": universe["source"] if universe else None,
            "universe_check": universe["check"] if universe else None,
            "coverage": coverage,
            "warnings": warnings[:20],
            "verification": verification,
            "proxy_checks": proxies,
            "sources": [
                {"name": "Yahoo Finance halka açık grafik verisi (yfinance)", "official": False,
                 "use": "Fiyat, hacim, endeksler, ETF'ler. VIX resmi Cboe dosyasıyla, S&P 500 SPY ile, Nasdaq Composite ONEQ ile çapraz kontrol edilir"},
                {"name": "Cboe VIX tarihsel dosyası", "official": True, "use": "VIX doğrulaması (son gün ertesi sabah yayınlanır)"},
                {"name": universe["source"] if universe else "Hisse listesi alınamadı",
                 "official": bool(universe and universe["official"]), "use": "S&P 500 bileşen listesi"},
            ],
        },
        "indexes": idx, "etfs": etf, "breadth": breadth, "pairs": pairs,
        "sectors": sectors, "ai": ai, "regime": reg,
    }
    try:
        url = os.environ.get("LIVE_DATA_URL", "https://mbay9.github.io/piyasa-paneli/data.json")
        ch = build_other_changes(out, json.loads(http_get(url, tries=2, timeout=30).text))
        if ch is not None:
            out["changes"] = ch
        log("değişenler (genel):", "karşılaştırma yok" if ch is None else f"{len(ch['items'])} (önceki: {ch['since']})")
    except Exception as e:  # noqa: BLE001
        log("Değişenler (genel) bölümü atlandı:", repr(e)[:120])
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, indent=1)
    log(f"data.json yazıldı | referans kapanış: {ref_date} | "
        f"kapsam: {coverage['received'] if coverage else '-'}/{coverage['requested'] if coverage else '-'} | "
        f"doğrulama: " + ", ".join(f"{v['id']}={v['status']}" for v in verification))


if __name__ == "__main__":
    main()
