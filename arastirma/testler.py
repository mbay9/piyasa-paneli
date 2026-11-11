#!/usr/bin/env python3
"""Gösterge sınamaları. Protokol: arastirma/PROTOKOL.md. Çıktı: sonuc.json (+ konsola özet)."""
import json, sys, traceback, warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from yardimci import *

warnings.filterwarnings("ignore")
SONUC = {}
MALIYET = 0.001  # her pozisyon değişiminde 10 baz puan


def kaydet(ad, d):
    SONUC[ad] = d
    print("==", ad, json.dumps(d, ensure_ascii=False, default=str)[:1500], flush=True)


def hata(ad, e):
    SONUC[ad] = {"hata": repr(e)}
    print("!!", ad, repr(e), flush=True)
    traceback.print_exc()


def dilimler(idx, yayin):
    """Tüm dönem, iki yarı, yayın sonrası maskeleri."""
    a, b = yarilar(idx)
    out = {"tum": idx, "ilk_yari": a, "son_yari": b}
    if yayin is not None:
        out["yayin_sonrasi"] = idx[idx >= yayin]
    return out


def strateji_degerlendir(rs, rb, per, blok, yayin, ad):
    """rs: strateji getirisi (maliyet dahil), rb: al-tut. Hem risk azaltma hem Sharpe hükmü için sayılar."""
    d = pd.concat([rs, rb], axis=1).dropna()
    d.columns = ["s", "b"]
    out = {"strateji": ozet(d["s"], per), "al_tut": ozet(d["b"], per)}
    fark, se, p = blok_bootstrap_fark(d["s"], d["b"], per, blok)
    out["sharpe_fark"] = {"fark": round(fark, 3), "se": round(se, 3), "p": round(p, 4)}
    # oynaklık oranı için bootstrap güven aralığı
    rng = np.random.default_rng(11)
    T = len(d); nb = int(np.ceil(T / blok)); oran = []
    v = d.values
    for _ in range(2000):
        st = rng.integers(0, T, nb)
        idx = (st[:, None] + np.arange(blok)[None, :]).ravel()[:T] % T
        x = v[idx]
        oran.append(x[:, 0].std() / x[:, 1].std())
    out["oynaklik_orani"] = {"nokta": round(float(d["s"].std() / d["b"].std()), 3), "ci95": [round(float(np.percentile(oran, 2.5)), 3), round(float(np.percentile(oran, 97.5)), 3)]}
    dl = dilimler(d.index, yayin)
    alt = {}
    for k, ix in dl.items():
        if len(ix) > 24:
            x = d.loc[ix]
            alt[k] = {"s_sharpe": round(sharpe(x["s"], per), 3), "b_sharpe": round(sharpe(x["b"], per), 3),
                      "s_dd": round(100 * maxdd(x["s"]), 1), "b_dd": round(100 * maxdd(x["b"]), 1), "n": int(len(x))}
    out["alt_donem"] = alt
    return out


def hukum_strateji(o):
    """Protokol: risk azaltma ve Sharpe için ayrı hüküm."""
    ci = o["oynaklik_orani"]["ci95"]
    dd_iyi = o["strateji"]["en_buyuk_dusus"] > o["al_tut"]["en_buyuk_dusus"] + 5  # dd negatif; daha az negatif = iyi
    risk = "GEÇTİ" if (ci[1] < 1 and dd_iyi) else ("KISMEN" if (ci[1] < 1 or dd_iyi) else "GEÇMEDİ")
    k1 = o["sharpe_fark"]["p"] < 0.01 and o["sharpe_fark"]["fark"] > 0
    k2 = all(v["s_sharpe"] > v["b_sharpe"] for k, v in o["alt_donem"].items() if k in ("ilk_yari", "son_yari"))
    yay = o["alt_donem"].get("yayin_sonrasi")
    k2b = True if yay is None else yay["s_sharpe"] > yay["b_sharpe"]
    if k1 and k2 and k2b:
        sh = "GEÇTİ"
    elif (o["sharpe_fark"]["fark"] > 0) and (k2 or k2b):
        sh = "KISMEN"
    else:
        sh = "GEÇMEDİ"
    return {"risk_azaltma": risk, "sharpe_getiri": sh}


# ---------------------------------------------------------------- T01 hareketli ortalama (aylık, French toplam getiri)
def t01_trend_aylik():
    ff = french("F-F_Research_Data_Factors_CSV")
    rf = ff["RF"]; mk = ff["Mkt-RF"] + rf
    lvl = (1 + mk).cumprod()
    out = {}
    for n in (6, 8, 10, 12):
        sma = lvl.rolling(n).mean()
        sig = (lvl > sma).astype(float).shift(1)  # t-1 ayı sonu bilgisi, t ayı pozisyonu
        sw = sig.diff().abs().fillna(0)
        rs = sig * mk + (1 - sig) * rf - sw * MALIYET
        rs = rs[sma.shift(1).notna()]
        o = strateji_degerlendir(rs, mk.loc[rs.index], 12, 12, pd.Period("2007-01", "M"), f"SMA{n}")
        o["piyasada_kalma_orani"] = round(float(sig.loc[rs.index].mean()), 3)
        o["ayda_gecis"] = round(float(sw.loc[rs.index].mean()), 3)
        o["hukum"] = hukum_strateji(o)
        out[f"{n}_ay"] = o
    kaydet("T01_trend_aylik_frenchTR", out)


