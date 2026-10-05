#!/usr/bin/env python3
"""Piyasa Komuta Paneli - gece veri güncelleyici.

Her gece GitHub Actions üzerinde çalışır, data.json üretir.
Kaynaklar:
  - Fiyat/hacim: Yahoo Finance halka açık grafik verisi (yfinance) - resmi borsa verisi DEĞİL
  - S&P 500 hisse listesi: iShares IVV resmi holdings CSV (yedek: datasets/s-and-p-500-companies)
  - Getiri eğrisi: U.S. Treasury günlük par getiri eğrisi (yedek: FRED DGS2/DGS10)
Kritik veri eksikse betik hata ile çıkar ve eski sayfa yerinde kalır; veri uydurulmaz.
"""
import io
import json
import math
import sys
import datetime as dt

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (piyasa-paneli; +github-actions)"}

# (kısa ad, Yahoo sembolü, açıklama, 7/24 işlem görür mü)
INDEXES = [
    ("SPX", "^GSPC", "S&P 500", False),
    ("NASDAQ", "^IXIC", "Nasdaq Composite", False),
    ("RUT", "^RUT", "Russell 2000", False),
    ("VIX", "^VIX", "CBOE Volatility Index", False),
    ("DXY", "DX-Y.NYB", "ABD Dolar Endeksi", False),
    ("GOLD", "GC=F", "Altın vadeli", False),
    ("SILVER", "SI=F", "Gümüş vadeli", False),
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


# ---------------------------------------------------------------- yardımcılar
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


def pct_change(s, n):
    if len(s) <= n:
        return None
    base = s.iloc[-1 - n]
    if not base:
        return None
    return (s.iloc[-1] / base - 1) * 100


def trend_label(close, s50, s200):
    if None in (s50, s200) or any(x is None or not math.isfinite(x) for x in (s50, s200)):
        return "Belirsiz"
    if close > s50 > s200:
        return "Yükseliş"
    if close < s50 < s200:
        return "Düşüş"
    return "Yatay / karışık"


def metrics(d):
    """d: Close ve Volume sütunlu DataFrame (tarih indeksli)."""
    c = d["Close"].astype(float)
    v = d["Volume"].astype(float) if "Volume" in d else pd.Series(dtype=float)
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
    # hacim: son gün / önceki 20 ve 50 günün ortalaması
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
    # 52 haftalık yeni zirve / dip sayısı
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
    # endeks trendi
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
    # volatilite: VIX 12 ve altı 100, 30 ve üstü 0
    if vix is not None:
        parts.append(("Volatilite", r(clamp((30 - vix) / 18 * 100), 0), f"VIX {vix:.2f}"))
    # getiri eğrisi: -0.5 -> 0, +1.0 -> 100
    if curve_spread is not None:
        parts.append(("Getiri eğrisi", r(clamp((curve_spread + 0.5) / 1.5 * 100), 0), f"10Y-2Y {curve_spread:+.2f} puan"))
    # sektör breadth
    sec = [s for s in sectors if s["above50"] is not None]
    if sec:
        n_up = sum(1 for s in sec if s["above50"])
        parts.append(("Sektör breadth", r(n_up / len(sec) * 100, 0), f"{n_up}/{len(sec)} sektör ETF'i 50G MA üzerinde"))
    # dolar: DXY 50G MA altında ise risk iştahı için olumlu
    if dxy and dxy.get("above50") is not None:
        parts.append(("Dolar", 70 if not dxy["above50"] else 30, "DXY 50G MA altında" if not dxy["above50"] else "DXY 50G MA üzerinde"))
    if not parts:
        return None
    score = sum(p[1] for p in parts) / len(parts)
    label = "RISK_ON" if score >= 65 else ("RISK_OFF" if score < 40 else "NÖTR")
    return {"score": r(score, 0), "label": label,
            "components": [{"name": n, "score": s, "note": t} for n, s, t in parts],
            "note": "Kural tabanlı model: bileşenlerin eşit ağırlıklı ortalaması. Resmi veri değildir."}


# ------------------------------------------------------------------ veri çekme
def get_universe():
    """S&P 500 hisse listesi. Önce iShares IVV resmi dosyası, olmazsa GitHub datasets."""
    try:
        url = ("https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
               "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund")
        txt = requests.get(url, headers=UA, timeout=60).text
        lines = txt.splitlines()
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
        df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
        df = df[df["Asset Class"].astype(str).str.strip() == "Equity"]
        tick = [str(t).strip().replace(".", "-") for t in df["Ticker"] if str(t).strip() not in ("-", "", "nan")]
        tick = sorted(set(tick))
        if len(tick) >= 450:
            return tick, "iShares IVV holdings CSV (resmi)"
    except Exception as e:  # noqa: BLE001
        print("iShares listesi alınamadı:", e, file=sys.stderr)
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        df = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=60).text))
        tick = sorted(set(str(t).strip().replace(".", "-") for t in df["Symbol"]))
        if len(tick) >= 450:
            return tick, "datasets/s-and-p-500-companies (GitHub, resmi değil)"
    except Exception as e:  # noqa: BLE001
        print("Yedek hisse listesi alınamadı:", e, file=sys.stderr)
    return [], None


