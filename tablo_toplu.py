"""Toplu bilanço tablosu: bildirim/ bültenleri + bilanco/ (Yahoo tabloları ve EPS sürprizi) -> tablolar.json.
Kural: her rakam hem Yahoo kaydında hem bültende birebir bulunmalı; bulunamayan satır YAZILMAZ.
Beklenti (bek) yalnız Yahoo EPS sürprizinin 'tahmin' değeri (bültendeki EPS ile eşleşen kayıttan). Diğer satırlarda beklenti yok.
Kullanım: python tablo_toplu.py <bildirim_dizini> <bilanco_dizini> [tablolar.json]"""
from __future__ import annotations

import datetime as dt
import glob
import json
import math
import os
import re
import sys

AYLAR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def adaylar(v_usd):
    """Dolar değerinin bültende yazılabileceği biçimler (en az 4 anlamlı hane)."""
    out = []
    m = v_usd / 1e6
    out.append(f"{round(v_usd / 1e3):,}")          # bin dolar: 392,400
    out.append(f"{m:,.1f}")                          # milyon, 1 ondalık: 6,055.0 / 392.4
    if m >= 1000:
        out.append(f"{round(m):,}")                  # milyon tam sayı: 6,055
    b = m / 1000
    for x in {math.floor(b * 100) / 100, math.ceil(b * 100) / 100, round(b, 2)}:
        out.append(f"{x:.2f} billion")               # 6.06 billion (yuvarlama yönü şirkete göre değişir)
    return out


def bul(metin, v_usd):
    """Bültende değerin geçtiği ilk biçimi döndürür (tam kelime sınırında)."""
    for a in adaylar(v_usd):
        if re.search(r"(?<![\d,.])" + re.escape(a) + r"(?![\d,]|\.\d)", metin):
            return a
    return None


def ceyrek_anahtari(ceyrekler, bulten_tarihi):
    d = dt.date.fromisoformat(bulten_tarihi)
    ks = [k for k in sorted(ceyrekler) if dt.date.fromisoformat(k) <= d and (d - dt.date.fromisoformat(k)).days <= 110]
    return ks[-1] if ks else None


def gecen_yil(ceyrekler, k):
    d = dt.date.fromisoformat(k)
    for x in ceyrekler:
        if abs((d - dt.date.fromisoformat(x)).days - 365) <= 12:
            return x
    return None


def etiket(metin, k):
    d = dt.date.fromisoformat(k)
    return f"Quarter ended {AYLAR[d.month - 1]} {d.day}, {d.year}"