# ---------------------------------------------------------------- T02 sitenin rejim kuralı (günlük, French günlük toplam getiri)
def t02_site_rejimi():
    fd = french("F-F_Research_Data_Factors_daily_CSV")
    rf = fd["RF"]; mk = fd["Mkt-RF"] + rf
    lvl = (1 + mk).cumprod()
    ma = lvl.rolling(200).mean()
    out = {}
    for band, conf, ad in ((0.015, 2, "site_kurali_bant1.5_onay2"), (0.0, 1, "sade_SMA200"), (0.0, 2, "sade_SMA200_onay2")):
        on, up, dn, pos = None, 0, 0, []
        for c, m in zip(lvl.values, ma.values):
            if np.isnan(m):
                pos.append(np.nan); continue
            up = up + 1 if c > m * (1 + band) else 0
            dn = dn + 1 if c < m * (1 - band) else 0
            if on is None:
                on = bool(c > m)
            else:
                on = True if up >= conf else (False if dn >= conf else on)
            pos.append(1.0 if on else 0.0)
        pos = pd.Series(pos, index=lvl.index).shift(1)  # bir gün sonra uygulanır
        sw = pos.diff().abs().fillna(0)
        rs = (pos * mk + (1 - pos) * rf - sw * MALIYET)[pos.notna()]
        o = strateji_degerlendir(rs, mk.loc[rs.index], 252, 63, pd.Timestamp("2007-01-01"), ad)
        yil = (rs.index[-1] - rs.index[0]).days / 365.25
        o["gecis_yilda"] = round(float(sw.loc[rs.index].sum() / yil), 2)
        o["piyasada_kalma_orani"] = round(float(pos.loc[rs.index].mean()), 3)
        # durum içi ortalama günlük getiri
        on_r = mk.loc[rs.index][pos.loc[rs.index] == 1]; off_r = mk.loc[rs.index][pos.loc[rs.index] == 0]
        t = stats.ttest_ind(on_r, off_r, equal_var=False)
        o["risk_on_gunluk_ort_bp"] = round(float(on_r.mean() * 1e4), 2); o["risk_off_gunluk_ort_bp"] = round(float(off_r.mean() * 1e4), 2)
        o["on_off_fark_t_naif"] = round(float(t.statistic), 2)
        o["risk_on_yillik_vol"] = round(float(on_r.std() * np.sqrt(252) * 100), 1); o["risk_off_yillik_vol"] = round(float(off_r.std() * np.sqrt(252) * 100), 1)
        o["hukum"] = hukum_strateji(o)
        # site 1993+ iddiası: en büyük düşüş
        s93 = pd.concat([rs, mk.loc[rs.index]], axis=1).loc["1993-01-01":]
        o["1993_sonrasi"] = {"strateji_dd": round(100 * maxdd(s93.iloc[:, 0]), 1), "al_tut_dd": round(100 * maxdd(s93.iloc[:, 1]), 1)}
        out[ad] = o
    kaydet("T02_site_rejim_kurali", out)


# ---------------------------------------------------------------- T03 zaman serisi momentumu (aylık tahmin regresyonu + strateji)
def t03_tsmom():
    ff = french("F-F_Research_Data_Factors_CSV")
    rf = ff["RF"]; ex = ff["Mkt-RF"]; mk = ex + rf
    out = {}
    for L in (1, 3, 12):
        past = (1 + mk).rolling(L).apply(np.prod, raw=True) - 1 - rf.rolling(L).apply(lambda x: np.prod(1 + x) - 1, raw=True)
        sig = np.sign(past)
        y = ex.shift(-1)
        m = hac(y, sig.rename("sig"), lags=12)
        a, b = yarilar(y.dropna().index)
        h = {}
        for k, ix in (("ilk_yari", a), ("son_yari", b), ("1993_sonrasi", y.dropna().index[y.dropna().index >= pd.Period("1993-01", "M")])):
            mm = hac(y.loc[ix], sig.loc[ix].rename("sig"), lags=12)
            h[k] = {"b_aylik_bp": round(float(mm.params["sig"] * 1e4), 1), "t": round(float(mm.tvalues["sig"]), 2)}
        out[f"{L}_ay_isaret_regresyon"] = {"b_aylik_bp": round(float(m.params["sig"] * 1e4), 1), "t": round(float(m.tvalues["sig"]), 2),
                                           "n": int(m.nobs), "alt_donem": h}
    # 1/3/12 eşit ağırlıklı kural (HOP), uzun/nakit; leverage yok
    sigs = []
    for L in (1, 3, 12):
        past = (1 + mk).rolling(L).apply(np.prod, raw=True) - rf.rolling(L).apply(lambda x: np.prod(1 + x), raw=True)
        sigs.append((past > 0).astype(float))
    pos = (sum(sigs) / 3).shift(1)
    sw = pos.diff().abs().fillna(0)
    rs = (pos * mk + (1 - pos) * rf - sw * MALIYET).dropna()
    o = strateji_degerlendir(rs, mk.loc[rs.index], 12, 12, pd.Period("2017-01", "M"), "HOP_1_3_12")
    o["hukum"] = hukum_strateji(o)
    out["strateji_1_3_12_uzun_nakit"] = o
    # 12 ay
    p12 = ((1 + mk).rolling(12).apply(np.prod, raw=True) - (1 + rf).rolling(12).apply(np.prod, raw=True) > 0).astype(float).shift(1)
    sw = p12.diff().abs().fillna(0)
    rs = (p12 * mk + (1 - p12) * rf - sw * MALIYET).dropna()
    o = strateji_degerlendir(rs, mk.loc[rs.index], 12, 12, pd.Period("2017-01", "M"), "TSMOM12")
    o["hukum"] = hukum_strateji(o)
    out["strateji_12_ay_uzun_nakit"] = o
    kaydet("T03_zaman_serisi_momentumu", out)


