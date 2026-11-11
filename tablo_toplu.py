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
    if m >= 1e6:
        out.append(f"{m / 1e6:.2f} trillion")       # KRW gibi: 24.45 trillion
        out.append(f"{m / 1e6:.1f} trillion")
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


def birim_faktoru(kg, gel):
    """Gelir bültende hangi birimle yazılmışsa (bin/milyon) o birimin çarpanı; milyar yazımında None."""
    if "billion" in kg:
        return None
    n = float(kg.replace(",", ""))
    return 1e3 if abs(n * 1e3 - gel) < abs(n * 1e6 - gel) else 1e6


def satir_sayisi(metin, etiketler, faktor, gecerli):
    """Etiketle başlayan tablo satırındaki ilk sayı (bültendeki yazılışı, dolar değeri); geçerli(v) sağlanmazsa None."""
    for m in re.finditer(r"(?im)^(?:" + etiketler + r")[^|\n]{0,40}\|(.*)$", metin):
        for tok in re.finditer(r"(\(?)\$?\s*(\d[\d,]*(?:\.\d+)?)(\)?)\s*(%?)", m.group(1)):
            if tok.group(4) or re.match(r"\s*(\|\s*)?%", m.group(1)[tok.end():]):
                break
            v = float(tok.group(2).replace(",", "")) * faktor
            if tok.group(1) and tok.group(3):
                v = -v
            if gecerli(v):
                return tok.group(2), v
            break
    return None


def ce_yakin(ce, d, gun):
    for x in ce:
        if abs((d - dt.date.fromisoformat(x)).days - gun) <= 12:
            return x
    return None


_ARALIK = r"\$\s*([\d.,]+)\s*(million|billion)?\s*(?:to|and|-|–|—)\s*\$?\s*([\d.,]+)\s*(million|billion)"
_BAGLAM = re.compile(r"(?i)outlook|guidance|expect|forecast|anticipate|range|between")


def _para(x, birim):
    return float(x.replace(",", "")) * (1000.0 if birim.lower() == "billion" else 1.0)


def _adaylar_gelir(metin):
    """Satırlardaki gelir rehberliği adayları: (orta $M, kanıt metni). Aralık, ± ve 'yaklaşık' biçimleri."""
    out = []
    cap = metin.lower().find("outlook")
    cap2 = metin.lower().find("guidance")
    bas = min([x for x in (cap, cap2) if x >= 0] or [len(metin)])
    pos = 0
    for satir in metin.split("\n"):
        konum = pos
        pos += len(satir) + 1
        baglam = bool(_BAGLAM.search(satir)) or konum > bas
        if not baglam:
            continue
        for m in re.finditer(r"(?i)(?:net )?(?:revenues?|sales)[^.\n]{0,110}?" + _ARALIK, satir):
            try:
                u2 = m.group(4)
                lo, hi = _para(m.group(1), m.group(2) or u2), _para(m.group(3), u2)
            except ValueError:
                continue
            if 0 < lo < hi:
                out.append(((lo + hi) / 2, m.group(0)[m.group(0).index("$"):]))
        for m in re.finditer(r"(?i)(?:net )?(?:revenues?|sales)[^.\n]{0,60}?\$\s*([\d.,]+)\s*(million|billion)\s*(?:\+/-|±|plus or minus)", satir):
            try:
                out.append((_para(m.group(1), m.group(2)), m.group(0)[m.group(0).index("$"):]))
            except ValueError:
                pass
        for m in re.finditer(r"(?i)(?:net )?(?:revenues?|sales)\s+(?:of|to be|at)\s+(?:approximately|about|around)\s+\$\s*([\d.,]+)\s*(million|billion)", satir):
            try:
                out.append((_para(m.group(1), m.group(2)), m.group(0)[m.group(0).index("$"):]))
            except ValueError:
                pass
    return out