def tablo(sym, dosya, metin, b):
    tarih = os.path.basename(dosya)[:10]
    acc = os.path.basename(dosya)[11:-4]
    if b.get("para") not in (None, "USD"):
        return None, "para birimi USD değil"
    ce = b.get("ceyrekler") or {}
    k = ceyrek_anahtari(ce, tarih)
    if not k:
        return None, "Yahoo tablolarında bu çeyrek yok"
    c = ce[k]
    gel = c.get("gelir")
    if not gel:
        return None, "gelir yok"
    kg = bul(metin, gel)
    if not kg:
        return None, "gelir bültende bulunamadı (çeyrek eşleşmedi)"
    M = lambda x: round(x / 1e6, 1)
    kaynak = metin.split("\n")[0].replace("KAYNAK:", "").strip()
    S = []
    def sat(ad, fmt, ger, bek=None, vurgu=0, kanit=None, hesap=None):
        r = {"ad": ad, "fmt": fmt, "ger": ger, "bek": bek, "sonuc": None, "vurgu": vurgu}
        if bek is not None:
            from tablo_kontrol import sonuc_beklenen
            r["sonuc"] = sonuc_beklenen(ger, bek, fmt)
        if kanit:
            r["kanit"] = kanit
        if hesap:
            r["hesap"] = hesap
        S.append(r)
    sat("Revenue ($M)", "m", M(gel), kanit=[kg])
    ky = gecen_yil(ce, k)
    if ky and ce[ky].get("gelir"):
        sat("Revenue Change YoY", "p", round((gel / ce[ky]["gelir"] - 1) * 100, 1), vurgu=1,
            hesap=f"{M(gel):,} / {M(ce[ky]['gelir']):,} - 1 (Yahoo Finance quarterly statements, {ky[:4]} same quarter)")
    # EPS: Yahoo sürpriz kaydı (gerçek bültende birebir geçmeli)
    for s in reversed(b.get("surpriz") or []):
        if s.get("donem") == k and s.get("gercek") is not None:
            g = s["gercek"]
            ks = f"{g:.2f}"
            m = re.search(r"(?<![\d.])" + re.escape(ks) + r"(?!\d)", metin)
            if not m:
                break
            ctx = metin[max(0, m.start() - 250): m.end() + 80].lower()
            yild = bool(re.search(r"non-gaap|adjusted", ctx))
            bek = s.get("tahmin")
            sat("EPS* ($)" if yild else "EPS ($)", "d", round(g, 2), round(bek, 2) if bek is not None else None, kanit=[ks])
            break
    for ad, an, oad in (("Gross Profit ($M)", "brut", "Gross Margin %"), ("Operating Income ($M)", "faaliyet", "Operating Margin %")):
        v = c.get(an)
        if v:
            kk = bul(metin, v)
            if kk:
                sat(ad, "m", M(v), kanit=[kk])
                sat(oad, "p", round(v / gel * 100, 1), vurgu=1, hesap=f"{M(v):,} / {M(gel):,}")
    fcf, on, cx = c.get("fcf"), c.get("isletme_nakit"), c.get("capex")
    if fcf is not None and on is not None and cx is not None:
        sat("FCF ($M)", "m", M(fcf), hesap=f"{M(on):,} operating cash flow - {M(abs(cx)):,} capital expenditures (Yahoo Finance cash flow statement)")
        sat("FCF Margin %", "p", round(fcf / gel * 100, 1), vurgu=1, hesap=f"{M(fcf):,} / {M(gel):,}")
    sonuc = {
        "tarih": tarih, "basvuru": acc, "kaynak": kaynak,
        "bolumler": [{"baslik": sym, "etiket": etiket(metin, k), "satirlar": S}],
        "dipnot": "* Adjusted/non-GAAP per the company release. Revenue, gross profit and operating income are as reported (GAAP) and appear in the company release; "
                  "EPS estimate is the Yahoo Finance consensus for that quarter. No estimate available for the other rows. Margins and growth are calculated from reported figures.",
    }
    return sonuc, None


def ana(bdir, ldir, cikti="tablolar.json", gun=100, bugun=None):
    bugun = bugun or dt.date.today()
    v = json.load(open(cikti, encoding="utf-8")) if os.path.exists(cikti) else {"v": 1, "tablolar": {}}
    yaz, atla = [], {}
    for sd in sorted(glob.glob(os.path.join(bdir, "*"))):
        sym = os.path.basename(sd)
        fs = sorted(f for f in glob.glob(os.path.join(sd, "*.txt")) if "nakit" not in f)
        if not fs:
            continue
        f = fs[-1]
        tarih = os.path.basename(f)[:10]
        if (bugun - dt.date.fromisoformat(tarih)).days > gun:
            atla[sym] = "bülten eski"
            continue
        if sym in v["tablolar"] and v["tablolar"][sym].get("basvuru") == os.path.basename(f)[11:-4]:
            continue
        if sym in v["tablolar"] and v["tablolar"][sym].get("tarih", "") > tarih:
            continue
        bp = os.path.join(ldir, f"{sym}.json")
        if not os.path.exists(bp):
            atla[sym] = "bilanco kaydı yok"
            continue
        t, neden = tablo(sym, f, open(f, encoding="utf-8").read(), json.load(open(bp, encoding="utf-8")))
        if t:
            v["tablolar"][sym] = t
            yaz.append(sym)
        else:
            atla[sym] = neden
    v["guncelleme"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v, yaz, atla


if __name__ == "__main__":
    v, yaz, atla = ana(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "tablolar.json")
    json.dump(v, open(sys.argv[3] if len(sys.argv) > 3 else "tablolar.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("yazıldı:", len(yaz), " ".join(yaz))
    print("atlandı:", len(atla))
    for k, n in atla.items():
        print("  ", k, n)
