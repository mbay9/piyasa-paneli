import datetime as dt
import pandas as pd
import update as U

def t_yeni_olan():
    eski = {"meta": {"generated_at": "2026-11-07T00:12:29Z", "ref_date": "2026-11-06"}}
    yeni = {"meta": {"generated_at": "2026-11-10T00:45:14Z", "ref_date": "2026-11-09"}}
    assert U.yeni_olan(eski, yeni) is yeni      # site eski (CDN), veri dalı yeni: yeni kullanılır
    assert U.yeni_olan(yeni, eski) is yeni
    assert U.yeni_olan(None, eski) is eski and U.yeni_olan(eski, None) is eski
    try:
        U.yeni_olan(None, None); assert False
    except RuntimeError:
        pass

def t_asya():
    f = lambda son: pd.DataFrame({"Close": [1.0, 2.0], "Volume": [1.0, 1.0]}, index=[pd.Timestamp("2026-11-09"), pd.Timestamp(son)])
    fr = {"^KS11": f("2026-11-10"), "^N225": f("2026-11-10")}
    U.drop_open_asia(fr, dt.datetime(2026, 11, 10, 0, 51, tzinfo=dt.timezone.utc))   # seans sürüyor: bugünün mumu atılır
    assert str(fr["^KS11"].index[-1].date()) == "2026-11-09" and len(fr["^N225"]) == 1
    fr = {"^KS11": f("2026-11-10")}
    U.drop_open_asia(fr, dt.datetime(2026, 11, 10, 6, 45, tzinfo=dt.timezone.utc))   # kapanıştan sonra: kalır
    assert len(fr["^KS11"]) == 2
    fr = {"^KS11": f("2026-11-10")}
    U.drop_open_asia(fr, dt.datetime(2026, 11, 10, 20, 33, tzinfo=dt.timezone.utc))
    assert len(fr["^KS11"]) == 2

def t_us():
    ny = U.ZoneInfo("America/New_York")
    ts = lambda g, h, m: int(dt.datetime(2026, 11, g, h, m, tzinfo=ny).timestamp())
    j = lambda close, rmt, gun=9: {"timestamp": [ts(6, 9, 30), ts(gun, 9, 30)], "indicators": {"quote": [{"close": [735.29, close], "open": [734.8, 741.95], "volume": [1, 5]}]},
                                    "meta": {"regularMarketPrice": 752.69, "regularMarketTime": rmt}}
    assert U.us_kapanis_coz(j(None, ts(9, 16, 0)), "2026-11-09") == (752.69, 5.0)   # kapanış boş, son fiyat kapanışta: eklenir
    assert U.us_kapanis_coz(j(None, ts(9, 15, 59)), "2026-11-09") is None            # seans bitmeden: eklenmez
    assert U.us_kapanis_coz(j(751.0, ts(9, 16, 0)), "2026-11-09") is None            # kapanış dolu: dokunulmaz
    assert U.us_kapanis_coz(j(None, ts(9, 16, 0)), "2026-11-10") is None             # mum başka güne ait: eklenmez
    assert U._us_sembol("SPY") and U._us_sembol("NVDA") and not U._us_sembol("^GSPC") and not U._us_sembol("005930.KS") and not U._us_sembol("BTC-USD") and not U._us_sembol("EURUSD=X")
    f = pd.DataFrame({"Close": [1.0], "Volume": [1.0]}, index=[pd.Timestamp("2026-11-09")])
    assert U.patch_us_close({"SPY": f, "^GSPC": f}, "2026-11-09") == 0               # eksik yoksa ağa çıkılmaz

t_yeni_olan(); t_asya(); t_us(); print("test_guncel: tamam")
