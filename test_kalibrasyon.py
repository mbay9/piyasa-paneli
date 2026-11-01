"""Kalibrasyon hesabı testleri (ağ yok): python test_kalibrasyon.py"""
import datetime as dt
import sys

import kalibrasyon as K

# 1) FactSet metni (gerçek PDF'ten alınan cümle biçimleri)
t = ("• Valuation: The forward 12 -month P/E ratio for the S&P 500 is 18.7. This P/E ratio is below the 5-year average\n"
     "The forward 12-month P/E ratio for the S&P 500 is 19.0 (based on Wednesday’s closing price and forward EPS). The trailing 12-month P/E ratio is 25.7 "
     "(based on Wednesday’s closing price and trailing EPS), which is above")
v = K.factset_ayristir(t)
assert (v["ileri"], v["son"], v["fiyat_gunu"]) == (18.7, 25.7, 2), v
assert K.factset_ayristir("alakasız")["ileri"] is None
t2 = ("The forward 12-month P/E ratio is 18.7, which is below the 5-year average (19.8) and below the 10-year average (19.1). "
      "The trailing 12-month P/E ratio is 25.7 (based on Thursday’s closing price and trailing EPS), which is above the 5-year average (24.4) and above the 10-year average (23.5).")
v2 = K.factset_ayristir(t2)
assert (v2["ileri_ort5"], v2["ileri_ort10"], v2["son_ort5"], v2["son_ort10"]) == (19.8, 19.1, 24.4, 23.5), v2
t3 = "The forward 12-month P/E ratio for the S&P 500 is 18.7. This P/E ratio is below the 5-year average of 19.8 and below the 10-year average of 1 9.1."
v3 = K.factset_ayristir(t3)
assert (v3["ileri_ort5"], v3["ileri_ort10"]) == (19.8, 19.1), v3

# 2) ChartRow ve Siblis
assert K.chartrow_ayristir("<title>Nasdaq-100 P/E Ratio (2026): 34.8 — Trailing</title> as of market close on October 30, 2026") == (34.8, "2026-10-30")
assert K.chartrow_ayristir("boş") == (None, None)
sb = K.siblis_ayristir("<p>Data through 30 September 2026</p><div>Trailing P/E 35.09</div><div>Forward P/E 23.26 (implied growth)</div>")
assert sb == {"son": 35.09, "ileri": 23.26, "tarih": "2026-09-30"}, sb

# 3) fiyat günü: Cuma raporu + 'Wednesday' -> aynı haftanın Çarşambası; gün yoksa bir önceki gün
assert K.fiyat_gunu("2026-10-02", 2) == "2026-09-30"
assert K.fiyat_gunu("2026-10-30", None) == "2026-10-29"

# 4) geçmişten okuma ve yakın gün
csv = "2026-10-29,18.9,,25.2,21.0,,30.0\n2026-10-30,18.69,22.93,25.06,20.85,27.71,30.11\nbozuk,1,2"
g = K.gecmis_oku(csv)
assert set(g) == {"2026-10-29", "2026-10-30"} and g["2026-10-30"]["spx_son"] == 22.93 and g["2026-10-29"]["spx_son"] is None
s, kayma = K.yakin_gun(g, "2026-10-29")
assert kayma == 0 and s["spx_ileri"] == 18.9
s, kayma = K.yakin_gun(g, "2026-10-31")
assert kayma == -1 and s["spx_ileri"] == 18.69
assert K.yakin_gun(g, "2026-11-10")[0] is None

# 5) kayıt: fark, yüzde; eksik değer kayıt üretmez
k = K.kayit("spx_ileri_factset", "2026-10-30", 18.69, 18.7, "FactSet")
assert k["fark"] == -0.01 and abs(k["fark_pct"] - (-0.05)) < 0.01
assert K.kayit("x", "2026-10-30", None, 18.7, "k") is None and K.kayit("x", "2026-10-30", 1.0, None, "k") is None

# 6) özet ve durum: az veri, iyi, izle, sapma
def seri(olcu, farklar):
    return [{"olcu": olcu, "tarih": f"2026-0{i + 1}-15", "bizim": 0, "resmi": 0, "fark": 0, "fark_pct": f, "kaynak": "t", "url": None, "kayma_gun": 0, "not": None} for i, f in enumerate(farklar)]
o = K.ozet(seri("a", [0.1, -0.2]))
assert o["a"]["durum"] == "yetersiz veri"
assert K.ozet(seri("a", [0.1, -0.2, 0.3]))["a"]["durum"] == "iyi"
assert K.ozet(seri("a", [3.0, 3.5, 3.2]))["a"]["durum"] == "izle"
x = K.ozet(seri("a", [6.0, 6.5, 5.5, 6.2]))["a"]
assert x["durum"] == "sapma" and x["sistematik"] is True, x
# tek ölçüm bile çok büyükse (örn. %15) 'izle' olarak işaretlenir, 'yetersiz veri' arkasına saklanmaz
assert K.ozet(seri("a", [15.0]))["a"]["durum"] == "izle"
# gürültü: ortalama ~0 ama dağınık: sistematik değil
assert K.ozet(seri("a", [1.5, -1.5, 1.2, -1.4]))["a"]["sistematik"] is False

# 7) birleştirme: aynı (ölçü, tarih) yinelenmez, yeni kayıt eskinin yerine geçer
e = seri("a", [1.0, 2.0])
y = [dict(e[0], fark_pct=9.9)]
b = K.birlestir(e, y)
assert len(b) == 2 and [k["fark_pct"] for k in b if k["tarih"] == e[0]["tarih"]] == [9.9]

# 8) ana hattın doğrulamaları
meta = {"verification": [{"id": "VIX", "yahoo": 19.42, "official": 19.42, "date": "2026-10-30"}],
        "proxy_checks": [{"id": "SPX", "etf": "SPY", "date": "2026-10-30", "index_d1": -1.818, "etf_d1": -1.773, "diff": 0.045}]}
a = K.ana_hat_kayitlari(meta)
assert {x["olcu"] for x in a} == {"vix_cboe", "spx_spy"} and a[0]["fark"] == 0.0 and abs(a[1]["fark_pct"] + 0.045) < 1e-6, a
print("test_kalibrasyon: tamam")
sys.exit(0)
