"""Analist tahminleri (Yahoo Finance, yfinance): cari ve gelecek yıl EPS ve gelir tahmini, analist sayısı, tahmin aralığı ve
7/30/60/90 gün önceki EPS tahmini. Kullanım: python tahmin.py [--rapor rapor.json]. Çıktı sözlüğü sembol -> alanlar."""
import json
import sys
import time



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
    import yfinance as yf
    t = yf.Ticker(sym)
    ee, re_, tr = t.earnings_estimate, t.revenue_estimate, t.eps_trend
    out = {}
    for ad, idx in (("y0", "0y"), ("y1", "+1y")):
        out[ad] = {
            "eps": _satir(ee, idx, "avg"), "eps_lo": _satir(ee, idx, "low"), "eps_hi": _satir(ee, idx, "high"), "an": _satir(ee, idx, "numberOfAnalysts"),
            "rev": _satir(re_, idx, "avg"), "rev_lo": _satir(re_, idx, "low"), "rev_hi": _satir(re_, idx, "high"), "rev_an": _satir(re_, idx, "numberOfAnalysts"),
            "eps_7g": _satir(tr, idx, "7daysAgo"), "eps_30g": _satir(tr, idx, "30daysAgo"), "eps_60g": _satir(tr, idx, "60daysAgo"), "eps_90g": _satir(tr, idx, "90daysAgo"),
        }
    try:  # çeyreklik beklenti (bu çeyrek / gelecek çeyrek): bilanço öncesi değerleri saklamak için her gün kaydedilir
        out["q"] = {"eps0q": _satir(ee, "0q", "avg"), "rev0q": _satir(re_, "0q", "avg"), "eps1q": _satir(ee, "+1q", "avg"), "rev1q": _satir(re_, "+1q", "avg")}
    except Exception:  # noqa: BLE001
        out["q"] = None
    try:
        info = t.info or {}
        out["fye"] = {"son": info.get("lastFiscalYearEnd"), "sonraki": info.get("nextFiscalYearEnd"), "ceyrek": info.get("mostRecentQuarter")}
        out["y0"]["eps_gecen"] = _satir(ee, "0y", "yearAgoEps")
        out["y1"]["eps_gecen"] = _satir(ee, "+1y", "yearAgoEps")
    except Exception:  # noqa: BLE001
        out["fye"] = None
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


def _r(v, n=2):
    return None if v is None else round(float(v), n)