# ---------------------------------------------------------------- T04 CAPE
def t04_cape():
    if not var("shiller_ie_data.xls"):
        kaydet("T04_CAPE", {"hukum": "TEST EDİLEMEDİ", "neden": "Shiller verisi indirilemedi"}); return
    raw = pd.read_excel(yol("shiller_ie_data.xls"), sheet_name="Data", header=None, skiprows=8)
    raw = raw.iloc[:, :14]
    raw.columns = ["date", "P", "D", "E", "CPI", "frac", "GS10", "RealP", "RealD", "RealTR", "RealE", "CAPE", "x", "y"]
    raw = raw[pd.to_numeric(raw["P"], errors="coerce").notna()].copy()
    raw["date"] = raw["date"].astype(float)
    yr = raw["date"].astype(int); mo = ((raw["date"] - yr) * 100).round().astype(int).clip(1, 12)
    raw.index = pd.PeriodIndex([f"{y}-{m:02d}" for y, m in zip(yr, mo)], freq="M")
    cape = pd.to_numeric(raw["CAPE"], errors="coerce")
    ln = np.log(cape)
    rtr = pd.to_numeric(raw["RealTR"], errors="coerce")
    out = {"son_cape": float(cape.dropna().iloc[-1]), "son_tarih": str(cape.dropna().index[-1])}
    for H, ad in ((12, "1y"), (60, "5y"), (120, "10y")):
        fwd = (rtr.shift(-H) / rtr) ** (12 / H) - 1
        d = pd.concat([fwd, ln], axis=1).dropna(); d.columns = ["y", "x"]
        m = hac(d["y"], d["x"].rename("x"), lags=H)
        a, b = yarilar(d.index)
        h = {}
        for k, ix in (("ilk_yari", a), ("son_yari", b), ("1990_sonrasi", d.index[d.index >= pd.Period("1990-01", "M")])):
            mm = hac(d.loc[ix, "y"], d.loc[ix, "x"].rename("x"), lags=H)
            h[k] = {"b": round(float(mm.params["x"]), 3), "t": round(float(mm.tvalues["x"]), 2), "r2": round(float(mm.rsquared), 3)}
        # genişleyen pencere örneklem dışı (ilk 40 yıl eğitim), 1 aylık adımla ama gerçekleşen getiri bilgisi H ay gecikmeli
        preds, bench = [], []
        idx = d.index
        start = 12 * 40
        for i in range(start, len(d)):
            tr = d.iloc[: i - H + 1]  # tahmin tarihinde gerçekleşmiş getiriler
            if len(tr) < 60: continue
            X = sm.add_constant(tr["x"]); mm = sm.OLS(tr["y"], X).fit()
            preds.append(mm.params["const"] + mm.params["x"] * d["x"].iloc[i]); bench.append(tr["y"].mean())
        pi = pd.Series(preds, index=idx[start:start + len(preds)]); bi = pd.Series(bench, index=pi.index)
        cw = clark_west(d["y"].loc[pi.index], pi, bi)
        out[ad] = {"b": round(float(m.params["x"]), 3), "t": round(float(m.tvalues["x"]), 2), "r2": round(float(m.rsquared), 3), "n": int(m.nobs),
                   "alt_donem": h, "oos_r2": round(cw[0], 3), "oos_cw_t": round(cw[1], 2), "oos_cw_p": round(cw[2], 4)}
    kaydet("T04_CAPE_gercek_getiri", out)


