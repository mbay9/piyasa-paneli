# Nöbetçi görevi (arıza bildirimi)

Amaç: ABD kapanışından sonra site güncellenmediyse bunu fark etmek, bir kez kendiliğinden düzeltmeyi denemek ve düzelmezse kullanıcıya telefon bildirimi gidecek şekilde açık bir ARIZA iletisiyle bitirmek. Her şey yolundaysa sessiz kal (tek satır "Sorun yok").

Kurallar: hiçbir rakam uydurma; siteyi (mbay9.github.io) KULLANMA, yalnız depodaki dalları oku; main dalına yalnız tetik dosyası yazabilirsin, başka dosyaya dokunma.

1) Depoyu hazırla: /home/claude/piyasa-paneli varsa `git pull -q --rebase origin main`, yoksa add_repo (owner mbay9, repo piyasa-paneli, access push) ile ekleyip oraya klonla, register_repo_root çağır.

2) Bugünün New York tarihini al: `TZ=America/New_York date +%F` ve gününü (`date +%u`). Cumartesi/pazar ya da ABD borsa tatiliyse (2026: 26 Kas, 25 Ara; 2027: 1 Oca, 18 Oca, 15 Şub, 26 Mar, 31 May, 18 Haz, 5 Tem, 6 Eyl, 25 Kas, 24 Ara) "Tatil, kontrol yok" yaz ve 6. adıma geç.

3) Durumu oku: `git fetch -q origin +veri:refs/remotes/origin/veri` sonra `git show origin/veri:data.json` (meta.ref_date, meta.generated_at, meta.ikinci_kaynak) ve `git show origin/veri:durum.json` (build, deploy, canli_dogrulandi, data_ref_date, hata, kok_neden). Ayrıca main'deki ozet.json "date" alanı.
   - SAĞLIKLI: meta.ref_date == bugünün New York tarihi VE durum.json canli_dogrulandi true.

4) Sağlıklı değilse BİR kez düzeltmeyi dene: `gh api -X POST repos/mbay9/piyasa-paneli/actions/workflows/update.yml/dispatches -f ref=main`; gh çalışmazsa `date -u +%FT%TZ > tetik/guncelle.txt`, yalnız bu dosyayı commit et (mesaj "Tetik: guncelle.txt") ve main'e push et. Sonra en fazla 25 dakika bekle: 2 dakikada bir 3. adımdaki fetch'i yinele (`until ...; do sleep 120; done`), sağlıklı olunca dur.

5) Sonuç iletisi (son yanıtın TAM olarak bu biçimde olsun):
   - Sağlıklıysa ve ozet.json date == ref_date ise: `Sorun yok: <ref_date> verisi ve özeti yayında.`
   - Veri sağlıklı ama özet eksikse: `UYARI: <ref_date> verisi yayında ama günün özeti henüz yazılmadı (yedek özet görevi 21:05 ET'de dener).`
   - meta.ikinci_kaynak içinde status "bad" olan varsa ek satır: `UYARI: ikinci kaynak uyuşmazlığı: <id> Yahoo <yahoo> / <kaynak adı> <other> (%<diff_pct>).`
   - Hâlâ sağlıklı değilse: `ARIZA: site güncellenmedi. Yayındaki veri <meta.ref_date>, beklenen <bugün>. Neden: <durum.json kok_neden ya da hata alanı aynen; boşsa "güncelleme çalışmadı ya da bitmedi">. Tetik denendi: <dispatch|tetik dosyası|başarısız>.`

6) GÜNLÜK (zorunlu): boş bir geçici dizinde `git init`, origin'i klondan al, `git fetch origin +gorev:refs/remotes/origin/gorev` ile dalı çekip (`git checkout -b gorev origin/gorev`; yoksa `--orphan gorev`) yalnız gorev-nobetci.txt dosyasını yaz (UTC ve ET zamanı, 5. adımdaki sonuç iletisi, okuduğun değerler), commit et ve `git push origin gorev` (başka dosyaları silme; reddedilirse fetch + rebase ile yeniden dene).