def download(tickers, period="2y", batch=80):
    import yfinance as yf  # geç import: testlerde gerekmez
    frames = {}
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            df = yf.download(chunk, period=period, interval="1d", auto_adjust=True,
                             group_by="ticker", threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print("indirme hatası:", e, file=sys.stderr)
            continue
        if df is None or df.empty:
            continue
        if len(chunk) == 1:
            df = pd.concat({chunk[0]: df}, axis=1)
        for t in chunk:
            try:
                d = df[t][["Close", "Volume"]].dropna(subset=["Close"])
            except KeyError:
                continue
            if len(d):
                d.index = pd.to_datetime(d.index).tz_localize(None)
                frames[t] = d
    return frames


def get_yields():
    """2Y/10Y getiri: Treasury CSV, yedek FRED."""
    year = dt.date.today().year
    try:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve"
               f"&field_tdr_date_value={year}&page&_format=csv")
        df = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=60).text))
        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
        df = df.sort_values("Date").dropna(subset=["2 Yr", "10 Yr"])
        if len(df) >= 6:
            return df.set_index("Date")[["2 Yr", "10 Yr"]].rename(columns={"2 Yr": "y2", "10 Yr": "y10"}), "U.S. Treasury günlük par getiri eğrisi"
    except Exception as e:  # noqa: BLE001
        print("Treasury alınamadı:", e, file=sys.stderr)
    try:
        cols = {}
        for sid, key in (("DGS2", "y2"), ("DGS10", "y10")):
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
            d = pd.read_csv(io.StringIO(requests.get(url, headers=UA, timeout=60).text))
            d.columns = ["Date", key]
            d["Date"] = pd.to_datetime(d["Date"])
            d[key] = pd.to_numeric(d[key], errors="coerce")
            cols[key] = d.set_index("Date")[key]
        df = pd.concat(cols.values(), axis=1).dropna()
        if len(df) >= 6:
            return df, "FRED DGS2 / DGS10 (yedek)"
    except Exception as e:  # noqa: BLE001
        print("FRED alınamadı:", e, file=sys.stderr)
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
def build_notes(idx, etf, breadth, pairs, yields, sectors, reg):
    notes = []

    def add(level, title, text):
        notes.append({"level": level, "title": title, "text": text})

    vix = idx.get("VIX")
    if vix:
        v = vix["close"]
        if v < 15:
            add("ok", "VIX DÜŞÜK", f"VIX {v:.2f}: 15 altı, piyasa sakin.")
        elif v < 20:
            add("ok", "VIX NORMAL", f"VIX {v:.2f}: 15-20 arası, normal bölge.")
        elif v < 30:
            add("warn", "VIX YÜKSEK", f"VIX {v:.2f}: 20-30 arası, gerginlik var.")
        else:
            add("bad", "VIX ÇOK YÜKSEK", f"VIX {v:.2f}: 30 üstü, stres bölgesi.")
        if vix.get("d5") is not None:
            if vix["d5"] >= 15:
                add("warn", "VIX SIÇRADI", f"VIX 1 haftada %{vix['d5']:.1f} arttı.")
            elif vix["d5"] <= -15:
                add("ok", "VIX GEVŞEDİ", f"VIX 1 haftada %{abs(vix['d5']):.1f} düştü.")
    for key in ("SPX", "NASDAQ", "RUT"):
        m = idx.get(key)
        if not m:
            continue
        if m.get("above200") is False:
            add("bad", f"{key} 200G ALTINDA", f"{key} 200 günlük ortalamanın altında ({m['dist200']:+.1f}%).")
        elif m.get("above50") is False:
            add("warn", f"{key} 50G ALTINDA", f"{key} 50 günlük ortalamanın altında ({m['dist50']:+.1f}%).")
    sp = etf.get("SPY")
    if sp and sp.get("vol_vs20") is not None:
        vv = sp["vol_vs20"]
        if vv >= 30:
            add("info", "HACİM YÜKSEK", f"SPY kapanış günü hacmi 20 günlük ortalamanın %{vv:.0f} üzerinde.")
        elif vv <= -25:
            add("info", "HACİM DÜŞÜK", f"SPY kapanış günü hacmi 20 günlük ortalamanın %{abs(vv):.0f} altında.")
        else:
            add("info", "HACİM NORMAL", f"SPY hacmi 20 günlük ortalamaya göre %{vv:+.0f}.")
    b50 = (breadth.get("ma50") or {}).get("pct")
    b200 = (breadth.get("ma200") or {}).get("pct")
    if b50 is not None:
        if b50 < 30:
            add("bad", "BREADTH ZAYIF", f"S&P 500 hisselerinin sadece %{b50:.0f}'i 50G MA üstünde.")
        elif b50 < 50:
            add("warn", "BREADTH ORTA-ZAYIF", f"S&P 500 hisselerinin %{b50:.0f}'i 50G MA üstünde.")
        else:
            add("ok", "BREADTH SAĞLAM", f"S&P 500 hisselerinin %{b50:.0f}'i 50G MA üstünde.")
    if b200 is not None and b200 < 40:
        add("warn", "UZUN VADE ZAYIF", f"Hisselerin sadece %{b200:.0f}'i 200G MA üstünde.")
    for p in pairs:
        if not p.get("available") or p.get("ret20_diff") is None:
            continue
        a, b, d = p["a"], p["b"], p["ret20_diff"]
        if p["verdict"] == "DAR":
            add("warn", f"{a}/{b} DAR", f"{a}, {b}'nin 20 günde {abs(d):.1f} puan gerisinde: yükseliş az sayıda büyük hisseyle taşınıyor.")
        elif p["verdict"] == "GENİŞ":
            add("ok", f"{a}/{b} GENİŞ", f"{a}, {b}'nin 20 günde {d:.1f} puan önünde: eşit ağırlıklı endeks de yükseliyor.")
        else:
            add("info", f"{a}/{b} DENGELİ", f"{a} ile {b} 20 günde yakın seyretti ({d:+.1f} puan).")
    y = yields.get("spread") if yields.get("available") else None
    if y and y["value"] is not None:
        if y["value"] < 0:
            add("bad", "TERS EĞRİ", f"10Y-2Y farkı {y['value']:+.2f} puan: eğri ters.")
        else:
            add("ok", "EĞRİ POZİTİF", f"10Y-2Y farkı {y['value']:+.2f} puan.")
    lead = [s["symbol"] for s in sectors if s["status"] == "Lider"][:3]
    lag = [s["symbol"] for s in sectors if s["status"] == "Geride"][-3:]
    if lead:
        add("info", "SEKTÖR LİDERLERİ", "SPY'a göre güçlü ve 50G üstünde: " + ", ".join(lead) + ("; geride kalanlar: " + ", ".join(lag) if lag else "."))
    return notes


