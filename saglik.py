#!/usr/bin/env python3
"""Sağlık kontrolü: sitenin kodu, verisi, yayını ve görev çıktıları yayına çıkmadan / çıktıktan sonra denetlenir.
Amaç: bir şey bozulursa hangi kontrolün neden başarısız olduğu anında görünsün (kök neden), baştan her şeyi incelemek gerekmesin.

Kullanım: python saglik.py <mod> [--cikti dosya.json]
  onkontrol  kod ve yapılandırma (Python/JS sözdizimi, sayfa kimlikleri, hisse listesi, özet dosyaları, workflow'lar). Ağ gerekmez.
  veri       üretilen data.json'un içerik denetimi (validate.py'ye ek, daha ayrıntılı).
  site       yayına hazır site/ klasörü gerçek tarayıcıda (Chrome, masaüstü ve telefon genişliği) açılır; her sekme çizilir, tıklanır, "undefined/NaN" ve konsol hatası aranır.
  canli      yayındaki sayfanın depodakiyle aynı olduğunu doğrular (ortam: URL, RUN_ID).
  nobetci    zamanlanmış çalışmalar ve görevler zamanında sonuç verdi mi (ortam: GH_TOKEN, REPO, URL).
Çıkış kodu: hata varsa 1. Sonuç JSON'a ve GitHub Actions çıktısına (kok=...) yazılır; ilk hata kök neden sayılır."""
import ast
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import datetime as dt
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
SONUC = []  # {"ad", "durum": ok|uyari|hata, "ayrinti"}


def kayit(ad, ok, ayrinti="", uyari=False):
    durum = "ok" if ok else ("uyari" if uyari else "hata")
    SONUC.append({"ad": ad, "durum": durum, "ayrinti": str(ayrinti)[:600]})
    print(("✓" if ok else ("!" if uyari else "✗")), ad, ("— " + str(ayrinti)[:300]) if ayrinti and not ok else "")


def yol(*a):
    return os.path.join(ROOT, *a)


def oku_json(p):
    def bad(c):
        raise ValueError(f"geçersiz sayı değeri: {c}")
    with open(p, encoding="utf-8") as f:
        return json.loads(f.read(), parse_constant=bad)


def http(url, tries=3, timeout=30, headers=None):
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(url, headers=headers or {"User-Agent": "saglik-kontrol"})
            with urllib.request.urlopen(rq, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"{url[:90]}: {last!r}"[:300])


