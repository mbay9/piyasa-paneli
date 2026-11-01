"""Ağırlık ve geçmiş veri kaynağı yoklaması (siteyi değiştirmez): python kaynak_testi.py --rapor kaynak-rapor.json"""
import io
import json
import sys
import requests
import pandas as pd

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
out = {}


def dene(ad, fn):
    try:
        out[ad] = fn()
    except Exception as e:  # noqa: BLE001
        out[ad] = {"hata": repr(e)[:300]}
    print(ad, json.dumps(out[ad], ensure_ascii=False, default=str)[:600])


def ssga():
    r = requests.get("https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx", headers=H, timeout=40)
    raw = pd.read_excel(io.BytesIO(r.content), header=None)
    baslik = next(i for i in range(15) if "Ticker" in [str(x).strip() for x in raw.iloc[i].tolist()])
    df = raw.iloc[baslik + 1:].copy()
    df.columns = [str(x).strip() for x in raw.iloc[baslik].tolist()]
    df = df[df["Ticker"].notna() & df["Weight"].notna()]
    w = pd.to_numeric(df["Weight"], errors="coerce")
    return {"ust_satirlar": raw.iloc[:baslik].fillna("").astype(str).values.tolist()[:6], "kolonlar": list(df.columns), "n": int(len(df)), "agirlik_toplam": float(w.sum()), "ilk5": df.head(5)[["Ticker", "Weight"]].values.tolist()}


def slick(url):
    r = requests.get(url, headers=H, timeout=40)
    tb = [t for t in pd.read_html(io.StringIO(r.text)) if any("Symbol" in str(c) for c in t.columns)]
    t = tb[0]
    wc = next(c for c in t.columns if "Weight" in str(c))
    w = pd.to_numeric(t[wc].astype(str).str.replace("%", ""), errors="coerce")
    return {"kolonlar": [str(c) for c in t.columns], "n": int(len(t)), "agirlik_toplam": float(w.sum()), "ilk5": t.head(5).astype(str).values.tolist()}


def shiller():
    r = requests.get("https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv", headers=H, timeout=40)
    df = pd.read_csv(io.StringIO(r.text))
    return {"kolonlar": list(df.columns), "n": int(len(df)), "ilk": df.head(2).astype(str).values.tolist(), "son3": df.tail(3).astype(str).values.tolist()}


def spglobal():
    r = requests.get("https://www.spglobal.com/spdji/en/documents/additional-material/sp-500-eps-est.xlsx", headers=H, timeout=60)
    return {"status": r.status_code, "bytes": len(r.content), "ctype": r.headers.get("content-type")}


def factset():
    r = requests.get("https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_102326.pdf", headers=H, timeout=60)
    return {"status": r.status_code, "bytes": len(r.content), "ctype": r.headers.get("content-type")}


def ndx_pr():
    r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?range=max&interval=1mo", headers=H, timeout=40)
    j = r.json()["result"][0]
    return {"status": r.status_code, "ilk": j["timestamp"][0], "n": len(j["timestamp"])}


for ad, fn in (("ssga_spy", ssga), ("slick_ndx", lambda: slick("https://www.slickcharts.com/nasdaq100")), ("slick_spx", lambda: slick("https://www.slickcharts.com/sp500")),
               ("shiller_datasets", shiller), ("spglobal_eps", spglobal), ("factset_pdf", factset), ("yahoo_ndx_max", ndx_pr)):
    dene(ad, fn)
if "--rapor" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False, default=str)
