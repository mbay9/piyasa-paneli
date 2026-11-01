"""Endeks çarpanı: S&P 500 ve Nasdaq-100 için ileri 12 ay ve son 12 ay F/K.

Yöntem: endeks F/K = 1 / sum(ağırlık_i x EPS_i / fiyat_i) (toplam piyasa değeri / toplam kazanç, ağırlıklı harmonik ortalama).
Ağırlıklar: S&P 500 için SPDR SPY, Nasdaq-100 için Slickcharts (QQQ portföyü) listesi; alınamazsa piyasa değeri ağırlığı ("yaklaşık").
Kazanç verisi her hisse için bir önbellekte tutulur: haftalık, bilançosu geçince ertesi gün ve eksikse yeniden yenilenir; fiyat her gün.
"""
import datetime as dt
import io
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

IKINCI_SINIF = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}  # aynı şirketin ikinci payı: yalnız ağırlık yedeğinde çift sayılmasın
YENILEME_GUN = 7
HEDEF_KAPSAM = 95.0  # ağırlığın en az bu kadarı hesaba girmeli
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def f(v):
    try:
        v = float(v)
        return None if v != v or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ üyelik ve ağırlık
def _sym(t):
    t = str(t).strip().upper()
    return t.replace(".", "-")


def parse_spy(raw):
    """SPDR SPY xlsx (başlıksız okunmuş DataFrame) -> ({sembol: ağırlık %}, 'GG-Ay-YYYY' tarihi)."""
    import pandas as pd
    hd = next(i for i in range(20) if "Ticker" in [str(x).strip() for x in raw.iloc[i].tolist()])
    tarih = None
    for i in range(hd):
        satir = [str(x) for x in raw.iloc[i].tolist()]
        if satir and satir[0].startswith("Holdings"):
            tarih = satir[1].replace("As of", "").strip()
    df = raw.iloc[hd + 1:].copy()
    df.columns = [str(x).strip() for x in raw.iloc[hd].tolist()]
    df = df[df["Ticker"].notna() & df["Weight"].notna()]
    w = pd.to_numeric(df["Weight"], errors="coerce")
    out = {}
    for t, x in zip(df["Ticker"], w):
        t = _sym(t)
        if x == x and t not in ("-", "", "CASH", "USD") and not t.startswith("USD"):
            out[t] = float(x)
    return out, tarih


def parse_slick(html):
    import pandas as pd
    for t in pd.read_html(io.StringIO(html)):
        if any("Symbol" in str(c) for c in t.columns):
            wc = next(c for c in t.columns if "Weight" in str(c))
            w = pd.to_numeric(t[wc].astype(str).str.replace("%", "", regex=False), errors="coerce")
            return {_sym(s): float(x) for s, x in zip(t["Symbol"], w) if x == x}
    raise ValueError("Slickcharts tablosu bulunamadı")


def _http(url, **kw):
    import requests
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=(10, 40), **kw)
    r.raise_for_status()
    return r


def spx_agirlik():
    """-> ({sembol: ağırlık %}, tarih) veya (None, None)."""
    try:
        import pandas as pd
        r = _http("https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx")
        w, tarih = parse_spy(pd.read_excel(io.BytesIO(r.content), header=None))
        if 480 <= len(w) <= 520 and 99 <= sum(w.values()) <= 101:
            return w, tarih
    except Exception:  # noqa: BLE001
        pass
    return None, None