# ------------------------------------------------------------------ onkontrol
def onkontrol():
    for f in ("update.py", "validate.py", "saglik.py", "test_regime.py"):
        try:
            ast.parse(open(yol(f), encoding="utf-8").read(), f)
            kayit(f"Python sözdizimi: {f}", True)
        except SyntaxError as e:
            kayit(f"Python sözdizimi: {f}", False, f"satır {e.lineno}: {e.msg}")

    try:
        r = subprocess.run(["node", "--check", yol("app.js")], capture_output=True, text=True, timeout=60)
        kayit("JavaScript sözdizimi: app.js", r.returncode == 0, (r.stderr or r.stdout).strip()[:400])
    except FileNotFoundError:
        kayit("JavaScript sözdizimi: app.js", False, "node bulunamadı", uyari=True)

    html = open(yol("index.html"), encoding="utf-8").read()
    js = open(yol("app.js"), encoding="utf-8").read()
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r'getElementById\("([^"]+)"\)', js))
    eksik = sorted(i for i in used if i not in ids and not i.endswith("-"))
    kayit("Sayfa kimlikleri: app.js'in aradığı her öğe index.html'de var", not eksik, f"eksik: {eksik}")
    tabs_html = set(re.findall(r'data-t="([^"]+)"', html))
    tabs_js = set(re.findall(r'id="t-([a-z]+)"', js))
    kayit("Sekmeler: menü bağlantıları ile çizilen bölümler aynı", tabs_html == tabs_js,
          f"menüde: {sorted(tabs_html)}, app.js'de: {sorted(tabs_js)}")
    kayit("Sayfa: app.js bağlantısı ve sıkı CSP var",
          '<script src="app.js"></script>' in html and "Content-Security-Policy" in html and "script-src 'self'" in html)
    satir_ici = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>|\son[a-z]+=\"", html)
    kayit("Sayfa: satır içi script/olay yok (CSP bunları engeller)", not satir_ici, satir_ici[:3])
    dis = [u for u in re.findall(r'(?:src|href)="(https?://[^"]+)"', html)]
    kayit("Sayfa: dış kaynak yüklemesi yok", not dis, dis[:3])

    # hisse listesi
    try:
        h = oku_json(yol("hisseler.json"))
        items = h["items"]
        syms = [x["symbol"] for x in items]
        kotu = [s for s in syms if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^=]*", s)]
        ad_yok = [x["symbol"] for x in items if not str(x.get("name", "")).strip()]
        tekrar = sorted({s for s in syms if syms.count(s) > 1})
        kayit("Hisse listesi: geçerli, adlı, tekrarsız", not (kotu or ad_yok or tekrar) and len(syms) >= 12,
              f"{len(syms)} hisse; geçersiz sembol: {kotu}; adsız: {ad_yok}; tekrar: {tekrar}")
    except Exception as e:  # noqa: BLE001
        kayit("Hisse listesi: geçerli, adlı, tekrarsız", False, repr(e))

    # özet dosyaları
    try:
        oz = oku_json(yol("ozet.json"))
        p = oz.get("paragraphs")
        ok = (re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(oz.get("date", ""))) and isinstance(p, list) and 3 <= len(p) <= 8
              and all(isinstance(x, str) and x.strip() for x in p) and p[-1].startswith("Özetle")
              and (oz.get("asya") is None or (isinstance(oz["asya"], list) and all(isinstance(x, str) and x.strip() for x in oz["asya"]))))
        kayit("ozet.json: biçim (tarih, 3-8 paragraf, son paragraf 'Özetle', asya listesi)", bool(ok), f"date={oz.get('date')} paragraf={len(p) if isinstance(p, list) else p}")
        metin = " ".join((p if isinstance(p, list) else []) + (oz.get("asya") or []))
        sorun = []
        if re.search(r"\d", metin):
            sorun.append("rakam var")
        if re.search(r"\b(biz|bizim|kapanmıştık|gördük|izliyoruz|görüyoruz)\b", metin, re.I):
            sorun.append("birinci çoğul kişi")
        kayit("ozet.json: üslup kuralları (rakamsız, tarafsız anlatıcı)", not sorun, ", ".join(sorun), uyari=True)
    except Exception as e:  # noqa: BLE001
        kayit("ozet.json: biçim (tarih, 3-8 paragraf, son paragraf 'Özetle', asya listesi)", False, repr(e))
    try:
        g = oku_json(yol("ozet_gecmis.json"))
        kayitlar = g if isinstance(g, list) else g.get("records") or g.get("items") or []
        tarih = [x.get("date") for x in kayitlar]
        ok = (isinstance(kayitlar, list) and kayitlar and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(t)) for t in tarih)
              and tarih == sorted(tarih) and len(set(tarih)) == len(tarih))
        kayit("ozet_gecmis.json: kayıtlar tarihli, sıralı, tekrarsız", bool(ok), f"{len(tarih)} kayıt, son: {tarih[-1:] }")
    except Exception as e:  # noqa: BLE001
        kayit("ozet_gecmis.json: kayıtlar tarihli, sıralı, tekrarsız", False, repr(e))

    # görev talimatları (zamanlanmış oturumlar bunları okur)
    for ad in ("aksam", "sabah"):
        try:
            t = open(yol("gorevler", ad + ".md"), encoding="utf-8").read()
            eksik = [x for x in ("+veri:refs/remotes/origin/veri", "GÜNLÜK", "gorev-" + ad + ".txt", "ozet.json") if x not in t]
            kayit(f"Görev talimatı gorevler/{ad}.md: veri dalını zorlamalı çeker (+), günlük yazar", not eksik, f"eksik: {eksik}")
        except FileNotFoundError:
            kayit(f"Görev talimatı gorevler/{ad}.md var", False, "dosya yok")

    # workflow'lar
    try:
        import yaml
    except ImportError:
        yaml = None
    wd = yol(".github", "workflows")
    for f in sorted(os.listdir(wd)):
        if not f.endswith(".yml"):
            continue
        if yaml is None:
            kayit(f"Workflow: {f}", False, "PyYAML yok, denetlenemedi", uyari=True)
            continue
        try:
            d = yaml.safe_load(open(os.path.join(wd, f), encoding="utf-8"))
            on = d.get(True, d.get("on")) or {}
            cr = [c["cron"] for c in (on.get("schedule") or [])]
            kotu = [c for c in cr if len(c.split()) != 5]
            kayit(f"Workflow: {f} (YAML geçerli, cron biçimi, işler)", not kotu and bool(d.get("jobs")), f"cron: {kotu}")
        except Exception as e:  # noqa: BLE001
            kayit(f"Workflow: {f} (YAML geçerli, cron biçimi, işler)", False, repr(e))
    r = subprocess.run(["bash", "-n", yol(".github", "kayit.sh")], capture_output=True, text=True)
    kayit("Yayın kaydı betiği: sözdizimi", r.returncode == 0, r.stderr)


