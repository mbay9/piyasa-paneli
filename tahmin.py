"""Analist tahminleri (Yahoo Finance, yfinance): cari ve gelecek yıl EPS ve gelir tahmini, analist sayısı, tahmin aralığı ve
7/30/60/90 gün önceki EPS tahmini. Kullanım: python tahmin.py [--rapor rapor.json]. Çıktı sözlüğü sembol -> alanlar."""
import json
import sys
import time

import yfinance as yf


def _f(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


def _satir(df, idx, col):
    try:
        return _f(df.loc[idx, col])
    except Exception:  # noqa: BLE001
        return None


def tek(sym):
    t = yf.Ticker(sym)
    ee, re_, tr = t.earnings_estimate, t.revenue_estimate, t.eps_trend
    out = {}
    for ad, idx in (("y0", "0y"), ("y1", "+1y")):
        out[ad] = {
            "eps": _satir(ee, idx, "avg"), "eps_lo": _satir(ee, idx, "low"), "eps_hi": _satir(ee, idx, "high"), "an": _satir(ee, idx, "numberOfAnalysts"),
            "rev": _satir(re_, idx, "avg"), "rev_lo": _satir(re_, idx, "low"), "rev_hi": _satir(re_, idx, "high"), "rev_an": _satir(re_, idx, "numberOfAnalysts"),
            "eps_7g": _satir(tr, idx, "7daysAgo"), "eps_30g": _satir(tr, idx, "30daysAgo"), "eps_60g": _satir(tr, idx, "60daysAgo"), "eps_90g": _satir(tr, idx, "90daysAgo"),
        }
    return out


def hepsi(semboller, bekle=0.3):
    sonuc, hata = {}, {}
    for s in semboller:
        try:
            r = tek(s)
            if r["y0"]["eps"] is not None or r["y0"]["rev"] is not None:
                sonuc[s] = r
            else:
                hata[s] = "tahmin boş"
        except Exception as e:  # noqa: BLE001
            hata[s] = repr(e)[:120]
        time.sleep(bekle)
    return sonuc, hata


if __name__ == "__main__":
    liste = [x["symbol"] for x in json.load(open("hisseler.json", encoding="utf-8"))["items"]]
    sonuc, hata = hepsi(liste)
    alan = lambda k: sum(1 for v in sonuc.values() if v["y0"].get(k) is not None)  # noqa: E731
    rapor = {"toplam": len(liste), "tahmin_var": len(sonuc), "eksik": hata,
             "kapsam": {k: alan(k) for k in ("eps", "eps_lo", "an", "rev", "eps_7g", "eps_30g", "eps_90g")}, "ornek": dict(list(sonuc.items())[:3]), "veri": sonuc}
    print(json.dumps({k: v for k, v in rapor.items() if k != "veri"}, ensure_ascii=False, indent=1))
    if "--rapor" in sys.argv:
        json.dump(rapor, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)
