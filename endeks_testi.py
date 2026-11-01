"""Endeks çarpanı denemesi (siteyi değiştirmez). S&P 500 (iShares IVV ağırlıkları) ve Nasdaq-100 için farklı yöntemlerle F/K hesaplar,
sonucu rapora yazar: python endeks_testi.py --rapor endeks-rapor.json
Yöntem: endeks F/K = 1 / sum(ağırlık_i x EPS_i / fiyat_i)  (toplam değer / toplam kazanç = ağırlıklı harmonik ortalama)."""
import io
import json
import math
import statistics
import sys
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import update as U

IKINCI_SINIF = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}  # aynı şirketin ikinci payı: piyasa değeri ağırlığında çift sayılmasın


def f(v):
    try:
        v = float(v)
        return None if v != v or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def ivv_agirlik():
    txt = U.http_get(U.ISHARES_URL).text
    lines = txt.lstrip("﻿").splitlines()
    st = next(i for i, ln in enumerate(lines[:80]) if ln.replace('"', "").startswith("Ticker,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[st:])), on_bad_lines="skip")
    df = df[df["Asset Class"].astype(str).str.strip() == "Equity"]
    col = next(c for c in df.columns if str(c).startswith("Weight"))
    out = {}
    for t, w, sec in zip(df["Ticker"], df[col], df["Sector"]):
        if str(t).strip() in ("-", "") or pd.isna(w):
            continue
        out[U.yahoo_symbol(t)] = (float(w), str(sec))
    return out


def ndx_liste():
    """Nasdaq-100 üyeleri: önce Nasdaq'ın kendi listesi, olmazsa Wikipedia."""
    try:
        j = U.http_get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", tries=2).json()
        rows = j["data"]["data"]["rows"]
        t = sorted({U.yahoo_symbol(r["symbol"]) for r in rows})
        if 90 <= len(t) <= 110:
            return t, "api.nasdaq.com"
    except Exception as e:  # noqa: BLE001
        U.log("Nasdaq listesi alınamadı:", repr(e)[:100])
    try:
        for tb in pd.read_html(io.StringIO(U.http_get("https://en.wikipedia.org/wiki/Nasdaq-100").text)):
            c = next((c for c in tb.columns if str(c).lower() in ("ticker", "symbol")), None)
            if c is not None and 90 <= len(tb) <= 110:
                return sorted({U.yahoo_symbol(x) for x in tb[c]}), "Wikipedia"
    except Exception as e:  # noqa: BLE001
        U.log("Wikipedia listesi alınamadı:", repr(e)[:100])
    return [], None


def getir(sym):
    import yfinance as yf
    o = {"sym": sym}
    for deneme in range(3):
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            o.update(fiyat=f(info.get("currentPrice") or info.get("regularMarketPrice")), mcap=f(info.get("marketCap")), cur=info.get("currency"),
                     fcur=info.get("financialCurrency"), gaap_ttm=f(info.get("trailingEps")), yahoo_fwd=f(info.get("forwardEps")),
                     fye=info.get("nextFiscalYearEnd"), fye_son=info.get("lastFiscalYearEnd"), mrq=info.get("mostRecentQuarter"), sektor=info.get("sector"))
            ee = t.earnings_estimate
            o["eps0"] = f(ee.loc["0y", "avg"]) if "0y" in ee.index else None
            o["eps1"] = f(ee.loc["+1y", "avg"]) if "+1y" in ee.index else None
            try:
                eh = t.earnings_history
                v = [f(x) for x in eh["epsActual"].tolist()]
                o["ttm_adj"] = round(sum(v[-4:]), 4) if len(v) >= 4 and all(x is not None for x in v[-4:]) else None
                o["son_ceyrek_tarih"] = str(eh.index[-1])[:10]
            except Exception:  # noqa: BLE001
                o["ttm_adj"] = None
            return o
        except Exception as e:  # noqa: BLE001
            o["hata"] = repr(e)[:100]
            time.sleep(2 + 3 * deneme)
    return o


def ntm(r, bugun):
    """İleri 12 ay EPS: mali yıl sonuna kalan süreye göre bu yıl ve gelecek yıl tahminlerinin zaman ağırlıklı karışımı."""
    e0, e1, fye = r.get("eps0"), r.get("eps1"), r.get("fye")
    if e0 is None or e1 is None or not fye:
        return None, None
    kalan = (dt.date.fromtimestamp(fye) - bugun).days
    w = min(max(kalan / 365.0, 0.0), 1.0)
    return w * e0 + (1 - w) * e1, w


def hesapla(ad, satirlar, bugun):
    """satirlar: [{sym, w (ağırlık, toplamı 1'e normalize), fiyat, eps...}]"""
    sonuc = {"ad": ad, "n": len(satirlar)}
    anahtarlar = {"fy1": lambda r: r.get("eps0"), "fy2": lambda r: r.get("eps1"), "ntm": lambda r: ntm(r, bugun)[0],
                  "ttm_duzeltilmis": lambda r: r.get("ttm_adj"), "ttm_gaap": lambda r: r.get("gaap_ttm"), "yahoo_forwardEps": lambda r: r.get("yahoo_fwd")}
    for k, fn in anahtarlar.items():
        ok = [(r, fn(r)) for r in satirlar if r.get("fiyat") and fn(r) is not None and r.get("para_ok")]
        kapsam = sum(r["w"] for r, _ in ok)
        if not ok or kapsam == 0:
            sonuc[k] = None
            continue
        tw = sum(r["w"] for r, _ in ok)
        ey = sum(r["w"] * e / r["fiyat"] for r, e in ok) / tw          # kazanç getirisi (zarar dahil)
        pos = [(r, e) for r, e in ok if e > 0]
        pw = sum(r["w"] for r, _ in pos)
        ey_pos = sum(r["w"] * e / r["fiyat"] for r, e in pos) / pw if pw else None
        pes = [r["fiyat"] / e for r, e in pos]
        agirlikli_ort = sum(r["w"] * r["fiyat"] / e for r, e in pos) / pw if pw else None
        esit_harm = len(pos) / sum(e / r["fiyat"] for r, e in pos) if pos else None
        sonuc[k] = {"kapsam_agirlik": round(kapsam * 100, 1), "adet": len(ok), "zarar_adet": len(ok) - len(pos),
                    "pe_toplam": round(1 / ey, 2) if ey > 0 else None,
                    "pe_zarar_haric": round(1 / ey_pos, 2) if ey_pos else None,
                    "pe_agirlikli_aritmetik": round(agirlikli_ort, 2) if agirlikli_ort else None,
                    "pe_esit_agirlik_harmonik": round(esit_harm, 2) if esit_harm else None,
                    "pe_medyan": round(statistics.median(pes), 2) if pes else None}
    # büyüme: ileri 12 ay / son 12 ay (aynı hisseler üzerinde)
    ort = [(r, ntm(r, bugun)[0], r.get("ttm_adj")) for r in satirlar if r.get("fiyat") and r.get("para_ok")]
    ort = [x for x in ort if x[1] is not None and x[2] is not None]
    if ort:
        a = sum(r["w"] * n / r["fiyat"] for r, n, _ in ort)
        b = sum(r["w"] * t / r["fiyat"] for r, _, t in ort)
        sonuc["ntm_ttm_buyume_pct"] = round((a / b - 1) * 100, 1) if b > 0 else None
    # yoğunlaşma: ilk 10 ağırlığın NTM kazanç payı
    pay = sorted(((r["w"] * ntm(r, bugun)[0] / r["fiyat"], r["sym"]) for r in satirlar if r.get("fiyat") and r.get("para_ok") and ntm(r, bugun)[0] is not None), reverse=True)
    tpl = sum(p for p, _ in pay)
    sonuc["kazanc_payi_ilk10"] = [[s, round(p / tpl * 100, 1)] for p, s in pay[:10]] if tpl > 0 else None
    return sonuc


def main():
    bugun = dt.date.today()
    ivv = ivv_agirlik()
    ndx, ndx_kaynak = ndx_liste()
    semboller = sorted(set(ivv) | set(ndx))
    U.log(f"{len(ivv)} S&P, {len(ndx)} Nasdaq-100 ({ndx_kaynak}), toplam {len(semboller)} sembol")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        veri = {r["sym"]: r for r in ex.map(getir, semboller)}
    U.log(f"Yahoo verisi {int(time.time() - t0)} sn")
    for r in veri.values():
        r["para_ok"] = bool(r.get("cur")) and r.get("cur") == r.get("fcur") == "USD" or (r.get("cur") == r.get("fcur") and r.get("cur") is not None)
    eksik = [s for s, r in veri.items() if not r.get("fiyat") or r.get("hata")]

    # S&P 500: iShares IVV ağırlıkları
    tp = sum(w for w, _ in ivv.values())
    spx_ivv = [dict(veri[s], w=w / tp) for s, (w, _) in ivv.items() if s in veri]
    # S&P 500: piyasa değeri ağırlığı (ikinci paylar çıkarılır)
    mc = {s: veri[s].get("mcap") for s in ivv if s in veri and s not in IKINCI_SINIF and veri[s].get("mcap")}
    tm = sum(mc.values())
    spx_mc = [dict(veri[s], w=m / tm) for s, m in mc.items()]
    # Nasdaq-100: piyasa değeri ağırlığı (gerçek endeks ağırlıkları değişikliklidir: tavanlı/dengeli; burada yaklaşık)
    nm = {s: veri[s].get("mcap") for s in ndx if s in veri and s not in IKINCI_SINIF and veri[s].get("mcap")}
    tn = sum(nm.values())
    ndx_mc = [dict(veri[s], w=m / tn) for s, m in nm.items()]

    bugun_s = bugun.isoformat()
    rapor = {"tarih": bugun_s, "ndx_kaynak": ndx_kaynak, "sembol": len(semboller), "eksik_veri": eksik[:40], "eksik_adet": len(eksik),
             "sure_sn": int(time.time() - t0),
             "para_uyumsuz": [s for s, r in veri.items() if not r.get("para_ok")][:40],
             "spx_ivv_agirlik": hesapla("S&P 500 (IVV ağırlıkları)", spx_ivv, bugun),
             "spx_mcap_agirlik": hesapla("S&P 500 (piyasa değeri)", spx_mc, bugun),
             "ndx_mcap_agirlik": hesapla("Nasdaq-100 (piyasa değeri, yaklaşık)", ndx_mc, bugun),
             "son_7_gunde_bilanco": [s for s, r in veri.items() if r.get("mrq") and (bugun - dt.date.fromtimestamp(r["mrq"])).days <= 45][:5],
             "mrq_dagilimi": {}}
    # bilanço akışı: kaç şirketin son çeyreği ne zaman
    sayac = {}
    for r in veri.values():
        if r.get("mrq"):
            k = dt.date.fromtimestamp(r["mrq"]).strftime("%Y-%m")
            sayac[k] = sayac.get(k, 0) + 1
    rapor["mrq_dagilimi"] = dict(sorted(sayac.items())[-8:])
    rapor.pop("son_7_gunde_bilanco")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))
    if "--rapor" in sys.argv:
        json.dump({**rapor, "ham": veri}, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        import traceback
        iz = traceback.format_exc()
        print(iz)
        if "--rapor" in sys.argv:
            json.dump({"hata": iz}, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)
