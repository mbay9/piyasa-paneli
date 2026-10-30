#!/usr/bin/env bash
# Yayın kaydı. Canlı sitedeki data.json'ı ve son çalışmanın sonucunu (durum.json) 'veri' dalına yazar.
# Amaç: günün özetini yazan görevler güncel veriyi siteden (önbellek, erişim kısıtı) değil doğrudan depodan okusun
# ve güncellemenin başarısız olup olmadığını, nedeniyle birlikte görebilsin. Dal her seferinde tek commit olarak yeniden yazılır (geçmiş birikmez).
# Girdiler (ortam): GH_TOKEN REPO URL EXPECT BUILD DEPLOY EVENT RUN_URL RUN_ID HATA KOK KONTROL (yapı denetimlerinin uyarı/hata listesi, JSON)
set -uo pipefail

live_ok=false
if [ "${BUILD:-}" = success ] && [ "${DEPLOY:-}" = success ] && [ -n "${EXPECT:-}" ]; then
  for i in 1 2 3 4 5 6 7 8 9; do
    if curl -fsS --max-time 30 "${URL}data.json?t=$RANDOM$i" -o live.json; then
      got=$(jq -r '(.meta.partial_refreshed_at // "") + "|" + .meta.generated_at' live.json 2>/dev/null || true)
      if [ "$got" = "$EXPECT" ]; then live_ok=true; break; fi
    fi
    sleep 20
  done
fi

# Yayının sağlığı: canlı sayfa depodakiyle aynı mı (app.js, index.html, ozet.json, sürüm eki)?
echo '[]' > canli.json
if [ "$live_ok" = true ]; then python3 saglik.py canli --cikti canli.json || true; fi
canli_hata=$(jq -r '[.[]|select(.durum=="hata")]|(.[0] | if . then "[canlı] \(.ad): \(.ayrinti)" else "" end)' canli.json)

git init -q v
cd v
git remote add origin "${ORIGIN:-https://x-access-token:${GH_TOKEN}@github.com/${REPO}.git}"
if git fetch -q --depth 1 origin veri; then git checkout -q -b onceki FETCH_HEAD; fi

if [ "$live_ok" = true ]; then cp ../live.json data.json; fi
ref=$(jq -r '.meta.ref_date // empty' data.json 2>/dev/null || true)
jq -n \
  --arg utc "$(date -u +%FT%TZ)" --arg et "$(TZ=America/New_York date '+%F %H:%M')" \
  --arg olay "${EVENT:-}" --arg run "${RUN_URL:-}" --arg build "${BUILD:-}" --arg deploy "${DEPLOY:-}" \
  --argjson canli "$live_ok" --arg ref "$ref" --arg hata "${HATA:-}" --arg kok "${KOK:-}" --arg chata "$canli_hata" \
  --argjson kontrol "$(echo "${KONTROL:-[]}" | jq -c . 2>/dev/null || echo '[]')" --slurpfile canlik ../canli.json \
  '{kayit_utc:$utc, kayit_et:$et, olay:$olay, run:$run, build:$build, deploy:$deploy, canli_dogrulandi:$canli, data_ref_date:$ref,
    kok_neden: (if $kok != "" then $kok elif $hata != "" then $hata elif $chata != "" then $chata else "" end),
    hata:$hata, kontroller: ($kontrol + [$canlik[0][]|select(.durum!="ok")|{ad,durum,ayrinti}])}' > durum.json

git checkout -q --orphan yeni
git add -A
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" commit -q -m "Yayın kaydı ${GITHUB_RUN_ID:-}"
git push -q --force origin yeni:veri
echo "veri dalı yazıldı: canlı doğrulandı=$live_ok, data ref_date=$ref"
# canlı sayfa kontrolü başarısızsa iş de kırmızı olsun (GitHub e-posta ile haber verir); kayıt zaten yazıldı
if [ -n "$canli_hata" ]; then echo "::error title=Yayın sağlık kontrolü başarısız::$canli_hata"; exit 1; fi