def rehberlik_gelir(metin, hedef=None, alt=0.65, ust=1.35):
    """İlk uygun aday. hedef ($M) verilirse orta nokta hedef*alt..hedef*ust içinde olmalı (yıllık rehberlik ve başka kalemleri eler)."""
    for orta, kanit in _adaylar_gelir(metin):
        if hedef is None or alt * hedef <= orta <= ust * hedef:
            return {"orta": orta, "kanit": kanit}
    return None


def rehberlik_eps(metin, yildizli):
    adaylar = []
    for satir in metin.split("\n"):
        if not _BAGLAM.search(satir):
            continue
        for m in re.finditer(r"(?i)(?:earnings|income) per (?:diluted )?share[^.\n]{0,120}?\$\s*(\d+\.\d\d)\s*(?:to|and|-|–|—)\s*\$?\s*(\d+\.\d\d)", satir):
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo < hi:
                ng = bool(re.search(r"(?i)non-gaap|adjusted", satir[max(0, m.start() - 60): m.end()]))
                adaylar.append((ng, (lo + hi) / 2, m.group(0)[m.group(0).index("$"):]))
    for ng, orta, kanit in adaylar:
        if ng == yildizli:
            return {"orta": orta, "kanit": kanit}
    return None


def onceki_bulten(dosya, tarih):
    d = dt.date.fromisoformat(tarih)
    en = None
    for f in sorted(glob.glob(os.path.join(os.path.dirname(dosya), "*.txt"))):
        if "nakit" in f:
            continue
        g = (d - dt.date.fromisoformat(os.path.basename(f)[:10])).days
        if 55 <= g <= 125:
            en = f
    return en


def gelir_bulten(metin, onceki_gelir):
    """Yahoo'da çeyrek geliri yoksa: bülten tablosundaki gelir satırı (birim, tablonun üstündeki 'in thousands/millions' ibaresinden)."""
    for m in re.finditer(r"(?im)^((?:total )?(?:net )?(?:revenues?|sales))\s*\|(.*)$", metin):
        sayilar = [t for t in re.finditer(r"\d[\d,]*(?:\.\d+)?", m.group(2))]
        if not sayilar or re.match(r"\s*(\|\s*)?%", m.group(2)[sayilar[0].end():]):
            continue
        u = None
        for x in re.finditer(r"(?i)in (thousands|millions)", metin[: m.start()]):
            u = x.group(1).lower()
        if not u:
            continue
        f = 1e3 if u == "thousands" else 1e6
        txt = sayilar[0].group(0)
        v = float(txt.replace(",", "")) * f
        if onceki_gelir and not (0.5 <= v / onceki_gelir <= 2.5):
            continue
        return {"gel": v, "kg": txt, "f": f, "sat": [float(t.group(0).replace(",", "")) * f for t in sayilar]}
    return None


