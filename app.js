(function () {
  var MONTHS = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
  function fmtDate(d) { if (!d) return "–"; var a = d.split("-"); return parseInt(a[2], 10) + " " + MONTHS[parseInt(a[1], 10) - 1] + " " + a[0]; }
  function num(v, dec) { return v === null || v === undefined ? "–" : Number(v).toLocaleString("tr-TR", { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
  function sgn(v) { return v > 0 ? "+" : v < 0 ? "−" : ""; }
  function pc(v, dec) { return v === null || v === undefined ? "–" : sgn(v) + num(Math.abs(v), dec === undefined ? 2 : dec) + "%"; }
  function pt(v, dec) { return v === null || v === undefined ? "–" : sgn(v) + num(Math.abs(v), dec === undefined ? 1 : dec) + " puan"; }
  function cls(v, risk) { if (v === null || v === undefined || v === 0) return "neu"; if (risk) return v > 0 ? "rsk" : "pos"; return v > 0 ? "pos" : "neg"; }
  function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function spark(vals) {
    vals = (vals || []).filter(function (x) { return x !== null; });
    if (vals.length < 2) return "";
    var W = 84, H = 22, p = 2, mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals), r = (mx - mn) || 1;
    var pts = vals.map(function (y, i) { return (p + i * (W - 2 * p) / (vals.length - 1)).toFixed(1) + "," + (H - p - (y - mn) / r * (H - 2 * p)).toFixed(1); }).join(" ");
    var up = vals[vals.length - 1] >= vals[0];
    return '<svg class="sp" viewBox="0 0 ' + W + ' ' + H + '" aria-hidden="true"><polyline points="' + pts + '" fill="none" stroke="' + (up ? "var(--up)" : "var(--down)") + '" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  }
  function h2(t) { return '<h2>' + t + '</h2>'; }
  function sub(t) { return '<p class="sub">' + t + '</p>'; }
  function stat(k, v, d, c) { return '<div class="stat"><div class="k">' + k + '</div><div class="v ' + (c || "") + '">' + v + '</div><div class="d">' + (d || "") + '</div></div>'; }
  function ma(flag, dist) {
    if (flag === null || flag === undefined) return '<span class="neu">–</span>';
    return '<span class="' + (flag ? "pos" : "neg") + '">' + (flag ? "üstünde" : "altında") + '</span><small>' + pc(dist, 1) + '</small>';
  }
  function vtext(m) {
    var v = m && m.verify; if (!v) return "";
    if (v.status === "ok") return '<span class="dot ok"></span>';
    if (v.status === "warn") return '<span class="dot warn"></span>';
    return "";
  }

  function regime(rg) {
    if (!rg) return "";
    var col = rg.label === "RISK_ON" ? "pos" : rg.label === "RISK_OFF" ? "neg" : "rsk";
    var bars = rg.components.map(function (c) {
      return '<div class="comp"><div class="n">' + esc(c.name) + '<small>' + esc(c.note) + '</small></div><div class="track"><i style="width:' + c.score + '%"></i></div><div class="neu" style="text-align:right">' + num(c.score, 0) + '</div></div>';
    }).join("");
    return h2("Makro rejim") +
      '<div class="score"><span class="big">' + num(rg.score, 0) + '</span><span class="lab ' + col + '">' + esc(rg.label.replace("_", " ")) + '</span></div>' +
      '<div style="margin-top:14px">' + bars + '</div>' + sub("Kural tabanlı skor: bileşenlerin eşit ağırlıklı ortalaması. 65 ve üstü RISK ON, 40 altı RISK OFF.");
  }

  function levels(d) {
    var rows = "";
    Object.keys(d.indexes).forEach(function (k) {
      var m = d.indexes[k], risk = k === "VIX";
      rows += '<tr><td><b>' + k + '</b>' + vtext(m) + '<small>' + esc(m.name) + '</small></td><td>' + num(m.close, 2) + '</td><td class="' + cls(m.d1, risk) + '">' + pc(m.d1) + '</td><td class="' + cls(m.d5, risk) + '">' + pc(m.d5) + '</td><td class="' + cls(m.d20, risk) + '">' + pc(m.d20) + '</td><td class="' + cls(m.from_high) + '">' + pc(m.from_high, 1) + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above100, m.dist100) + '</td><td>' + ma(m.above200, m.dist200) + '</td></tr>';
    });
    return h2("Seviyeler") + '<div class="tw"><table><thead><tr><th>Gösterge</th><th>Son</th><th>1G</th><th>5G</th><th>20G</th><th>Zirveye uzaklık</th><th>SMA 50</th><th>SMA 100</th><th>SMA 200</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      sub("Noktalı satırlar resmi kaynakla doğrulandı. Değişimler işlem günü bazındadır. KOSPI ve Nikkei kendi borsalarının kapanışıdır, ABD kapanışından önce biter. 2 ve 10 yıllık getiriler yalnızca makro rejim skorunda kullanılır. Petrol, Altın ve Gümüş ön ay vadeli sözleşme fiyatıdır; sözleşme yenilendiğinde (roll) fiyatta küçük süreksizlik olabilir. Zirveye uzaklık son 252 işlem gününün en yüksek kapanışına göredir.").replace('<p class="sub">', '<p class="fine">');
  }

  function trend(d) {
    var rows = [];
    ["SPX", "NASDAQ", "RUT", "WTI", "BRENT", "KOSPI", "NIKKEI"].forEach(function (k) { if (d.indexes[k]) rows.push([k, d.indexes[k]]); });
    ["SPY", "QQQ", "IWM", "RSP", "QQQE", "RWJ"].forEach(function (k) { if (d.etfs[k]) rows.push([k, d.etfs[k]]); });
    var body = rows.map(function (x) {
      var m = x[1], tc = m.trend === "Yükseliş" ? "pos" : m.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + x[0] + '</b></td><td class="' + tc + '">' + esc(m.trend) + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above100, m.dist100) + '</td><td>' + ma(m.above200, m.dist200) + '</td>' +
        '<td class="' + cls(m.from_high) + '">' + pc(m.from_high, 1) + '</td><td>' + (m.vol_vs20 === null ? '<span class="neu">–</span>' : '<span class="' + (m.vol_vs20 >= 30 ? "rsk" : "") + '">' + pc(m.vol_vs20, 0) + '</span>') + '</td><td>' + (m.vol_vs50 === null ? '<span class="neu">–</span>' : pc(m.vol_vs50, 0)) + '</td></tr>';
    }).join("");
    return h2("Trend ve hacim") + '<div class="tw"><table><thead><tr><th>Sembol</th><th>Trend</th><th>SMA 50</th><th>SMA 100</th><th>SMA 200</th><th>Zirveye uzaklık</th><th>Hacim / 20G</th><th>Hacim / 50G</th></tr></thead><tbody>' + body + '</tbody></table></div>' +
      '<p class="fine">Trend: kapanış &gt; SMA50 &gt; SMA200 yükseliş, tersi düşüş, diğerleri yatay. Hacim, son günün önceki 20 ve 50 günün ortalamasına farkıdır. Endeks ve vadeli sözleşme hacimleri Yahoo verisinde güvenilir olmadığı için yalnızca ETF satırlarında gösterilir.</p>';
  }

  function notes(n) {
    if (!n || !n.length) return "";
    return h2("Risk notları") + n.map(function (x) {
      var c = { ok: "ok", warn: "warn", bad: "bad" }[x.level] || "";
      return '<div class="note"><b><span class="dot ' + c + '"></span>' + esc(x.title) + '</b><span>' + esc(x.text) + '</span></div>';
    }).join("");
  }

  function breadth(b) {
    if (!b || !b.ma50) return h2("Piyasa genişliği") + sub("Hisse listesi alınamadığı için hesaplanmadı.");
    var s = [50, 100, 200].map(function (n) {
      var m = b["ma" + n]; if (!m) return "";
      return stat(n + " günlük ortalama üstü", "%" + num(m.pct, 1), m.above + " / " + m.total + " hisse · 1G " + pt(m.d1) + " · 5G " + pt(m.d5));
    }).join("") + stat("52 hafta", '<span class="pos">' + num(b.new_highs, 0) + '</span> <span class="mute">/</span> <span class="neg">' + num(b.new_lows, 0) + '</span>', "yeni zirve / yeni dip");
    return h2("Piyasa genişliği") + sub("S&P 500 hisselerinin kaçı ortalamalarının üstünde. " + fmtDate(b.date)) + '<div class="stats">' + s + '</div>';
  }

  function pairs(p) {
    var rows = p.map(function (x) {
      if (!x.available) return '<tr><td><b>' + x.a + ' / ' + x.b + '</b></td><td colspan="5" class="neu">Veri alınamadı</td></tr>';
      var vc = x.verdict === "GENİŞ" ? "pos" : x.verdict === "DAR" ? "rsk" : "neu";
      return '<tr><td><b>' + x.a + ' / ' + x.b + '</b><small>' + esc(x.label) + '</small></td><td class="' + cls(x.ret20_a) + '">' + pc(x.ret20_a) + '</td><td class="' + cls(x.ret20_b) + '">' + pc(x.ret20_b) + '</td><td class="' + cls(x.ret20_diff) + '">' + pt(x.ret20_diff, 2) + '</td><td class="' + vc + '"><b>' + x.verdict + '</b></td></tr>';
    }).join("");
    return h2("Dar mı geniş mi") + '<div class="tw"><table><thead><tr><th>Çift</th><th>Eşit ağırlık 20G</th><th>Ağırlıklı 20G</th><th>Fark</th><th>Karar</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<p class="fine">Eşit ağırlıklı ETF 20 günde 1 puan veya daha fazla geride ise yükseliş DAR (az sayıda büyük hisse taşıyor), 1 puan veya fazla öndeyse GENİŞ.</p>';
  }

  var SEC_SORT = { k: "rel20", dir: -1 };
  function sectors(rows) {
    if (!rows || !rows.length) return "";
    var cols = [["symbol", "Sektör"], ["status", "Durum"], ["rel20", "SPY'a göre 20G"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["from_high", "Zirveye uzaklık"], ["trend", "Trend"], ["dist50", "SMA 50"], ["dist100", "SMA 100"], ["dist200", "SMA 200"], ["vol_vs20", "Hacim / 20G"]];
    var sorted = rows.slice().sort(function (x, y) {
      var k = SEC_SORT.k, u = x[k], v = y[k];
      if (u === null || u === undefined) return 1; if (v === null || v === undefined) return -1;
      if (typeof u === "string") return u.localeCompare(v, "tr") * SEC_SORT.dir;
      return (u - v) * SEC_SORT.dir;
    });
    var head = cols.map(function (c) { return '<th class="s" data-t="sec" data-k="' + c[0] + '">' + c[1] + (SEC_SORT.k === c[0] ? (SEC_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    var opts = cols.map(function (c) { return '<option value="' + c[0] + '"' + (SEC_SORT.k === c[0] ? " selected" : "") + '>' + c[1] + '</option>'; }).join("");
    var body = sorted.map(function (s) {
      var sc = { "Lider": "pos", "Toparlanıyor": "neu", "Zayıflıyor": "rsk", "Geride": "neg" }[s.status] || "";
      var tc = s.trend === "Yükseliş" ? "pos" : s.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + s.symbol + '</b> <span class="mute">' + esc(s.name) + '</span></td><td class="' + sc + '">' + esc(s.status) + '</td><td class="' + cls(s.rel20) + '">' + pt(s.rel20, 2) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td>' +
        '<td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td><td class="' + tc + '">' + esc(s.trend || "–") + '</td><td>' + ma(s.above50, s.dist50) + '</td><td>' + ma(s.above100, s.dist100) + '</td><td>' + ma(s.above200, s.dist200) + '</td>' +
        '<td>' + (s.vol_vs20 === null || s.vol_vs20 === undefined ? "–" : pc(s.vol_vs20, 0)) + '</td></tr>';
    }).join("");
    return h2("Sektör liderliği") + '<div class="sortbar"><label for="secsort">Sırala</label><select id="secsort">' + opts + '</select></div><div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>' +
      '<p class="fine">Başlığa tıklayınca o sütuna göre sıralanır; tekrar tıklayınca yön değişir. Lider: SPY\'dan güçlü ve SMA50 üstünde. Toparlanıyor: güçlü ama altında. Zayıflıyor: zayıf ama üstünde. Geride: ikisi de zayıf. Zirveye uzaklık son 252 işlem gününün en yüksek kapanışına göredir.</p>';
  }

  var AI_SORT = { k: "d20", dir: -1 };
  function aiTable(a) {
    var cols = [["symbol", "Hisse"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["rel20", "SPY'a göre 20G"], ["above50", "SMA 50"], ["above100", "SMA 100"], ["above200", "SMA 200"], ["from_high", "Zirveye uzaklık"], ["vol_vs20", "Hacim / 20G"]];
    var rows = a.stocks.slice().sort(function (x, y) {
      var k = AI_SORT.k, u = x[k], v = y[k];
      if (typeof u === "boolean") { u = u ? 1 : 0; v = v ? 1 : 0; }
      if (u === null || u === undefined) return 1; if (v === null || v === undefined) return -1;
      if (typeof u === "string") return u.localeCompare(v) * AI_SORT.dir;
      return (u - v) * AI_SORT.dir;
    });
    var head = cols.map(function (c) { return '<th class="s" data-k="' + c[0] + '">' + c[1] + (AI_SORT.k === c[0] ? (AI_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    function ab(f) { return f === null || f === undefined ? "–" : '<span class="' + (f ? "pos" : "neg") + '">' + (f ? "üstünde" : "altında") + '</span>'; }
    var body = rows.map(function (s) {
      return '<tr><td><b>' + esc(s.symbol) + '</b> <span class="mute">' + esc(s.name) + '</span></td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td class="' + cls(s.rel20) + '">' + pt(s.rel20, 1) + '</td><td>' + ab(s.above50) + '</td><td>' + ab(s.above100) + '</td><td>' + ab(s.above200) + '</td><td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td><td>' + (s.vol_vs20 === null ? "–" : pc(s.vol_vs20, 0)) + '</td></tr>';
    }).join("");
    var opts = cols.map(function (c) { return '<option value="' + c[0] + '"' + (AI_SORT.k === c[0] ? " selected" : "") + '>' + c[1] + '</option>'; }).join("");
    return '<div class="sortbar"><label for="aisort">Sırala</label><select id="aisort">' + opts + '</select></div><div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }
  function aiMini(list) {
    return '<div class="tw"><table><tbody>' + list.map(function (s) {
      return '<tr><td><b>' + esc(s.symbol) + '</b><small>' + esc(s.name) + '</small></td><td data-label="20G" class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td data-label="1G" class="' + cls(s.d1) + '">' + pc(s.d1) + '</td></tr>';
    }).join("") + '</tbody></table></div>';
  }
  function aiDetail(a) {
    var names = { SOXX: "SOXX · iShares", SMH: "SMH · VanEck", DRAM: "DRAM · Roundhill" };
    var rows = ["SOXX", "SMH", "DRAM"].map(function (k) {
      var d = a.detail && a.detail[k]; if (!d) return "";
      var vc = d.verdict === "GENİŞ" ? "pos" : d.verdict === "DAR" ? "rsk" : "neu";
      var top = d.top.map(function (t) { return esc(t.symbol); }).join(" · ");
      return '<tr><td><b>' + names[k] + '</b><small>liste: ' + fmtDate(d.asof) + ' · ' + d.covered + '/' + d.listed + ' hisse, ağırlığın %' + num(d.covered_weight, 0) + '\'i</small></td>' +
        '<td class="' + cls(d.w_d1) + '">' + pc(d.w_d1) + '</td><td class="' + cls(d.w_d5) + '">' + pc(d.w_d5) + '</td><td class="' + cls(d.w_d20) + '">' + pc(d.w_d20) + '</td><td class="' + cls(d.eq_d20) + '">' + pc(d.eq_d20) + '</td>' +
        '<td>%' + num(d.above50_w, 0) + '<small>sayı: %' + num(d.above50_n, 0) + '</small></td><td>%' + num(d.above100_w, 0) + '<small>sayı: %' + num(d.above100_n, 0) + '</small></td><td>%' + num(d.above200_w, 0) + '<small>sayı: %' + num(d.above200_n, 0) + '</small></td><td class="' + vc + '"><b>' + (d.verdict || "–") + '</b></td><td class="mute">' + top + '</td></tr>';
    }).join("");
    return h2("ETF içi görünüm (ağırlıklı)") + '<div class="tw"><table><thead><tr><th>ETF</th><th>Ağırlıklı 1G</th><th>Ağırlıklı 5G</th><th>Ağırlıklı 20G</th><th>Eşit ağırlıklı 20G</th><th>SMA 50 üstü (ağırlık)</th><th>SMA 100 üstü (ağırlık)</th><th>SMA 200 üstü (ağırlık)</th><th>Yapı</th><th>En büyük 5 hisse</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<p class="fine">Ağırlıklı değerler fonun gerçek pozisyon ağırlıklarıyla, eşit ağırlıklı değer her hissenin aynı payla hesaplanır. Eşit ağırlıklı 20G, ETF\'in kendi 20G getirisinin 1 puan veya fazla gerisindeyse yapı DAR (birkaç dev pozisyon taşıyor), önündeyse GENİŞ. DRAM\'de aynı hisseye hem doğrudan hem swap ile verilen pozisyonlar toplandı; ağırlıklar fon varlığının yüzdesidir ve nakit/tahvil kalemleri dahil değildir. Fonun %5,01\'lik CXMT pozisyonu borsada işlem görmediği için hesaba katılmaz.</p>';
  }
  function ai(a) {
    if (!a || !a.etfs) return h2("Yapay zeka") + sub("Bu bölüm bu güncellemede hesaplanamadı. Bir sonraki çalışmada yeniden denenir.");
    var e = a.etfs.map(function (m) {
      if (!m.available) return '<tr><td><b>' + m.symbol + '</b><small>' + esc(m.name) + '</small></td><td colspan="11" class="neu">Veri alınamadı</td></tr>';
      return '<tr><td><b>' + m.symbol + '</b><small>' + esc(m.name) + '</small></td><td>' + num(m.close, 2) + '</td><td class="' + cls(m.d1) + '">' + pc(m.d1) + '</td><td class="' + cls(m.d5) + '">' + pc(m.d5) + '</td><td class="' + cls(m.d20) + '">' + pc(m.d20) + '</td><td class="' + cls(m.d60) + '">' + pc(m.d60) + '</td>' +
        '<td class="' + cls(m.rel.spy[20]) + '">' + pt(m.rel.spy[20], 1) + '</td><td class="' + cls(m.rel.qqq[20]) + '">' + pt(m.rel.qqq[20], 1) + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above100, m.dist100) + '</td><td>' + ma(m.above200, m.dist200) + '</td></tr>';
    }).join("");
    var out = h2("Yapay zeka ve yarı iletken ETF'leri") +
      '<div class="tw"><table><thead><tr><th>ETF</th><th>Son</th><th>1G</th><th>5G</th><th>20G</th><th>60G</th><th>SPY\'a göre 20G</th><th>QQQ\'ya göre 20G</th><th>SMA 50</th><th>SMA 100</th><th>SMA 200</th></tr></thead><tbody>' + e + '</tbody></table></div>';
    if (!a.available) return out + sub("Bileşen verisi yetersiz: " + esc(a.error || ""));
    var b = a.breadth;
    out += aiDetail(a) + h2("Genişlik (tüm bileşenler birlikte)") + '<div class="stats">' +
      stat("SMA 50 üstü", "%" + num(b.above50, 1), a.count + " benzersiz hisse") +
      stat("SMA 100 üstü", "%" + num(b.above100, 1), "orta vade") +
      stat("SMA 200 üstü", "%" + num(b.above200, 1), "uzun vade") +
      stat("20 günde pozitif", "%" + num(b.positive_d20, 1), "hisse payı") +
      stat("Zirveye %5 yakın", "%" + num(b.near_high, 1), "52 hafta") +
      stat("Bellek hisseleri 20G", pc(a.memory.avg_d20), a.memory.count + " hisse (DRAM'in bileşenleri)", cls(a.memory.avg_d20)) + '</div>' +
      '<div class="two"><div>' + h2("20 günlük liderler") + aiMini(a.leaders) + '</div><div>' + h2("20 günlük gerideler") + aiMini(a.laggards) + '</div></div>' +
      h2("Tüm bileşenler") + aiTable(a);
    var asof = Object.keys(a.detail || {}).map(function (k) { return k + " " + fmtDate(a.detail[k].asof); }).join(", ");
    var old = Object.keys(a.detail || {}).some(function (k) { return (Date.now() - new Date(a.detail[k].asof).getTime()) / 864e5 > 120; });
    out += '<p class="fine">Bileşen listeleri fonların resmi dosyalarından alınmıştır (' + esc(asof) + '). Fiyatlar her gece güncellenir; liste ağırlıkları fon yeniden dengelendikçe değişir.' + (old ? ' <span class="rsk">Liste 120 günden eski, ağırlıklar güncel olmayabilir.</span>' : '') + ' Kore, Tayvan, Japonya ve Çin borsasındaki hisselerin fiyatları kendi para birimi ve kendi işlem saatlerindedir; yüzde değişimleri karşılaştırılabilir.</p>';
    return out;
  }

  var DATA = null;
  function clean(o) {
    if (typeof o === "string") return o.replace(/[<>"'`]/g, "");
    if (Array.isArray(o)) return o.map(clean);
    if (o && typeof o === "object") { var r = {}; Object.keys(o).forEach(function (k) { r[k] = clean(o[k]); }); return r; }
    return o;
  }
  function tabs(d) {
    return '<section class="tab" id="t-genel">' + regime(d.regime) + levels(d) + trend(d) + notes(d.notes) + '</section>' +
      '<section class="tab" id="t-genislik">' + breadth(d.breadth) + pairs(d.pairs) + '</section>' +
      '<section class="tab" id="t-sektor">' + sectors(d.sectors) + '</section>' +
      '<section class="tab" id="t-ai">' + ai(d.ai) + '</section>';
  }
  function show() {
    var h = (location.hash || "#genel").slice(1);
    if (!document.getElementById("t-" + h)) h = "genel";
    Array.prototype.forEach.call(document.querySelectorAll("section.tab"), function (s) { s.classList.toggle("on", s.id === "t-" + h); });
    Array.prototype.forEach.call(document.querySelectorAll("nav a"), function (a) { a.classList.toggle("on", a.getAttribute("data-t") === h); });
  }
  function labels() {
    Array.prototype.forEach.call(document.querySelectorAll("#app table"), function (t) {
      var hs = Array.prototype.map.call(t.querySelectorAll("thead th"), function (h) { return h.textContent.replace(/[↑↓]/g, "").trim(); });
      if (!hs.length) return;
      Array.prototype.forEach.call(t.querySelectorAll("tbody tr"), function (tr) {
        Array.prototype.forEach.call(tr.children, function (td, i) { if (!td.hasAttribute("data-label") && hs[i]) td.setAttribute("data-label", hs[i]); });
      });
    });
  }
  function draw() { document.getElementById("app").innerHTML = tabs(DATA); labels(); show(); }

  function render(d) {
    d = clean(d);
    DATA = d;
    var q = d.meta.quality || {}, el = document.getElementById("dq");
    el.textContent = q.level || "–";
    el.className = q.level === "YÜKSEK" ? "pos" : q.level === "DÜŞÜK" ? "neg" : "rsk";
    var ageH = (Date.now() - new Date(d.meta.generated_at).getTime()) / 36e5;
    document.getElementById("banner").innerHTML = ageH > 96 ? '<div class="banner">Bu veri ' + Math.floor(ageH / 24) + ' günden eski. Otomatik güncelleme beklenenden uzun süredir yayın yapamadı; son doğrulanmış veri gösteriliyor.</div>' : "";
    document.getElementById("refDate").textContent = fmtDate(d.meta.ref_date);
    document.getElementById("gen").textContent = new Date(d.meta.generated_at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", dateStyle: "medium", timeStyle: "short" });
    draw();
  }
  document.addEventListener("click", function (e) {
    var th = e.target.closest && e.target.closest("th.s");
    if (!th || !DATA) return;
    var k = th.getAttribute("data-k"), sec = th.getAttribute("data-t") === "sec";
    var cur = sec ? SEC_SORT : AI_SORT, nx = { k: k, dir: cur.k === k ? -cur.dir : (k === "symbol" || k === "status" || k === "trend" ? 1 : -1) };
    if (sec) SEC_SORT = nx; else AI_SORT = nx;
    draw();
  });
  document.addEventListener("change", function (e) {
    if (e.target && (e.target.id === "aisort" || e.target.id === "secsort") && DATA) {
      var k = e.target.value, o = { k: k, dir: (k === "symbol" || k === "status" || k === "trend") ? 1 : -1 };
      if (e.target.id === "secsort") SEC_SORT = o; else AI_SORT = o;
      draw();
    }
  });
  window.addEventListener("hashchange", show);
  fetch("data.json?v=" + Date.now()).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(render).catch(function (e) {
    document.getElementById("app").innerHTML = '<div class="err">Veri yüklenemedi (' + esc(e.message) + '). Birkaç dakika sonra yenile.</div>';
  });
})();