# ------------------------------------------------------------------ veri
def veri():
    p = yol("data.json")
    try:
        d = oku_json(p)
    except Exception as e:  # noqa: BLE001
        kayit("data.json: geçerli JSON (NaN/Infinity yok)", False, repr(e))
        return
    kayit("data.json: geçerli JSON (NaN/Infinity yok)", True)
    kayit("data.json: boyut makul", 20_000 < os.path.getsize(p) < 8_000_000, f"{os.path.getsize(p)} bayt")
    gerekli = ["meta", "indexes", "etfs", "breadth", "pairs", "sectors", "ai", "regime"]
    kayit("data.json: tüm bölümler var", all(k in d for k in gerekli), [k for k in gerekli if k not in d])
    m = d.get("meta", {})
    ref = m.get("ref_date")
    try:
        gen = max(dt.datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                  for x in (m["generated_at"], m.get("partial_refreshed_at") or m["generated_at"]))
        yas = (dt.datetime.now(dt.timezone.utc) - gen).total_seconds() / 60
        kayit("data.json: üretim zamanı taze (son 2 saat)", 0 <= yas < 120, f"{yas:.0f} dakika önce")
    except Exception as e:  # noqa: BLE001
        kayit("data.json: üretim zamanı taze (son 2 saat)", False, repr(e))
    idx = d.get("indexes", {})
    geride = {k: v.get("date") for k, v in idx.items() if k in ("SPX", "NASDAQ", "RUT", "VIX") and v.get("date") != ref}
    kayit("Endeksler: ABD endeksleri referans günde", not geride, geride)
    for k in ("SPX", "NASDAQ", "RUT", "VIX", "BTC", "KOSPI", "NIKKEI", "DXY"):
        if k not in idx or idx[k].get("close") in (None, 0):
            kayit(f"Endeks verisi: {k}", False, "yok ya da kapanış boş", uyari=k in ("DXY",))
    asya = {k: idx.get(k, {}).get("date") for k in ("KOSPI", "NIKKEI")}
    try:
        eski = [k for k, t in asya.items() if (dt.date.fromisoformat(ref) - dt.date.fromisoformat(t)).days > 4]
    except Exception:  # noqa: BLE001
        eski = list(asya)
    kayit("Asya endeksleri: son 4 gün içinde", not eski, asya, uyari=True)
    cov = m.get("coverage") or {}
    kayit("S&P 500 kapsamı yüksek", (cov.get("ratio") or 0) >= 0.97, cov.get("missing"), uyari=(cov.get("ratio") or 0) >= 0.95)
    ai = d.get("ai", {})
    kayit("AI bölümü: tüm hisseler geldi", ai.get("available") and ai.get("count") == ai.get("requested"), f"eksik: {ai.get('missing')}", uyari=True)
    kayit("Değişenler bölümü var", bool((d.get("changes") or {}).get("items") is not None), "", uyari=True)
    prox = m.get("proxy_checks") or []
    kayit("Çapraz kontroller: S&P 500 / Nasdaq ETF ile uyumlu", prox and all(x.get("status") == "ok" for x in prox), prox)
    vix = [v for v in m.get("verification", []) if v.get("status") == "ok"]
    kayit("Çapraz kontroller: VIX resmi Cboe ile uyumlu", bool(vix), m.get("verification"), uyari=True)
    for b in ("ma50", "ma100", "ma200"):
        v = (d.get("breadth") or {}).get(b) or {}
        kayit(f"Genişlik {b}: yüzde 0-100", isinstance(v.get("pct"), (int, float)) and 0 <= v["pct"] <= 100, v)
    kayit("Sektörler: en az 10 ETF", len(d.get("sectors") or []) >= 10, len(d.get("sectors") or []))


