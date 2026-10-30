# Piyasa Genel Bakış

ABD piyasaları için sade, kendini güncelleyen Türkçe gösterge paneli: https://mbay9.github.io/piyasa-paneli/

GitHub Actions her işlem günü ABD kapanışından sonra `update.py` ile `data.json` üretir, `validate.py` ile denetler ve GitHub Pages'e yayınlar. Denetim başarısız olursa eski sayfa yerinde kalır.

- **Makro rejim:** S&P 500, 200 günlük ortalamanın %1,5 üzerinde iki kapanış = RİSK-ON, %1,5 altında iki kapanış = RİSK-OFF, arada önceki durum korunur. Kural `test_regime.py` ile test edilir.
- **Veri:** Yahoo Finance (yfinance). VIX, Cboe'nin resmi dosyasıyla; S&P 500 SPY ile, Nasdaq Composite ONEQ ile çapraz kontrol edilir. S&P 500 listesi resmi kaynaktan alınır.
- **AI hisse listesi:** `hisseler.json` (takip edilen hisseler, elle düzenlenir).
- **Yerelde çalıştırma:** `pip install -r requirements.txt && python test_regime.py && python update.py && python validate.py`

- **Sağlık kontrolü (`saglik.py`):** yayın bu kontrollerden geçmeden çıkmaz. `onkontrol` kod, sayfa kimlikleri, hisse listesi, özet dosyaları ve workflow'ları; `veri` üretilen veriyi; `site` sayfayı gerçek tarayıcıda (masaüstü ve telefon, her sekme, tıklamalar, `undefined/NaN`); `canli` yayındaki sayfanın depodakiyle aynı olduğunu denetler. Sonuç ve ilk hatanın nedeni (`kok_neden`) `veri` dalındaki `durum.json`'a yazılır. `kontrol.yml` her kod değişikliğinde çalışır; zamanlanmış nöbetçisi güncelleme ya da günün özeti zamanında gelmezse nedeniyle birlikte kırmızıya döner.
- **`veri` dalı:** her yayında güncel `data.json` ve `durum.json` (çalışma sonucu, hata nedeni) buraya yazılır; günün özetini yazan görevler siteyi değil bu dalı okur. Dal her seferinde baştan yazılır (`git fetch origin +veri:refs/remotes/origin/veri`).
- **Kendini onarma:** zamanlanmış güncelleme ya da Asya yenilemesi hiç başlamazsa `kontrol.yml` nöbetçisi onu kendisi başlatır. Günün özeti ve sabah eki görevlerinin talimatları `gorevler/aksam.md` ve `gorevler/sabah.md` dosyalarındadır (zamanlanmış oturumlar bunları okur; `onkontrol` varlığını denetler).
