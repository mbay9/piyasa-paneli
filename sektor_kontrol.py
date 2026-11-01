"""Grup doğrulaması için veri toplar: Yahoo sektör/sanayi sınıflaması, iş özeti ve bilanço profili (marjlar, stok, Ar-Ge, capex yoğunluğu)."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor

def bilgi(sym):
    import yfinance as yf
    son = None
    for i in range(3):
        try:
            inf = yf.Ticker(sym).info or {}
            if inf.get("quoteType") or inf.get("sector") or inf.get("longBusinessSummary"):
                return {"sektor": inf.get("sector"), "sanayi": inf.get("industry"), "ozet": (inf.get("longBusinessSummary") or "")[:700],
                        "ulke": inf.get("country"), "ad": inf.get("longName") or inf.get("shortName")}
            son = "boş"
        except Exception as e:  # noqa: BLE001
            son = repr(e)[:100]
        time.sleep(2 + 3 * i)
    return {"hata": son}

def profil(yol):
    try:
        d = json.load(open(yol, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    q = d.get("ceyrekler") or {}
    t = [x for x in sorted(q) if q[x].get("gelir")]
    if not t:
        return None
    s = q[t[-1]]
    g = s["gelir"]
    r = lambda a: None if s.get(a) is None else round(s[a] / g * 100, 1)
    return {"donem": t[-1], "brut_marj": r("brut"), "faaliyet_marj": r("faaliyet"), "arge": r("arge"), "capex": None if s.get("capex") is None else round(abs(s["capex"]) / g * 100, 1),
            "stok": r("stok"), "nakit_borc": None if s.get("nakit") is None or s.get("borc") is None else round((s["nakit"] - s["borc"]) / g * 100, 0)}

def main(rapor, bilanco_dizin):
    gr = json.load(open("gruplar.json", encoding="utf-8"))
    ad = {x["symbol"]: x["name"] for x in json.load(open("hisseler.json", encoding="utf-8"))["items"]}
    liste = [(g, s) for g, ss in gr.items() for s in ss]
    with ThreadPoolExecutor(4) as ex:
        bil = list(ex.map(lambda gs: bilgi(gs[1]), liste))
    out = []
    for (g, s), b in zip(liste, bil):
        out.append({"s": s, "grup": g, "hisse_adi": ad.get(s), "yahoo": b, "profil": profil(os.path.join(bilanco_dizin, s + ".json"))})
    json.dump(out, open(rapor, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("tamam", len(out), "hatalı:", sum(1 for x in out if x["yahoo"].get("hata")))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