# ------------------------------------------------------------------ site (gerçek tarayıcı)
def site():
    dizin = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else yol("site")
    for f in ("index.html", "app.js", "data.json"):
        kayit(f"Yayın klasörü: {f} var", os.path.isfile(os.path.join(dizin, f)), dizin)
    if any(s["durum"] == "hata" for s in SONUC):
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        kayit("Sayfa testi: playwright kurulu", False, "pip install playwright gerekli")
        return
    import functools
    import http.server
    import socketserver
    import threading

    class Sessiz(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: D102
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Sessiz, directory=dizin))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    ref = oku_json(os.path.join(dizin, "data.json"))["meta"]["ref_date"]
    oz = oku_json(os.path.join(dizin, "ozet.json")) if os.path.isfile(os.path.join(dizin, "ozet.json")) else None
    kotu = re.compile(r"undefined|NaN|\[object|Infinity")
    try:
        with sync_playwright() as pw:
            try:
                tarayici = pw.chromium.launch(channel="chrome")
            except Exception:  # noqa: BLE001
                try:
                    tarayici = pw.chromium.launch()
                except Exception as e:  # noqa: BLE001  # ortam sorunu, site sorunu değil: yayını engellemez
                    kayit("Sayfa testi: tarayıcı başlatıldı", False, repr(e)[:300], uyari=not os.environ.get("GITHUB_ACTIONS"))  # yayın hattında tarayıcı yoksa test atlanmış sayılmaz: yayın durur
                    return
            for ad, w, h in (("masaüstü", 1280, 900), ("telefon", 400, 800)):
                sayfa = tarayici.new_page(viewport={"width": w, "height": h})
                hatalar = []
                sayfa.on("pageerror", lambda e: hatalar.append("sayfa hatası: " + str(e)[:200]))
                sayfa.on("console", lambda m: hatalar.append("konsol: " + m.text[:200]) if m.type == "error" else None)
                sayfa.on("requestfailed", lambda r: hatalar.append("istek başarısız: " + r.url[-60:]))
                sayfa.on("response", lambda r: hatalar.append(f"HTTP {r.status}: {r.url[-60:]}") if r.status >= 400 else None)
                sayfa.goto(url)
                try:
                    sayfa.wait_for_selector("#app section.tab", state="attached", timeout=15000)
                except Exception:  # noqa: BLE001
                    kayit(f"Sayfa testi ({ad}): sayfa çizildi", False, (sayfa.inner_text("#app")[:200] or "boş") + " | " + " | ".join(hatalar[:3]))
                    continue
                sayfa.wait_for_timeout(500)
                kayit(f"Sayfa testi ({ad}): sayfa çizildi, hata kutusu yok", sayfa.query_selector("#app .err") is None)
                kayit(f"Sayfa testi ({ad}): üst bilgide kapanış ve güncelleme zamanı dolu",
                      "–" not in (sayfa.inner_text("#refDate") + sayfa.inner_text("#gen")), sayfa.inner_text("#refDate"))
                sekmeler = sayfa.eval_on_selector_all("nav a", "els => els.map(e => e.getAttribute('data-t'))")
                for t in sekmeler:
                    sayfa.evaluate(f"location.hash = '#{t}'")
                    sayfa.wait_for_timeout(150)
                    gorunur = sayfa.is_visible(f"#t-{t}")
                    metin = sayfa.inner_text(f"#t-{t}") if gorunur else ""
                    m = kotu.search(metin)
                    kayit(f"Sayfa testi ({ad}): sekme '{t}' görünüyor, dolu, undefined/NaN yok",
                          gorunur and len(metin.strip()) > 80 and not m,
                          "görünmüyor" if not gorunur else (f"metinde '{m.group(0)}': ..." + metin[max(0, m.start() - 60):m.end() + 40]) if m else f"kısa içerik ({len(metin.strip())})")
                    taşma = sayfa.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    kayit(f"Sayfa testi ({ad}): sekme '{t}' yatay taşma yok", taşma <= 2, f"{taşma}px taşıyor", uyari=True)
                n = sayfa.evaluate("""() => { let n = 0; document.querySelectorAll('button, th, [data-tip], .ddb').forEach(e => { e.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); n++; }); document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); return n; }""")
                sayfa.wait_for_timeout(200)
                kayit(f"Sayfa testi ({ad}): {n} öğeye tıklandı, hata/başarısız istek yok", not hatalar, " | ".join(hatalar[:4]))
                if oz and oz.get("date") == ref:
                    sayfa.evaluate("location.hash = '#genel'")
                    sayfa.wait_for_timeout(150)
                    g = sayfa.inner_text("#t-genel")
                    kayit(f"Sayfa testi ({ad}): günün özeti Genel sekmesinde görünüyor", oz["paragraphs"][0][:30] in g, f"özet tarihi {oz['date']}")
                    if oz.get("asya"):
                        kayit(f"Sayfa testi ({ad}): Asya ve Bitcoin eki görünüyor", "Asya ve Bitcoin" in g)
                sayfa.close()
            tarayici.close()
    except Exception as e:  # noqa: BLE001
        kayit("Sayfa testi: tarayıcı çalıştı", False, repr(e)[:400])
    finally:
        srv.shutdown()