def ndx_resmi():
    """Nasdaq'ın kendi Nasdaq-100 listesi: ({sembol: piyasa değeri}, tarih) veya (None, None)."""
    try:
        j = _http("https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers={"Accept": "application/json", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}).json()
        rows = j["data"]["data"]["rows"]
        out = {}
        for x in rows:
            mc = f(str(x.get("marketCap", "")).replace(",", ""))
            out[_sym(x["symbol"])] = mc
        if 95 <= len(out) <= 110:
            return out, j["data"].get("date")
    except Exception:  # noqa: BLE001
        pass
    return None, None


def ndx_agirlik(resmi):
    """-> ({sembol: ağırlık %}, kaynak). Önce Slickcharts (QQQ portföyü) ve resmi listeyle uyumu; olmazsa piyasa değeri (yaklaşık)."""
    try:
        w = parse_slick(_http("https://www.slickcharts.com/nasdaq100").text)
        uyum = len(set(w) & set(resmi or w)) / max(len(w), 1)
        if 95 <= len(w) <= 110 and 99 <= sum(w.values()) <= 101 and uyum >= 0.95:
            return w, "slickcharts"
    except Exception:  # noqa: BLE001
        pass
    if resmi:
        mc = {s: v for s, v in resmi.items() if v and s not in IKINCI_SINIF}
        t = sum(mc.values())
        if t > 0:
            return {s: v / t * 100 for s, v in mc.items()}, "piyasa_degeri"
    return None, None


def spy_tarih(s):
    """'29-Oct-2026' -> date."""
    try:
        return dt.datetime.strptime(s, "%d-%b-%Y").date()
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ hisse başına kazanç önbelleği
# giriş alanları: t alım tarihi, cur fiyat parası, fcur rapor parası, eps0 bu mali yıl, eps1 gelecek yıl, fye mali yıl sonu (epoch),
# ttm son 4 çeyrek EPS (analist tabanı), gaap Yahoo son 12 ay EPS, nt sonraki bilanço (epoch), mc piyasa değeri ve p alım günkü fiyat (ağırlık yedeği için)


def getir(sym, tries=3):
    import yfinance as yf
    son = None
    for i in range(tries):
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            ee = t.earnings_estimate
            e0 = f(ee.loc["0y", "avg"]) if "0y" in ee.index else None
            e1 = f(ee.loc["+1y", "avg"]) if "+1y" in ee.index else None
            ttm = None
            try:
                v = [f(x) for x in t.earnings_history["epsActual"].tolist()]
                if len(v) >= 4 and all(x is not None for x in v[-4:]):
                    ttm = round(sum(v[-4:]), 4)
            except Exception:  # noqa: BLE001
                pass
            if info.get("currency") is None and e0 is None and e1 is None:
                raise ValueError("boş yanıt")
            return {"cur": info.get("currency"), "fcur": info.get("financialCurrency"), "eps0": e0, "eps1": e1, "fye": info.get("nextFiscalYearEnd"),
                    "ttm": ttm, "gaap": f(info.get("trailingEps")), "nt": info.get("earningsTimestamp"),
                    "mc": f(info.get("marketCap")), "p": f(info.get("currentPrice") or info.get("regularMarketPrice"))}
        except Exception as e:  # noqa: BLE001
            son = repr(e)[:80]
            time.sleep(2 + 3 * i)
    return {"hata": son}


def yenilenecekler(onbellek, semboller, bugun, enfazla=600):
    """Hangi hisselerin kazanç verisi yenilenmeli, sırayla: hiç yok > bilançosu geçti > en eski (haftalık)."""
    bugun_s = bugun.isoformat()
    yok, olay, eski = [], [], []
    for s in semboller:
        e = onbellek.get(s)
        if not e:
            yok.append((0, s))
            continue
        t = e.get("t") or "0000-00-00"
        yas = (bugun - dt.date.fromisoformat(t)).days
        nt = e.get("nt")
        if nt:
            nd = dt.date.fromtimestamp(nt)
            if nd < bugun and t <= nd.isoformat():  # bilanço tarihi, son alımdan sonra geçti
                olay.append((yas, s))
                continue
        if yas >= YENILEME_GUN or e.get("hata"):
            eski.append((-yas, s))
    sira = [s for _, s in sorted(yok)] + [s for _, s in sorted(olay, reverse=True)] + [s for _, s in sorted(eski)]
    return sira[:enfazla], {"yok": len(yok), "bilanco": len(olay), "haftalik": len(eski)}


def yenile(onbellek, semboller, bugun, butce=420, isci=4, log=print):
    """Önbelleği günceller (yerinde). Alınamayan hissenin eski verisi kalır. -> özet."""
    sira, neden = yenilenecekler(onbellek, semboller, bugun)
    t0 = time.time()
    basarili, basarisiz = 0, []
    if sira:
        def is_(s):
            return s, (getir(s) if time.time() - t0 < butce else {"hata": "süre doldu"})
        with ThreadPoolExecutor(max_workers=isci) as ex:
            for s, r in ex.map(is_, sira):
                if r.get("hata"):
                    basarisiz.append(s)
                    if s in onbellek:
                        onbellek[s]["hata"] = r["hata"]
                    continue
                r["t"] = bugun.isoformat()
                onbellek[s] = r
                basarili += 1
    if basarisiz and time.time() - t0 < butce - 60:  # istek sınırına takılanlar için ikinci tur: biraz bekle, az işçiyle
        time.sleep(20)
        ikinci = list(basarisiz)
        basarisiz = []
        with ThreadPoolExecutor(max_workers=2) as ex:
            for s, r in ex.map(lambda x: (x, getir(x)), ikinci):
                if r.get("hata"):
                    basarisiz.append(s)
                    continue
                r["t"] = bugun.isoformat()
                onbellek[s] = r
                basarili += 1
    log(f"endeks önbelleği: {len(sira)} hisse denendi ({neden}), {basarili} yenilendi, {len(basarisiz)} alınamadı, {int(time.time() - t0)} sn")
    return {"denenen": len(sira), "neden": neden, "yenilenen": basarili, "alinamayan": basarisiz[:30]}


def paketle(onbellek):
    """data.json için: her hisse tek satırlık metin (dosya şişmesin)."""
    return {s: json.dumps({k: v for k, v in e.items() if v is not None}, separators=(",", ":")) for s, e in sorted(onbellek.items())}


def ac(paket):
    out = {}
    for s, v in (paket or {}).items():
        try:
            out[s] = json.loads(v)
        except Exception:  # noqa: BLE001
            continue
    return out


# ------------------------------------------------------------------ hesap
def ntm(e, bugun):
    """İleri 12 ay EPS: bu mali yıl ve gelecek yıl tahmininin, mali yıl sonuna kalan süreye göre zaman ağırlıklı karışımı. -> (eps, w, mali_yil_gecti_mi)"""
    e0, e1, fye = e.get("eps0"), e.get("eps1"), e.get("fye")
    if e0 is None or e1 is None or not fye:
        return None, None, False
    kalan = (dt.date.fromtimestamp(fye) - bugun).days
    w = min(max(kalan / 365.0, 0.0), 1.0)
    return w * e0 + (1 - w) * e1, w, kalan < 0


def para_ok(e):
    return bool(e.get("cur")) and e.get("cur") == e.get("fcur")


def olcu(satirlar, fn):
    """satirlar: [(sembol, w, fiyat, eps_kaydı)]; fn(kayıt)->EPS. Toplam yöntemi: zarar dahil ve zarar hariç."""
    ok = [(w, p, fn(e)) for s, w, p, e in satirlar if p and para_ok(e) and fn(e) is not None]
    if not ok:
        return None
    tw = sum(w for w, _, _ in ok)
    ey = sum(w * x / p for w, p, x in ok) / tw
    pos = [(w, p, x) for w, p, x in ok if x > 0]
    pw = sum(w for w, _, _ in pos)
    ey_p = sum(w * x / p for w, p, x in pos) / pw if pw else None
    return {"pe": round(1 / ey, 2) if ey > 0 else None, "pe_zh": round(1 / ey_p, 2) if ey_p else None, "n": len(ok), "zarar": len(ok) - len(pos),
            "kapsam": tw, "ey": ey}


def hesapla(uyeler, fiyat, onbellek, bugun):
    """uyeler: {sembol: ağırlık (toplamı 1)}; fiyat: {sembol: kapanış}. -> endeks bloğu."""
    satirlar = [(s, w, fiyat.get(s), onbellek.get(s) or {}) for s, w in uyeler.items()]
    tum = sum(w for _, w, _, _ in satirlar) or 1.0
    satirlar = [(s, w / tum, p, e) for s, w, p, e in satirlar]
    gecti = sum(1 for _, _, _, e in satirlar if ntm(e, bugun)[2])
    o = {}
    for ad, fn in (("ileri", lambda e: ntm(e, bugun)[0]), ("fy1", lambda e: e.get("eps0")), ("fy2", lambda e: e.get("eps1")), ("son", lambda e: e.get("ttm")), ("gaap", lambda e: e.get("gaap"))):
        m = olcu(satirlar, fn)
        if m:
            m["kapsam"] = round(m["kapsam"] * 100, 1)
            o[ad] = m
    ay = olcu(satirlar, lambda e: ntm(e, bugun)[0])
    ttm = olcu([x for x in satirlar if ntm(x[3], bugun)[0] is not None and x[3].get("ttm") is not None], lambda e: ntm(e, bugun)[0])
    ttm0 = olcu([x for x in satirlar if ntm(x[3], bugun)[0] is not None and x[3].get("ttm") is not None], lambda e: e.get("ttm"))
    if ttm and ttm0 and ttm0["ey"] > 0:
        o["buyume"] = round((ttm["ey"] / ttm0["ey"] - 1) * 100, 1)
    pay = sorted(((w * ntm(e, bugun)[0] / p, s) for s, w, p, e in satirlar if p and para_ok(e) and ntm(e, bugun)[0] is not None), reverse=True)
    top = sum(x for x, _ in pay)
    if top > 0:
        o["ilk"] = [[s, round(x / top * 100, 1)] for x, s in pay[:5]]
    o["uye"] = len(satirlar)
    o["verisiz"] = sorted(s for s, w, p, e in satirlar if not (p and para_ok(e) and ntm(e, bugun)[0] is not None))[:25]
    o["mali_yil_gecti"] = gecti
    if ay is None:
        return None
    return o


def rolla(w, fiyat_ref, fiyat_hold):
    """Ağırlıkları tutuş tarihinden referans tarihe fiyat getirisiyle ilerletir (toplamı 1)."""
    a = {s: x * (fiyat_ref[s] / fiyat_hold[s]) if fiyat_ref.get(s) and fiyat_hold.get(s) else x for s, x in w.items()}
    t = sum(a.values())
    return {s: x / t for s, x in a.items()}


def yedek_agirlik(semboller, onbellek, fiyat):
    """Ağırlık kaynağı yoksa: piyasa değeri ağırlığı (alım günkü değer x fiyat değişimi; ikinci paylar bir kez)."""
    mc = {}
    for s in semboller:
        e = onbellek.get(s) or {}
        if s in IKINCI_SINIF or not (e.get("mc") and e.get("p") and fiyat.get(s)) or e.get("cur") != "USD":
            continue
        mc[s] = e["mc"] * fiyat[s] / e["p"]
    t = sum(mc.values())
    return {s: v / t for s, v in mc.items()} if t else {}
