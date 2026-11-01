"""Ağırlık kaynağı yoklaması (siteyi değiştirmez): hangi adres Actions'tan erişilebilir? python kaynak_testi.py --rapor kaynak-rapor.json"""
import json
import sys
import io
import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "*/*"}
URLS = {
    "nasdaq_api_ndx": ("https://api.nasdaq.com/api/quote/list-type/nasdaq100", {"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}),
    "invesco_qqq": ("https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund?idType=ticker&interval=monthly&productType=ETF", {}),
    "ssga_spy": ("https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx", {}),
    "ishares_ivv": ("https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund", {}),
    "slick_ndx": ("https://www.slickcharts.com/nasdaq100", {}),
    "slick_spx": ("https://www.slickcharts.com/sp500", {}),
    "stockanalysis_qqq": ("https://stockanalysis.com/etf/qqq/holdings/", {}),
    "stockanalysis_spy": ("https://stockanalysis.com/etf/spy/holdings/", {}),
    "sec_nport_index": ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001067839&type=NPORT-P&dateb=&owner=include&count=3", {}),
}
out = {}
for k, (u, h) in URLS.items():
    try:
        r = requests.get(u, headers={**H, **h}, timeout=(10, 40))
        out[k] = {"status": r.status_code, "bytes": len(r.content), "ctype": r.headers.get("content-type"), "head": r.text[:400] if "text" in (r.headers.get("content-type") or "") or "json" in (r.headers.get("content-type") or "") else None}
        if k == "nasdaq_api_ndx" and r.status_code == 200:
            try:
                rows = r.json()["data"]["data"]["rows"]
                out[k]["row0"] = rows[0]
                out[k]["n"] = len(rows)
            except Exception as e:  # noqa: BLE001
                out[k]["parse"] = repr(e)
    except Exception as e:  # noqa: BLE001
        out[k] = {"hata": repr(e)[:200]}
    print(k, {a: b for a, b in out[k].items() if a != "head"})
if "--rapor" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--rapor") + 1], "w", encoding="utf-8"), ensure_ascii=False)
