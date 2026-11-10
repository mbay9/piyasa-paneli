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

t_yeni_olan(); t_asya(); print("test_guncel: tamam")
