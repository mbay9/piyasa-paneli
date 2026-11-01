"""Kalibrasyon: sitenin hesapladığı değerleri resmi ya da bağımsız kaynaklarla karşılaştırır, farkları kalibrasyon.json'a biriktirir.
Amaç: hata ya da sistematik sapma (kalibrasyon farkı) zamanla görünsün. Siteyi değiştirmez.

Kullanım: python kalibrasyon.py --veri data.json --dosya kalibrasyon.json
Kaynaklar (her biri bir 'ölçü'):
  spx_ileri_factset, spx_son_duz_factset, spx_son_gaap_factset   FactSet Earnings Insight (haftalık PDF, S&P 500)
  ndx_son_gaap_chartrow                                         ChartRow (resmi değil; QQQ ağırlıklı, GAAP, günlük)
  ndx_ileri_siblis, ndx_son_siblis                              Siblis Research (aylık, normalleştirilmiş kazanç)
  vix_cboe, spx_spy, nasdaq_oneq                                ana hattın mevcut doğrulamaları (Cboe resmi VIX, ETF yakınlığı)
"""
import datetime as dt
import io
import json
import re
import statistics
import sys

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
GUN = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
# durum eşikleri (yüzde): ortalama fark ve son fark. Resmi değerler bir ondalığa yuvarlandığından ±0,3 puan gürültü normaldir.
ESIK = {"iyi": (2.0, 4.0), "izle": (4.0, 8.0)}
MIN_N = 3


def _get(url, **kw):
    import requests
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=(10, 60), **kw)
    r.raise_for_status()
    return r


# ------------------------------------------------------------------ kaynak ayrıştırıcıları (saf fonksiyonlar: metin -> değer)
def factset_ayristir(t):
    """FactSet Earnings Insight metninden S&P 500 ileri ve son 12 ay F/K ile fiyat günü."""
    t = re.sub(r"\s+", " ", t)
    ileri = re.search(r"forward 12\s*-?\s*month P/E ratio (?:for the S&P 500 )?is (\d{1,2}\.\d)", t, re.I)
    son = re.search(r"trailing 12\s*-?\s*month P/E ratio (?:for the S&P 500 )?is (\d{1,2}\.\d)", t, re.I)
    gun = re.search(r"based on (\w+)[’']s closing price", t, re.I)
    def ort(m):
        """cümlenin devamındaki 5 ve 10 yıllık ortalamalar: '5-year average (19.8) ... 10-year average (19.1)' ya da '... of 19.8 ... of 1 9.1'"""
        if not m:
            return None, None
        parca = t[m.end():m.end() + 260]
        parca = re.sub(r"\b(\d) (\d\.\d)\b", r"\1\2", parca)  # PDF'te '19.1' bazen '1 9.1' çıkıyor
        a = re.search(r"5-year average (?:of |\()?(\d{1,2}\.\d)", parca)
        b = re.search(r"10-year average (?:of |\()?(\d{1,2}\.\d)", parca)
        return (float(a.group(1)) if a else None), (float(b.group(1)) if b else None)
    i5, i10 = ort(ileri)
    s5, s10 = ort(son)
    return {"ileri": float(ileri.group(1)) if ileri else None, "son": float(son.group(1)) if son else None,
            "fiyat_gunu": GUN.get(gun.group(1).lower()) if gun else None, "ileri_ort5": i5, "ileri_ort10": i10, "son_ort5": s5, "son_ort10": s10}