# ---------------------------------------------------------------- T05 getiri eğrisi
def t05_getiri_egrisi():
    if not (var("fred_T10Y3M.csv") and var("fred_USREC.csv")):
        kaydet("T05_getiri_egrisi", {"hukum": "TEST EDİLEMEDİ", "neden": "FRED serisi yok"}); return
    sp = fred("T10Y3M"); rec = fred("USREC")
    spm = sp.resample("ME").last()
    recm = rec.resample("MS").last(); recm.index = recm.index + pd.offsets.MonthEnd(0)
    y = pd.Series(0.0, index=spm.index)
    for t in spm.index:
        w = recm[(recm.index > t) & (recm.index <= t + pd.DateOffset(months=12) + pd.offsets.MonthEnd(0))]
        y.loc[t] = float((w == 1).any()) if len(w) else np.nan
    d = pd.concat([y.rename("y"), spm.rename("sp")], axis=1).dropna()
    out = {"ornek": f"{d.index[0].date()}..{d.index[-1].date()}", "n": int(len(d)), "aylik_yatay_ortusme_var": True}
    from sklearn.metrics import roc_auc_score
    from sklearn.linear_model import LogisticRegression
    auc_tum = roc_auc_score(d["y"], -d["sp"])
    a, b = yarilar(d.index)
    out["auc_tum"] = round(float(auc_tum), 3)
    out["auc_ilk_yari"] = round(float(roc_auc_score(d.loc[a, "y"], -d.loc[a, "sp"])), 3) if d.loc[a, "y"].nunique() > 1 else None
    out["auc_son_yari"] = round(float(roc_auc_score(d.loc[b, "y"], -d.loc[b, "sp"])), 3) if d.loc[b, "y"].nunique() > 1 else None
    inv = d["sp"] < 0
    out["ters_egri_aylari"] = int(inv.sum()); out["ters_egri_sonrasi_12ay_icinde_resesyon_orani"] = round(float(d.loc[inv, "y"].mean()), 3)
    out["normal_egri_sonrasi_12ay_icinde_resesyon_orani"] = round(float(d.loc[~inv, "y"].mean()), 3)
    # örneklem dışı AUC (genişleyen pencere, 12 ay gecikmeli etiket)
    p = []
    for i in range(120, len(d)):
        tr = d.iloc[: i - 12]
        if tr["y"].nunique() < 2: p.append(np.nan); continue
        lr = LogisticRegression().fit(tr[["sp"]], tr["y"]); p.append(lr.predict_proba(d[["sp"]].iloc[[i]])[0, 1])
    p = pd.Series(p, index=d.index[120:]).dropna()
    out["oos_auc"] = round(float(roc_auc_score(d["y"].loc[p.index], p)), 3)
    # hisse tarafı: ters eğri sonrası S&P (French toplam getiri) 12 aylık ileri getiri
    ff = french("F-F_Research_Data_Factors_CSV"); mk = (ff["Mkt-RF"] + ff["RF"])
    mk.index = mk.index.to_timestamp("M")
    fwd = ((1 + mk).rolling(12).apply(np.prod, raw=True).shift(-12) - 1)
    dd = pd.concat([fwd.rename("f"), d["sp"]], axis=1).dropna()
    m = hac(dd["f"], (dd["sp"] < 0).astype(float).rename("inv"), lags=12)
    out["hisse_12ay_ileri_getiri_ters_egri_farki_pp"] = round(float(m.params["inv"] * 100), 2); out["hisse_fark_t"] = round(float(m.tvalues["inv"]), 2)
    out["hisse_ort_12ay_ters"] = round(float(dd.loc[dd["sp"] < 0, "f"].mean() * 100), 1); out["hisse_ort_12ay_normal"] = round(float(dd.loc[dd["sp"] >= 0, "f"].mean() * 100), 1)
    kaydet("T05_getiri_egrisi_resesyon_ve_hisse", out)


# ---------------------------------------------------------------- T06 kredi spreadi
def t06_kredi():
    if not var("fred_BAA10Y.csv"):
        kaydet("T06_kredi", {"hukum": "TEST EDİLEMEDİ", "neden": "FRED serisi yok"}); return
    s = fred("BAA10Y").resample("ME").last()
    ff = french("F-F_Research_Data_Factors_CSV"); ex = ff["Mkt-RF"]; ex.index = ex.index.to_timestamp("M")
    out = {"ornek": f"{s.index[0].date()}..{s.index[-1].date()}"}
    lvl = s
    z = (lvl - lvl.rolling(120, min_periods=60).mean()) / lvl.rolling(120, min_periods=60).std()
    for nm, x in (("seviye", lvl), ("3ay_degisim", lvl.diff(3)), ("10y_z", z)):
        for H in (1, 3, 12):
            fwd = (1 + ex).rolling(H).apply(np.prod, raw=True).shift(-H) - 1
            d = pd.concat([fwd, x.rename("x")], axis=1).dropna(); d.columns = ["y", "x"]
            xs = (d["x"] - d["x"].mean()) / d["x"].std()
            m = hac(d["y"], xs.rename("x"), lags=max(H, 3))
            a, b = yarilar(d.index)
            ma = hac(d.loc[a, "y"], xs.loc[a].rename("x"), lags=max(H, 3)); mb = hac(d.loc[b, "y"], xs.loc[b].rename("x"), lags=max(H, 3))
            out[f"{nm}_{H}ay"] = {"b_pp_per_sd": round(float(m.params["x"] * 100), 2), "t": round(float(m.tvalues["x"]), 2),
                                  "ilk_yari_t": round(float(ma.tvalues["x"]), 2), "son_yari_t": round(float(mb.tvalues["x"]), 2), "n": int(m.nobs)}
    kaydet("T06_kredi_spreadi_BAA10Y", out)


