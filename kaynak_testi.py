"""Resmi çarpan kaynaklarının biçim yoklaması (siteyi değiştirmez): python kaynak_testi.py --rapor kaynak-rapor.json"""
import io
import json
import re
import sys
import datetime as dt
import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
out = {"factset": {}, "siblis": None, "chartrow": None}


def pdf_metin(url):
    from pypdf import PdfReader
    r = requests.get(url, headers=H, timeout=60)
    if r.status_code != 200 or "pdf" not in (r.headers.get("content-type") or ""):
        return None, r.status_code
    rd = PdfReader(io.BytesIO(r.content))
    return "\n".join((p.extract_text() or "") for p in rd.pages), 200


bugun = dt.date(2026, 11, 1)
tarihler = []
d = bugun
while len(tarihler) < 8:
    d -= dt.timedelta(days=1)
    if d.weekday() == 4:
        tarihler.append(d)
for d in tarihler:
    ad = d.strftime("%m%d%y")
    for host in ("advantage.factset.com/hubfs/Website", "insight.factset.com/hubfs", "go.factset.com/hubfs"):
        url = f"https://{host}/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_{ad}.pdf"
        try:
            t, st = pdf_metin(url)
        except Exception as e:  # noqa: BLE001
            t, st = None, repr(e)[:80]
        if t:
            sat = [re.sub(r"\s+", " ", x) for x in t.splitlines() if "P/E" in x or "p/e" in x]
            out["factset"][d.isoformat()] = {"url": url, "n": len(t), "satirlar": sat[:14]}
            break
        out["factset"][d.isoformat()] = {"hata": st}
    print(d, {k: v for k, v in out["factset"][d.isoformat()].items() if k != "satirlar"}, (out["factset"][d.isoformat()].get("satirlar") or [])[:4])
for ad, url in (("siblis", "https://siblisresearch.com/data/nasdaq-100-pe-ratio/"), ("chartrow", "https://chartrow.com/nasdaq-100/pe-ratio")):
    try:
        r = requests.get(url, headers=H, timeout=40)
        t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)
        t = re.sub(r"\s+", " ", t)
        i = t.find("P/E")
        out[ad] = {"status": r.status_code, "bytes": len(r.text), "ornek": t[max(0, i - 200):i + 900]}
    except Exception as e:  # noqa: BLE001
        out[ad] = {"hata": repr(e)[:150]}
    print(ad, str(out[ad])[:500])
if "--rapor" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)