# ------------------------------------------------------------------ canli
def canli():
    url = os.environ.get("URL", "").rstrip("/") + "/"
    run_id = os.environ.get("RUN_ID", "")
    import random
    t = random.randint(1, 10**9)
    try:
        idx_c = http(f"{url}index.html?t={t}").decode()
        app_c = http(f"{url}app.js?t={t}")
    except Exception as e:  # noqa: BLE001
        kayit("Yayın: index.html ve app.js açılıyor", False, repr(e))
        return
    kayit("Yayın: index.html ve app.js açılıyor", True)
    repo_app = open(yol("app.js"), "rb").read()
    kayit("Yayın: app.js depodakiyle birebir aynı", hashlib.sha256(app_c).digest() == hashlib.sha256(repo_app).digest())
    repo_idx = open(yol("index.html"), encoding="utf-8").read()
    kayit("Yayın: index.html depodakiyle aynı (sürüm eki hariç)", re.sub(r"app\.js\?v=\d+", "app.js", idx_c) == repo_idx)
    if run_id:
        kayit("Yayın: sayfa bu çalışmanın sürüm ekini taşıyor", f"app.js?v={run_id}" in idx_c)
    try:
        oz_c = json.loads(http(f"{url}ozet.json?t={t}"))
        oz_r = oku_json(yol("ozet.json"))
        kayit("Yayın: ozet.json depodakiyle aynı", oz_c == oz_r, f"yayında {oz_c.get('date')}, depoda {oz_r.get('date')}", uyari=True)
    except Exception as e:  # noqa: BLE001
        kayit("Yayın: ozet.json açılıyor", False, repr(e), uyari=True)


# ------------------------------------------------------------------ nöbetçi
def gh(yolu):
    return json.loads(http("https://api.github.com/repos/" + os.environ["REPO"] + yolu,
                           headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json",
                                    "User-Agent": "saglik-kontrol"}))


