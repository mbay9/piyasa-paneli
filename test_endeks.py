"""Endeks çarpanı hesabı için birim testleri (ağ yok): python test_endeks.py"""
import datetime as dt
import sys

import endeks as E


def ep(y, m, d):
    return int(dt.datetime(y, m, d, 12).timestamp())


def yakin(a, b, tol=0.02):
    assert abs(a - b) <= tol, (a, b)


BUGUN = dt.date(2026, 11, 2)

# 1) ileri 12 ay: mali yıl sonuna 59 gün kala w = 59/365
e = {"eps0": 10.0, "eps1": 20.0, "fye": ep(2026, 12, 31)}
v, w, gecti = E.ntm(e, BUGUN)
yakin(w, 59 / 365, 0.003)
yakin(v, w * 10 + (1 - w) * 20, 1e-6)
assert gecti is False
# mali yıl bitti ama Yahoo hâlâ eski yılı gösteriyor: w=0, gelecek yıl alınır ve işaretlenir
v, w, gecti = E.ntm({"eps0": 10.0, "eps1": 20.0, "fye": ep(2026, 10, 1)}, BUGUN)
assert w == 0 and v == 20.0 and gecti is True
# eksik tahmin: hesap yok
assert E.ntm({"eps0": 10.0, "fye": ep(2026, 12, 31)}, BUGUN)[0] is None

# 2) toplam yöntemi: iki hisse, A kazançlı (fiyat 100, EPS 5), B zararda (fiyat 50, EPS -1), ağırlık 0.6/0.4
onb = {"A": {"cur": "USD", "fcur": "USD", "eps0": 5.0, "eps1": 6.0, "fye": ep(2026, 12, 31), "ttm": 4.5, "gaap": 4.0},
       "B": {"cur": "USD", "fcur": "USD", "eps0": -1.0, "eps1": 1.0, "fye": ep(2027, 3, 31), "ttm": -0.5, "gaap": -1.0}}
satir = [("A", 0.6, 100.0, onb["A"]), ("B", 0.4, 50.0, onb["B"])]
m = E.olcu(satir, lambda x: x["eps0"])
yakin(m["pe"], 1 / (0.6 * 0.05 + 0.4 * -0.02), 0.01)      # zarar dahil: toplam değer / toplam kazanç
yakin(m["pe_zh"], 20.0, 0.01)                              # zarar hariç yalnız A: 100/5
assert m["zarar"] == 1 and m["n"] == 2
# toplam kazanç eksiye düşerse çarpan yok (None), sahte sayı üretilmez
neg = [("B", 1.0, 50.0, onb["B"])]
assert E.olcu(neg, lambda x: x["eps0"])["pe"] is None

# 3) para birimi uyuşmazlığı hesaba girmez
onb2 = {"A": dict(onb["A"], fcur="EUR")}
assert E.olcu([("A", 1.0, 100.0, onb2["A"])], lambda x: x["eps0"]) is None

# 4) hesapla: kapsam ve verisiz listesi
blok = E.hesapla({"A": 0.5, "B": 0.3, "C": 0.2}, {"A": 100.0, "B": 50.0, "C": 10.0}, onb, BUGUN)
assert blok["uye"] == 3 and "C" in blok["verisiz"]
yakin(blok["ileri"]["kapsam"], 80.0, 0.1)                  # C'nin verisi yok: ağırlığın %80'i hesapta
assert blok["mali_yil_gecti"] == 0

# 5) yenileme sırası: önce hiç olmayan, sonra bilançosu geçen, sonra haftalık eski; taze olan dokunulmaz
onb3 = {"TAZE": {"t": "2026-11-01", "nt": ep(2026, 11, 20)},
        "ESKI": {"t": "2026-10-10", "nt": ep(2026, 11, 20)},
        "BILANCO": {"t": "2026-10-28", "nt": ep(2026, 10, 30)},          # 30 Ekim'de bilanço verdi, 28'inde alınmıştı
        "BILANCO_ALINDI": {"t": "2026-10-31", "nt": ep(2026, 10, 30)},   # bilançodan sonra alındı: yenilenmez
        "HATALI": {"t": "2026-11-01", "hata": "x"}}
sira, neden = E.yenilenecekler(onb3, ["TAZE", "ESKI", "BILANCO", "BILANCO_ALINDI", "HATALI", "YENI"], BUGUN)
assert sira[0] == "YENI" and sira[1] == "BILANCO", sira
assert "ESKI" in sira and "HATALI" in sira and "TAZE" not in sira and "BILANCO_ALINDI" not in sira, sira
assert neden == {"yok": 1, "bilanco": 1, "haftalik": 2}, neden

# 6) önbellek paketle/aç gidiş dönüş
assert E.ac(E.paketle(onb)) == {k: {a: b for a, b in v.items() if b is not None} for k, v in onb.items()}

# 7) ağırlık ilerletme: A %10 yükselir, B sabit
r = E.rolla({"A": 50.0, "B": 50.0}, {"A": 110.0, "B": 10.0}, {"A": 100.0, "B": 10.0})
yakin(r["A"], 55 / 105, 1e-6)
yakin(sum(r.values()), 1.0, 1e-9)

# 8) yedek ağırlık: ikinci pay (GOOG) ve USD olmayan hisse dışarıda
yed = E.yedek_agirlik(["GOOGL", "GOOG", "X", "Y"], {"GOOGL": {"mc": 300.0, "p": 100.0, "cur": "USD"}, "GOOG": {"mc": 300.0, "p": 100.0, "cur": "USD"},
                                                  "X": {"mc": 100.0, "p": 10.0, "cur": "USD"}, "Y": {"mc": 100.0, "p": 10.0, "cur": "EUR"}},
                      {"GOOGL": 100.0, "GOOG": 100.0, "X": 20.0, "Y": 10.0})
assert set(yed) == {"GOOGL", "X"}, yed
yakin(yed["GOOGL"], 300 / (300 + 200), 1e-6)

# 9) SPY dosyası ve Slickcharts tablosu ayrıştırma (örnek veri)
try:
    import pandas as pd
    raw = pd.DataFrame([["Fund Name:", "SPDR", None, None, None, None, None, None], ["Holdings:", "As of 29-Oct-2026", None, None, None, None, None, None], [None] * 8,
                        ["Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"],
                        ["NVIDIA", "NVDA", "x", "y", 7.5, "IT", 1, "USD"], ["Berkshire", "BRK.B", "x", "y", 1.5, "Fin", 1, "USD"], ["Cash", "USD", "x", "y", 0.1, "-", 1, "USD"]])
    w, t = E.parse_spy(raw)
    assert t == "29-Oct-2026" and w == {"NVDA": 7.5, "BRK-B": 1.5}, (w, t)
    assert E.spy_tarih(t) == dt.date(2026, 10, 29)
    html = "<table><tr><th>#</th><th>Company</th><th>Symbol</th><th>Weight</th></tr><tr><td>1</td><td>Apple</td><td>AAPL</td><td>12.52%</td></tr><tr><td>2</td><td>Nvidia</td><td>NVDA</td><td>12.30%</td></tr></table>"
    assert E.parse_slick(html) == {"AAPL": 12.52, "NVDA": 12.3}
except ImportError as ex:
    print("UYARI: pandas/lxml yok, ayrıştırma testi atlandı:", ex)

print("test_endeks: tamam")
sys.exit(0)
