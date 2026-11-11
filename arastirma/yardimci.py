"""Veri yükleme ve istatistik yardımcıları (arastirma testleri için)."""
import io, os, re
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

VERI = os.environ.get("VERI", "veri")


def yol(n):
    return os.path.join(VERI, n)


def var(n):
    return os.path.exists(yol(n))


# ---------------- yükleyiciler
def yahoo(sym, col="Adj Close"):
    df = pd.read_csv(yol(f"yahoo_{sym.replace('^','')}.csv"), index_col=0, parse_dates=True)
    c = col if col in df.columns else "Close"
    return df[c].astype(float).dropna().rename(sym)


def fred(sid):
    df = pd.read_csv(yol(f"fred_{sid}.csv"))
    df.columns = ["date", sid]
    df["date"] = pd.to_datetime(df["date"])
    s = pd.to_numeric(df[sid], errors="coerce")
    return pd.Series(s.values, index=df["date"], name=sid).dropna()


def french_bloklar(ad):
    """French CSV dosyasındaki tüm sayısal blokları (başlık, DataFrame) olarak döndürür; değerler yüzde."""
    txt = open(yol(f"french_{ad}.txt"), encoding="latin-1").read().splitlines()
    bloklar, cur, hdr, last_text = [], [], None, ""
    for ln in txt + [""]:
        parts = [p.strip() for p in ln.split(",")]
        first = parts[0]
        if re.fullmatch(r"\d{6}|\d{8}|\d{4}", first) and len(parts) > 1 and all(re.fullmatch(r"-?\d+(\.\d+)?", p) or p == "" for p in parts[1:]):
            cur.append(parts)
        else:
            if cur:
                bloklar.append((last_text, hdr, cur))
                cur = []
            if ln.strip() and not re.fullmatch(r"\d.*", first):
                if len(parts) > 2 and parts[0] == "":
                    hdr = parts[1:]
                elif len(parts) <= 2 or not any(parts[1:]):
                    last_text = ln.strip()
    out = []
    for text, h, rows in bloklar:
        n = len(rows[0]) - 1
        cols = h if h and len(h) == n else [f"c{i}" for i in range(n)]
        df = pd.DataFrame([[float(x) if x != "" else np.nan for x in r[1:]] for r in rows], columns=cols,
                          index=[r[0] for r in rows])
        df = df.replace([-99.99, -999], np.nan)
        out.append((text, df))
    return out


def french(ad, blok=0):
    t, df = french_bloklar(ad)[blok]
    idx = df.index
    if len(idx[0]) == 6:
        df.index = pd.PeriodIndex(idx, freq="M")
    elif len(idx[0]) == 8:
        df.index = pd.to_datetime(idx, format="%Y%m%d")
    else:
        df.index = pd.PeriodIndex(idx, freq="Y")
    return df / 100.0


# ---------------- istatistik
def hac(y, X, lags=None):
    """OLS + Newey-West. X sabit içermez, otomatik eklenir. (katsayı, t, n) döndürür."""
    d = pd.concat([y, X], axis=1).dropna()
    yy, XX = d.iloc[:, 0], sm.add_constant(d.iloc[:, 1:])
    L = lags if lags is not None else int(np.floor(4 * (len(d) / 100) ** (2 / 9)))
    m = sm.OLS(yy, XX).fit(cov_type="HAC", cov_kwds={"maxlags": max(L, 1)})
    return m


def sharpe(r, per=12):
    r = pd.Series(r).dropna()
    return np.nan if r.std() == 0 or len(r) < 3 else r.mean() / r.std() * np.sqrt(per)


def ann_ret(r, per=12):
    r = pd.Series(r).dropna()
    return (1 + r).prod() ** (per / len(r)) - 1 if len(r) else np.nan


def maxdd(r):
    r = pd.Series(r).dropna()
    w = (1 + r).cumprod()
    return float((w / w.cummax() - 1).min())


def ozet(r, per=12):
    r = pd.Series(r).dropna()
    return {"yillik_getiri": round(100 * ann_ret(r, per), 2), "yillik_oynaklik": round(100 * r.std() * np.sqrt(per), 2),
            "sharpe": round(sharpe(r, per), 3), "en_buyuk_dusus": round(100 * maxdd(r), 1), "n": int(len(r))}


def blok_bootstrap_fark(a, b, per, blok, n=5000, seed=7):
    """Sharpe(a) - Sharpe(b) farkının dairesel blok bootstrap p değeri (iki taraflı, sıfır hipotezine ortalanmış)."""
    d = pd.concat([a, b], axis=1).dropna().values
    T = len(d)
    rng = np.random.default_rng(seed)
    def fark(x):
        sa = x[:, 0].mean() / x[:, 0].std(); sb = x[:, 1].mean() / x[:, 1].std()
        return (sa - sb) * np.sqrt(per)
    obs = fark(d)
    nb = int(np.ceil(T / blok))
    sims = np.empty(n)
    for i in range(n):
        st = rng.integers(0, T, nb)
        idx = (st[:, None] + np.arange(blok)[None, :]).ravel()[:T] % T
        sims[i] = fark(d[idx])
    se = sims.std()
    p = 2 * (1 - stats.norm.cdf(abs(obs) / se)) if se > 0 else np.nan
    return float(obs), float(se), float(p)


def clark_west(y, f_model, f_bench):
    """Clark-West MSPE-düzeltmeli istatistik (tek taraflı p). Seriler aynı indeksli."""
    d = pd.concat([y, f_model, f_bench], axis=1).dropna()
    e1 = d.iloc[:, 0] - d.iloc[:, 2]
    e2 = d.iloc[:, 0] - d.iloc[:, 1]
    adj = e1 ** 2 - (e2 ** 2 - (d.iloc[:, 2] - d.iloc[:, 1]) ** 2)
    m = sm.OLS(adj.values, np.ones(len(adj))).fit(cov_type="HAC", cov_kwds={"maxlags": 12})
    oosr2 = 1 - (e2 ** 2).sum() / (e1 ** 2).sum()
    return float(oosr2), float(m.tvalues[0]), float(1 - stats.norm.cdf(m.tvalues[0]))


def yarilar(idx):
    """İndeksi iki eşit yarıya böler."""
    n = len(idx)
    return idx[: n // 2], idx[n // 2:]
