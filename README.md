# Piyasa Genel Bakış

ABD piyasaları için sade, kendini güncelleyen Türkçe gösterge paneli: https://mbay9.github.io/piyasa-paneli/

GitHub Actions her işlem günü ABD kapanışından sonra `update.py` ile `data.json` üretir, `validate.py` ile denetler ve GitHub Pages'e yayınlar. Denetim başarısız olursa eski sayfa yerinde kalır.

- **Makro rejim:** S&P 500, 200 günlük ortalamanın %1,5 üzerinde iki kapanış = RİSK-ON, %1,5 altında iki kapanış = RİSK-OFF, arada önceki durum korunur. Kural `test_regime.py` ile test edilir.
- **Veri:** Yahoo Finance (yfinance). VIX, Cboe'nin resmi dosyasıyla; S&P 500 ve Nasdaq, SPY ve QQQ ile çapraz kontrol edilir. S&P 500 listesi resmi kaynaktan alınır.
- **ETF bileşenleri:** `holdings.json` elle ayda bir yenilenir (SOXX, SMH, DRAM resmi bileşen dosyaları).
- **Yerelde çalıştırma:** `pip install -r requirements.txt && python test_regime.py && python update.py && python validate.py`

