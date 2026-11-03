import datetime as dt, json, os, tempfile
import update as U

def main():
    d = dt.date
    assert U.son_ceyrek_sonu(d(2026, 11, 3)) == d(2026, 9, 30)
    assert U.son_ceyrek_sonu(d(2026, 1, 5)) == d(2025, 12, 31)
    assert U.son_ceyrek_sonu(d(2026, 9, 30)) == d(2026, 6, 30)
    t = tempfile.mkdtemp()
    json.dump({"surpriz": [{"donem": "2026-06-30", "gercek": 1.0}, {"donem": "2026-09-30", "gercek": 4.57}]}, open(os.path.join(t, "A.json"), "w"))
    json.dump({"surpriz": [{"donem": "2026-06-30", "gercek": 1.0}]}, open(os.path.join(t, "B.json"), "w"))
    ref = d(2026, 11, 3)
    assert U.rapor_edilmis("A", ref, t) == "2026-09-30"   # son çeyrek açıklanmış: takvim tarihi geçersiz
    assert U.rapor_edilmis("B", ref, t) is None            # henüz açıklanmamış: tarih korunur
    assert U.rapor_edilmis("YOK", ref, t) is None          # dosya yok: dokunma
    print("test_earn: tamam")

main()
