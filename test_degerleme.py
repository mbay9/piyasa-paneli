import degerleme as D

def st(sym, pe0, bl=None, pc5=None, d5=0, r5=0):
    return {"symbol": sym, "d5": d5, "est": {"pe0": pe0, "bl": bl, "pc5": pc5, "r5": r5}}

def main():
    assert D.bolge(0.8) == "ucuz" and D.bolge(1.0) == "normal" and D.bolge(1.2) == "pahalı" and D.bolge(1.4) == "çok pahalı"
    hs = [st("A", 30, {"for": "2026-10-28", "pe": 20, "d": "2026-10-27"}),      # +50% bilanço sonrası
          st("B", 21, {"for": "2026-10-28", "pe": 20, "d": "2026-10-27"}),      # +5%: eşik altı
          st("C", 10, {"for": "2026-11-05", "pe": 12, "d": "2026-10-27"}),      # bilanço henüz olmadı
          st("D", 10, pc5=-25.0), st("E", 10, pc5=5.0)]
    b, h = D.sirket_listeleri(hs, "2026-10-30")
    assert [x["s"] for x in b] == ["A"] and b[0]["deg"] == 50.0 and b[0]["yon"] == "pahalandı"
    assert [x["s"] for x in h] == ["D"] and h[0]["yon"] == "ucuzladı"
    g = "tarih,a,b,c,d,e,f,g\n" + "\n".join(f"2026-10-{i:02d},{10+i},1,1,{20+i},1,1" for i in range(1, 25))
    e = {"spx": {"ileri": {"pe": 40}}, "ndx": {"ileri": {"pe": 50}}, "gecmis": g}
    r = D.endeks_satirlari(e, {"ileri_ort5": 20, "ileri_ort10": 20})
    assert r[0]["bolge"] == "çok pahalı" and r[0]["ort10_oran"] == 2.0 and r[0]["d5"] is not None
    assert "bolge" not in r[1]
    assert D.endeks_satirlari(None) == []
    assert D.ai_medyan([st("A", 10), st("B", 30), st("C", 20)]) == 20
    print("test_degerleme: tamam")

main()
