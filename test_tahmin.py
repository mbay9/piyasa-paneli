"""tahmin.turet için birim testleri (ağ gerekmez)."""
import tahmin


def e(eps0=10.0, eps1=12.0, e7=None, e30=None, rev0=2e9, rev1=2.4e9):
    y = lambda eps, rev: {"eps": eps, "eps_lo": eps - 1, "eps_hi": eps + 1, "an": 20.0, "rev": rev, "rev_lo": rev, "rev_hi": rev, "rev_an": 18.0,  # noqa: E731
                          "eps_7g": e7, "eps_30g": e30, "eps_60g": None, "eps_90g": None}
    return {"y0": y(eps0, rev0), "y1": y(eps1, rev1)}


def x(**k):
    d = {"close": 100.0, "d5": 5.0, "d20": -10.0, "mcap": 5e10, "cur": "USD", "fcu": "USD", "earn": None}
    d.update(k)
    return d


# temel F/K ve F/S
o = tahmin.turet(x(), e(), None, "2026-11-02")
assert o["pe0"] == 10.0 and o["pe1"] == 8.33 and o["ps0"] == 25.0, o
# 5g: fiyat 100/1.05, EPS tahmini 9.5 -> F/K 10.025; değişim -> %-0.2 civarı; EPS revizyonu +%5.26
o = tahmin.turet(x(), e(e7=9.5, e30=8.0), None, "2026-11-02")
assert abs(o["pe5"] - round(100 / 1.05 / 9.5, 2)) < 1e-9 and o["r5"] == 5.26, o
assert o["pc20"] is not None and o["r20"] == 25.0, o
# ADR: fiyat parası ile raporlama parası farklıysa F/K yok
o = tahmin.turet(x(cur="USD", fcu="TWD"), e(), None, "2026-11-02")
assert o.get("kur_uyari") and "pe0" not in o, o
# zarar: F/K yok, F/S var
o = tahmin.turet(x(), e(eps0=-1.0, eps1=-0.5), None, "2026-11-02")
assert o["pe0"] is None and o["pe1"] is None and o["ps0"] == 25.0, o
# geçmiş: aynı gün tekrar çalışınca çoğalmaz, 60 ile sınırlı
old = {"eh": [[f"2026-09-{i:02d}", 9.0] for i in range(1, 29)] * 3}
o = tahmin.turet(x(), e(), old, "2026-11-02")
o2 = tahmin.turet(x(), e(), {"eh": o["eh"]}, "2026-11-02")
assert len(o["eh"]) <= 60 and o2["eh"] == o["eh"] and o["eh"][-1] == ["2026-11-02", 10.0], o
# bilanço öncesi kayıt: yaklaşırken güncellenir, bilanço geçince sabit kalır
o = tahmin.turet(x(earn="2026-11-05"), e(), None, "2026-11-02")
assert o["bl"]["for"] == "2026-11-05" and o["bl"]["pe"] == 10.0, o
o = tahmin.turet(x(earn=None, close=80.0), e(), {"bl": o["bl"]}, "2026-11-06")
assert o["bl"]["pe"] == 10.0 and o["pe0"] == 8.0, o
o2 = tahmin.turet(x(earn=None, close=80.0), e(), {"bl": {"for": "2026-11-05", "pe": 10.0, "d": "2026-11-03", "eps": 8.0}}, "2026-11-03")
assert "bl" not in o2, o2   # takvimde tarih kalmadı ve tarih gelecekte görünüyor: eski öncesi kayıt kullanılmaz
print("test_tahmin: tamam")