def tablo(sym, dosya, metin, b):
    tarih = os.path.basename(dosya)[:10]
    acc = os.path.basename(dosya)[11:-4]
    para = b.get("para") or "USD"
    yabanci = para != "USD"  # yabancı para: tutarlar şirketin raporlama para biriminde, etikette yazılır; "$" kalıplı rehberlik okuması yapılmaz
    ce = b.get("ceyrekler") or {}
    k = ceyrek_anahtari(ce, tarih)
    if not k or not (ce.get(k) or {}).get("gelir"):
        k2 = ceyrek_anahtari({x["donem"]: {} for x in (b.get("surpriz") or []) if x.get("donem")}, tarih)
        k = k2 or k
    if not k:
        return None, "Yahoo tablolarında bu çeyrek yok"
    c = dict(ce.get(k) or {})
    gel = c.get("gelir")
    yedek = None
    if not gel:
        oncekiler = [ce[x].get("gelir") for x in sorted(ce) if x < k and ce[x].get("gelir")]
        yedek = gelir_bulten(metin, oncekiler[-1] if oncekiler else None)
        if not yedek:
            return None, "gelir ne Yahoo'da ne bültende bulunamadı"
        gel, kg = yedek["gel"], yedek["kg"]
        c = {"gelir": gel}
        for an, et in (("brut", r"gross (?:profit|income)"), ("faaliyet", r"operating income|income from operations|operating profit")):
            r_ = satir_sayisi(metin, et, yedek["f"], lambda v: -gel < v < gel)
            if r_:
                c[an] = r_[1]
    else:
        kg = bul(metin, gel)
        if not kg:
            return None, "gelir bültende bulunamadı (çeyrek eşleşmedi)"
    from tablo_kontrol import sonuc_beklenen
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
    if yedek and ky and ce[ky].get("gelir"):
        bul_ky = [x for x in yedek["sat"][1:] if abs(x - ce[ky]["gelir"]) <= 0.0006 * ce[ky]["gelir"] + 1000]
        if not bul_ky:
            ky = None
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
    faktor = birim_faktoru(kg, gel)
    brut, faal = c.get("brut"), c.get("faaliyet")
    ng = {}
    if faktor:
        ng["gp"] = satir_sayisi(metin, r"(?:non-gaap|adjusted)(?: \(non-gaap\))? gross (?:profit|income|margin)|gross (?:profit|income|margin) (?:\(non-gaap\)|on (?:a )?non-gaap basis|- non-gaap)|total non-gaap gross (?:profit|margin)", faktor,
                                lambda v: 0 < v < gel and (brut is None or brut * 0.98 <= v <= brut * 1.35))
        ng["op"] = satir_sayisi(metin, r"(?:non-gaap|adjusted)(?: \(non-gaap\))? (?:operating income|income from operations|operating profit|income \(loss\) from operations|operating income \(loss\))|(?:operating income|income from operations|operating profit) (?:\(non-gaap\)|on (?:a )?non-gaap basis|- non-gaap)", faktor,
                                lambda v: -gel < v < gel and (faal is None or abs(v - faal) <= 0.4 * gel))
        ng["eb"] = satir_sayisi(metin, r"adjusted ebitda|non-gaap ebitda|ebitda \(non-gaap\)|ebitda, as adjusted", faktor,
                                lambda v: -gel < v < gel and (faal is None or v >= faal - 0.02 * gel))
    def blok(ad, oad, an, kod):
        if ng.get(kod):
            txt, v = ng[kod]
            sat(ad.replace(" (", "* (", 1), "m", M(v), kanit=[txt])
            sat(oad.replace(" %", " %*", 1) if oad.endswith(" %") else oad, "p", round(v / gel * 100, 1), vurgu=1, hesap=f"{M(v):,} / {M(gel):,}")
            return
        v = c.get(an)
        if v and an in ("brut", "faaliyet"):
            kk = bul(metin, v)
            if kk:
                sat(ad, "m", M(v), kanit=[kk])
                sat(oad, "p", round(v / gel * 100, 1), vurgu=1, hesap=f"{M(v):,} / {M(gel):,}")
    blok("Gross Profit ($M)", "Gross Margin %", "brut", "gp")
    blok("Operating Income ($M)", "Operating Margin %", "faaliyet", "op")
    if ng.get("eb"):
        txt, v = ng["eb"]
        sat("EBITDA* ($M)", "m", M(v), kanit=[txt])
        sat("EBITDA Margin % *", "p", round(v / gel * 100, 1), vurgu=1, hesap=f"{M(v):,} / {M(gel):,}")
    fcf, on, cx = c.get("fcf"), c.get("isletme_nakit"), c.get("capex")
    # yabancı şirkette Yahoo nakit akışı güvenilir değil (ASML 3Ç26: gelirin %97'si kadar FCF gösterdi): işletme nakit akışı bültende birebir geçmiyorsa FCF yazılmaz
    if fcf is not None and on is not None and cx is not None and (not yabanci or bul(metin, on)):
        sat("FCF ($M)", "m", M(fcf), hesap=f"{M(on):,} operating cash flow - {M(abs(cx)):,} capital expenditures (Yahoo Finance cash flow statement)")
        sat("FCF Margin %", "p", round(fcf / gel * 100, 1), vurgu=1, hesap=f"{M(fcf):,} / {M(gel):,}")
    # önceki çeyrek şirket rehberliği: gelir için beklenti (†)
    bg_kullanildi = False
    onceki = None if yabanci else onceki_bulten(dosya, tarih)
    if onceki:
        rg = rehberlik_gelir(open(onceki, encoding="utf-8").read(), gel / 1e6)
        if rg:
            ptar = os.path.basename(onceki)[:10]
            bgm = f"{sym} prior-quarter release ({ptar}): " + rg["kanit"]
            for r in S:
                if r["ad"] == "Revenue ($M)":
                    r["bek"] = round(rg["orta"], 1); r["sonuc"] = sonuc_beklenen(r["ger"], r["bek"], "m"); r["bg"] = bgm; bg_kullanildi = True
                if r["ad"] == "Revenue Change YoY" and ky and ce[ky].get("gelir"):
                    r["bek"] = round((rg["orta"] * 1e6 / ce[ky]["gelir"] - 1) * 100, 1); r["sonuc"] = sonuc_beklenen(r["ger"], r["bek"], "p"); r["bg"] = bgm
    bolumler = [{"baslik": sym, "etiket": etiket(metin, k), "satirlar": S}]
    # sonraki çeyrek rehberliği
    rn = None if yabanci else rehberlik_gelir(metin, gel / 1e6, 0.6, 1.6)
    if rn:
        G = []
        G.append({"ad": "Revenue Guidance ($M)", "fmt": "m", "ger": round(rn["orta"], 1), "bek": None, "sonuc": None, "vurgu": 0, "kanit": [rn["kanit"]], "hesap": "aralığın orta noktası"})
        kn = ce_yakin(ce, dt.date.fromisoformat(k), 274)
        if kn and ce[kn].get("gelir"):
            G.append({"ad": "Revenue Change YoY", "fmt": "p", "ger": round((rn["orta"] * 1e6 / ce[kn]["gelir"] - 1) * 100, 1), "bek": None, "sonuc": None, "vurgu": 1,
                      "hesap": f"{rn['orta']:,.1f} / {M(ce[kn]['gelir']):,} - 1 (guidance midpoint vs. same quarter a year earlier, Yahoo Finance quarterly statements)"})
        yildizli = any(r["ad"].startswith("EPS*") for r in S)
        re_ = rehberlik_eps(metin, yildizli)
        if re_ and any(r["ad"].startswith("EPS") for r in S):
            G.append({"ad": "EPS* Guidance ($)" if yildizli else "EPS Guidance ($)", "fmt": "d", "ger": round(re_["orta"], 2), "bek": None, "sonuc": None, "vurgu": 0, "kanit": [re_["kanit"]], "hesap": "aralığın orta noktası"})
        bolumler.append({"baslik": "Next Quarter Guidance", "etiket": "Next quarter", "satirlar": G})
    yild = any("*" in r["ad"] for r in S)
    if yabanci:  # etiketlerde "$" yerine raporlama para birimi; EPS'in para birimi bültendeki gibidir (ADR için USD olabilir), bu yüzden yalnız "EPS"
        for bb in bolumler:
            for r in bb["satirlar"]:
                r["ad"] = r["ad"].replace("($M)", f"({para} M)").replace(" ($)", "")
    dip = []
    if yabanci:
        dip.append(f"Amounts in {para} millions (company reporting currency); EPS as stated in the company release.")
    if yild:
        dip.append("* Adjusted/non-GAAP per the company release; rows without * are GAAP as reported.")
    if any(r["ad"].startswith("EPS") and r["bek"] is not None for r in S):
        dip.append("EPS estimate: Yahoo Finance consensus for that quarter.")
    if bg_kullanildi:
        dip.append("† Estimate is the company's own guidance from the prior-quarter release (midpoint), not analyst consensus.")
    dip.append("No estimate available for the other rows. Margins and growth are calculated from reported figures; FCF from the Yahoo Finance cash flow statement.")
    sonuc = {
        "tarih": tarih, "basvuru": acc, "kaynak": kaynak,
        "bolumler": bolumler,
        "uretici": "toplu",
        "dipnot": " ".join(dip),
    }
    return sonuc, None


