"""Günlük değerleme özeti: tamamen kuralla üretilir, her sayı veriden gelir (uydurma yok).

Girdi: data.json içeriği (endeks, ai.stocks) ve isteğe bağlı FactSet referansı (kalibrasyon.json 'referans').
Çıktı: {"tarih", "endeks": [...], "sirketler": {...}, "notlar": [...]}
"""
from __future__ import annotations

BILANCO_ESIK = 15.0   # bilanço öncesine göre ileri F/K değişimi (%), mutlak
HAREKET_ESIK = 20.0   # 5 günde ileri F/K değişimi (%), mutlak
BOLGE = [(0.90, "ucuz"), (1.10, "normal"), (1.25, "pahalı"), (9e9, "çok pahalı")]


def bolge(oran):
    for sinir, ad in BOLGE:
        if oran < sinir:
            return ad
    return BOLGE[-1][1]


def _gecmis(csv):
    out = []
    for ln in (csv or "").splitlines()[1:] if (csv or "").startswith("tarih") else (csv or "").splitlines():
        p = ln.split(",")
        if len(p) == 7:
            try:
                out.append((p[0], p[1:]))
            except ValueError:
                pass
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _degisim(satirlar, idx, n, simdi):
    """n işlem günü önceki değere göre % değişim; yeterli geçmiş yoksa None."""
    if simdi is None or len(satirlar) <= n:
        return None
    eski = _f(satirlar[-1 - n][1][idx])
    if not eski:
        return None
    return round((simdi / eski - 1) * 100, 1)


def endeks_satirlari(endeks, ref=None):
    sat = []
    if not endeks:
        return sat
    g = _gecmis(endeks.get("gecmis"))
    for ad, anah, idx, ort in (("S&P 500", "spx", 0, True), ("Nasdaq-100", "ndx", 3, False)):
        b = endeks.get(anah) or {}
        il = (b.get("ileri") or {}).get("pe")
        if il is None:
            continue
        r = {"ad": ad, "ileri": il, "son": (b.get("son") or {}).get("pe"), "gaap": (b.get("gaap") or {}).get("pe"),
             "zarar_hariç": (b.get("ileri") or {}).get("pe_zh"), "büyüme": b.get("buyume"),
             "ilk": b.get("ilk") or [], "d5": _degisim(g, idx, 5, il), "d20": _degisim(g, idx, 20, il)}
        if ort and ref:
            for k, a in (("ort5", "ileri_ort5"), ("ort10", "ileri_ort10")):
                if ref.get(a):
                    r[k] = ref[a]
                    r[k + "_oran"] = round(il / ref[a], 2)
            if r.get("ort10_oran"):
                r["bolge"] = bolge(r["ort10_oran"])
        sat.append(r)
    return sat


def sirket_listeleri(hisseler, ref_tarih):
    """Bilanço sonrası yeniden fiyatlanma ve 5 günlük çarpan hareketleri."""
    bilanco, hareket = [], []
    for s in hisseler or []:
        e = s.get("est") or {}
        sym = s.get("symbol")
        pe0 = e.get("pe0")
        bl = e.get("bl")
        if pe0 and bl and bl.get("for") and bl["for"] <= ref_tarih and bl.get("pe") and bl.get("d", "") < ref_tarih:
            dm = round((pe0 / bl["pe"] - 1) * 100, 1)
            if abs(dm) >= BILANCO_ESIK:
                bilanco.append({"s": sym, "bilanco": bl["for"], "once": bl["pe"], "simdi": pe0, "deg": dm,
                                "fiyat": s.get("d5"), "eps": e.get("r5"), "yon": "pahalandı" if dm > 0 else "ucuzladı"})
        pc5 = e.get("pc5")
        if pe0 and pc5 is not None and abs(pc5) >= HAREKET_ESIK and not any(b["s"] == sym for b in bilanco):
            hareket.append({"s": sym, "simdi": pe0, "deg": pc5, "fiyat": s.get("d5"), "eps": e.get("r5"),
                            "yon": "pahalandı" if pc5 > 0 else "ucuzladı"})
    bilanco.sort(key=lambda x: -abs(x["deg"]))
    hareket.sort(key=lambda x: -abs(x["deg"]))
    return bilanco[:12], hareket[:12]


def ai_medyan(hisseler):
    pe = sorted(x["est"]["pe0"] for x in hisseler or [] if (x.get("est") or {}).get("pe0") and 0 < x["est"]["pe0"] < 500)
    if not pe:
        return None
    n = len(pe)
    return round(pe[n // 2] if n % 2 else (pe[n // 2 - 1] + pe[n // 2]) / 2, 1)


def uret(veri, ref=None):
    tarih = (veri.get("meta") or {}).get("ref_date")
    st = (veri.get("ai") or {}).get("stocks") or []
    b, h = sirket_listeleri(st, tarih or "")
    return {"tarih": tarih, "endeks": endeks_satirlari(veri.get("endeks"), ref), "bilanco": b, "hareket": h,
            "ai_medyan": ai_medyan(st), "ai_n": len(st), "ref_kaynak": (ref or {}).get("kaynak")}
