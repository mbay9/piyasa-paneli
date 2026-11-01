import json, os, tempfile
import altsektor as A

def st(sym, d5, d20, pe0=20, eps0=1.0, eps1=1.5, fcf=1):
    return {"symbol": sym, "d1": 0, "d5": d5, "d20": d20, "fcf": fcf, "nc": 1, "earn": None,
            "est": {"pe0": pe0, "r20": 2.0, "pc20": 1.0, "eps0": eps0, "eps1": eps1, "rev0": 100, "rev1": 120}}

def main():
    gr = {"A": ["X", "Y"], "B": ["Z", "GONE"]}
    hs = [st("X", 5, 10), st("Y", -1, 30), st("Z", 0, 5), st("NEW", 2, 2)]
    d = tempfile.mkdtemp()
    json.dump({"analiz": {"donem": "2026-09-30", "qoq": {"ozet": {"iyi": 3, "kotu": 1}, "satirlar": [
        {"k": "gelir", "fark": 40.0, "sonuc": "iyileşti"}, {"k": "brut_marj", "fark": 2.5, "sonuc": "iyileşti"}]}}}, open(os.path.join(d, "X.json"), "w"))
    r = A.uret(hs, gr, d, "2026-10-30")
    g = {x["ad"]: x for x in r["gruplar"]}
    assert r["atanmamis"] == ["NEW"] and "Diğer" in g and [u["s"] for u in g["Diğer"]["uyeler"]] == ["NEW"]
    assert [u["s"] for u in g["A"]["uyeler"]] == ["Y", "X"]            # 20G'ye göre sıralı
    assert g["A"]["ozet"]["d20"] == 20.0 and g["A"]["ozet"]["eps_b"] == 50.0 and g["A"]["ozet"]["gelir_b"] == 20.0
    assert g["A"]["ozet"]["gelir_qoq"] == 40.0 and g["A"]["ozet"]["bil_n"] == 1
    assert g["B"]["ozet"]["gelir_qoq"] is None and g["B"]["ozet"]["n"] == 1   # GONE listede yok, atlandı
    assert A.medyan([None]) is None
    mk = lambda s, r: {"s": s, "bil": {"qoq_sonuc": r}}
    iyi = {"gelir": "iyileşti", "brut_marj": "iyileşti", "faaliyet_marj": "iyileşti", "stok_oran": "kötüleşti"}
    kotu = {"gelir": "kötüleşti", "brut_marj": "kötüleşti", "faaliyet_marj": "kötüleşti"}
    r = A.uyum([mk("A", iyi), mk("B", iyi), mk("C", iyi), mk("D", iyi), mk("E", kotu)])
    assert r["karar"].startswith("çoğunlukla iyi") and r["ayrisan"] == ["E"]
    assert A.uyum([mk(x, iyi) for x in "ABCD"])["karar"].startswith("hepsi iyi")
    assert A.uyum([mk("A", iyi), mk("B", kotu), mk("C", iyi), mk("D", kotu)])["karar"] == "karışık mesaj"
    assert A.uyum([mk("A", iyi), mk("B", iyi)])["karar"] == "yetersiz veri"
    assert A.hisse_yonu({"qoq_sonuc": {"gelir": "iyileşti"}}) is None
    # okuma
    assert "ters yönde" in A.okuma("çoğunlukla iyi, birbirini doğruluyor", -20, 10, 20)
    assert "fiyatta görünüyor" in A.okuma("hepsi iyi yönde, birbirini doğruluyor", 15, 40, 20)
    assert A.okuma("yetersiz veri", 1, 1, 1) is None and "karışık" in A.okuma("karışık mesaj", 0, 20, 20)
    # güvenilmez bilanço medyana girmez
    d2 = tempfile.mkdtemp()
    for sym, gy, gv in (("X", 40.0, True), ("Y", 900.0, False)):
        json.dump({"analiz": {"donem": "2026-09-30", "guvenilir": gv, "uyari": [] if gv else ["aşırı"],
                  "qoq": {"ozet": {"iyi": 1, "kotu": 0}, "satirlar": [{"k": "gelir", "fark": gy, "sonuc": "iyileşti"}]}}}, open(os.path.join(d2, sym + ".json"), "w"))
    r2 = A.uret([st("X", 1, 1), st("Y", 1, 1)], {"G": ["X", "Y"]}, d2, "2026-10-30")
    o = r2["gruplar"][0]["ozet"]
    assert o["gelir_qoq"] == 40.0 and o["dislanan"] == ["Y"] and o["bil_n"] == 1
    # olaylar: bilanço açıklayan hisse + diğerlerinin hareketi, günler birikir, önceki korunur
    def sb(sym, d1, bf=None, dt_="2026-10-30"):
        x = st(sym, 0, 0); x["d1"] = d1; x["date"] = dt_; x["est"]["bl"] = {"for": bf, "pe": 10, "d": "2026-10-20"} if bf else None
        return x
    r3 = A.uret([sb("P", -10, "2026-10-29"), sb("Q", 2), sb("R", 4)], {"G": ["P", "Q", "R"]}, None, "2026-10-30")
    ol = r3["olaylar"]
    assert len(ol) == 1 and ol[0]["s"] == "P" and ol[0]["gunler"]["2026-10-30"] == {"d1": -10, "es": 3.0, "yuk": 2, "n": 2}
    r4 = A.uret([sb("P", 1, "2026-10-29", "2026-10-31"), sb("Q", 0, None, "2026-10-31"), sb("R", 0, None, "2026-10-31")], {"G": ["P", "Q", "R"]}, None, "2026-10-31", onceki=r3)
    assert len(r4["olaylar"][0]["gunler"]) == 2
    # önceki karar kaydı
    assert "onceki" in r4["gruplar"][0]["uyum"]
    print("test_altsektor: tamam")
main()
