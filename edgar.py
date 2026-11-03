"""Bilanço bültenlerini SEC EDGAR'dan indirir (8-K, madde 2.02, ek 99.1).
Her hisse için son günlerde yapılan başvuruların bülten metnini bildirim/<SEMBOL>/<tarih>_<başvuru>.txt olarak yazar.
Metin olduğu gibi (HTML etiketleri temizlenmiş) kaydedilir; rakam yorumlanmaz. SEC'in adil kullanım kuralı gereği iletişim bilgili kimlik gönderilir ve saniyede 10 istekten az yapılır."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request

UA = "piyasa-paneli research tantalos@duck.com"
GUN = 4  # son kaç takvim günündeki başvurular


def al(url, tries=3):
    for i in range(tries):
        try:
            time.sleep(0.2)
            r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(r, timeout=40) as f:
                return f.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 + 3 * i)


def metne(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)</(p|div|tr|li|h\d|table)>|<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)</t[dh]>", " | ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h).replace("\xa0", " ")
    satirlar = [re.sub(r"[ \t]+", " ", s).strip() for s in h.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(s for s in satirlar if s)).strip()


def basvurular(cik, bugun, gun=GUN):
    d = json.loads(al(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))["filings"]["recent"]
    esik = (bugun - dt.timedelta(days=gun)).isoformat()
    out = []
    for i, f in enumerate(d["form"]):
        if f == "8-K" and "2.02" in (d["items"][i] or "").split(",") and d["filingDate"][i] >= esik:
            out.append((d["filingDate"][i], d["accessionNumber"][i], d["primaryDocument"][i]))
    return out


def bulten(cik, acc, birincil=""):
    """Bülten metni: önce adında 99 geçen ek; yoksa ana belge dışındaki en büyük htm/txt (bazı şirketler eki başka adla verir)."""
    kok = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/"
    ind = json.loads(al(kok + "index.json"))
    dosyalar = [x for x in ind["directory"]["item"] if x["name"].lower().endswith((".htm", ".html", ".txt")) and not re.match(r"(?i)r\d+\.htm", x["name"])]
    adaylar = [x["name"] for x in dosyalar if re.search(r"(?i)(ex|exhibit)[-_ ]?99", x["name"])]
    adaylar.sort(key=lambda n: (not re.search(r"99[-_.]?1|991", n), n))
    yedek = sorted((x for x in dosyalar if x["name"] != birincil and x["name"] not in adaylar and not re.search(r"(?i)index|xbrl|graphic|ex[-_]?(3|4|10|21|23|31|32|101|104)", x["name"])),
                   key=lambda x: -int(x.get("size") or 0) if str(x.get("size") or "0").isdigit() else 0)
    for ad in adaylar[:2] + [x["name"] for x in yedek[:2]]:
        t = metne(al(kok + ad))
        if len(t) > 1500 and re.search(r"(?i)(results|revenue|net income|quarter)", t):
            return kok + ad, t
    return None, None


def ana(semboller, cikti="bildirim", bugun=None):
    bugun = bugun or dt.date.today()
    tick = {v["ticker"].upper(): v["cik_str"] for v in json.loads(al("https://www.sec.gov/files/company_tickers.json")).values()}
    yeni, hata = 0, {}
    for s in semboller:
        if "." in s and s.split(".")[-1].upper() in ("KS", "TW", "T", "SS"):
            continue  # EDGAR'da yok
        cik = tick.get(s.upper().replace(".", "-"))
        if not cik:
            continue
        try:
            for tarih, acc, bir in basvurular(cik, bugun):
                yol = os.path.join(cikti, s, f"{tarih}_{acc}.txt")
                if os.path.exists(yol):
                    continue
                url, t = bulten(cik, acc, bir)
                if not t:
                    hata[s] = f"{acc}: ek 99 bulunamadı"
                    continue
                os.makedirs(os.path.dirname(yol), exist_ok=True)
                open(yol, "w", encoding="utf-8").write(f"KAYNAK: {url}\nSEMBOL: {s}\nBASVURU_TARIHI: {tarih}\nBASVURU: {acc}\n\n{t}\n")
                yeni += 1
                print("yeni:", s, tarih, len(t), "karakter")
        except Exception as e:  # noqa: BLE001
            hata[s] = repr(e)[:120]
    print(f"bildirim: {yeni} yeni bülten, {len(hata)} hata")
    for k, v in hata.items():
        print("  hata", k, v)
    return yeni, hata


if __name__ == "__main__":
    syms = [x["symbol"] for x in json.load(open("hisseler.json", encoding="utf-8"))["items"]]
    if len(sys.argv) > 1:
        syms = sys.argv[1].split(",")
    ana(syms)
