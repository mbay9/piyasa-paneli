"""İkinci kaynaklar (Yahoo dışı, ücretsiz, anahtarsız). Amaç: Yahoo bir günün mumunu vermediğinde boşluğu doldurmak ve Yahoo'nun
verdiği kapanışı bağımsız bir kaynakla karşılaştırmak. Hepsi 10 Kas 2026'da GitHub çalıştırıcısından denendi.

  NIKKEI  : Nikkei Inc. resmi günlük dosyası (indexes.nikkei.co.jp)            -> resmi kapanış
  KOSPI   : Naver Finance günlük fiyat listesi (m.stock.naver.com)              -> KRX kapanışı
  BTC     : Coinbase borsası günlük mumları (UTC 00:00 kapanış)                 -> borsa fiyatı (Yahoo'nun bileşik fiyatından az farklıdır)
  SPY/ONEQ/COMP : Nasdaq.com geçmiş fiyat tablosu                               -> resmi kapanış (ertesi sabaha kadar gecikebilir)

Çözücüler (…_coz) ağdan bağımsızdır ve test edilir; getiriciler hata verirse {} döner (ikinci kaynak hiçbir zaman güncellemeyi durdurmaz)."""
from __future__ import annotations

import datetime as dt
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}


def _sayi(x):
    return float(str(x).replace("$", "").replace(",", "").strip())


def nikkei_coz(metin):
    """"2026/11/09","50123.45",... satırları -> {"2026-11-09": 50123.45}"""
    out = {}
    for m in re.finditer(r'"(\d{4})/(\d{2})/(\d{2})","([\d.]+)"', metin):
        out[f"{m.group(1)}-{m.group(2)}-{m.group(3)}"] = float(m.group(4))
    return out


def kospi_coz(liste):
    out = {}
    for r in liste or []:
        t, c = r.get("localTradedAt"), r.get("closePrice")
        if t and c and re.match(r"\d{4}-\d{2}-\d{2}", t):
            out[t[:10]] = _sayi(c)
    return out


def nasdaq_coz(j):
    out = {}
    rows = (((j or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    for r in rows:
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", r.get("date") or "")
        if m and r.get("close") not in (None, "", "N/A", "--"):
            out[f"{m.group(3)}-{m.group(1)}-{m.group(2)}"] = _sayi(r["close"])
    return out


def coinbase_coz(liste):
    """[[zaman, low, high, open, close, volume], ...] -> {gün (UTC): kapanış}"""
    out = {}
    for r in liste or []:
        out[dt.datetime.fromtimestamp(r[0], dt.timezone.utc).strftime("%Y-%m-%d")] = float(r[4])
    return out


def _al(url, zaman=25):
    r = requests.get(url, headers=UA, timeout=(10, zaman))
    r.raise_for_status()
    return r


def getir(ad, bugun=None):
    """ad: NIKKEI | KOSPI | BTC | SPY | ONEQ | COMP. {gün: kapanış}; hata olursa {}."""
    bugun = bugun or dt.datetime.now(dt.timezone.utc).date()
    try:
        if ad == "NIKKEI":
            return nikkei_coz(_al("https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_en.csv").text)
        if ad == "KOSPI":
            return kospi_coz(json.loads(_al("https://m.stock.naver.com/api/index/KOSPI/price?pageSize=12&page=1").text))
        if ad == "BTC":
            a, b = bugun - dt.timedelta(days=12), bugun + dt.timedelta(days=1)
            return coinbase_coz(json.loads(_al(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start={a}T00:00:00Z&end={b}T00:00:00Z").text))
        if ad in ("SPY", "ONEQ", "COMP"):
            sinif = "index" if ad == "COMP" else "etf"
            a = bugun - dt.timedelta(days=12)
            return nasdaq_coz(json.loads(_al(f"https://api.nasdaq.com/api/quote/{ad}/historical?assetclass={sinif}&fromdate={a}&todate={bugun}&limit=15").text))
    except Exception:  # noqa: BLE001
        return {}
    return {}


def kapanmis(kaynak, now, asya=False, btc=False):
    """Henüz bitmemiş günü at: Asya seansı 06:35 UTC'den önce bugünü, Bitcoin her zaman bugünü (UTC günü bitmedi) içermez."""
    bugun = now.strftime("%Y-%m-%d")
    out = {}
    for g, v in kaynak.items():
        if g > bugun:
            continue
        if g == bugun and (btc or (asya and (now.hour, now.minute) < (6, 35))):
            continue
        out[g] = v
    return out


def karsilastir(ad, kaynak_adi, yahoo, kaynak, tol):
    """yahoo ve kaynak: {gün: kapanış}. Ortak son günde yüzde fark. Durum: ok | bad | unavailable."""
    ortak = sorted(set(yahoo) & set(kaynak))
    if not ortak:
        return {"id": ad, "source": kaynak_adi, "status": "unavailable", "note": "ortak gün yok" if kaynak else "kaynak okunamadı"}
    g = ortak[-1]
    fark = (yahoo[g] / kaynak[g] - 1) * 100
    return {"id": ad, "source": kaynak_adi, "date": g, "yahoo": round(yahoo[g], 4), "other": round(kaynak[g], 4),
            "diff_pct": round(fark, 3), "tol_pct": tol, "status": "ok" if abs(fark) <= tol else "bad"}


def eksikler(yahoo_gunleri, kaynak, son_n=8):
    """Kaynakta olup Yahoo'da olmayan günler (yalnız Yahoo'nun bildiği aralığın son_n günü içinde ya da sonrasında)."""
    if not yahoo_gunleri:
        return []
    y = sorted(yahoo_gunleri)
    esik = y[-son_n] if len(y) >= son_n else y[0]
    return sorted(g for g in kaynak if g > esik and g not in set(y))