# ---------------------------------------------------------------- T07 VIX / varyans risk primi / vade yapısı / site yüzdelik dilimi
def t07_vix():
    if not (var("yahoo_GSPC.csv") and var("yahoo_VIX.csv")):
        kaydet("T07_vix", {"hukum": "TEST EDİLEMEDİ", "neden": "Yahoo verisi yok"}); return
    px = yahoo("^GSPC", "Close"); vix = yahoo("^VIX", "Close")
    r = np.log(px).diff().dropna()
    rv21 = (r ** 2).rolling(21).sum() * 252 / 21  # yıllık varyans (gerçekleşen, son 21 gün)
    d = pd.concat([px.rename("px"), vix.rename("vix"), rv21.rename("rv")], axis=1).dropna()
    d["vrp"] = (d["vix"] / 100) ** 2 - d["rv"]
    out = {"ornek": f"{d.index[0].date()}..{d.index[-1].date()}", "n": int(len(d))}
    for H in (21, 63):
        fwd = np.log(px).shift(-H) - np.log(px)
        for nm in ("vrp", "vix"):
            dd = pd.concat([fwd.rename("y"), d[nm]], axis=1).dropna()
            xs = (dd[nm] - dd[nm].mean()) / dd[nm].std()
            m = hac(dd["y"], xs.rename("x"), lags=H)
            a, b = yarilar(dd.index)
            ma = hac(dd.loc[a, "y"], xs.loc[a].rename("x"), lags=H); mb = hac(dd.loc[b, "y"], xs.loc[b].rename("x"), lags=H)
            out[f"{nm}_ileri{H}g"] = {"b_pp_per_sd": round(float(m.params["x"] * 100), 2), "t": round(float(m.tvalues["x"]), 2), "r2": round(float(m.rsquared), 4),
                                      "ilk_yari_t": round(float(ma.tvalues["x"]), 2), "son_yari_t": round(float(mb.tvalues["x"]), 2), "n": int(m.nobs)}
    # siteye özel: 252 günlük yüzdelik dilim dilimleri
    pct = vix.rolling(252).apply(lambda w: (w <= w.iloc[-1]).mean() * 100, raw=False)
    fwd20 = np.log(px).shift(-20) - np.log(px)
    dd = pd.concat([fwd20.rename("y"), pct.rename("p")], axis=1).dropna()
    gr = {}
    for nm, mask in (("0-20", dd["p"] <= 20), ("20-80", (dd["p"] > 20) & (dd["p"] < 80)), ("80-100", dd["p"] >= 80)):
        gr[nm] = {"ort_20g_pp": round(float(dd.loc[mask, "y"].mean() * 100), 2), "n": int(mask.sum()), "kayip_orani": round(float((dd.loc[mask, "y"] < 0).mean()), 3),
                  "std_pp": round(float(dd.loc[mask, "y"].std() * 100), 2)}
    m = hac(dd["y"], (dd["p"] >= 80).astype(float).rename("yuksek"), lags=20)
    gr["yuksek_vix_farki_pp"] = round(float(m.params["yuksek"] * 100), 2); gr["yuksek_t"] = round(float(m.tvalues["yuksek"]), 2)
    out["site_yuzdelik_dilimi_20g_ileri"] = gr
    # vade yapısı
    if var("yahoo_VIX3M.csv"):
        v3 = yahoo("^VIX3M", "Close")
        ts = (v3 - vix).dropna()
        dd = pd.concat([fwd20.rename("y"), ts.rename("ts")], axis=1).dropna()
        xs = (dd["ts"] - dd["ts"].mean()) / dd["ts"].std()
        m = hac(dd["y"], xs.rename("x"), lags=20)
        out["vade_yapisi_VIX3M_eksi_VIX_ileri20g"] = {"b_pp_per_sd": round(float(m.params["x"] * 100), 2), "t": round(float(m.tvalues["x"]), 2), "n": int(m.nobs),
                                                         "backwardation_gun_orani": round(float((ts < 0).mean()), 3),
                                                         "backward_sonrasi_ort_20g_pp": round(float(dd.loc[dd["ts"] < 0, "y"].mean() * 100), 2),
                                                         "contango_sonrasi_ort_20g_pp": round(float(dd.loc[dd["ts"] >= 0, "y"].mean() * 100), 2)}
    kaydet("T07_VIX_VRP_vade_yuzdelik", out)


# ---------------------------------------------------------------- T08 oynaklık yönetimi (günlük French)
def t08_volyonetim():
    fd = french("F-F_Research_Data_Factors_daily_CSV")
    rf = fd["RF"]; ex = fd["Mkt-RF"]; mk = ex + rf
    mi = mk.copy()
    out = {}
    rv = (ex ** 2).rolling(21).sum().shift(1)  # önceki 21 gün gerçekleşen varyans
    c0 = rv.median()
    for ad, cap in (("kaldiracsiz_en_fazla_1x", 1.0), ("en_fazla_2x", 2.0)):
        w = (c0 / rv).clip(upper=cap)
        w = w.fillna(0)
        # ağırlık yalnız kullanılabilir geçmişle: median sabit değil, genişleyen medyan (ileriye bakma yok)
        c_exp = rv.expanding(min_periods=252).median()
        w = (c_exp / rv).clip(upper=cap)
        dw = w.diff().abs().fillna(0)
        rs = (w * ex + rf - dw * MALIYET)[w.notna()]
        o = strateji_degerlendir(rs, mk.loc[rs.index], 252, 63, pd.Timestamp("2017-01-01"), ad)
        o["ort_agirlik"] = round(float(w.loc[rs.index].mean()), 3)
        # alfa: rs_excess ~ ex
        d = pd.concat([(rs - rf.loc[rs.index]).rename("y"), ex.loc[rs.index].rename("x")], axis=1)
        m = hac(d["y"], d["x"], lags=21)
        o["alfa_yillik_pp"] = round(float(m.params["const"] * 252 * 100), 2); o["alfa_t"] = round(float(m.tvalues["const"]), 2)
        o["hukum"] = hukum_strateji(o)
        out[ad] = o
    kaydet("T08_oynaklik_yonetimi_gunluk", out)


