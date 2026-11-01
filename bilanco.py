"""Bilanço indirme, kayıt ve çeyrek karşılaştırma (kuralla; her rakam Yahoo tablolarından gelir).

Her hisse için bilanco/<SEMBOL>.json: {"sembol","para","guncelleme","ceyrekler":{tarih:{kalem:değer}},"analiz":{...}}
Çeyrekler birikir: Yahoo'nun verdiği pencere eski çeyrekleri düşürse de dosyada kalır.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

# (anahtar, Yahoo satır adları (ilk bulunan), tablo)
KALEMLER = [
    ("gelir", ["Total Revenue", "Operating Revenue"], "g"),
    ("brut", ["Gross Profit"], "g"),
    ("faaliyet", ["Operating Income", "Total Operating Income As Reported"], "g"),
    ("net", ["Net Income", "Net Income Common Stockholders"], "g"),
    ("ebitda", ["EBITDA", "Normalized EBITDA"], "g"),
    ("eps", ["Diluted EPS", "Basic EPS"], "g"),
    ("arge", ["Research And Development"], "g"),
    ("fgy", ["Selling General And Administration"], "g"),
    ("nakit", ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"], "b"),
    ("borc", ["Total Debt"], "b"),
    ("ozkaynak", ["Stockholders Equity", "Common Stock Equity"], "b"),
    ("varlik", ["Total Assets"], "b"),
    ("stok", ["Inventory"], "b"),
    ("alacak", ["Accounts Receivable", "Receivables"], "b"),
    ("isletme_nakit", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], "c"),
    ("capex", ["Capital Expenditure"], "c"),
    ("fcf", ["Free Cash Flow"], "c"),
]
# yön: 1 = artış iyi, -1 = artış kötü, 0 = tek başına yorumlanmaz (gider: gelire oranı bakılır)
YON = {"gelir": 1, "brut": 1, "faaliyet": 1, "net": 1, "ebitda": 1, "eps": 1, "nakit": 1, "borc": -1, "ozkaynak": 1,
       "varlik": 1, "stok": 0, "alacak": 0, "isletme_nakit": 1, "fcf": 1, "arge": 0, "fgy": 0, "capex": 0}
AD = {"gelir": "Gelir", "brut": "Brüt kâr", "faaliyet": "Faaliyet kârı", "net": "Net kâr", "ebitda": "FAVÖK", "eps": "Hisse başı kâr",
      "nakit": "Nakit ve kısa vadeli yatırımlar", "borc": "Toplam borç", "ozkaynak": "Özkaynak", "varlik": "Toplam varlık",
      "isletme_nakit": "İşletme nakit akışı", "fcf": "Serbest nakit akışı", "net_nakit": "Net nakit (nakit − borç)",
      "brut_marj": "Brüt marj", "faaliyet_marj": "Faaliyet marjı", "net_marj": "Net marj", "fcf_marj": "FCF marjı",
      "arge_oran": "Ar-Ge / gelir", "fgy_oran": "Satış-yönetim gideri / gelir", "stok_oran": "Stok / çeyrek geliri",
      "alacak_oran": "Alacak / çeyrek geliri"}
# oran kalemlerinde iyi yön (marjlar +1; gider ve stok/alacak oranları -1)
ORAN_YON = {"brut_marj": 1, "faaliyet_marj": 1, "net_marj": 1, "fcf_marj": 1, "arge_oran": 0, "fgy_oran": -1, "stok_oran": -1, "alacak_oran": -1}
ESIK_PCT = 2.0     # tutar değişimi bunun altındaysa "değişmedi"
ESIK_PUAN = 0.5    # oran değişimi (yüzde puanı) bunun altındaysa "değişmedi"


def _sayi(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def cikar(gelir_tab, bilanco_tab, nakit_tab):
    """Üç Yahoo tablosundan (satır=kalem, sütun=dönem sonu) {tarih: {kalem: değer}} üretir."""
    ceyrek: dict[str, dict] = {}
    tablolar = {"g": gelir_tab, "b": bilanco_tab, "c": nakit_tab}
    for anahtar, adlar, t in KALEMLER:
        df = tablolar[t]
        if df is None or getattr(df, "empty", True):
            continue
        for ad in adlar:
            if ad in df.index:
                for col in df.columns:
                    v = _sayi(df.at[ad, col])
                    if v is not None:
                        tarih = str(col)[:10]
                        ceyrek.setdefault(tarih, {}).setdefault(anahtar, v)
                break
    return ceyrek


def turet(c):
    """Marj ve oranlar. Ham kalemler eksikse ilgili oran üretilmez."""
    d = dict(c)
    g = c.get("gelir")
    if g and g > 0:
        for k, a in (("brut_marj", "brut"), ("faaliyet_marj", "faaliyet"), ("net_marj", "net"), ("fcf_marj", "fcf"),
                     ("arge_oran", "arge"), ("fgy_oran", "fgy"), ("stok_oran", "stok"), ("alacak_oran", "alacak")):
            if c.get(a) is not None:
                d[k] = round(c[a] / g * 100, 2)
    if c.get("nakit") is not None and c.get("borc") is not None:
        d["net_nakit"] = c["nakit"] - c["borc"]
    return d


def birlestir(eski, yeni):
    """Eski dosyadaki çeyrekleri korur, yenilerle aynı tarihliyi günceller."""
    out = {t: dict(v) for t, v in (eski or {}).items()}
    for t, v in yeni.items():
        out.setdefault(t, {}).update(v)
    return dict(sorted(out.items()))


def _ceyrek_arasi(t1, t2):
    return abs((dt.date.fromisoformat(t2) - dt.date.fromisoformat(t1)).days)


def karsilastir(yeni, eski, ad_haritasi=None):
    """İki dönemi kalem kalem karşılaştırır. Dönüş: [{k, ad, once, simdi, fark, tur, sonuc}]"""
    out = []
    for k in list(AD):
        a, b = eski.get(k), yeni.get(k)
        if a is None or b is None:
            continue
        if k in ORAN_YON or k.endswith("_marj"):
            fark = round(b - a, 2)
            yon = ORAN_YON.get(k, 0)
            if abs(fark) < ESIK_PUAN:
                s = "değişmedi"
            elif yon == 0:
                s = "arttı" if fark > 0 else "azaldı"
            else:
                s = "iyileşti" if (fark > 0) == (yon > 0) else "kötüleşti"
            out.append({"k": k, "ad": AD[k], "once": a, "simdi": b, "fark": fark, "tur": "puan", "sonuc": s})
        else:
            if k == "net_nakit":
                fark = round(b - a, 2)
                pct = None if a == 0 else round((b - a) / abs(a) * 100, 1)
                yon = 1
            else:
                pct = None if a == 0 else round((b - a) / abs(a) * 100, 1)
                fark = pct
                yon = YON.get(k, 0)
            if k == "net_nakit":
                s = "değişmedi" if pct is not None and abs(pct) < ESIK_PCT else ("iyileşti" if b > a else "kötüleşti")
                out.append({"k": k, "ad": AD[k], "once": a, "simdi": b, "fark": pct, "tur": "yuzde", "sonuc": s})
                continue
            if pct is None:
                continue
            if abs(pct) < ESIK_PCT:
                s = "değişmedi"
            elif yon == 0:
                s = "arttı" if pct > 0 else "azaldı"
            else:
                s = "iyileşti" if (pct > 0) == (yon > 0) else "kötüleşti"
            # zarardan kâra / kârdan zarara geçiş yüzdeyle yanıltır
            if k in ("net", "faaliyet", "eps", "fcf", "ebitda", "isletme_nakit") and (a < 0) != (b < 0):
                s = "iyileşti" if b > a else "kötüleşti"
                out.append({"k": k, "ad": AD[k], "once": a, "simdi": b, "fark": None, "tur": "yuzde", "sonuc": s, "isaret": True})
                continue
            out.append({"k": k, "ad": AD[k], "once": a, "simdi": b, "fark": pct, "tur": "yuzde", "sonuc": s})
    return out


def _ozet(satirlar):
    return {"iyi": sum(x["sonuc"] == "iyileşti" for x in satirlar), "kotu": sum(x["sonuc"] == "kötüleşti" for x in satirlar),
            "n": len(satirlar)}


def analiz(ceyrekler):
    """En son çeyreği bir önceki çeyrek (QoQ) ve geçen yılın aynı çeyreği (YoY) ile karşılaştırır."""
    tarihler = sorted(ceyrekler)
    if not tarihler:
        return None
    t = tarihler[-1]
    son = turet(ceyrekler[t])
    sonuc = {"donem": t, "kalem_sayisi": len([k for k in son if k in AD])}
    oncekiler = [x for x in tarihler[:-1] if 60 <= _ceyrek_arasi(x, t) <= 120]
    if oncekiler:
        o = oncekiler[-1]
        sat = karsilastir(son, turet(ceyrekler[o]))
        sonuc["qoq"] = {"donem": o, "satirlar": sat, "ozet": _ozet(sat)}
    yillar = [x for x in tarihler[:-1] if 330 <= _ceyrek_arasi(x, t) <= 400]
    if yillar:
        o = yillar[-1]
        sat = karsilastir(son, turet(ceyrekler[o]))
        sonuc["yoy"] = {"donem": o, "satirlar": sat, "ozet": _ozet(sat)}
    return sonuc


def hisse_dosyasi(sym, para, ceyrek, onceki=None):
    c = birlestir((onceki or {}).get("ceyrekler"), ceyrek)
    return {"sembol": sym, "para": para, "guncelleme": dt.date.today().isoformat(), "ceyrekler": c, "analiz": analiz(c)}


def getir(sym, tries=3):
    import time
    import yfinance as yf
    son = None
    for i in range(tries):
        try:
            t = yf.Ticker(sym)
            c = cikar(t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow)
            if c:
                try:
                    para = (t.info or {}).get("financialCurrency")
                except Exception:  # noqa: BLE001
                    para = None
                return c, para
            son = "boş tablo"
        except Exception as e:  # noqa: BLE001
            son = repr(e)[:120]
        time.sleep(2 + 3 * i)
    raise RuntimeError(son)


def ana(cikti="bilanco", onceki=None, semboller=None, isci=4):
    from concurrent.futures import ThreadPoolExecutor
    if semboller is None:
        semboller = [x["symbol"] for x in json.load(open("hisseler.json", encoding="utf-8"))["items"]]
    os.makedirs(cikti, exist_ok=True)
    hata = {}

    def is_(sym):
        ad = sym.replace("/", "_") + ".json"
        eski = None
        if onceki and os.path.exists(os.path.join(onceki, ad)):
            try:
                eski = json.load(open(os.path.join(onceki, ad), encoding="utf-8"))
            except Exception:  # noqa: BLE001
                eski = None
        try:
            c, para = getir(sym)
        except Exception as e:  # noqa: BLE001
            hata[sym] = str(e)
            if eski:   # eski kayıt korunur
                json.dump(eski, open(os.path.join(cikti, ad), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return
        d = hisse_dosyasi(sym, para or (eski or {}).get("para"), c, eski)
        json.dump(d, open(os.path.join(cikti, ad), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with ThreadPoolExecutor(isci) as ex:
        list(ex.map(is_, semboller))
    json.dump({"guncelleme": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "adet": len(semboller), "hata": hata},
              open(os.path.join(cikti, "_durum.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"bilanço: {len(semboller) - len(hata)}/{len(semboller)} hisse; hata: {sorted(hata)}")
    return hata


if __name__ == "__main__":
    ana(onceki=sys.argv[1] if len(sys.argv) > 1 else None)
