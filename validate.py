#!/usr/bin/env python3
"""Yayınlamadan önce data.json'u denetler. Çekirdek veri bozuksa çıkış kodu 1 verir, eski sayfa yerinde kalır."""
import json
import sys
import datetime as dt

d = json.load(open("data.json", encoding="utf-8"))
errs = []
today = dt.datetime.now(dt.timezone.utc).date()
ref = dt.date.fromisoformat(d["meta"]["ref_date"])
if (today - ref).days > 5:
    errs.append(f"referans tarih çok eski: {ref}")
for k in ("SPX", "NASDAQ", "VIX"):
    m = d["indexes"].get(k)
    if not m or m.get("close") is None or m["close"] <= 0:
        errs.append(f"{k} kapanışı eksik")
if not d.get("breadth") or not d["breadth"].get("ma50"):
    errs.append("breadth eksik")
b = d.get("breadth", {}).get("ma50")
if b and not (0 <= b["pct"] <= 100):
    errs.append("breadth yüzdesi geçersiz")
rg = d.get("regime")
if not rg or rg.get("market_regime") not in ("RISK_ON", "NEUTRAL", "RISK_OFF", "INSUFFICIENT_DATA") or not (-4 <= rg.get("total_score", 99) <= 4):
    errs.append("rejim sonucu geçersiz")
elif rg["market_regime"] == "INSUFFICIENT_DATA":
    errs.append("rejim hesaplanamadı (veri yetersiz): " + "; ".join(rg["data_quality"].get("stale_data", []) + rg["data_quality"].get("missing_data", [])))
if d["meta"].get("quality", {}).get("level") == "DÜŞÜK":
    errs.append("veri kalitesi DÜŞÜK: " + "; ".join(d["meta"]["quality"].get("reasons", [])))
if errs:
    print("DOĞRULAMA BAŞARISIZ:", *errs, sep="\n - ", file=sys.stderr)
    sys.exit(1)
ai = d.get("ai", {})
print("data.json geçerli | referans", ref, "| kalite", d["meta"]["quality"]["level"],
      "| AI:", "var" if ai.get("available") else "eksik")
