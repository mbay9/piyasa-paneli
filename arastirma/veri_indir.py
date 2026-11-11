#!/usr/bin/env python3
"""Uzun geçmiş verileri indirir ve CSV olarak yazar. Ulaşılamayan kaynak raporlanır, uydurulmaz."""
import io, json, os, sys, time, zipfile, traceback
import pandas as pd
import requests

OUT = sys.argv[1] if len(sys.argv) > 1 else "veri"
os.makedirs(OUT, exist_ok=True)
DURUM = {}
UA = {"User-Agent": "Mozilla/5.0 (research; piyasa-paneli)"}


def kayit(ad, ok, ayr=""):
    DURUM[ad] = {"ok": ok, "ayrinti": str(ayr)[:300]}
    print(("OK  " if ok else "FAIL"), ad, str(ayr)[:200], flush=True)


def get(url, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
            err = r.status_code
        except Exception as e:  # noqa
            err = repr(e)
        time.sleep(2 + i * 3)
    raise RuntimeError(f"{url} -> {err}")


# ---- Yahoo
def yahoo():
    import yfinance as yf
    for sym in ["^GSPC", "^VIX", "^VIX3M", "^TNX", "^IRX", "^FVX", "SPY", "RSP",
                "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC", "QQQ", "IWM", "^NDX", "^RUT"]:
        try:
            d = yf.download(sym, period="max", interval="1d", auto_adjust=False, progress=False, threads=False)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = [c[0] for c in d.columns]
            d = d.dropna(how="all")
            if len(d) < 50:
                raise RuntimeError(f"{len(d)} satır")
            d.index.name = "date"
            d.to_csv(f"{OUT}/yahoo_{sym.replace('^', '')}.csv")
            kayit("yahoo " + sym, True, f"{d.index[0].date()}..{d.index[-1].date()} n={len(d)}")
        except Exception as e:
            kayit("yahoo " + sym, False, e)


# ---- FRED
def fred():
    for sid in ["T10Y3M", "T10Y2Y", "USREC", "USRECD", "BAA10Y", "BAMLH0A0HYM2", "DGS10", "DGS3MO", "BAA", "AAA", "GS10", "TB3MS", "VIXCLS", "UNRATE"]:
        try:
            r = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
            df = pd.read_csv(io.StringIO(r.text))
            df.to_csv(f"{OUT}/fred_{sid}.csv", index=False)
            kayit("fred " + sid, True, f"{df.iloc[0,0]}..{df.iloc[-1,0]} n={len(df)}")
        except Exception as e:
            kayit("fred " + sid, False, e)


# ---- Ken French
FR = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRENCH = ["F-F_Research_Data_Factors_CSV", "F-F_Research_Data_Factors_daily_CSV", "F-F_Momentum_Factor_CSV",
          "F-F_Momentum_Factor_daily_CSV", "F-F_Research_Data_5_Factors_2x3_CSV", "F-F_Research_Data_5_Factors_2x3_daily_CSV",
          "49_Industry_Portfolios_CSV", "10_Portfolios_Prior_12_2_CSV", "Portfolios_Formed_on_ME_CSV",
          "F-F_ST_Reversal_Factor_CSV", "F-F_LT_Reversal_Factor_CSV"]


def french():
    for n in FRENCH:
        try:
            r = get(FR + n + ".zip")
            z = zipfile.ZipFile(io.BytesIO(r.content))
            nm = z.namelist()[0]
            open(f"{OUT}/french_{n}.txt", "wb").write(z.read(nm))
            kayit("french " + n, True, f"{nm} {len(z.read(nm))} bayt")
        except Exception as e:
            kayit("french " + n, False, e)


# ---- Shiller, Baker-Wurgler
def digerleri():
    urls = {
        "shiller_ie_data.xls": ["http://www.econ.yale.edu/~shiller/data/ie_data.xls",
                                "https://img1.wsimg.com/blobby/go/e5e77e9f-e038-4cd3-9e9f-4cc0e1ae2d1a/downloads/ie_data.xls"],
        "bw_sentiment.xlsx": ["https://people.stern.nyu.edu/jwurgler/data/Investor_Sentiment_Data_20190327_POST.xlsx",
                              "https://pages.stern.nyu.edu/~jwurgler/data/Investor_Sentiment_Data_20190327_POST.xlsx"],
        "aaii_sentiment.xls": ["https://www.aaii.com/files/surveys/sentiment.xls"],
    }
    for fn, us in urls.items():
        ok = False
        for u in us:
            try:
                r = get(u)
                open(f"{OUT}/{fn}", "wb").write(r.content)
                kayit(fn, True, f"{u} {len(r.content)} bayt")
                ok = True
                break
            except Exception as e:
                last = e
        if not ok:
            kayit(fn, False, last)


if __name__ == "__main__":
    for f in (yahoo, fred, french, digerleri):
        try:
            f()
        except Exception:
            traceback.print_exc()
    json.dump(DURUM, open(f"{OUT}/_durum.json", "w"), ensure_ascii=False, indent=1)
