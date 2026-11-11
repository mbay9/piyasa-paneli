"""Uçtan uca prova: 10 Kasım 2026 gecesinde yaşanan üç hatayı, ağ olmadan, gerçek akışın kendi fonksiyonlarıyla yeniden oynatır.
Parça testleri tek tek geçerken hatalar parçaların birleştiği yerde çıkmıştı; bu test o birleşimi sınar."""
import datetime as dt
import json
import os
import tempfile

import pandas as pd

import update as U


def seri(son_gun, n=320, bas=100.0, adim=0.1, atla=(), her_gun=False):
    gunler = [g for g in (pd.date_range if her_gun else pd.bdate_range)(end=son_gun, periods=n + len(atla)) if g.strftime("%Y-%m-%d") not in atla][-n:]
    return pd.DataFrame({"Close": [bas + i * adim for i in range(len(gunler))], "Volume": [1e6] * len(gunler)}, index=gunler)


class Yanit:
    def __init__(self, text):
        self.text = text


def t_gece_akisi():
    """Makro akış: Asya seans içi mumu + Yahoo'nun atladığı gün + ABD ETF'lerinde boş kapanış -> yayın koşulları sağlanmalı."""
    now = dt.datetime(2026, 11, 10, 1, 20, tzinfo=dt.timezone.utc)
    fr = {
        "^GSPC": seri("2026-11-09", bas=6800), "^IXIC": seri("2026-11-09", bas=24000),
        "SPY": seri("2026-11-06", bas=680), "ONEQ": seri("2026-11-06", bas=95),          # 9 Kasım kapanışı boş geldi, yfinance mumu attı
        "^KS11": seri("2026-11-10", bas=5000, atla=("2026-11-09",)),                     # 9 Kasım yok, 10 Kasım seans içi
        "^N225": seri("2026-11-10", bas=57000, atla=("2026-11-09",)),
        "BTC-USD": seri("2026-11-10", bas=70000, atla=("2026-11-09",), her_gun=True),              # 7/24: hafta sonu da var
    }
    asya_onceki = {s: float(fr[s]["Close"].iloc[-2]) for s in ("^KS11", "^N225")}
    btc_onceki = float(fr["BTC-USD"]["Close"].iloc[-2])
    gercek_http = U.http_get
    U.http_get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ağ yok"))   # Yahoo yamaları ağa çıkamaz: sessizce geçmeli
    try:
        U.drop_open_asia(fr, now)
        assert str(fr["^KS11"].index[-1].date()) == "2026-11-06", "seans içi Asya mumu atılmadı"
        U.patch_asia_close(fr)
        U.patch_btc_close(fr, now)
        kaynak = {"KOSPI": {"2026-11-06": asya_onceki["^KS11"], "2026-11-09": 5018.85, "2026-11-10": 5220.0},
                  "NIKKEI": {"2026-11-06": asya_onceki["^N225"], "2026-11-09": 57900.0},
                  "BTC": {"2026-11-08": btc_onceki * 1.002, "2026-11-09": 75259.28}}
        ik = U.ikinci_kaynak(fr, now, getir=lambda ad, b: kaynak.get(ad, {}))
    finally:
        U.http_get = gercek_http
    assert str(fr["^KS11"].index[-1].date()) == "2026-11-09" and fr["^KS11"]["Close"].iloc[-1] == 5018.85, "KOSPI eksik günü dolmadı"
    assert str(fr["^N225"].index[-1].date()) == "2026-11-09"
    assert "2026-11-09" in [str(d.date()) for d in fr["BTC-USD"].index], "BTC eksik günü dolmadı"
    assert not [x for x in ik if x["status"] == "bad"], ik
    ref = fr["^GSPC"].index[-1].strftime("%Y-%m-%d")
    assert ref == "2026-11-09"
    once = U.verify_proxies(fr, ref)
    assert all(x["status"] != "ok" for x in once), "ETF mumu eksikken çapraz kontrol geçmemeli (koruma)"
    gercek = U.us_kapanis_yamasi
    son = {s: float(fr[s]["Close"].iloc[-1]) for s in ("SPY", "ONEQ")}
    oran = {"SPY": fr["^GSPC"]["Close"].iloc[-1] / fr["^GSPC"]["Close"].iloc[-2], "ONEQ": fr["^IXIC"]["Close"].iloc[-1] / fr["^IXIC"]["Close"].iloc[-2]}
    U.us_kapanis_yamasi = lambda sym, r: (son[sym] * oran[sym], 5e6)
    try:
        assert U.patch_us_close(fr, ref, "prova") == 2
    finally:
        U.us_kapanis_yamasi = gercek
    sonra = U.verify_proxies(fr, ref)
    assert all(x["status"] == "ok" for x in sonra), sonra


def t_kismi_yenileme_geri_almaz():
    """Kısmi yenileme: site (CDN) 3 gün eski kopyayı verse bile veri dalındaki yeni kopya temel alınır; yayın geri gitmez."""
    def veri(gen, ref, btc_gun):
        return {"meta": {"generated_at": gen, "ref_date": ref}, "isaret": gen,
                "indexes": {"BTC": {"date": btc_gun, "close": 1.0}, "SPX": {"date": ref, "close": 2.0}}}
    eski = veri("2026-11-07T00:12:29Z", "2026-11-06", "2026-11-05")
    yeni = veri("2026-11-10T00:45:14Z", "2026-11-09", "2026-11-08")
    bugun = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    d0 = os.getcwd()
    tmp = tempfile.mkdtemp()
    yol = os.path.join(tmp, "veri.json")
    json.dump(yeni, open(yol, "w"))
    saklanan = (U.http_get, U.download, os.environ.get("VERI_DATA_FILE"))
    U.http_get = lambda url, **k: Yanit(json.dumps(eski)) if "data.json" in url else (_ for _ in ()).throw(RuntimeError("ağ yok"))
    U.download = lambda syms, **k: ({"BTC-USD": seri(bugun, bas=70000, her_gun=True), "^GSPC": seri(bugun, bas=6800)}, [])
    os.environ["VERI_DATA_FILE"] = yol
    import ikinci
    g0 = ikinci.getir
    ikinci.getir = lambda ad, b=None: {}
    try:
        os.chdir(tmp)
        U.partial_refresh(["BTC"])
        out = json.load(open("data.json"))
    finally:
        os.chdir(d0)
        U.http_get, U.download = saklanan[0], saklanan[1]
        ikinci.getir = g0
        if saklanan[2] is None:
            os.environ.pop("VERI_DATA_FILE", None)
        else:
            os.environ["VERI_DATA_FILE"] = saklanan[2]
    assert out["meta"]["ref_date"] == "2026-11-09" and out["isaret"] == "2026-11-10T00:45:14Z", "kısmi yenileme eski kopyayı geri yazdı"
    assert out["indexes"]["SPX"]["date"] == "2026-11-09" and out["indexes"]["BTC"]["date"] > "2026-11-08"
    assert out["meta"]["partial_refreshed"] == ["BTC"]


t_gece_akisi(); t_kismi_yenileme_geri_almaz(); print("test_prova: tamam")
