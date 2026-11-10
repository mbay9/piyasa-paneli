import datetime as dt
import pandas as pd
import ikinci as I
import update as U

def t_coz():
    assert I.nikkei_coz('Date of Data,Close,Open\n"2026/11/06","50100.50","1","2","3"\n"2026/11/09","50200.25","1","2","3"\nfooter') == {"2026-11-06": 50100.5, "2026-11-09": 50200.25}
    assert I.kospi_coz([{"localTradedAt": "2026-11-09", "closePrice": "5,018.85"}, {"localTradedAt": None, "closePrice": "1"}]) == {"2026-11-09": 5018.85}
    j = {"data": {"tradesTable": {"rows": [{"date": "11/06/2026", "close": "$735.29"}, {"date": "11/05/2026", "close": "24,315.00"}, {"date": "x", "close": "1"}]}}}
    assert I.nasdaq_coz(j) == {"2026-11-06": 735.29, "2026-11-05": 24315.0} and I.nasdaq_coz(None) == {}
    assert I.coinbase_coz([[1794182400, 73636, 75500, 74756.52, 75259.28, 1.0]]) == {"2026-11-09": 75259.28}

def t_kapanmis():
    k = {"2026-11-09": 1.0, "2026-11-10": 2.0, "2026-11-11": 3.0}
    assert list(I.kapanmis(k, dt.datetime(2026, 11, 10, 1, 0, tzinfo=dt.timezone.utc), asya=True)) == ["2026-11-09"]      # seans sürüyor
    assert list(I.kapanmis(k, dt.datetime(2026, 11, 10, 7, 0, tzinfo=dt.timezone.utc), asya=True)) == ["2026-11-09", "2026-11-10"]
    assert list(I.kapanmis(k, dt.datetime(2026, 11, 10, 23, 0, tzinfo=dt.timezone.utc), btc=True)) == ["2026-11-09"]       # BTC: bugün bitmedi

def t_karsilastir():
    r = I.karsilastir("X", "k", {"2026-11-06": 100.0, "2026-11-09": 101.0}, {"2026-11-06": 100.02}, 0.05)
    assert r["status"] == "ok" and r["date"] == "2026-11-06"
    assert I.karsilastir("X", "k", {"2026-11-06": 100.0}, {"2026-11-06": 101.0}, 0.05)["status"] == "bad"
    assert I.karsilastir("X", "k", {"2026-11-06": 100.0}, {}, 0.05)["status"] == "unavailable"
    assert I.eksikler(["2026-11-05", "2026-11-06", "2026-11-10"], {"2026-11-06": 1, "2026-11-09": 2, "2026-10-01": 3}) == ["2026-11-09"]

def t_doldur():
    f = lambda gunler, v: pd.DataFrame({"Close": v, "Volume": [1.0] * len(v)}, index=[pd.Timestamp(g) for g in gunler])
    now = dt.datetime(2026, 11, 10, 1, 20, tzinfo=dt.timezone.utc)
    # KOSPI: Yahoo 9 Kasım'ı vermiyor (10 Kas 2026'da yaşandı); kaynak 6 Kasım'da Yahoo ile uyumlu -> 9 Kasım eklenir, bitmemiş 10 Kasım eklenmez
    fr = {"^KS11": f(["2026-11-05", "2026-11-06"], [5383.8, 5059.69])}
    kay = {"KOSPI": {"2026-11-10": 5220.6, "2026-11-09": 5018.85, "2026-11-06": 5059.69, "2026-11-05": 5383.80}}
    out = U.ikinci_kaynak(fr, now, getir=lambda ad, b: kay.get(ad, {}))
    assert [str(d.date()) for d in fr["^KS11"].index] == ["2026-11-05", "2026-11-06", "2026-11-09"] and fr["^KS11"]["Close"].iloc[-1] == 5018.85
    assert out[0]["status"] == "ok" and out[0]["filled"] == ["2026-11-09"]
    # kaynak Yahoo ile uyuşmuyorsa doldurulmaz
    fr = {"^KS11": f(["2026-11-05", "2026-11-06"], [5383.8, 5059.69])}
    kay = {"KOSPI": {"2026-11-09": 5018.85, "2026-11-06": 5200.0}}
    out = U.ikinci_kaynak(fr, now, getir=lambda ad, b: kay.get(ad, {}))
    assert len(fr["^KS11"]) == 2 and out[0]["status"] == "bad"
    # kaynak okunamazsa hiçbir şey değişmez; ABD ETF'inde doldurma yapılmaz (yalnız karşılaştırma)
    fr = {"SPY": f(["2026-11-05", "2026-11-06"], [733.0, 735.29])}
    out = U.ikinci_kaynak(fr, now, getir=lambda ad, b: {"2026-11-06": 735.29, "2026-11-09": 752.6} if ad == "SPY" else {})
    assert len(fr["SPY"]) == 2 and out[0]["status"] == "ok" and "filled" not in out[0]
    out = U.ikinci_kaynak({"SPY": f(["2026-11-06"], [735.29])}, now, getir=lambda ad, b: {})
    assert out[0]["status"] == "unavailable"

t_coz(); t_kapanmis(); t_karsilastir(); t_doldur(); print("test_ikinci: tamam")
