"""Alt sektör grupları: gruplar.json'daki gruplara göre fiyat, tahmin ve bilanço göstergelerinin medyanı.

Gruplanmamış hisse "Diğer"e eklenir (ve uyarı olarak raporlanır), listeden çıkmış hisse atlanır.
Bilanço göstergeleri bilanco/<SEMBOL>.json dosyalarından gelir; dosya yoksa o gösterge boş kalır.
"""
from __future__ import annotations

import json
import os
import statistics

DIGER = "Diğer"
# Uyum için bakılan kalemler: büyüme, kârlılık, nakit ve stok. Her biri "iyileşti / kötüleşti / değişmedi" olarak sayılır.
SINYAL = ["gelir", "brut_marj", "faaliyet_marj", "net_marj", "fcf_marj", "stok_oran"]
SINYAL_AD = {"gelir": "gelir", "brut_marj": "brüt marj", "faaliyet_marj": "faaliyet marjı", "net_marj": "net marj", "fcf_marj": "FCF marjı", "stok_oran": "stok/gelir"}
MIN_HISSE = 4      # uyum yorumu için bilançosu olan en az hisse
ESIK_UYUM = 0.70   # hisselerin bu oranı aynı yöndeyse "aynı yönde"


def medyan(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def oran(a, b):
    return round((a / b - 1) * 100, 1) if a is not None and b not in (None, 0) and b > 0 else None


def bilanco_gostergeleri(b):
    """Bilanço dosyasından son çeyrek göstergeleri: gelir (YoY, QoQ), brüt marj değişimi, stok oranı değişimi."""
    a = (b or {}).get("analiz")
    out = {"donem": a.get("donem") if a else None}
    if not a:
        return out
    for ad in ("yoy", "qoq"):
        d = {x["k"]: x for x in (a.get(ad) or {}).get("satirlar", [])}
        out[ad + "_gelir"] = d["gelir"]["fark"] if "gelir" in d else None
        out[ad + "_brut"] = d["brut_marj"]["fark"] if "brut_marj" in d else None
        out[ad + "_stok"] = d["stok_oran"]["fark"] if "stok_oran" in d else None
        out[ad + "_iyi"] = (a[ad]["ozet"]["iyi"], a[ad]["ozet"]["kotu"]) if a.get(ad) else None
        out[ad + "_sonuc"] = {k: d[k]["sonuc"] for k in SINYAL if k in d}
    return out


def _sinirla(v, sinir=500):
    """Küçük tabandan gelen anlamsız büyüme oranlarını medyana sokmaz."""
    return None if v is not None and abs(v) > sinir else v


def hisse_yonu(bil, donem="yoy"):
    """Bir hissenin tüm kalemlerinde iyileşen/kötüleşen sayısına göre tek yön: 1 iyi, -1 kötü, 0 karışık/nötr, None veri yok."""
    d = (bil or {}).get(donem + "_sonuc") or {}
    iyi = sum(v == "iyileşti" for v in d.values())
    kotu = sum(v == "kötüleşti" for v in d.values())
    if len(d) < 3:
        return None
    if iyi >= 2 * max(kotu, 1) and iyi >= 3:
        return 1
    if kotu >= 2 * max(iyi, 1) and kotu >= 3:
        return -1
    return 0


def uyum(uyeler, donem="yoy"):
    """Aynı gruptaki şirketlerin bilançoları birbirini doğruluyor mu?"""
    yon = [(u["s"], hisse_yonu(u["bil"], donem)) for u in uyeler]
    v = [(s, y) for s, y in yon if y is not None]
    out = {"n": len(v), "iyi": sum(y == 1 for _, y in v), "kotu": sum(y == -1 for _, y in v), "karisik": sum(y == 0 for _, y in v)}
    sinyal = {}
    for k in SINYAL:
        sat = [(u["bil"] or {}).get(donem + "_sonuc", {}).get(k) for u in uyeler]
        sat = [x for x in sat if x]
        if sat:
            sinyal[k] = {"iyi": sat.count("iyileşti"), "kotu": sat.count("kötüleşti"), "n": len(sat)}
    out["sinyal"] = sinyal
    if out["n"] < MIN_HISSE:
        out["karar"] = "yetersiz veri"
        out["ayrisan"] = []
        return out
    if out["iyi"] / out["n"] >= ESIK_UYUM:
        out["karar"], ana = ("hepsi iyi yönde, birbirini doğruluyor" if out["iyi"] == out["n"] else "çoğunlukla iyi, birbirini doğruluyor"), 1
    elif out["kotu"] / out["n"] >= ESIK_UYUM:
        out["karar"], ana = ("hepsi kötü yönde, birbirini doğruluyor" if out["kotu"] == out["n"] else "çoğunlukla kötü, birbirini doğruluyor"), -1
    else:
        out["karar"], ana = "karışık mesaj", None
    out["ayrisan"] = [s for s, y in v if ana is not None and y == -ana]
    return out


def uye(s, bil):
    e = s.get("est") or {}
    return {"s": s["symbol"], "d1": s.get("d1"), "d5": s.get("d5"), "d20": s.get("d20"),
            "pe": e.get("pe0"), "r20": e.get("r20"), "pc20": e.get("pc20"),
            "eps_b": _sinirla(oran(e.get("eps1"), e.get("eps0"))), "gelir_b": oran(e.get("rev1"), e.get("rev0")),
            "fcf": None if s.get("fcf") is None else s["fcf"] > 0, "bs": None if s.get("nc") is None else s["nc"] > 0,
            "earn": s.get("earn"), "bil": bil}


def uret(hisseler, gruplar, bilanco_dizin=None, ref_tarih=None):
    atanan = {}
    for g, sy in gruplar.items():
        for x in sy:
            atanan.setdefault(x, g)
    by = {s["symbol"]: s for s in hisseler}
    kovalar = {g: [] for g in gruplar}
    kovalar.setdefault(DIGER, [])
    atanmamis = []
    for sym, s in by.items():
        g = atanan.get(sym)
        if g is None:
            g = DIGER
            atanmamis.append(sym)
        b = None
        if bilanco_dizin:
            yol = os.path.join(bilanco_dizin, sym + ".json")
            if os.path.exists(yol):
                try:
                    b = bilanco_gostergeleri(json.load(open(yol, encoding="utf-8")))
                except Exception:  # noqa: BLE001
                    b = None
        kovalar[g].append(uye(s, b))
    out = []
    for g, u in kovalar.items():
        if not u:
            continue
        bl = [x["bil"] for x in u if x["bil"]]
        k = {"n": len(u), "d1": medyan([x["d1"] for x in u]), "d5": medyan([x["d5"] for x in u]), "d20": medyan([x["d20"] for x in u]),
             "yukselen5": sum(1 for x in u if (x["d5"] or 0) > 0), "r20": medyan([x["r20"] for x in u]),
             "eps_b": medyan([x["eps_b"] for x in u]), "gelir_b": medyan([x["gelir_b"] for x in u]),
             "pe": medyan([x["pe"] for x in u if x["pe"] and 0 < x["pe"] < 500]),
             "fcf_pozitif": sum(1 for x in u if x["fcf"]), "fcf_n": sum(1 for x in u if x["fcf"] is not None),
             "gelir_yoy": medyan([x.get("yoy_gelir") for x in bl]), "gelir_qoq": medyan([x.get("qoq_gelir") for x in bl]),
             "brut_yoy": medyan([x.get("yoy_brut") for x in bl]), "brut_qoq": medyan([x.get("qoq_brut") for x in bl]),
             "stok_yoy": medyan([x.get("yoy_stok") for x in bl]), "bil_n": len(bl)}
        u.sort(key=lambda x: -(x["d20"] if x["d20"] is not None else -1e9))
        out.append({"ad": g, "ozet": k, "uyeler": u, "uyum": uyum(u, "yoy"), "uyum_qoq": uyum(u, "qoq")})
    return {"tarih": ref_tarih, "gruplar": out, "atanmamis": sorted(atanmamis)}
