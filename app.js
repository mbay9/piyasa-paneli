(function () {
  var MONTHS = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
  function fmtDate(d) { if (!d) return "–"; var a = d.split("-"); return parseInt(a[2], 10) + " " + MONTHS[parseInt(a[1], 10) - 1] + " " + a[0]; }
  function fmtShort(d) { if (!d) return ""; var a = d.split("-"); return parseInt(a[2], 10) + " " + MONTHS[parseInt(a[1], 10) - 1]; }
  var TK = { "005930.KS": "Samsung", "688825.SS": "CXMT", "285A.T": "Kioxia", "2408.TW": "Nanya", "603986.SS": "GigaDevice", "2344.TW": "Winbond" };
  function tk(s) { return TK[s] || s; }
  function dtag(m, ref) {
    return m && m.date && ref && m.date !== ref ? " · son kapanış " + fmtShort(m.date) : "";
  }
  function px(v, cur) {
    if (v === null || v === undefined) return "";
    return (cur === "USD" || !cur ? "$" : "") + num(v, v >= 1000 ? 0 : 2) + (cur && cur !== "USD" ? " " + cur : "");
  }
  function cap(v) {
    if (v === null || v === undefined) return "–";
    if (v >= 1e12) return "$" + num(v / 1e12, 2) + " Tr";
    if (v >= 1e9) return "$" + num(v / 1e9, v >= 1e10 ? 0 : 1) + " Mr";
    return "$" + num(v / 1e6, 0) + " Mn";
  }
  function num(v, dec) { return v === null || v === undefined ? "–" : Number(v).toLocaleString("tr-TR", { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
  function sgn(v) { return v > 0 ? "+" : v < 0 ? "−" : ""; }
  function pc(v, dec) { return v === null || v === undefined ? "–" : sgn(v) + num(Math.abs(v), dec === undefined ? 2 : dec) + "%"; }
  function pt(v, dec) { return v === null || v === undefined ? "–" : sgn(v) + num(Math.abs(v), dec === undefined ? 1 : dec) + " puan"; }
  function cls(v, risk) { if (v === null || v === undefined || v === 0) return "neu"; if (risk) return v > 0 ? "rsk" : "pos"; return v > 0 ? "pos" : "neg"; }
  function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function h2(t) { return '<h2>' + t + '</h2>'; }
  function sub(t) { return '<p class="sub">' + t + '</p>'; }
  function stat(k, v, d, c) { return '<div class="stat"><div class="k">' + k + '</div><div class="v ' + (c || "") + '">' + v + '</div><div class="d">' + (d || "") + '</div></div>'; }
  function ma(flag, dist) {
    if (flag === null || flag === undefined) return '<span class="neu">–</span>';
    return '<span class="' + (flag ? "pos" : "neg") + '">' + (flag ? "üstünde" : "altında") + '</span><small>' + pc(dist, 1) + '</small>';
  }
  function vtext(m) {
    var v = m && m.verify; if (!v) return "";
    if (v.status === "warn") return '<span class="dot warn"></span>';
    return "";
  }

  var REG_LABELS = { RISK_ON: ["RİSK-ON", "pos"], RISK_OFF: ["RİSK-OFF", "neg"], INSUFFICIENT_DATA: ["BELİRSİZ / VERİ YETERSİZ", "neu"] };

  function regime(rg) {
    if (!rg) return "";
    var ok = rg.market_regime === "RISK_ON" || rg.market_regime === "RISK_OFF";
    var lab = REG_LABELS[rg.market_regime] || REG_LABELS.INSUFFICIENT_DATA;
    var c = rg.context || {}, dq = rg.data_quality || {}, miss = (dq.missing_data || []).concat(dq.stale_data || []);
    var st = "";
    if (ok) {
      if (rg.days_in_state !== null && rg.days_in_state !== undefined) st += '<div><small>Süre</small><b>' + rg.days_in_state + ' gün</b></div>';
      if (c.vix !== null && c.vix !== undefined) st += '<div><small>VIX</small><b>' + num(c.vix, 1) + '</b></div>';
      if (c.breadth_pct200 !== null && c.breadth_pct200 !== undefined) st += '<div><small>Breadth</small><b>%' + num(c.breadth_pct200, 0) + '</b><div class="rgbar"><i style="width:' + Math.max(0, Math.min(100, c.breadth_pct200)) + '%"></i></div></div>';
    }
    var out = '<div class="rgc"><span class="rgp ' + lab[1] + '">' + esc(lab[0]) + '</span><div class="rgm"><span class="big">' + (ok ? pc(rg.distance_pct, 1) : "–") + '</span>' + (ok ? '<span class="rgs">SMA 200\'ün ' + (rg.distance_pct >= 0 ? "üzerinde" : "altında") + '</span>' : "") + '</div>' + (st ? '<div class="rgst">' + st + '</div>' : "") + '</div>';
    var head = out; out = "";
    if (ok) {
      out += '<p class="fine">S&amp;P 500 ' + num(rg.close, 2) + ', 200 günlük ortalama ' + num(rg.sma200, 2) + '. ' +
        (rg.state_since ? fmtDate(rg.state_since) + ' tarihinden beri, ' + rg.days_in_state + ' işlem günüdür bu durumda.' : "Durumun başlangıcı mevcut geçmişte yok.") + '</p>' +
        '<p class="fine">Kural: iki kapanış üst üste ortalamanın %1,5 altında (' + num(rg.lower_band, 2) + ' ve altı) ise RİSK-OFF, %1,5 üzerinde (' + num(rg.upper_band, 2) + ' ve üstü) ise RİSK-ON. Arada önceki durum korunur.</p>';
      if (rg.recent_flips && rg.recent_flips.length) out += '<p class="fine">Son geçişler: ' + rg.recent_flips.map(function (f) { return fmtDate(f.date) + " " + (f.to === "RISK_ON" ? "RİSK-ON" : "RİSK-OFF"); }).join(" · ") + '.</p>';
      var info = [];
      if (c.vix !== null && c.vix !== undefined) info.push("VIX " + num(c.vix, 2) + ", son 252 gözlemde yüzdelik dilim %" + num(c.vix_percentile, 0));
      if (c.breadth_pct200 !== null && c.breadth_pct200 !== undefined) info.push("bileşenlerin %" + num(c.breadth_pct200, 1) + " kadarı 200G ortalamanın üzerinde (" + c.breadth_valid + "/" + c.breadth_total + ")");
      if (info.length) out += '<p class="fine">Bilgi, puana dahil değil: ' + esc(info.join(" · ")) + '.</p>';
    }
    if (miss.length) head += '<p class="fine"><span class="rsk">Hesaplanamayan: ' + esc(miss.join(", ")) + '.</span></p>';
    REG_BOX = '<details class="srcbox"><summary>Rejim kuralı ve geçmiş testi</summary>' + out + '<p class="fine">Geçmiş testi (1993–2026, işlem ertesi gün, maliyet dahil): bu kural en büyük düşüşü %55&#39;ten %20&#39;ye indirdi, yıllık getiri %9,5 (al-tut %10,9). Geçmiş performans geleceği garanti etmez.</p></details>';
    return head;
  }
  var REG_BOX = "";

  function levels(d) {
    var rows = [], ref = d.meta.ref_date;
    Object.keys(d.indexes).forEach(function (k) { rows.push([k, d.indexes[k]]); });
    ["SPY", "QQQ", "IWM", "RSP", "QQQE", "RWJ"].forEach(function (k) { if (d.etfs[k]) rows.push([k, d.etfs[k]]); });
    var body = rows.map(function (x) {
      var k = x[0], m = x[1], risk = k === "VIX", tc = m.trend === "Yükseliş" ? "pos" : m.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + k + '</b>' + vtext(m) + ' <span class="px ' + (m.d1 > 0 ? "up" : m.d1 < 0 ? "dn" : "nu") + (risk ? " inv" : "") + '">' + num(m.close, 2) + '</span><small>' + esc(m.name || "") + esc(dtag(m, ref)) + '</small></td><td class="hm ' + cls(m.d5, risk) + '">' + pc(m.d5) + '</td><td class="' + cls(m.d20, risk) + '">' + pc(m.d20) + '</td><td class="' + cls(m.from_high) + '">' + pc(m.from_high, 1) + '</td><td class="' + tc + '">' + esc(m.trend || "–") + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above100, m.dist100) + '</td><td>' + ma(m.above200, m.dist200) + '</td>' +
        '<td>' + (m.vol_vs20 == null ? '<span class="neu">–</span>' : '<span class="' + (m.vol_vs20 >= 30 ? "rsk" : "") + '">' + pc(m.vol_vs20, 0) + '</span>') + '</td><td class="hm">' + (m.vol_vs50 == null ? '<span class="neu">–</span>' : pc(m.vol_vs50, 0)) + '</td></tr>';
    }).join("");
    return '<div class="tw"><table><thead><tr><th>Gösterge</th><th class="hm">5G</th><th>20G</th><th>Zirveye uzaklık</th><th>Trend</th><th>SMA 50</th><th>SMA 100</th><th>SMA 200</th><th>Hacim / 20G</th><th class="hm">Hacim / 50G</th></tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  function notes(n) {
    if (!n || !n.length) return "";
    return '<details class="srcbox"><summary>Risk notları · ' + n.length + ' not</summary>' + n.map(function (x) {
      var c = { ok: "ok", warn: "warn", bad: "bad" }[x.level] || "";
      return '<div class="note"><b><span class="dot ' + c + '"></span>' + esc(x.title) + '</b><span>' + esc(x.text) + '</span></div>';
    }).join("") + '</details>';
  }

  function partCard(p) {
    if (!p || !p.series || p.series.length < 2) return "";
    var W = 600, H = 110, P = 4, n = p.series.length, pts = p.series.map(function (v, i) { return [P + i * (W - 2 * P) / (n - 1), H - P - (Math.max(0, Math.min(100, v)) / 100) * (H - 2 * P)]; });
    var line = pts.map(function (q, i) { return (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join(" ");
    var area = line + " L" + pts[n - 1][0].toFixed(1) + " " + H + " L" + pts[0][0].toFixed(1) + " " + H + " Z";
    var last = pts[n - 1];
    return '<div class="part"><div class="partk">Sektör ETF katılımı <span class="badge">Fiyat bazlı</span></div>' +
      '<div class="partv">%' + num(p.pct, 0) + '<span class="partd">' + p.above + ' / ' + p.count + ' sektör ETF\'i SMA 50 üzerinde' + (p.d5 === null || p.d5 === undefined ? "" : " · 5G " + pt(p.d5, 0)) + '</span></div>' +
      '<svg class="partsvg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img" aria-label="Sektör ETF katılımı, son ' + n + ' gün"><path d="' + area + '" class="partarea"/><path d="' + line + '" class="partline" vector-effect="non-scaling-stroke"/></svg>' +
      '<div class="partax"><span>' + fmtDate(p.dates[0]) + '</span><span>' + fmtDate(p.dates[n - 1]) + '</span></div>' +
      '<div class="fine">Bileşen genişliği değildir; erişilebilen ' + p.count + ' sektör ETF\'inden hesaplanan vekildir.</div></div>';
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
    var head = cols.map(function (c) { return '<th class="s' + (c[0] === "d5" || c[0] === "dist100" || c[0] === "vol_vs20" ? " hm" : "") + '" data-t="sec" data-k="' + c[0] + '" tabindex="0" role="button" aria-sort="' + (SEC_SORT.k === c[0] ? (SEC_SORT.dir > 0 ? "ascending" : "descending") : "none") + '">' + c[1] + (SEC_SORT.k === c[0] ? (SEC_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    var body = sorted.map(function (s) {
      var sc = { "Lider": "pos", "Toparlanıyor": "neu", "Zayıflıyor": "rsk", "Geride": "neg" }[s.status] || "";
      var tc = s.trend === "Yükseliş" ? "pos" : s.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + s.symbol + '</b> <span class="mute">' + esc(s.name) + '</span></td><td class="' + sc + '">' + esc(s.status) + '</td><td class="' + cls(s.rel20) + '">' + pt(s.rel20, 2) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td>' +
        '<td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td><td class="' + tc + '">' + esc(s.trend || "–") + '</td><td>' + ma(s.above50, s.dist50) + '</td><td class="hm">' + ma(s.above100, s.dist100) + '</td><td>' + ma(s.above200, s.dist200) + '</td>' +
        '<td class="hm">' + (s.vol_vs20 === null || s.vol_vs20 === undefined ? "–" : pc(s.vol_vs20, 0)) + '</td></tr>';
    }).join("");
    return h2("Sektör liderliği") + '<div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  var AI_SORT = { k: "mcap", dir: -1 };
  function aiTable(a) {
    var ref = DATA.meta.ref_date, hmk = { d5: 1, vol5_vs20: 1 };
    var cols = [["symbol", "Hisse"], ["mcap", "Piyasa değeri"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["above50", "SMA 50"], ["above100", "SMA 100"], ["above200", "SMA 200"], ["from_high", "Zirveye uzaklık"], ["vol5_vs20", "Hacim 5G / 20G"], ["vol_trend", "Hacim eğilimi"]];
    var rows = a.stocks.slice().sort(function (x, y) {
      var k = AI_SORT.k, u = x[k], v = y[k];
      if (typeof u === "boolean") { u = u ? 1 : 0; v = v ? 1 : 0; }
      if (u === null || u === undefined) return 1; if (v === null || v === undefined) return -1;
      if (typeof u === "string") return u.localeCompare(v) * AI_SORT.dir;
      return (u - v) * AI_SORT.dir;
    });
    var head = cols.map(function (c) { return '<th class="s' + (hmk[c[0]] ? " hm" : "") + '" data-k="' + c[0] + '" tabindex="0" role="button" aria-sort="' + (AI_SORT.k === c[0] ? (AI_SORT.dir > 0 ? "ascending" : "descending") : "none") + '">' + c[1] + (AI_SORT.k === c[0] ? (AI_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    function ab(f) { return f === null || f === undefined ? "–" : '<span class="' + (f ? "pos" : "neg") + '">' + (f ? "üstünde" : "altında") + '</span>'; }
    var body = rows.map(function (s) {
      var dl = s.date && s.date !== ref ? '<small>son kapanış ' + fmtShort(s.date) + '</small>' : "";
      return '<tr><td><b>' + esc(tk(s.symbol)) + '</b> <span class="px ' + (s.d1 > 0 ? "up" : s.d1 < 0 ? "dn" : "nu") + '">' + esc(px(s.close, s.cur)) + '</span>' + dl + '</td><td>' + cap(s.mcap) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td>' + ab(s.above50) + '</td><td>' + ab(s.above100) + '</td><td>' + ab(s.above200) + '</td><td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td><td class="hm">' + (s.vol5_vs20 == null ? "–" : pc(s.vol5_vs20, 0)) + '</td><td class="' + (s.vol_trend === "Artıyor" ? "pos" : s.vol_trend === "Azalıyor" ? "neg" : "neu") + '">' + esc(s.vol_trend || "–") + '</td></tr>';
    }).join("");
    var noMob = { symbol: 1, above50: 1, above100: 1, above200: 1, vol5_vs20: 1, vol_trend: 1 };
    var mc = cols.filter(function (c) { return !noMob[c[0]]; }), curLabel = (mc.filter(function (c) { return c[0] === AI_SORT.k; })[0] || mc[0])[1];
    var opts = mc.map(function (c) { return '<li role="option" tabindex="0" data-k="' + c[0] + '" aria-selected="' + (AI_SORT.k === c[0]) + '">' + c[1] + '</li>'; }).join("");
    return '<div class="sortbar"><span>Sırala</span><div class="dd"><button type="button" class="ddb" id="aisort" aria-haspopup="listbox" aria-expanded="false">' + esc(curLabel) + '</button><ul class="ddl" role="listbox" hidden>' + opts + '</ul></div></div><div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }
  function aiStocks(a) {
    if (!a || !a.stocks) return h2("AI hisseleri") + sub("Bu bölüm bu güncellemede hesaplanamadı.");
    var w = a.stocks.filter(function (s) { return s.watch; }).length;
    return h2("AI hisseleri (" + a.stocks.length + ")") + aiTable(a);
  }
  function aiMini(list) {
    return '<div class="tw"><table><tbody>' + list.map(function (s) {
      return '<tr><td><b>' + esc(tk(s.symbol)) + '</b><small>' + esc(s.name) + '</small></td><td data-label="20G" class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td data-label="1G" class="' + cls(s.d1) + '">' + pc(s.d1) + '</td></tr>';
    }).join("") + '</tbody></table></div>';
  }
  function aiDetail(a) {
    var names = { SOXX: "SOXX · iShares", SMH: "SMH · VanEck", DRAM: "DRAM · Roundhill" };
    var rows = ["SOXX", "SMH", "DRAM"].map(function (k) {
      var d = a.detail && a.detail[k]; if (!d) return "";
      var vc = d.verdict === "GENİŞ" ? "pos" : d.verdict === "DAR" ? "rsk" : "neu";
      var top = d.top.map(function (t) { return esc(tk(t.symbol)); }).join(" · ");
      return '<tr><td><b>' + names[k] + '</b><small>liste: ' + fmtDate(d.asof) + ' (' + Math.max(0, Math.floor((Date.now() - new Date(d.asof).getTime()) / 864e5)) + ' gün)</small></td>' +
        '<td class="' + cls(d.w_d1) + '">' + pc(d.w_d1) + '</td><td class="' + cls(d.w_d5) + '">' + pc(d.w_d5) + '</td><td class="' + cls(d.w_d20) + '">' + pc(d.w_d20) + '</td><td class="' + cls(d.eq_d20) + '">' + pc(d.eq_d20) + '</td>' +
        '<td>%' + num(d.above50_w, 0) + '<small>sayı: %' + num(d.above50_n, 0) + '</small></td><td>%' + num(d.above100_w, 0) + '<small>sayı: %' + num(d.above100_n, 0) + '</small></td><td>%' + num(d.above200_w, 0) + '<small>sayı: %' + num(d.above200_n, 0) + '</small></td><td class="' + vc + '"><b>' + (d.verdict || "–") + '</b></td><td class="mute">' + top + '</td></tr>';
    }).join("");
    return h2("ETF içi görünüm (ağırlıklı)") + '<div class="tw"><table><thead><tr><th>ETF</th><th>Ağırlıklı 1G</th><th>Ağırlıklı 5G</th><th>Ağırlıklı 20G</th><th>Eşit ağırlıklı 20G</th><th>SMA 50 üstü (ağırlık)</th><th>SMA 100 üstü (ağırlık)</th><th>SMA 200 üstü (ağırlık)</th><th>Yapı</th><th>En büyük 5 hisse</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
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
    out += aiDetail(a) + h2("Genişlik (tüm hisseler birlikte)") + '<div class="stats">' +
      stat("SMA 50 üstü", "%" + num(b.above50, 1), a.count + " benzersiz hisse") +
      stat("SMA 100 üstü", "%" + num(b.above100, 1), "orta vade") +
      stat("SMA 200 üstü", "%" + num(b.above200, 1), "uzun vade") +
      stat("20 günde pozitif", "%" + num(b.positive_d20, 1), "hisse payı") +
      stat("Zirveye %5 yakın", "%" + num(b.near_high, 1), "52 hafta") +
      (a.volume && a.volume.valid ? stat("Hacmi artan", num(a.volume.rising, 0) + " / " + num(a.volume.valid, 0), "5G ort. 20G ortalamasının %20 üstünde", "pos") + stat("Hacmi azalan", num(a.volume.falling, 0) + " / " + num(a.volume.valid, 0), "5G ort. 20G ortalamasının %20 altında", "neg") : "") +
      stat("Bellek hisseleri 20G", pc(a.memory.avg_d20), a.memory.count + " hisse (DRAM'in bileşenleri)", cls(a.memory.avg_d20)) + '</div>' +
      '<div class="two"><div>' + h2("20 günlük liderler") + aiMini(a.leaders) + '</div><div>' + h2("20 günlük gerideler") + aiMini(a.laggards) + '</div></div>';
    var old = Object.keys(a.detail || {}).some(function (k) { return (Date.now() - new Date(a.detail[k].asof).getTime()) / 864e5 > 45; });
    if (old) out += '<p class="fine"><span class="rsk">ETF bileşen listesi 45 günden eski, ağırlıklar güncel olmayabilir.</span></p>';
    return out;
  }

  function sourcesBox(d) {
    var m = d.meta || {}, q = m.quality || {};
    var items = (m.sources || []).map(function (x) { return '<li><b>' + esc(x.name) + '</b> ' + (x.official ? '<span class="pos">resmi</span>' : '<span class="rsk">resmi değil</span>') + ' · ' + esc(x.use) + '</li>'; }).join("");
    var px = (d.meta.proxy_checks || []).filter(function (p) { return p.status === "ok"; }).map(function (p) { return esc(p.id) + " ile " + esc(p.etf) + " günlük getiri farkı " + num(p.diff, 2) + " puan"; });
    return '<details class="srcbox"><summary>Veri kaynakları ve doğrulama · kalite ' + esc(q.level || "–") + '</summary>' +
      ((q.reasons || []).length ? '<p class="fine">Kalite notları: ' + esc(q.reasons.join("; ")) + '.</p>' : "") +
      (px.length ? '<p class="fine">Çapraz kontrol: ' + px.join("; ") + '.</p>' : "") +
      '<ul class="src">' + items + '</ul><p class="fine">Veriler bilgi amaçlıdır, yatırım tavsiyesi değildir.</p></details>';
  }

  var DATA = null;
  function clean(o) {
    if (typeof o === "string") return o.replace(/'/g, "\u2019").replace(/[<>"`]/g, "");
    if (Array.isArray(o)) return o.map(clean);
    if (o && typeof o === "object") { var r = {}; Object.keys(o).forEach(function (k) { r[k] = clean(o[k]); }); return r; }
    return o;
  }
  function tabs(d) {
    return '<section class="tab" id="t-genel">' + regime(d.regime) + levels(d) + sourcesBox(d) + REG_BOX + notes(d.notes) + '</section>' +
      '<section class="tab" id="t-genislik">' + partCard(d.sector_participation) + breadth(d.breadth) + pairs(d.pairs) + '</section>' +
      '<section class="tab" id="t-sektor">' + sectors(d.sectors) + '</section>' +
      '<section class="tab" id="t-ai">' + ai(d.ai) + '</section>' +
      '<section class="tab" id="t-aihisse">' + aiStocks(d.ai) + '</section>';
  }
  function show() {
    var h = (location.hash || "#genel").slice(1);
    if (!document.getElementById("t-" + h)) h = "genel";
    Array.prototype.forEach.call(document.querySelectorAll("section.tab"), function (s) { s.classList.toggle("on", s.id === "t-" + h); });
    document.body.classList.toggle("tg", h === "genel");
    Array.prototype.forEach.call(document.querySelectorAll("nav a"), function (a) { var on = a.getAttribute("data-t") === h; a.classList.toggle("on", on); if (on && a.parentNode) a.parentNode.scrollLeft = Math.max(0, a.offsetLeft - 24); });
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

  function weekdaysBehind(ref) {
    try {
      var ny = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
      var t = new Date(ref + "T00:00:00Z").getTime(), end = new Date(ny + "T00:00:00Z").getTime() - 864e5, n = 0;
      for (t += 864e5; t <= end; t += 864e5) { var w = new Date(t).getUTCDay(); if (w !== 0 && w !== 6) n++; }
      return n;
    } catch (e) { return 0; }
  }
  function render(d) {
    d = clean(d);
    DATA = d;
    var ageH = (Date.now() - new Date(d.meta.generated_at).getTime()) / 36e5;
    var lag = weekdaysBehind(d.meta.ref_date);
    document.getElementById("banner").innerHTML = (ageH > 96 || lag >= 2) ? '<div class="banner">Veri güncel olmayabilir: son kapanış ' + fmtDate(d.meta.ref_date) + ', yayın ' + Math.floor(ageH / 24) + ' gün önce. Otomatik güncelleme beklenenden uzun süredir yayın yapamadı; son doğrulanmış veri gösteriliyor.</div>' : "";
    document.getElementById("refDate").textContent = fmtDate(d.meta.ref_date);
    document.getElementById("gen").textContent = new Date(d.meta.generated_at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul", dateStyle: "medium", timeStyle: "short" });
    draw();
  }
  function closeDd() {
    Array.prototype.forEach.call(document.querySelectorAll(".ddl"), function (l) { l.hidden = true; });
    Array.prototype.forEach.call(document.querySelectorAll(".ddb"), function (b) { b.setAttribute("aria-expanded", "false"); });
  }
  document.addEventListener("click", function (e) {
    var t = e.target, b = t.closest && t.closest(".ddb"), o = t.closest && t.closest(".ddl li");
    if (o && DATA) { AI_SORT = { k: o.getAttribute("data-k"), dir: -1 }; draw(); return; }
    var wasOpen = b && !b.parentNode.querySelector(".ddl").hidden;
    closeDd();
    if (b && !wasOpen) { b.parentNode.querySelector(".ddl").hidden = false; b.setAttribute("aria-expanded", "true"); }
  });
  document.addEventListener("click", function (e) {
    var th = e.target.closest && e.target.closest("th.s");
    if (!th || !DATA) return;
    var k = th.getAttribute("data-k"), sec = th.getAttribute("data-t") === "sec";
    var cur = sec ? SEC_SORT : AI_SORT, nx = { k: k, dir: cur.k === k ? -cur.dir : (k === "symbol" || k === "status" || k === "trend" ? 1 : -1) };
    if (sec) SEC_SORT = nx; else AI_SORT = nx;
    draw();
  });
  document.addEventListener("keydown", function (e) {
    if ((e.key === "Enter" || e.key === " ") && e.target && e.target.matches && e.target.matches("th.s, .ddl li")) { e.preventDefault(); e.target.click(); }
    if (e.key === "Escape") closeDd();
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