def chartrow_ayristir(html):
    """ChartRow Nasdaq-100 sayfası: (son 12 ay F/K, veri tarihi)."""
    m = re.search(r"P/E Ratio \(\d{4}\):\s*(\d{1,3}\.\d)", html)
    d = re.search(r"as of (?:market )?close on ([A-Z][a-z]+ \d{1,2}, \d{4})", html)
    tarih = None
    if d:
        try:
            tarih = dt.datetime.strptime(d.group(1), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    return (float(m.group(1)) if m else None), tarih


def siblis_ayristir(html):
    """Siblis Nasdaq-100 sayfası: {'son': .., 'ileri': .., 'tarih': 'YYYY-MM-DD'}; bulunamayan alan None."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    out = {"son": None, "ileri": None, "tarih": None}
    for k, desen in (("son", r"Trailing P/E[^0-9]{0,60}(\d{1,3}\.\d{1,2})"), ("ileri", r"Forward P/E[^0-9]{0,60}(\d{1,3}\.\d{1,2})")):
        m = re.search(desen, t, re.I)
        if m:
            out[k] = float(m.group(1))
    d = re.search(r"Data through (\d{1,2} [A-Z][a-z]+ \d{4})", t)
    if d:
        try:
            out["tarih"] = dt.datetime.strptime(d.group(1), "%d %B %Y").date().isoformat()
        except ValueError:
            pass
    return out


# ------------------------------------------------------------------ bizim değerler
def gecmis_oku(csv):
    """endeks.gecmis -> {tarih: {spx_ileri, spx_son, spx_gaap, ndx_ileri, ndx_son, ndx_gaap}}"""
    ad = ("spx_ileri", "spx_son", "spx_gaap", "ndx_ileri", "ndx_son", "ndx_gaap")
    out = {}
    for satir in (csv or "").split("\n"):
        p = satir.split(",")
        if len(p) == 7:
            out[p[0]] = {a: (float(v) if v else None) for a, v in zip(ad, p[1:])}
    return out


def yakin_gun(gecmis, tarih, pay=1):
    """tarihe en yakın satır (en fazla ±pay gün). -> (satır, kayma_gün) ya da (None, None). Eşitlikte öncesi tercih edilir."""
    d0 = dt.date.fromisoformat(tarih)
    en = None
    for k in gecmis:
        k_gun = (dt.date.fromisoformat(k) - d0).days
        if abs(k_gun) <= pay and (en is None or abs(k_gun) < abs(en[1]) or (abs(k_gun) == abs(en[1]) and k_gun < en[1])):
            en = (k, k_gun)
    return (gecmis[en[0]], en[1]) if en else (None, None)


def fiyat_gunu(rapor_tarihi, hafta_gunu):
    """FactSet raporunun dayandığı kapanış günü: metinde gün adı varsa raporun öncesindeki o gün, yoksa bir önceki gün."""
    d = dt.date.fromisoformat(rapor_tarihi)
    if hafta_gunu is None:
        return (d - dt.timedelta(days=1)).isoformat()
    while d.weekday() != hafta_gunu or d.isoformat() == rapor_tarihi:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def kayit(olcu, tarih, bizim, resmi, kaynak, url=None, kayma=0, not_=None):
    if bizim is None or resmi in (None, 0):
        return None
    fark = bizim - resmi
    return {"olcu": olcu, "tarih": tarih, "bizim": round(bizim, 3), "resmi": resmi, "fark": round(fark, 3), "fark_pct": round(fark / resmi * 100, 2),
            "kaynak": kaynak, "url": url, "kayma_gun": kayma, "not": not_}


# ------------------------------------------------------------------ özet ve durum
def ozet(kayitlar):
    """ölçü başına istatistik: n, ortalama/son fark %, std, durum (iyi/izle/sapma/yetersiz veri)."""
    gr = {}
    for k in kayitlar:
        gr.setdefault(k["olcu"], []).append(k)
    out = {}
    for o, ks in gr.items():
        ks = sorted(ks, key=lambda x: x["tarih"])
        f = [k["fark_pct"] for k in ks]
        ort = statistics.mean(f)
        std = statistics.pstdev(f) if len(f) > 1 else 0.0
        son = f[-1]
        if len(f) < MIN_N:
            durum = "yetersiz veri" if abs(son) <= ESIK["izle"][1] else "izle"
        elif abs(ort) <= ESIK["iyi"][0] and abs(son) <= ESIK["iyi"][1]:
            durum = "iyi"
        elif abs(ort) <= ESIK["izle"][0] and abs(son) <= ESIK["izle"][1]:
            durum = "izle"
        else:
            durum = "sapma"
        out[o] = {"n": len(f), "ort_fark_pct": round(ort, 2), "std_pct": round(std, 2), "son_fark_pct": son, "son_tarih": ks[-1]["tarih"], "durum": durum,
                  "sistematik": len(f) >= MIN_N and abs(ort) > 2 * max(std, 0.5) / max(len(f), 1) ** 0.5 and abs(ort) > 1.0}
    return out


def birlestir(eski, yeni):
    """(ölçü, tarih) anahtarıyla yinelenmeden birleştirir; aynı anahtarda yeni kayıt eskinin yerine geçer."""
    d = {(k["olcu"], k["tarih"]): k for k in eski}
    for k in yeni:
        if k:
            d[(k["olcu"], k["tarih"])] = k
    return sorted(d.values(), key=lambda k: (k["olcu"], k["tarih"]))


# ------------------------------------------------------------------ toplama
def factset_topla(gecmis, bugun, hafta=6, ref=None):
    from pypdf import PdfReader
    out, hata = [], []
    d = bugun
    sayi = 0
    while sayi < hafta:
        d -= dt.timedelta(days=1)
        if d.weekday() != 4:
            continue
        sayi += 1
        ad = d.strftime("%m%d%y")
        metin = url = None
        for host in ("advantage.factset.com/hubfs/Website", "insight.factset.com/hubfs", "go.factset.com/hubfs"):
            u = f"https://{host}/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_{ad}.pdf"
            try:
                r = _get(u)
                if "pdf" in (r.headers.get("content-type") or ""):
                    metin = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
                    url = u
                    break
            except Exception:  # noqa: BLE001
                continue
        if not metin:
            hata.append(f"FactSet {d}: rapor alınamadı")
            continue
        v = factset_ayristir(metin)
        if v["ileri"] is None:
            hata.append(f"FactSet {d}: ileri F/K metinden okunamadı (biçim değişmiş olabilir)")
            continue
        if ref is not None and "tarih" not in ref and v["ileri_ort5"] is not None:  # en yeni rapor: uzun dönem ortalamalar (değerleme "pahalı mı ucuz mu" kıyası için)
            ref.update({"tarih": d.isoformat(), "ileri": v["ileri"], "ileri_ort5": v["ileri_ort5"], "ileri_ort10": v["ileri_ort10"],
                        "son": v["son"], "son_ort5": v["son_ort5"], "son_ort10": v["son_ort10"], "kaynak": "FactSet Earnings Insight (S&P 500)", "url": url})
        fg = fiyat_gunu(d.isoformat(), v["fiyat_gunu"])
        satir, kayma = yakin_gun(gecmis, fg)
        if satir is None:
            continue  # o güne ait kendi kaydımız yok (geçmiş yalnız yayına girdiğimiz günden başlar)
        k = "FactSet Earnings Insight"
        out.append(kayit("spx_ileri_factset", fg, satir["spx_ileri"], v["ileri"], k, url, kayma))
        if v["son"] is not None:
            out.append(kayit("spx_son_duz_factset", fg, satir["spx_son"], v["son"], k, url, kayma, "FactSet son 12 ay tanımını açıklamıyor"))
            out.append(kayit("spx_son_gaap_factset", fg, satir["spx_gaap"], v["son"], k, url, kayma, "FactSet son 12 ay tanımını açıklamıyor"))
    return out, hata


def chartrow_topla(gecmis):
    try:
        v, tarih = chartrow_ayristir(_get("https://chartrow.com/nasdaq-100/pe-ratio").text)
    except Exception as e:  # noqa: BLE001
        return [], [f"ChartRow: {repr(e)[:80]}"]
    if v is None or tarih is None:
        return [], ["ChartRow: değer ya da tarih okunamadı"]
    satir, kayma = yakin_gun(gecmis, tarih, 0)
    if satir is None:
        return [], []
    return [kayit("ndx_son_gaap_chartrow", tarih, satir["ndx_gaap"], v, "ChartRow (resmi değil; QQQ ağırlıkları, GAAP, zarar dahil)", "https://chartrow.com/nasdaq-100/pe-ratio", kayma)], []


def siblis_topla(gecmis):
    try:
        v = siblis_ayristir(_get("https://siblisresearch.com/data/nasdaq-100-pe-ratio/").text)
    except Exception as e:  # noqa: BLE001
        return [], [f"Siblis: {repr(e)[:80]}"]
    if v["tarih"] is None or (v["son"] is None and v["ileri"] is None):
        return [], ["Siblis: değer ya da tarih okunamadı (biçim değişmiş olabilir)"]
    satir, kayma = yakin_gun(gecmis, v["tarih"], 3)
    if satir is None:
        return [], []
    k = "Siblis Research (aylık, normalleştirilmiş kazanç)"
    u = "https://siblisresearch.com/data/nasdaq-100-pe-ratio/"
    return [kayit("ndx_ileri_siblis", v["tarih"], satir["ndx_ileri"], v["ileri"], k, u, kayma), kayit("ndx_son_siblis", v["tarih"], satir["ndx_gaap"], v["son"], k, u, kayma)], []


def ana_hat_kayitlari(meta):
    """Ana hattın kendi doğrulamaları (VIX / Cboe resmi, endeks / ETF yakınlığı) aynı kayıt biçimine çevrilir."""
    out = []
    for v in (meta or {}).get("verification") or []:
        if v.get("id") == "VIX" and v.get("yahoo") and v.get("official") and v.get("date"):
            out.append(kayit("vix_cboe", v["date"], v["yahoo"], v["official"], "Cboe VIX_History (resmi)", None, 0))
    for p in (meta or {}).get("proxy_checks") or []:
        if p.get("index_d1") is not None and p.get("etf_d1") is not None and p.get("date"):
            kayit_ = {"olcu": ("spx_spy" if p["id"] == "SPX" else "nasdaq_oneq"), "tarih": p["date"], "bizim": p["index_d1"], "resmi": p["etf_d1"],
                      "fark": round(p["index_d1"] - p["etf_d1"], 3), "fark_pct": None, "kaynak": f"{p.get('etf')} günlük getiri (yakınlık kontrolü)", "url": None, "kayma_gun": 0, "not": "fark yüzde puan"}
            kayit_["fark_pct"] = kayit_["fark"]  # getiri farkı zaten puan cinsinden
            out.append(kayit_)
    return out


def calistir(veri, eski, bugun):
    d = veri or {}
    gec = gecmis_oku((d.get("endeks") or {}).get("gecmis"))
    yeni, hatalar = [], []
    ref = {}
    for fn in (lambda: factset_topla(gec, bugun, ref=ref), lambda: chartrow_topla(gec), lambda: siblis_topla(gec)):
        try:
            k, h = fn()
        except Exception as e:  # noqa: BLE001
            k, h = [], [repr(e)[:100]]
        yeni += [x for x in k if x]
        hatalar += h
    yeni += ana_hat_kayitlari(d.get("meta"))
    kay = birlestir((eski or {}).get("kayitlar") or [], yeni)
    return {"guncelleme": bugun.isoformat(), "kayitlar": kay[-1500:], "ozet": ozet(kay), "hatalar": hatalar, "eklenen": len([x for x in yeni if x]),
            "referans": ref or (eski or {}).get("referans") or {}}


if __name__ == "__main__":
    a = sys.argv
    veri = json.load(open(a[a.index("--veri") + 1], encoding="utf-8"))
    dosya = a[a.index("--dosya") + 1]
    try:
        eski = json.load(open(dosya, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        eski = {}
    sonuc = calistir(veri, eski, dt.date.today())
    json.dump(sonuc, open(dosya, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"eklenen": sonuc["eklenen"], "hatalar": sonuc["hatalar"], "ozet": sonuc["ozet"]}, ensure_ascii=False, indent=1))
    for o, x in sonuc["ozet"].items():
        if x["durum"] in ("izle", "sapma"):
            print(f"::warning title=Kalibrasyon {x['durum']}::{o}: ortalama fark %{x['ort_fark_pct']}, son fark %{x['son_fark_pct']} ({x['n']} ölçüm)")