def turet(x, e, onceki=None, bugun=None):
    """Hisse satırı x (close, d5, d20, mcap, cur, fcu, earn) ve Yahoo tahmini e'den değerleme alanları.
    İleri F/K yalnız fiyat ve EPS aynı para biriminde ise hesaplanır (ADR'lerde Yahoo EPS'i şirketin raporlama parasıyla verebilir: karışırsa gösterilmez).
    5 işlem günü = 7 takvim günü (eps_7g), 20 işlem günü ~ 1 ay (eps_30g). Geçmiş (eh) ve bilanço öncesi kayıt (bl) önceki yayından taşınır."""
    c = x.get("close")
    y0, y1 = e["y0"], e["y1"]
    kur_ok = bool(x.get("cur")) and x.get("cur") == x.get("fcu")
    o = {"cur": x.get("cur"), "an0": y0.get("an") and int(y0["an"]), "an1": y1.get("an") and int(y1["an"]),
         "eps0": _r(y0["eps"], 3), "eps0_lo": _r(y0["eps_lo"], 3), "eps0_hi": _r(y0["eps_hi"], 3),
         "eps1": _r(y1["eps"], 3), "eps1_lo": _r(y1["eps_lo"], 3), "eps1_hi": _r(y1["eps_hi"], 3),
         "rev0": _r(y0["rev"] and y0["rev"] / 1e6, 1), "rev1": _r(y1["rev"] and y1["rev"] / 1e6, 1), "revu": x.get("fcu")}
    q = e.get("q")
    if bugun and q and any(v is not None for v in q.values()):
        qh = [p for p in ((onceki or {}).get("qh") or []) if p[0] != bugun]
        qh.append([bugun, _r(q.get("eps0q"), 3), _r(q.get("rev0q") and q["rev0q"] / 1e6, 1), _r(q.get("eps1q"), 3), _r(q.get("rev1q") and q["rev1q"] / 1e6, 1)])
        o["qh"] = qh[-14:]  # [tarih, bu çeyrek EPS, bu çeyrek gelir (milyon), gelecek çeyrek EPS, gelecek çeyrek gelir]
    if not kur_ok:
        o["kur_uyari"] = True
        return o
    pos = lambda v: v is not None and v > 0  # noqa: E731
    o["pe0"] = _r(c / y0["eps"], 2) if pos(y0["eps"]) and c else None
    o["pe1"] = _r(c / y1["eps"], 2) if pos(y1["eps"]) and c else None
    mc = x.get("mcap")
    if x.get("cur") == "USD" and mc:
        o["ps0"] = _r(mc / y0["rev"], 2) if pos(y0["rev"]) else None
        o["ps1"] = _r(mc / y1["rev"], 2) if pos(y1["rev"]) else None
    # 5 ve 20 günlük: fiyat o günkü fiyata, EPS tahmini 7 ve 30 gün önceki tahmine bölünür
    for ad, d, ek in (("5", x.get("d5"), "eps_7g"), ("20", x.get("d20"), "eps_30g")):
        old = y0.get(ek)
        if pos(old) and pos(y0["eps"]) and d is not None and c:
            o["pe" + ad] = _r((c / (1 + d / 100)) / old, 2)
            o["r" + ad] = _r((y0["eps"] / old - 1) * 100, 2)
            o["pc" + ad] = _r((o["pe0"] / o["pe" + ad] - 1) * 100, 1)
        elif pos(old) and y0["eps"] is not None:
            o["r" + ad] = _r((y0["eps"] / old - 1) * 100, 2)
    # geçmiş: her yayında bir nokta (tarih, ileri F/K), son 60
    eh = list((onceki or {}).get("eh") or [])
    if bugun and o["pe0"] is not None:
        eh = [p for p in eh if p[0] != bugun] + [[bugun, o["pe0"]]]
    o["eh"] = eh[-60:]
    # bilanço öncesi kayıt: bilanço yaklaşırken her gün güncellenir; bilanço geçince sabit kalır ve bugünkü çarpanla kıyaslanır
    bl = (onceki or {}).get("bl")
    nxt = x.get("earn")
    if not nxt and bl and (bl.get("for") or "") >= (bugun or ""):  # takvimde artık tarih yok: kayıtlı öncesi değer yanlış zamana ait olabilir
        bl = None
    if x.get("earn_rep"):  # bilanço takvimdeki tarihten önce açıklanmış: eski öncesi kaydı yanlış zamana ait olur, kullanılmaz
        bl, nxt = None, None
    if bugun and o["pe0"] is not None and nxt and nxt >= bugun and (bl is None or bl.get("for") != nxt):
        bl = {"for": nxt, "pe": o["pe0"], "d": bugun, "eps": o["eps0"]}
    elif bugun and o["pe0"] is not None and bl and bl.get("for") and bl["for"] >= bugun:
        bl = dict(bl, pe=o["pe0"], d=bugun, eps=o["eps0"])
    if bl:
        o["bl"] = bl
    return o


if __name__ == "__main__":
    liste = [x["symbol"] for x in json.load(open("hisseler.json", encoding="utf-8"))["items"]]
    sonuc, hata = hepsi(liste)
    alan = lambda k: sum(1 for v in sonuc.values() if v["y0"].get(k) is not None)  # noqa: E731
    rapor = {"toplam": len(liste), "tahmin_var": len(sonuc), "eksik": hata,
             "kapsam": {k: alan(k) for k in ("eps", "eps_lo", "an", "rev", "eps_7g", "eps_30g", "eps_90g")}, "ornek": dict(list(sonuc.items())[:3]), "fye_var": sum(1 for v in sonuc.values() if v.get("fye") and (v["fye"].get("sonraki") or v["fye"].get("son"))), "veri": sonuc}
    print(json.dumps({k: v for k, v in rapor.items() if k != "veri"}, ensure_ascii=False, indent=1))
    if "--rapor" in sys.argv:
        json.dump(rapor, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)