def gh_post(yolu, govde):
    rq = urllib.request.Request("https://api.github.com/repos/" + os.environ["REPO"] + yolu, data=json.dumps(govde).encode(), method="POST",
                                headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json",
                                         "User-Agent": "saglik-kontrol", "Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=30) as r:
        return r.status


def gh_dosya(dal, ad):
    try:
        j = gh(f"/contents/{ad}?ref={dal}")
        return base64.b64decode(j["content"]).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return f"(okunamadı: {e!r})"[:200]


def son_islem_gunu(simdi_et):
    """Veri yayını beklenen en son hafta içi gün: ET 18:30'dan sonra o günün verisi beklenir (tatil ayrımı çalışma sonucundan yapılır)."""
    d = simdi_et.date()
    if (simdi_et.hour, simdi_et.minute) < (18, 30):
        d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def nobetci(simdi=None, canli_veri=None, calismalar=None, ozet=None, dosya=None, tetikle=None, asia_calismalar=None):
    et = ZoneInfo("America/New_York")
    simdi = simdi or dt.datetime.now(dt.timezone.utc)
    sim_et = simdi.astimezone(et)
    D = son_islem_gunu(sim_et)
    url = os.environ.get("URL", "").rstrip("/") + "/"
    dosya = dosya or gh_dosya
    tetikle = tetikle or gh_post
    try:
        veri_c = canli_veri or json.loads(http(f"{url}data.json?t={int(simdi.timestamp())}"))
    except Exception as e:  # noqa: BLE001
        kayit("Yayın: data.json açılıyor", False, repr(e))
        return
    ref = dt.date.fromisoformat(veri_c["meta"]["ref_date"])
    if ref >= D:
        kayit(f"Veri güncel: yayındaki kapanış {ref}, beklenen {D}", True)
    else:
        bas = dt.datetime(D.year, D.month, D.day, 16, 0, tzinfo=et)
        try:
            runs = calismalar if calismalar is not None else gh("/actions/workflows/update.yml/runs?per_page=15")["workflow_runs"]
        except Exception as e:  # noqa: BLE001
            kayit("Güncelleme çalışmaları okunuyor", False, repr(e))
            return
        yeni = [r for r in runs if dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= bas]
        durum = dosya("veri", "durum.json")
        if any(r["conclusion"] == "success" for r in yeni):
            kayit(f"Veri {ref}'de kaldı ama {D} için başarılı çalışma var (tatil/yeni veri yok olabilir)", True)
        elif any(r["status"] in ("queued", "in_progress") for r in yeni):
            gecen = (simdi - max(dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in yeni)).total_seconds() / 60
            kayit(f"Güncelleme sürüyor ({gecen:.0f} dk)", gecen < 90, "çalışma 90 dakikadan uzun sürdü, takılmış olabilir")
        elif yeni:
            kayit(f"{D} için güncelleme BAŞARISIZ oldu", False, f"çalışma: {[r['conclusion'] for r in yeni]}; veri dalı durum.json: {durum}")
        else:
            neden = f"{sim_et:%H:%M} ET; son çalışmalar: {[(r['created_at'], r['event'], r['conclusion']) for r in runs[:3]]}"
            try:
                tetikle("/actions/workflows/update.yml/dispatches", {"ref": "main"})
                kayit(f"{D} için zamanlanmış güncelleme HİÇ BAŞLAMADI (GitHub zamanlayıcısı gecikmesi); nöbetçi kendisi başlattı", False, neden, uyari=True)
            except Exception as e:  # noqa: BLE001
                kayit(f"{D} için zamanlanmış güncelleme HİÇ BAŞLAMADI ve otomatik başlatılamadı", False, f"{neden}; {e!r}")
    # Asya yenilemesi (yalnız hafta içi, UTC 08:30-20:00): KOSPI ve Nikkei bugünün tarihinde olmalı; tatil ayrımı çalışma sonucundan yapılır
    if simdi.weekday() < 5 and (8 * 60 + 30) <= simdi.hour * 60 + simdi.minute < 20 * 60:
        bugun = simdi.date().isoformat()
        geri = [k for k in ("KOSPI", "NIKKEI") if veri_c.get("indexes", {}).get(k, {}).get("date") != bugun]
        if geri:
            try:
                ar = asia_calismalar if asia_calismalar is not None else gh("/actions/workflows/asia.yml/runs?per_page=15")["workflow_runs"]
            except Exception as e:  # noqa: BLE001
                ar = None
                kayit("Asya yenileme çalışmaları okunuyor", False, repr(e))
            if ar is not None:
                bas = dt.datetime(simdi.year, simdi.month, simdi.day, 6, 0, tzinfo=dt.timezone.utc)
                yeni = [r for r in ar if dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= bas]
                if any(r["conclusion"] == "success" for r in yeni) or any(r["status"] in ("queued", "in_progress") for r in yeni):
                    kayit(f"Asya endeksleri ({geri}) bugünün tarihinde değil ama yenileme çalıştı/sürüyor (tatil ya da Yahoo gecikmesi olabilir)", True)
                elif yeni:
                    kayit(f"Asya yenilemesi BAŞARISIZ oldu ({geri} bugünün tarihinde değil)", False, f"çalışmalar: {[r['conclusion'] for r in yeni]}; veri dalı durum.json: {dosya('veri', 'durum.json')}")
                else:
                    try:
                        tetikle("/actions/workflows/asia.yml/dispatches", {"ref": "main", "inputs": {"only": "KOSPI,NIKKEI"}})
                        kayit(f"Asya yenilemesi HİÇ BAŞLAMADI (GitHub zamanlayıcısı gecikmesi); nöbetçi kendisi başlattı", False, f"{simdi:%H:%M} UTC; {geri} bugünün tarihinde değil", uyari=True)
                    except Exception as e:  # noqa: BLE001
                        kayit("Asya yenilemesi HİÇ BAŞLAMADI ve otomatik başlatılamadı", False, repr(e))
        else:
            kayit("Asya endeksleri bugünün tarihinde", True)
    # özet
    try:
        oz = ozet or json.loads(http(f"{url}ozet.json?t={int(simdi.timestamp())}"))
    except Exception as e:  # noqa: BLE001
        kayit("Yayın: ozet.json açılıyor", False, repr(e))
        return
    ref_oz = dt.date.fromisoformat(oz["date"])
    if ref_oz >= ref:
        kayit(f"Günün özeti güncel ({ref_oz})", True)
    else:
        gec = sim_et >= dt.datetime(ref.year, ref.month, ref.day, 21, 30, tzinfo=et) and ref >= D
        if gec:
            kayit(f"Günün özeti {ref} için YAZILMADI (özet {ref_oz}'de kaldı)", False, "görev günlüğü (gorev-aksam.txt): " + dosya("gorev", "gorev-aksam.txt")[:450])
        else:
            kayit(f"Günün özeti henüz {ref_oz} (bekleniyor)", True)
    if ref_oz >= ref and not oz.get("asya"):
        sonraki = ref + dt.timedelta(days=1)
        while sonraki.weekday() >= 5:
            sonraki += dt.timedelta(days=1)
        sinir = dt.datetime(sonraki.year, sonraki.month, sonraki.day, 12, 30, tzinfo=dt.timezone.utc)
        if simdi >= sinir and ref >= D - dt.timedelta(days=3):
            kayit(f"Sabah Asya/Bitcoin eki YAZILMADI ({ref} özeti için)", False, "görev günlüğü (gorev-sabah.txt): " + dosya("gorev", "gorev-sabah.txt")[:450])


MODLAR = {"onkontrol": onkontrol, "veri": veri, "site": site, "canli": canli, "nobetci": nobetci}


def main():
    mod = sys.argv[1] if len(sys.argv) > 1 else ""
    if mod not in MODLAR:
        print("kullanım: saglik.py", "|".join(MODLAR))
        return 2
    MODLAR[mod]()
    hatalar = [s for s in SONUC if s["durum"] == "hata"]
    cikti = sys.argv[sys.argv.index("--cikti") + 1] if "--cikti" in sys.argv else None
    if cikti:
        onceki = []
        if os.path.exists(cikti):
            try:
                onceki = json.load(open(cikti, encoding="utf-8"))
            except Exception:  # noqa: BLE001
                onceki = []
        with open(cikti, "w", encoding="utf-8") as f:
            json.dump(onceki + [dict(s, mod=mod) for s in SONUC], f, ensure_ascii=False, indent=1)
    print(f"\n{mod}: {len(SONUC)} kontrol, {len(hatalar)} hata, {sum(1 for s in SONUC if s['durum'] == 'uyari')} uyarı")
    if hatalar:
        kok = f"[{mod}] {hatalar[0]['ad']}: {hatalar[0]['ayrinti']}"
        for h in hatalar:
            print(f"::error title=Kontrol başarısız ({mod}): {h['ad']}::{h['ayrinti']}".replace("\n", "%0A"))
        go = os.environ.get("GITHUB_OUTPUT")
        if go:
            with open(go, "a", encoding="utf-8") as f:
                f.write("kok=" + kok.replace("\n", " ")[:600] + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
