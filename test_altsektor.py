import json, os, tempfile
import altsektor as A

def st(sym, d5, d20, pe0=20, eps0=1.0, eps1=1.5, fcf=1):
    return {"symbol": sym, "d1": 0, "d5": d5, "d20": d20, "fcf": fcf, "nc": 1, "earn": None,
            "est": {"pe0": pe0, "r20": 2.0, "pc20": 1.0, "eps0": eps0, "eps1": eps1, "rev0": 100, "rev1": 120}}

def main():
    gr = {"A": ["X", "Y"], "B": ["Z", "GONE"]}
    hs = [st("X", 5, 10), st("Y", -1, 30), st("Z", 0, 5), st("NEW", 2, 2)]
    d = tempfile.mkdtemp()
    json.dump({"analiz": {"donem": "2026-09-30", "yoy": {"ozet": {"iyi": 3, "kotu": 1}, "satirlar": [
        {"k": "gelir", "fark": 40.0, "sonuc": "iyileşti"}, {"k": "brut_marj", "fark": 2.5, "sonuc": "iyileşti"}]}}}, open(os.path.join(d, "X.json"), "w"))
    r = A.uret(hs, gr, d, "2026-10-30")
    g = {x["ad"]: x for x in r["gruplar"]}
    assert r["atanmamis"] == ["NEW"] and "Diğer" in g and [u["s"] for u in g["Diğer"]["uyeler"]] == ["NEW"]
    assert [u["s"] for u in g["A"]["uyeler"]] == ["Y", "X"]            # 20G'ye göre sıralı
    assert g["A"]["ozet"]["d20"] == 20.0 and g["A"]["ozet"]["eps_b"] == 50.0 and g["A"]["ozet"]["gelir_b"] == 20.0
    assert g["A"]["ozet"]["gelir_yoy"] == 40.0 and g["A"]["ozet"]["bil_n"] == 1
    assert g["B"]["ozet"]["gelir_yoy"] is None and g["B"]["ozet"]["n"] == 1   # GONE listede yok, atlandı
    assert A.medyan([None]) is None
    mk = lambda s, r: {"s": s, "bil": {"yoy_sonuc": r}}
    iyi = {"gelir": "iyileşti", "brut_marj": "iyileşti", "faaliyet_marj": "iyileşti", "stok_oran": "kötüleşti"}
    kotu = {"gelir": "kötüleşti", "brut_marj": "kötüleşti", "faaliyet_marj": "kötüleşti"}
    r = A.uyum([mk("A", iyi), mk("B", iyi), mk("C", iyi), mk("D", iyi), mk("E", kotu)])
    assert r["karar"].startswith("çoğunlukla iyi") and r["ayrisan"] == ["E"]
    assert A.uyum([mk(x, iyi) for x in "ABCD"])["karar"].startswith("hepsi iyi")
    assert A.uyum([mk("A", iyi), mk("B", kotu), mk("C", iyi), mk("D", kotu)])["karar"] == "karışık mesaj"
    assert A.uyum([mk("A", iyi), mk("B", iyi)])["karar"] == "yetersiz veri"
    assert A.hisse_yonu({"yoy_sonuc": {"gelir": "iyileşti"}}) is None
    print("test_altsektor: tamam")
main()
