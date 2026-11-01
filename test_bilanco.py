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
    import datetime as dt
    bg = dt.date(2026, 11, 2)
    a2 = B.analiz(q, "USD", bg)
    assert a2["guvenilir"] is True or any("kalem" in x for x in a2["uyari"])   # az kalem sentetikte olabilir
    # aşırı sıçrama güvenilmez sayılır
    q2 = {"2026-09-30": {"gelir": 500, "brut": 100, "faaliyet": 10, "net": 5, "ebitda": 1, "eps": 1, "nakit": 1, "borc": 1, "varlik": 1, "isletme_nakit": 1, "fcf": 1},
          "2025-09-30": {"gelir": 100, "brut": 50, "faaliyet": 10, "net": 5, "ebitda": 1, "eps": 1, "nakit": 1, "borc": 1, "varlik": 1, "isletme_nakit": 1, "fcf": 1}}
    a3 = B.analiz(q2, "USD", bg)
    assert a3["guvenilir"] is False and any("aşırı" in x for x in a3["uyari"])
    # düzgün yükselen seri kabul edilir, dalgalı sıçrama reddedilir
    def seri(g):
        ds = ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
        return {d: {"gelir": v, "brut": v / 2, "faaliyet": v / 4, "net": v / 5, "ebitda": 1, "eps": 1, "nakit": 1, "borc": 1, "varlik": 1, "isletme_nakit": 1, "fcf": 1} for d, v in zip(ds, g)}
    assert B.analiz(seri([10, 20, 40, 80, 160]), "USD", bg)["guvenilir"] is True
    assert B.analiz(seri([10, 90, 15, 20, 160]), "USD", bg)["guvenilir"] is False
    # gelirsiz kısmi çeyrek karşılaştırmaya girmez
    qq = seri([10, 11, 12, 13, 14]); qq["2026-12-31"] = {"eps": 1.0}
    assert B.analiz(qq, "USD", bg)["donem"] == "2026-09-30"
    # eski çeyrek uyarısı
    a4 = B.analiz(q2, "USD", dt.date(2027, 6, 1))
    assert any("150 günden eski" in x for x in a4["uyari"])
    # capex pozitife çevrilir
    assert B.turet({"gelir": 10, "capex": -4})["capex"] == 4
    # sürpriz
    df = pd.DataFrame({"epsEstimate": [1.0, 2.0, 0.0], "epsActual": [1.2, 1.9, 0.1]}, index=pd.to_datetime(["2026-03-31", "2026-06-30", "2026-09-30"]))
    sp = B.surpriz_satirlari(df)
    assert [B.sonuc_surpriz(x) for x in sp] == ["aştı", "kaçırdı", None] and sp[0]["yuzde"] == 20.0
    assert len(B.surpriz_birlestir(sp[:1], sp)) == 3
    print("test_bilanco: tamam")
main()
