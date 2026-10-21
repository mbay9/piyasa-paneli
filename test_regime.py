"""Rejim kuralı için sentetik testler: python test_regime.py"""
import numpy as np
import pandas as pd
import update as u


def series(vals):
    idx = pd.bdate_range("2024-01-01", periods=len(vals))
    return pd.Series(vals, index=idx), idx[-1].strftime("%Y-%m-%d")


def run(vals):
    s, ref = series(vals)
    return u.regime(s, pd.Series(dtype=float), None, 0, ref)


up = list(np.linspace(100, 200, 400))
assert run(up)["market_regime"] == "RISK_ON", "yükselen seri RISK_ON olmalı"
down = list(np.linspace(200, 100, 400))
assert run(down)["market_regime"] == "RISK_OFF", "düşen seri RISK_OFF olmalı"
one_day = up + [up[-1] * 0.9] + [up[-1]] * 3
assert run(one_day)["market_regime"] == "RISK_ON", "tek günlük düşüş rejimi çevirmemeli"
two_days = up + [up[-1] * 0.6] * 3
assert run(two_days)["market_regime"] == "RISK_OFF", "iki ardışık bant altı kapanış RISK_OFF yapmalı"
in_band = up + list(np.linspace(up[-1], up[-1] * 0.93, 10))
r = run(in_band)
assert r["market_regime"] == "RISK_ON", "bant içinde önceki durum korunmalı"
assert run(up[:100])["market_regime"] == "INSUFFICIENT_DATA", "kısa geçmiş yetersiz sayılmalı"
print("regime testleri geçti")