TABLO_GUN = 120  # tablo bu kadar gün gösterilir (bir sonraki bilançoya kadar); eskisi silinir


def temizle(v, bugun, gun=TABLO_GUN):
    """tarih alanı gun günden eski tabloları siler; silinen sembolleri döndürür."""
    eski = [s for s, t in v.get("tablolar", {}).items() if (bugun - dt.date.fromisoformat(t.get("tarih", "1970-01-01"))).days > gun]
    for s in eski:
        del v["tablolar"][s]
    return eski


def ana(bdir, ldir, cikti="tablolar.json", gun=100, bugun=None):
    bugun = bugun or dt.date.today()
    v = json.load(open(cikti, encoding="utf-8")) if os.path.exists(cikti) else {"v": 1, "tablolar": {}}
    eski = temizle(v, bugun)
    if eski:
        print("eski tablolar silindi:", " ".join(eski))
    yaz, atla = [], {}
    for sd in sorted(glob.glob(os.path.join(bdir, "*"))):
        sym = os.path.basename(sd)
        fs = sorted(f for f in glob.glob(os.path.join(sd, "*.txt")) if "nakit" not in f)
        if not fs:
            continue
        bp = os.path.join(ldir, f"{sym}.json")
        if not os.path.exists(bp):
            atla[sym] = "bilanco kaydı yok"
            continue
        bil = json.load(open(bp, encoding="utf-8"))
        mevcut = v["tablolar"].get(sym)
        neden = "bülten eski"
        # En yeni bültenden eskiye: son bülten sonuç bildirisi olmayabilir (ön açıklama, birleşme duyurusu); tablo çıkaran ilk bülten kullanılır.
        for f in reversed(fs):
            tarih = os.path.basename(f)[:10]
            if (bugun - dt.date.fromisoformat(tarih)).days > gun:
                break
            acc = os.path.basename(f)[11:-4]
            if mevcut and mevcut.get("basvuru") == acc and mevcut.get("uretici") != "toplu":
                neden = None  # elle (görev) hazırlanmış tabloya dokunma; toplu üretici kendi tablolarını yeniler
                break
            if mevcut and (mevcut.get("tarih", "") > tarih or (mevcut.get("tarih", "") == tarih and mevcut.get("uretici") != "toplu")):
                neden = None
                break
            t, neden = tablo(sym, f, open(f, encoding="utf-8").read(), bil)
            if t:
                v["tablolar"][sym] = t
                yaz.append(sym)
                neden = None
                break
        if neden:
            atla[sym] = neden
    v["guncelleme"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return v, yaz, atla


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--temizle":
    _yol = sys.argv[2] if len(sys.argv) > 2 else "tablolar.json"
    _v = json.load(open(_yol, encoding="utf-8"))
    _e = temizle(_v, dt.date.today())
    if _e:
        json.dump(_v, open(_yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("silinen eski tablo:", len(_e), " ".join(_e))
elif __name__ == "__main__":
    v, yaz, atla = ana(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "tablolar.json")
    json.dump(v, open(sys.argv[3] if len(sys.argv) > 3 else "tablolar.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("yazıldı:", len(yaz), " ".join(yaz))
    print("atlandı:", len(atla))
    for k, n in atla.items():
        print("  ", k, n)
