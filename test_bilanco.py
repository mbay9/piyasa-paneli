import pandas as pd
import bilanco as B

def tab(satirlar, tarihler):
    return pd.DataFrame(satirlar, index=None if False else None).T if False else pd.DataFrame({pd.Timestamp(t): {k: v[i] for k, v in satirlar.items()} for i, t in enumerate(tarihler)})

def main():
    T = ["2026-09-30", "2026-06-30", "2025-09-30"]
    g = tab({"Total Revenue": [120, 100, 90], "Gross Profit": [60, 50, 40], "Operating Income": [30, 30, 10], "Net Income": [-5, 20, 8], "Diluted EPS": [1.2, 1.0, 0.8]}, T)
    b = tab({"Total Debt": [50, 40, 60], "Cash And Cash Equivalents": [70, 60, 20], "Inventory": [30, 20, 25]}, T)
    c = tab({"Free Cash Flow": [10, 5, -3]}, T)
    q = B.cikar(g, b, c)
    assert q["2026-09-30"]["gelir"] == 120 and q["2026-09-30"]["nakit"] == 70
    a = B.analiz(q)
    assert a["donem"] == "2026-09-30" and a["qoq"]["donem"] == "2026-06-30" and a["yoy"]["donem"] == "2025-09-30"
    d = {x["k"]: x for x in a["qoq"]["satirlar"]}
    assert d["gelir"]["sonuc"] == "iyileşti" and d["gelir"]["fark"] == 20.0
    assert d["borc"]["sonuc"] == "kötüleşti"            # borç arttı
    assert d["net"]["sonuc"] == "kötüleşti" and d["net"].get("isaret")  # kârdan zarara
    assert d["brut_marj"]["sonuc"] == "değişmedi"       # 50 -> 50
    assert d["faaliyet_marj"]["sonuc"] == "kötüleşti"   # 30 -> 25
    assert d["stok_oran"]["sonuc"] == "kötüleşti"       # 20/100 -> 30/120 = 25
    y = {x["k"]: x for x in a["yoy"]["satirlar"]}
    assert y["fcf"]["sonuc"] == "iyileşti" and y["net_nakit"]["sonuc"] == "iyileşti"
    # birikim: eski çeyrek korunur
    m = B.birlestir({"2024-09-30": {"gelir": 1}}, q)
    assert "2024-09-30" in m and len(m) == 4
    # eksik tablo çökmez
    assert B.cikar(None, None, None) == {} and B.analiz({}) is None
    print("test_bilanco: tamam")
main()
