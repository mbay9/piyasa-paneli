import tablo_kontrol as T

def satir(**k):
    r = {"ad": "Revenue ($M)", "fmt": "m", "ger": 1262.6, "bek": 1255.5, "sonuc": "Beat", "vurgu": 0, "kanit": ["1,262.6"]}
    r.update(k); return r

def veri(r):
    return {"v": 1, "tablolar": {"X": {"tarih": "2026-11-02", "basvuru": "0001", "kaynak": "https://www.sec.gov/a", "bolumler": [{"baslik": "X", "satirlar": [r]}]}}}

def main():
    assert T.denetle(veri(satir())) == []
    assert T.denetle(veri(satir(sonuc="Miss")))                       # sonuç tutarsız
    assert T.denetle(veri(satir(bek=None)))                           # beklenti yok ama sonuç var
    assert T.denetle(veri(satir(sonuc=None)))                         # beklenti var ama sonuç yok
    assert T.denetle(veri(satir(bek=None, sonuc=None))) == []         # beklenti yok: yalnız gerçek
    assert T.denetle(veri(satir(kanit=None)))                         # kanıt yok
    assert T.denetle(veri(satir(kanit=None, hesap="Q/Q"))) == []
    assert T.sonuc_beklenen(0.45, 0.45, "d") == "In line" and T.sonuc_beklenen(50.04, 50.0, "p") == "In line"
    print("test_tablo: tamam")

main()