# ---------------------------------------------------------------- T09 genişlik vekilleri (sektör ETF sayımı) ve RSP/SPY GENİŞ-DAR
def t09_genislik_vekili():
    secs = [s for s in ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY") if var(f"yahoo_{s}.csv")]
    if len(secs) < 8 or not var("yahoo_SPY.csv"):
        kaydet("T09_genislik", {"hukum": "TEST EDİLEMEDİ", "neden": "ETF verisi yok"}); return
    P = pd.concat([yahoo(s) for s in secs], axis=1).dropna()
    spy = yahoo("SPY").reindex(P.index)
    out = {"ornek": f"{P.index[0].date()}..{P.index[-1].date()}", "sektor_sayisi": len(secs)}
    fwd20 = np.log(spy).shift(-20) - np.log(spy)
    for n in (50, 200):
        cnt = (P > P.rolling(n).mean()).sum(axis=1)
        dd = pd.concat([fwd20.rename("y"), cnt.rename("c")], axis=1).dropna()
        dd = dd[P.rolling(n).mean().notna().all(axis=1).reindex(dd.index).fillna(False)]
        xs = (dd["c"] - dd["c"].mean()) / dd["c"].std()
        m = hac(dd["y"], xs.rename("x"), lags=20)
        a, b = yarilar(dd.index)
        ma = hac(dd.loc[a, "y"], xs.loc[a].rename("x"), lags=20); mb = hac(dd.loc[b, "y"], xs.loc[b].rename("x"), lags=20)
        lo = dd["c"] <= 2; hi = dd["c"] >= 8
        out[f"MA{n}_ustu_sektor_sayisi"] = {"b_pp_per_sd": round(float(m.params["x"] * 100), 2), "t": round(float(m.tvalues["x"]), 2), "ilk_yari_t": round(float(ma.tvalues["x"]), 2),
                                            "son_yari_t": round(float(mb.tvalues["x"]), 2), "dusuk_geniflik_(<=2)_ort_20g_pp": round(float(dd.loc[lo, "y"].mean() * 100), 2), "n_dusuk": int(lo.sum()),
                                            "yuksek_(>=8)_ort_20g_pp": round(float(dd.loc[hi, "y"].mean() * 100), 2), "n_yuksek": int(hi.sum()), "n": int(m.nobs)}
    # RSP/SPY: site kuralı: eşit ağırlık - ağırlıklı 20g fark >= +1 puan GENİŞ, <= -1 DAR
    if var("yahoo_RSP.csv"):
        rsp = yahoo("RSP").reindex(spy.index).dropna(); sp2 = spy.reindex(rsp.index)
        diff = (rsp / rsp.shift(20) - sp2 / sp2.shift(20)) * 100
        f20 = np.log(sp2).shift(-20) - np.log(sp2)
        dd = pd.concat([f20.rename("y"), diff.rename("d")], axis=1).dropna()
        gen = dd["d"] >= 1; dar = dd["d"] <= -1
        m = hac(dd["y"], (dd["d"] / dd["d"].std()).rename("x"), lags=20)
        out["RSP_SPY_20g_fark"] = {"b_pp_per_sd": round(float(m.params["x"] * 100), 2), "t": round(float(m.tvalues["x"]), 2), "n": int(m.nobs),
                                   "GENIS_ort_20g_pp": round(float(dd.loc[gen, "y"].mean() * 100), 2), "n_gen": int(gen.sum()), "DAR_ort_20g_pp": round(float(dd.loc[dar, "y"].mean() * 100), 2), "n_dar": int(dar.sum()),
                                   "ara_ort_20g_pp": round(float(dd.loc[~gen & ~dar, "y"].mean() * 100), 2)}
    kaydet("T09_genislik_vekilleri", out)


# ---------------------------------------------------------------- T10 mevsimsellik (Halloween)
def t10_halloween():
    ff = french("F-F_Research_Data_Factors_CSV")
    mk = ff["Mkt-RF"] + ff["RF"]; ex = ff["Mkt-RF"]
    mo = pd.Series([p.month for p in mk.index], index=mk.index)
    win = mo.isin([11, 12, 1, 2, 3, 4]).astype(float)
    out = {}
    for ad, ix in (("tum_1926", mk.index), ("1926_1969", mk.index[mk.index < pd.Period("1970-01", "M")]), ("1970_1999", mk.index[(mk.index >= pd.Period("1970-01", "M")) & (mk.index < pd.Period("2000-01", "M"))]),
                   ("2000_sonrasi", mk.index[mk.index >= pd.Period("2000-01", "M")]), ("2002_sonrasi_yayin", mk.index[mk.index >= pd.Period("2002-01", "M")])):
        m = hac(mk.loc[ix], win.loc[ix].rename("kas_nisan"), lags=6)
        out[ad] = {"kas_nisan_fazlasi_bp_ay": round(float(m.params["kas_nisan"] * 1e4), 1), "t": round(float(m.tvalues["kas_nisan"]), 2), "n": int(m.nobs)}
    # ay-ay: tek ay tarafından mı taşınıyor
    ay = {}
    for k in range(1, 13):
        x = mk[mo == k]
        ay[k] = {"ort_bp": round(float(x.mean() * 1e4), 0), "t": round(float(x.mean() / (x.std() / np.sqrt(len(x)))), 2)}
    out["ay_ay"] = ay
    # strateji: Mayıs-Ekim'de nakit
    pos = win; rf = ff["RF"]
    sw = pos.diff().abs().fillna(0)
    rs = pos * mk + (1 - pos) * rf - sw * MALIYET
    o = strateji_degerlendir(rs, mk, 12, 12, pd.Period("2002-01", "M"), "halloween")
    o["hukum"] = hukum_strateji(o)
    out["strateji_mayis_ekim_nakit"] = o
    kaydet("T10_mevsimsellik_halloween", out)


# ---------------------------------------------------------------- T11 kesitsel momentum (French UMD, decil)
def t11_momentum():
    mom = french("F-F_Momentum_Factor_CSV")
    mom.columns = [c.strip() for c in mom.columns]
    umd = mom.iloc[:, 0]
    ff = french("F-F_Research_Data_Factors_CSV"); mk = ff["Mkt-RF"]
    out = {"ornek": f"{umd.index[0]}..{umd.index[-1]}"}
    for ad, ix in (("tum", umd.index), ("1927_1963", umd.index[umd.index < pd.Period("1964-01", "M")]), ("1964_1992", umd.index[(umd.index >= pd.Period("1964-01", "M")) & (umd.index < pd.Period("1993-01", "M"))]),
                   ("1993_sonrasi_yayin", umd.index[umd.index >= pd.Period("1993-01", "M")]), ("2010_sonrasi", umd.index[umd.index >= pd.Period("2010-01", "M")])):
        x = umd.loc[ix]
        m = hac(x, pd.Series(0.0, index=x.index, name="z") + np.random.default_rng(0).normal(0, 1e-9, len(x)), lags=6)
        out[ad] = {"aylik_ort_bp": round(float(x.mean() * 1e4), 1), "t": round(float(m.tvalues["const"]), 2), "sharpe": round(float(sharpe(x)), 2), "en_buyuk_dusus": round(100 * maxdd(x), 1), "n": int(len(x))}
    # momentum çöküşleri: en kötü 10 ay
    out["en_kotu_5_ay"] = {str(k): round(float(v * 100), 1) for k, v in umd.nsmallest(5).items()}
    # Daniel-Moskowitz panik durumu: piyasa son 24 ay < 0 ve piyasa oynaklığı üst %?  (basit tanım: 24 ay getirisi < 0 ve son 6 ay günlük değil aylık oynaklık üst çeyrek)
    cum24 = (1 + (mk + ff["RF"])).rolling(24).apply(np.prod, raw=True) - 1
    vol6 = mk.rolling(6).std()
    panik = ((cum24 < 0) & (vol6 > vol6.expanding(60).quantile(0.75))).shift(1)
    d = pd.concat([umd.rename("u"), panik.rename("p")], axis=1).dropna(); d["p"] = d["p"].astype(float)
    m = hac(d["u"], d["p"].rename("panik"), lags=6)
    out["panik_durumu"] = {"panik_ay_sayisi": int(d["p"].sum()), "umd_ort_panik_bp": round(float(d.loc[d["p"] == 1, "u"].mean() * 1e4), 1), "umd_ort_diger_bp": round(float(d.loc[d["p"] == 0, "u"].mean() * 1e4), 1),
                           "fark_t": round(float(m.tvalues["panik"]), 2)}
    # oynaklık ölçekli UMD (Barroso–Santa-Clara): önceki 6 ay UMD oynaklığıyla ölçekle (hedef sabit %10 yıllık), ileriye bakma yok
    sig = umd.rolling(6).std().shift(1) * np.sqrt(12)
    w = (0.10 / sig).clip(upper=2.0)
    ru = (w * umd).dropna()
    out["vol_olcekli_UMD"] = {"ham": ozet(umd.loc[ru.index]), "olcekli": ozet(ru), "olcekli_en_kotu_ay": round(float(ru.min() * 100), 1)}
    kaydet("T11_kesitsel_momentum_UMD", out)


# ---------------------------------------------------------------- T12 sektör momentumu (French 49 sanayi) ve sitenin sektör göreceli gücü (ETF)
def t12_sektor():
    out = {}
    try:
        b = french_bloklar("49_Industry_Portfolios_CSV")[0][1].replace(-99.99, np.nan) / 100
        b.index = pd.PeriodIndex(b.index, freq="M")
        res = {}
        for L, skip, ad in ((1, 0, "1ay"), (6, 0, "6ay"), (12, 1, "12_1ay"), (3, 0, "3ay")):
            past = (1 + b).rolling(L).apply(np.prod, raw=True)
            if skip:
                past = (1 + b.shift(skip)).rolling(L - skip if L > skip else 1).apply(np.prod, raw=True)
            rk = past.shift(1).rank(axis=1, pct=True)  # t-1 sonu bilgisi
            top = (rk >= 0.8).astype(float); bot = (rk <= 0.2).astype(float)
            rt = (b * top).sum(axis=1) / top.sum(axis=1).replace(0, np.nan); rbt = (b * bot).sum(axis=1) / bot.sum(axis=1).replace(0, np.nan)
            ls = (rt - rbt).dropna()
            x = ls
            m = hac(x, pd.Series(0.0, index=x.index, name="z") + np.random.default_rng(0).normal(0, 1e-9, len(x)), lags=6)
            a_, b_ = yarilar(x.index)
            ma = hac(x.loc[a_], pd.Series(0.0, index=a_, name="z") + np.random.default_rng(1).normal(0, 1e-9, len(a_)), lags=6)
            mb = hac(x.loc[b_], pd.Series(0.0, index=b_, name="z") + np.random.default_rng(2).normal(0, 1e-9, len(b_)), lags=6)
            res[ad] = {"uzun_kisa_aylik_bp": round(float(x.mean() * 1e4), 1), "t": round(float(m.tvalues["const"]), 2), "ilk_yari_t": round(float(ma.tvalues["const"]), 2),
                       "son_yari_t": round(float(mb.tvalues["const"]), 2), "1993_sonrasi_bp": round(float(x[x.index >= pd.Period('1993-01', 'M')].mean() * 1e4), 1), "sharpe": round(float(sharpe(x)), 2), "n": int(len(x))}
        out["fr49_ust_dilim_eksi_alt_dilim"] = res
    except Exception as e:
        out["fr49_hata"] = repr(e)
    # sitenin kendisi: 9 sektör ETF'i, SPY'a göre getiri sıralaması -> sonraki 20 günde SPY'a göre getiri (sıra korelasyonu, IC)
    secs = [s for s in ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY") if var(f"yahoo_{s}.csv")]
    if len(secs) >= 8 and var("yahoo_SPY.csv"):
        P = pd.concat([yahoo(s) for s in secs], axis=1).dropna(); spy = yahoo("SPY").reindex(P.index)
        res = {}
        for L, ad in ((20, "20g_site_tanimi"), (60, "60g"), (120, "120g"), (250, "250g")):
            past = P / P.shift(L) - spy.values[:, None] / spy.shift(L).values[:, None]
            fut = P.shift(-20) / P - (spy.shift(-20) / spy).values[:, None]
            ic = []
            idx = past.dropna().index.intersection(fut.dropna().index)
            for t in idx[::20]:  # örtüşmeyen 20 günlük adımlar
                ic.append(stats.spearmanr(past.loc[t], fut.loc[t])[0])
            ic = pd.Series(ic)
            top3 = []; bot3 = []
            for t in idx[::20]:
                rk = past.loc[t].rank(ascending=False)
                top3.append(fut.loc[t][rk <= 3].mean()); bot3.append(fut.loc[t][rk >= len(secs) - 2].mean())
            ls = pd.Series(top3) - pd.Series(bot3)
            res[ad] = {"ic_ort": round(float(ic.mean()), 3), "ic_t": round(float(ic.mean() / (ic.std() / np.sqrt(len(ic)))), 2), "n": int(len(ic)),
                       "ust3_eksi_alt3_aylik_pp": round(float(ls.mean() * 100), 2), "ls_t": round(float(ls.mean() / (ls.std() / np.sqrt(len(ls)))), 2),
                       "ic_ilk_yari": round(float(ic[: len(ic) // 2].mean()), 3), "ic_son_yari": round(float(ic[len(ic) // 2:].mean()), 3)}
        out["etf_sektor_siralamasi_ileri20g"] = res
        out["etf_ornek"] = f"{P.index[0].date()}..{P.index[-1].date()}"
    kaydet("T12_sektor_momentumu", out)


# ---------------------------------------------------------------- T13 kalite / karlılık / yatırım / değer (French 5 faktör)
def t13_faktorler():
    f5 = french("F-F_Research_Data_5_Factors_2x3_CSV")
    f5.columns = [c.strip() for c in f5.columns]
    out = {}
    for fct, yayin in (("RMW", "2013-01"), ("CMA", "2013-01"), ("HML", "1992-01"), ("SMB", "1981-01")):
        x = f5[fct]
        res = {}
        for ad, ix in (("tum", x.index), ("ilk_yari", yarilar(x.index)[0]), ("son_yari", yarilar(x.index)[1]), ("yayin_sonrasi", x.index[x.index >= pd.Period(yayin, "M")]), ("2013_sonrasi", x.index[x.index >= pd.Period("2013-01", "M")])):
            z = x.loc[ix]
            if len(z) < 24: continue
            m = hac(z, pd.Series(0.0, index=z.index, name="z") + np.random.default_rng(3).normal(0, 1e-9, len(z)), lags=6)
            res[ad] = {"aylik_bp": round(float(z.mean() * 1e4), 1), "t": round(float(m.tvalues["const"]), 2), "sharpe": round(float(sharpe(z)), 2), "n": int(len(z))}
        out[fct] = res
    kaydet("T13_faktorler_FF5", out)


# ---------------------------------------------------------------- T14 yatırımcı duyarlılığı (Baker-Wurgler)
def t14_bw():
    if not var("bw_sentiment.xlsx"):
        kaydet("T14_baker_wurgler", {"hukum": "TEST EDİLEMEDİ", "neden": "Baker-Wurgler verisi indirilemedi"}); return
    x = pd.read_excel(yol("bw_sentiment.xlsx"), sheet_name=None)
    nm = list(x.keys())[0]
    df = x[nm]
    cols = [str(c) for c in df.columns]
    kaydet("T14_baker_wurgler_hamsutunlar", {"sayfalar": list(x.keys()), "sutunlar": cols[:20], "ilk": df.head(3).astype(str).values.tolist()})


if __name__ == "__main__":
    secim = sys.argv[1:] or [k for k in globals() if k.startswith("t") and k[1:3].isdigit()]
    for k in sorted(secim):
        try:
            globals()[k]()
        except Exception as e:
            hata(k, e)
    json.dump(SONUC, open("sonuc.json", "w"), ensure_ascii=False, indent=1, default=str)