# ----------------------------------------------------------------------- ana akış
def main():
    now = dt.datetime.now(dt.timezone.utc)
    tickers_idx = [t for _, t, _, _ in INDEXES]
    tickers_etf = [t for t, _ in ETFS] + [t for t, _ in SECTORS]
    macro_frames = download(tickers_idx + tickers_etf)

    if "^GSPC" not in macro_frames:
        print("HATA: S&P 500 verisi alınamadı, güncelleme iptal.", file=sys.stderr)
        sys.exit(1)
    ref_date = macro_frames["^GSPC"].index[-1].strftime("%Y-%m-%d")

    idx = {}
    for key, sym, name, h24 in INDEXES:
        if sym in macro_frames:
            m = metrics(macro_frames[sym])
            m.update({"symbol": key, "yahoo": sym, "name": name, "h24": h24,
                      "stale": (not h24) and m["date"] < ref_date})
            idx[key] = m
    etf_frames = {t: macro_frames[t] for t, _ in ETFS + SECTORS if t in macro_frames}
    etf = {t: dict(metrics(etf_frames[t]), symbol=t, name=n) for t, n in ETFS if t in etf_frames}

    universe, uni_src = get_universe()
    breadth, coverage = {}, None
    if universe:
        stock_frames = download(universe)
        closes = pd.DataFrame({t: f["Close"] for t, f in stock_frames.items()}).sort_index()
        closes = closes[closes.index <= pd.Timestamp(ref_date)]
        coverage = {"requested": len(universe), "received": len(stock_frames),
                    "ratio": r(len(stock_frames) / len(universe), 3)}
        if len(stock_frames) < 0.8 * len(universe):
            print(f"HATA: hisse verisi yetersiz ({len(stock_frames)}/{len(universe)}), güncelleme iptal.", file=sys.stderr)
            sys.exit(1)
        breadth = breadth_block(closes)
        breadth["date"] = closes.index[-1].strftime("%Y-%m-%d")
    else:
        print("UYARI: hisse listesi alınamadı, breadth hesaplanmadı.", file=sys.stderr)

    pairs = [pair_block(a, b, lbl, etf_frames) for a, b, lbl in PAIRS]
    sectors = sector_block(etf_frames)
    ydf, ysrc = get_yields()
    yields = yield_block(ydf, ysrc)
    spread_val = yields["spread"]["value"] if yields.get("available") else None
    vix_val = idx["VIX"]["close"] if "VIX" in idx else None
    reg = regime(idx, vix_val, spread_val, sectors, idx.get("DXY"))
    notes = build_notes(idx, etf, breadth, pairs, yields, sectors, reg)

    out = {
        "meta": {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ref_date": ref_date,
            "universe_source": uni_src,
            "coverage": coverage,
            "sources": [
                {"name": "Yahoo Finance halka açık grafik verisi (yfinance)", "official": False,
                 "use": "Fiyat, hacim, endeksler, ETF'ler"},
                {"name": uni_src or "Hisse listesi alınamadı", "official": bool(uni_src and "resmi" in uni_src and "değil" not in uni_src),
                 "use": "S&P 500 bileşen listesi"},
                {"name": ysrc or "Getiri verisi alınamadı", "official": True, "use": "2Y/10Y getiri"},
            ],
        },
        "indexes": idx, "etfs": etf, "breadth": breadth, "pairs": pairs,
        "sectors": sectors, "yields": yields, "regime": reg, "notes": notes,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, allow_nan=False, indent=1)
    print("data.json yazıldı, referans kapanış:", ref_date)


if __name__ == "__main__":
    main()
