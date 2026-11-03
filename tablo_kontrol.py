"""tablolar.json denetimi: biçim, Beat/Miss tutarlılığı ve (bülten dizini verilirse) her rakamın bültende birebir geçmesi.
Kullanım: python tablo_kontrol.py tablolar.json [bildirim_dizini]
Satır alanları: ad, fmt (m milyon, p yüzde, d dolar), ger (gerçek), bek (beklenti ya da null), sonuc (Beat|Miss|In line|null),
vurgu (0/1 sarı satır), kanit (bültende birebir geçen metinler) ya da hesap (türetilmiş satırın açıklaması)."""
from __future__ import annotations

import glob
import json
import os
import re
import sys

DEC = {"m": 1, "p": 1, "d": 2}


def sonuc_beklenen(ger, bek, fmt):
    d = DEC[fmt]
    a, b = round(ger, d), round(bek, d)
    return "Beat" if a > b else "Miss" if a < b else "In line"


def denetle(veri, bildirim=None):
    hata = []
    if not isinstance(veri, dict) or veri.get("v") != 1 or not isinstance(veri.get("tablolar"), dict):
        return ["biçim: v=1 ve tablolar sözlüğü gerekli"]
    for sym, t in veri["tablolar"].items():
        p = f"{sym}: "
        if not re.match(r"\d{4}-\d{2}-\d{2}$", str(t.get("tarih"))):
            hata.append(p + "tarih yok")
        if not str(t.get("kaynak", "")).startswith("https://www.sec.gov/"):
            hata.append(p + "kaynak SEC adresi değil")
        if not t.get("basvuru") or not t.get("bolumler"):
            hata.append(p + "başvuru ya da bölümler yok")
            continue
        metin = None
        if bildirim:
            for f in glob.glob(os.path.join(bildirim, sym, f"*{t['basvuru']}.txt")):
                metin = open(f, encoding="utf-8").read()
            if metin is None:
                hata.append(p + "bülten dosyası bulunamadı, rakamlar doğrulanamadı")
        for b in t["bolumler"]:
            if not b.get("baslik") or not b.get("satirlar"):
                hata.append(p + "bölüm başlığı ya da satırı yok")
                continue
            for r in b["satirlar"]:
                q = p + f"{b['baslik']} / {r.get('ad')}: "
                if r.get("fmt") not in DEC:
                    hata.append(q + "fmt geçersiz"); continue
                if not isinstance(r.get("ger"), (int, float)):
                    hata.append(q + "gerçek değer sayı değil"); continue
                if r.get("bek") is not None and not isinstance(r["bek"], (int, float)):
                    hata.append(q + "beklenti sayı değil"); continue
                if r.get("sonuc") not in (None, "Beat", "Miss", "In line"):
                    hata.append(q + "sonuc geçersiz")
                if r.get("sonuc") is not None:
                    if r.get("bek") is None:
                        hata.append(q + "beklenti yokken sonuç yazılmış")
                    elif r["sonuc"] != sonuc_beklenen(r["ger"], r["bek"], r["fmt"]):
                        hata.append(q + f"sonuç tutarsız: gerçek {r['ger']} beklenti {r['bek']} -> {sonuc_beklenen(r['ger'], r['bek'], r['fmt'])}")
                elif r.get("bek") is not None:
                    hata.append(q + "beklenti var ama sonuç yok")
                if not r.get("kanit") and not r.get("hesap"):
                    hata.append(q + "kanıt ya da hesap açıklaması yok")
                if metin is not None:
                    for k in r.get("kanit") or []:
                        if k not in metin:
                            hata.append(q + f"kanıt bültende birebir geçmiyor: {k!r}")
    return hata


if __name__ == "__main__":
    v = json.load(open(sys.argv[1], encoding="utf-8"))
    h = denetle(v, sys.argv[2] if len(sys.argv) > 2 else None)
    for x in h:
        print("HATA", x)
    print("tablo_kontrol:", "tamam" if not h else f"{len(h)} hata")
    sys.exit(1 if h else 0)
