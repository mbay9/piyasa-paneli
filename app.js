(function () {
  var MONTHS = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
  function fmtDate(d) { if (!d) return "–"; var a = d.split("-"); return parseInt(a[2], 10) + " " + MONTHS[parseInt(a[1], 10) - 1] + " " + a[0]; }
  function fmtShort(d) { if (!d) return ""; var a = d.split("-"); return parseInt(a[2], 10) + " " + MONTHS[parseInt(a[1], 10) - 1]; }
  var TK = { "005930.KS": "Samsung", "688825.SS": "CXMT", "285A.T": "Kioxia", "2408.TW": "Nanya", "603986.SS": "GigaDevice", "2344.TW": "Winbond" };
  function tk(s) { return TK[s] || s; }
  function sa(s) { return /^[A-Z0-9-]+$/.test(s) ? ' <span class="lk"><a class="sa" href="https://seekingalpha.com/symbol/' + encodeURIComponent(s) + '" target="_blank" rel="noopener noreferrer" title="Seeking Alpha\'da aç" aria-label="' + esc(s) + ' Seeking Alpha sayfası">SA</a><a class="sa" href="https://www.zacks.com/stock/research/' + encodeURIComponent(s) + '/price-target-stock-forecast" target="_blank" rel="noopener noreferrer" title="Zacks hedef fiyat" aria-label="' + esc(s) + ' Zacks hedef fiyat sayfası">Z</a></span>' : ""; }
  function eb(s) {
    if (!s.earn) return "";
    var t = new Date(), td = Date.UTC(t.getFullYear(), t.getMonth(), t.getDate());
    var n = Math.round((Date.parse(s.earn) - td) / 864e5);
    if (!(n >= 0 && n <= 14)) return "";
    return ' <span class="eb' + (n <= 1 ? " soon" : "") + '">Bilanço ' + (n === 0 ? "bugün" : n === 1 ? "yarın" : fmtShort(s.earn)) + (s.earn_est ? " (tahmini)" : "") + '</span>';
  }
  function money(v, cu) {
    var CS = { USD: "$", TWD: "NT$", EUR: "€", KRW: "₩", JPY: "¥", CNY: "CN¥" };
    var a = Math.abs(v), c = CS[cu] || (cu ? cu + " " : "");
    return sgn(v) + c + (a >= 1e6 ? num(a / 1e6, 2) + " Tr" : a >= 1e3 ? num(a / 1e3, a >= 1e4 ? 0 : 1) + " Mr" : num(a, 0) + " Mn");
  }
  function fb(s) {
    if (s.fcf === null || s.fcf === undefined) return "";
    function mm(v) { return money(v, s.fcu); }
    function my(d) { return d ? MONTHS[parseInt(d.split("-")[1], 10) - 1] + " '" + d.slice(2, 4) : ""; }
    function t(l, v, per) { return '<span class="f ' + (v > 0 ? "y" : "k") + '" data-tip="' + esc(l + " · " + mm(v) + (per ? " · " + per : "")) + '">' + (l === "FCF" ? "FCF" : "BS") + '</span>'; }
    var fp = (s.fcp ? s.fcp + " · " : "") + my(s.fcd);
    return ' <span class="lk">' + t("FCF", s.fcf, fp) + (s.nc === null || s.nc === undefined ? "" : t("BS", s.nc, (s.ncp ? s.ncp + " · " : "") + my(s.ncd))) + '</span>';
  }
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
  function cls(v) { if (v === null || v === undefined || v === 0) return "neu"; return v > 0 ? "pos" : "neg"; }
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
      if (c.vix !== null && c.vix !== undefined) st += '<div><small>VIX · korku endeksi</small><b>' + num(c.vix, 1) + '</b></div>';
      if (c.breadth_pct200 !== null && c.breadth_pct200 !== undefined) st += '<div><small>Breadth</small><b>%' + num(c.breadth_pct200, 0) + '</b><div class="rgbar"><i style="width:' + Math.max(0, Math.min(100, c.breadth_pct200)) + '%"></i></div></div>';
    }
    var head = '<div class="rgc"><span class="rgp ' + lab[1] + '">' + esc(lab[0]) + '</span><div class="rgm"><span class="big">' + (ok ? pc(rg.distance_pct, 1) : "–") + '</span>' + (ok ? '<span class="rgs">SMA 200\'ün ' + (rg.distance_pct >= 0 ? "üzerinde" : "altında") + '</span>' : "") + '</div>' + (st ? '<div class="rgst">' + st + '</div>' : "") + '</div>';
    if (miss.length) head += '<p class="fine"><span class="rsk">Hesaplanamayan: ' + esc(miss.join(", ")) + '.</span></p>';
    return head;
  }

  function levels(d) {
    var rows = [], ref = d.meta.ref_date;
    Object.keys(d.indexes).forEach(function (k) { rows.push([k, d.indexes[k]]); });
    ["SPY", "QQQ", "IWM", "RSP", "QQQE", "RWJ"].forEach(function (k) { if (d.etfs[k]) rows.push([k, d.etfs[k]]); });
    var body = rows.map(function (x) {
      var k = x[0], m = x[1], tc = m.trend === "Yükseliş" ? "pos" : m.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + k + '</b>' + vtext(m) + ' <span class="px ' + (m.d1 > 0 ? "up" : m.d1 < 0 ? "dn" : "nu") + '">' + num(m.close, 2) + (m.d1 == null ? "" : " · " + pc(m.d1)) + '</span><small>' + esc(m.name || "") + (k === "VIX" ? " · korku endeksi" : "") + esc(dtag(m, ref)) + '</small></td><td class="hm ' + cls(m.d5) + '">' + pc(m.d5) + '</td><td class="' + cls(m.d20) + '">' + pc(m.d20) + '</td><td class="' + (k === "VIX" ? "nv" : cls(m.from_high)) + '">' + (k === "VIX" ? "" : pc(m.from_high, 1)) + '</td><td class="' + tc + '">' + esc(m.trend || "–") + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above200, m.dist200) + '</td></tr>';
    }).join("");
    return '<div class="tw"><table><thead><tr><th>Gösterge</th><th class="hm">5G</th><th>20G</th><th>Zirveye uzaklık</th><th>Trend</th><th>SMA 50</th><th>SMA 200</th></tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  function breadth(b) {
    if (!b || !b.ma50) return h2("Piyasa genişliği") + sub("Hisse listesi alınamadığı için hesaplanmadı.");
    var s = [50, 200].map(function (n) {
      var m = b["ma" + n]; if (!m) return "";
      return stat(n + " günlük ortalamanın üstünde", "%" + num(m.pct, 0), m.above + " / " + m.total + " hisse · 1 günde " + pt(m.d1) + " · 5 günde " + pt(m.d5));
    }).join("");
    return h2("Yükseliş ne kadar geniş?") + sub("Endeks yükselirken hisselerin çoğu da yükseliyor mu, yoksa az sayıda büyük hisse mi taşıyor? Aşağıdaki üç ölçü bu soruyu üç farklı yönden cevaplar. Hepsi bugünü anlatır, yön tahmin etmez. " + fmtDate(b.date)) +
      '<h3 class="qh">1 · Hisselerin kaçı ortalamalarının üstünde?</h3><div class="stats">' + s + '</div>' +
      '<p class="fine">S&amp;P 500\'ün 500 hissesi üzerinden. Oran ne kadar yüksekse yükselişe katılan hisse o kadar çok demektir. Endeks yükselirken oran düşüyorsa yükseliş inceliyor demektir.</p>' +
      '<h3 class="qh">2 · Kaç hisse zirvede, kaç hisse dipte?</h3><div class="stats">' + stat("Son 52 hafta", '<span class="pos">' + num(b.new_highs, 0) + '</span> <span class="mute">/</span> <span class="neg">' + num(b.new_lows, 0) + '</span>', "yeni zirve yapan / yeni dip yapan hisse") + '</div>' +
      '<p class="fine">52 haftanın en yüksek ya da en düşük seviyesine ulaşan hisse sayısı. Zirve sayısı dipten ne kadar fazlaysa piyasa o kadar güçlü, tersi ise zayıf demektir.</p>';
  }

  function pairs(p) {
    var rows = p.map(function (x) {
      var nm = esc((x.label || "").split(":")[0]);
      if (!x.available) return '<tr><td><b>' + nm + '</b></td><td colspan="4" class="neu">Veri alınamadı</td></tr>';
      var vc = x.verdict === "GENİŞ" ? "pos" : x.verdict === "DAR" ? "rsk" : "neu";
      var vt = x.verdict === "GENİŞ" ? "GENİŞ · herkes yükseliyor" : x.verdict === "DAR" ? "DAR · büyükler taşıyor" : esc(x.verdict || "–");
      return '<tr><td><b>' + nm + '</b><small>' + x.a + ' (eşit ağırlıklı) / ' + x.b + ' (ağırlıklı)</small></td><td class="' + cls(x.ret20_a) + '">' + pc(x.ret20_a) + '</td><td class="' + cls(x.ret20_b) + '">' + pc(x.ret20_b) + '</td><td class="' + cls(x.ret20_diff) + '">' + pt(x.ret20_diff, 2) + '</td><td class="' + vc + '"><b>' + vt + '</b></td></tr>';
    }).join("");
    return '<h3 class="qh">3 · Büyük hisseler mi taşıyor, herkes mi?</h3><div class="tw"><table><thead><tr><th>Endeks</th><th>Eşit ağırlıklı ETF · 20G</th><th>Ağırlıklı ETF · 20G</th><th>Fark</th><th>Okuma</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<p class="fine">Aynı hisseler iki farklı şekilde tartılıyor. Eşit ağırlıklı ETF\'te her hisse aynı ağırlıktadır, ağırlıklı ETF\'te büyük şirketler daha çok etki eder. Eşit ağırlıklı ETF 20 günde 1 puan veya daha fazla gerideyse DAR (az sayıda büyük hisse taşıyor), 1 puan veya daha fazla öndeyse GENİŞ.</p>';
  }

  var SEC_SORT = { k: "rel20", dir: -1 };
  function sectors(rows) {
    if (!rows || !rows.length) return "";
    var cols = [["symbol", "Sektör"], ["status", "Durum"], ["rel20", "SPY'a göre 20G"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["from_high", "Zirveye uzaklık"], ["trend", "Trend"], ["dist50", "SMA 50"], ["dist200", "SMA 200"]];
    var sorted = rows.slice().sort(function (x, y) {
      var k = SEC_SORT.k, u = x[k], v = y[k];
      if (u === null || u === undefined) return 1; if (v === null || v === undefined) return -1;
      if (typeof u === "string") return u.localeCompare(v, "tr") * SEC_SORT.dir;
      return (u - v) * SEC_SORT.dir;
    });
    var head = cols.map(function (c) { return '<th class="s' + (c[0] === "d5" ? " hm" : "") + '" data-t="sec" data-k="' + c[0] + '" tabindex="0" role="button" aria-sort="' + (SEC_SORT.k === c[0] ? (SEC_SORT.dir > 0 ? "ascending" : "descending") : "none") + '">' + c[1] + (SEC_SORT.k === c[0] ? (SEC_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    var body = sorted.map(function (s) {
      var sc = { "Lider": "pos", "Toparlanıyor": "neu", "Zayıflıyor": "rsk", "Geride": "neg" }[s.status] || "";
      var tc = s.trend === "Yükseliş" ? "pos" : s.trend === "Düşüş" ? "neg" : "rsk";
      return '<tr><td><b>' + s.symbol + '</b> <span class="mute">' + esc(s.name) + '</span></td><td class="' + sc + '">' + esc(s.status) + '</td><td class="' + cls(s.rel20) + '">' + pt(s.rel20, 2) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td>' +
        '<td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td><td class="' + tc + '">' + esc(s.trend || "–") + '</td><td>' + ma(s.above50, s.dist50) + '</td><td>' + ma(s.above200, s.dist200) + '</td></tr>';
    }).join("");
    return h2("Sektör liderliği") + '<div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  var AI_SORT = { k: "mcap", dir: -1 };
  function aiTable(a) {
    var ref = DATA.meta.ref_date, hmk = { d5: 1 };
    var cols = [["symbol", "Hisse"], ["mcap", "Piyasa değeri"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["above50", "SMA 50"], ["above200", "SMA 200"], ["from_high", "Zirveye uzaklık"]];
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
      return '<tr><td><b>' + esc(tk(s.symbol)) + '</b> <span class="px ' + (s.d1 > 0 ? "up" : s.d1 < 0 ? "dn" : "nu") + '">' + esc(px(s.close, s.cur)) + (s.d1 == null ? "" : " · " + pc(s.d1)) + '</span>' + sa(s.symbol) + fb(s) + eb(s) + dl + '</td><td>' + cap(s.mcap) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td>' + ab(s.above50) + '</td><td>' + ab(s.above200) + '</td><td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td></tr>';
    }).join("");
    var noMob = { symbol: 1, above50: 1, above200: 1 };
    var mc = cols.filter(function (c) { return !noMob[c[0]]; }), curLabel = (mc.filter(function (c) { return c[0] === AI_SORT.k; })[0] || mc[0])[1];
    var opts = mc.map(function (c) { return '<li role="option" tabindex="0" data-k="' + c[0] + '" aria-selected="' + (AI_SORT.k === c[0]) + '">' + c[1] + '</li>'; }).join("");
    return '<div class="sortbar"><span>Sırala</span><div class="dd"><button type="button" class="ddb" id="aisort" aria-haspopup="listbox" aria-expanded="false">' + esc(curLabel) + '</button><ul class="ddl" role="listbox" hidden>' + opts + '</ul></div></div><div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }
  function aiStocks(a) {
    if (!a || !a.stocks) return h2("AI hisseleri") + sub("Bu bölüm bu güncellemede hesaplanamadı.");
    return h2("AI hisseleri (" + a.stocks.length + ")") + aiTable(a);
  }
  function h3q(t) { return '<h3 class="qh">' + t + '</h3>'; }
  function tierRow(name, list) {
    var n = list.length; if (!n) return "";
    function pct(f) { return "%" + num(100 * list.filter(f).length / n, 0); }
    var d = list.map(function (s) { return s.d20; }).filter(function (v) { return v !== null && v !== undefined; }).sort(function (x, y) { return x - y; });
    var med = d.length ? (d.length % 2 ? d[(d.length - 1) / 2] : (d[d.length / 2 - 1] + d[d.length / 2]) / 2) : null;
    return '<tr><td><b>' + name + '</b><small>' + n + ' hisse</small></td><td>' + pct(function (s) { return s.above50; }) + '</td><td>' + pct(function (s) { return s.above200; }) + '</td><td>' + pct(function (s) { return s.d20 > 0; }) + '</td><td class="' + cls(med) + '">' + pc(med) + '</td><td>' + pct(function (s) { return s.from_high !== null && s.from_high !== undefined && s.from_high >= -5; }) + '</td></tr>';
  }
  function aiTiers(a) {
    var st = a.stocks || [], big = st.filter(function (s) { return s.mcap >= 1e11; }), small = st.filter(function (s) { return s.mcap !== null && s.mcap !== undefined && s.mcap < 1e11; });
    var unk = st.length - big.length - small.length;
    return h3q("2 · Listendeki hisseler büyüklüğe göre nasıl?") + '<div class="tw"><table><thead><tr><th>Grup</th><th>SMA 50 üstü</th><th>SMA 200 üstü</th><th>20 günde artıda</th><th>20G ortanca getiri</th><th>Zirveye %5 içinde</th></tr></thead><tbody>' +
      tierRow("Tüm liste", st) + tierRow("100 Mr$ ve üstü", big) + tierRow("100 Mr$ altı", small) + '</tbody></table></div>' +
      '<p class="fine">Her satırda grubun hisselerinin yüzde kaçı koşulu sağlıyor; ortanca getiri grubun ortadaki hissesinin 20 günlük getirisidir. Büyük ve küçük hisseler birbirinden çok ayrışıyorsa yükseliş tek bir kesime dayanıyor demektir.' + (unk ? " Piyasa değeri bilinmeyen " + unk + " hisse büyüklük satırlarına dahil değil." : "") + '</p>';
  }

  var OZ = null;
  function summary(d) {
    if (OZ && OZ.date === d.meta.ref_date && OZ.paragraphs && OZ.paragraphs.length) {
      var as = OZ.asya && OZ.asya.length ? h3q("Gece: Asya ve Bitcoin") + '<div class="sum">' + OZ.asya.map(function (x) { return "<p>" + esc(x) + "</p>"; }).join("") + '</div>' : "";
      return h2("Günün özeti") + '<div class="sum">' + OZ.paragraphs.map(function (x) { return "<p>" + esc(x).replace(/^Özetle:/, "<b>Özetle:</b>") + "</p>"; }).join("") + '</div>' + as;
    }
    return "";
  }
  function chgBox(items, since, note) {
    items = (items || []).filter(function (i) { return i.k !== "sma" && i.k !== "sma50"; });
    if (!items.length) return "";
    var arrow = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6h8M7 3l3 3-3 3"/></svg>';
    function tc(t) { return t === "Yükseliş" || t === "Lider" || t === "Risk-on" || t === "GENİŞ" ? "pos" : t === "Düşüş" || t === "Geride" || t === "Risk-off" || t === "DAR" ? "neg" : ""; }
    function fl(i) { return esc(i.from) + " " + arrow + ' <span class="to ' + tc(i.to) + '">' + esc(i.to) + "</span>"; }
    var G = [
      ["regime", "Rejim", "rejim"], ["trend", "Trend", "trend"], ["sma", "Ortalama", "ortalama"], ["status", "Sektör durumu", "durum"],
      ["thr", "Genişlik", "genişlik"], ["verdict", "Yapı", "yapı"], ["hi20", "20 günlük zirve", "zirve"], ["fund", "Bilanço", "bilanço"]
    ];
    var chips = "", body = "";
    G.forEach(function (g) {
      var L = items.filter(function (i) { return (i.k === "sma50" ? "sma" : i.k) === g[0]; });
      if (!L.length) return;
      chips += '<span class="cs">' + L.length + " " + g[2] + "</span>";
      body += '<div class="cg"><h3>' + g[1] + "</h3>" + L.map(function (i) {
        var f, m = "", lab = i.s ? '<b>' + esc(tk(i.s)) + "</b>" : "", w = i.s ? "" : " w";
        if (i.k === "regime") { f = "S&amp;P 500 rejimi: " + fl(i); }
        else if (i.k === "trend") { f = fl(i); m = i.d1 == null ? "" : pc(i.d1) + " bugün"; }
        else if (i.k === "status") { f = fl(i); }
        else if (i.k === "verdict") { f = esc(i.n) + ": " + fl(i); }
        else if (i.k === "thr") { f = esc(i.n) + ' <span class="to ' + (i.up ? "pos" : "neg") + '">%50 ' + (i.up ? "üstüne çıktı" : "altına indi") + "</span>"; m = "%" + num(i.v, 0); }
        else if (i.k === "fund") {
          var fv = function (a, b) { return a == null || b == null ? "" : money(a, i.cur) + " " + arrow + ' <span class="to ' + (b > a ? "pos" : b < a ? "neg" : "") + '">' + money(b, i.cur) + "</span>"; };
          var fp = fv(i.f0, i.f1), np = fv(i.n0, i.n1);
          f = (fp ? "FCF " + fp : i.f1 != null ? "FCF " + money(i.f1, i.cur) : "") + (np ? (fp || i.f1 != null ? " · " : "") + "Net nakit " + np : "");
          m = esc(i.per || "");
        }
        else if (i.k === "hi20") { f = '<span class="to">Yeni zirve</span>'; m = i.prev_hi == null ? "" : "önceki " + num(i.prev_hi, 2); }
        else { var n = i.m || 50, sv = i.sma !== undefined ? i.sma : i.sma50; f = '<span class="to ' + (i.up ? "pos" : "neg") + '">SMA ' + n + " " + (i.up ? "üstüne çıktı" : "altına indi") + "</span>"; m = num(i.close, 2) + " · SMA " + n + " " + num(sv, 2); }
        return '<div class="cr' + w + '">' + lab + '<span class="cf">' + f + '</span><span class="cm">' + m + "</span></div>";
      }).join("") + "</div>";
    });
    return '<details class="chg"><summary><span class="cd"></span><span class="ct">Dünden beri ' + items.length + ' değişiklik</span><span class="csum">' + chips + '</span><svg class="car" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5"/></svg></summary><div class="cb">' + body +
      '<p class="fine">Karşılaştırma: ' + esc(fmtShort(since)) + " kapanışı" + (note ? " · " + note : "") + "</p></div></details>";
  }
  function chgFor(area) {
    var c = DATA && DATA.changes;
    return c && c.items ? c.items.filter(function (i) { return i.a === area; }) : [];
  }
  function ai(a) {
    if (!a || !a.etfs) return h2("Yapay zeka") + sub("Bu bölüm bu güncellemede hesaplanamadı. Bir sonraki çalışmada yeniden denenir.");
    var e = a.etfs.map(function (m) {
      if (!m.available) return '<tr><td><b>' + m.symbol + '</b><small>' + esc(m.name) + '</small></td><td colspan="10" class="neu">Veri alınamadı</td></tr>';
      return '<tr><td><b>' + m.symbol + '</b><small>' + esc(m.name) + '</small></td><td>' + num(m.close, 2) + '</td><td class="' + cls(m.d1) + '">' + pc(m.d1) + '</td><td class="' + cls(m.d5) + '">' + pc(m.d5) + '</td><td class="' + cls(m.d20) + '">' + pc(m.d20) + '</td><td class="' + cls(m.d60) + '">' + pc(m.d60) + '</td>' +
        '<td class="' + cls(m.rel.spy[20]) + '">' + pt(m.rel.spy[20], 1) + '</td><td class="' + cls(m.rel.qqq[20]) + '">' + pt(m.rel.qqq[20], 1) + '</td><td>' + ma(m.above50, m.dist50) + '</td><td>' + ma(m.above200, m.dist200) + '</td></tr>';
    }).join("");
    var ca = (a.changes && a.changes.items) || [], cs = chgFor("ai"), out = chgBox(ca.concat(cs), (a.changes && a.changes.since) || (DATA.changes && DATA.changes.since), "AI hisseleri ve ETF'leri") + h2("Yapay zeka ve yarı iletken") +
      sub("İki soru: ETF'ler nasıl gidiyor, listendeki hisseler büyüklüğe göre farklı mı davranıyor? Hepsi bugünkü durumu anlatır, yön tahmin etmez.") +
      h3q("1 · ETF'ler nasıl gidiyor?") + '<div class="tw"><table><thead><tr><th>ETF</th><th>Son</th><th>1G</th><th>5G</th><th>20G</th><th>60G</th><th>SPY\'a göre 20G</th><th>QQQ\'ya göre 20G</th><th>SMA 50</th><th>SMA 200</th></tr></thead><tbody>' + e + '</tbody></table></div>' +
      '<p class="fine">"SPY\'a göre 20G": ETF son 20 günde SPY\'dan kaç puan fazla (+) ya da az (−) getiri sağladı. QQQ için de aynı. SMA sütunları fiyatın o ortalamanın üstünde mi altında mı olduğunu ve ne kadar uzakta olduğunu gösterir.</p>';
    if (!a.available) return out + sub("Bileşen verisi yetersiz: " + esc(a.error || ""));
    out += aiTiers(a);
    return out;
  }

  var DATA = null;
  function clean(o) {
    if (typeof o === "string") return o.replace(/'/g, "\u2019").replace(/[<>"`]/g, "");
    if (Array.isArray(o)) return o.map(clean);
    if (o && typeof o === "object") { var r = {}; Object.keys(o).forEach(function (k) { r[k] = clean(o[k]); }); return r; }
    return o;
  }
  function tabs(d) {
    return '<section class="tab" id="t-genel">' + regime(d.regime) + summary(d) + chgBox(chgFor("genel"), d.changes && d.changes.since, "ana göstergeler ve ETF'ler") + levels(d) + '</section>' +
      '<section class="tab" id="t-genislik">' + chgBox(chgFor("genislik"), d.changes && d.changes.since, "S&P 500 genişliği") + breadth(d.breadth) + pairs(d.pairs) + '</section>' +
      '<section class="tab" id="t-sektor">' + chgBox(chgFor("sektor"), d.changes && d.changes.since, "sektör ETF'leri") + sectors(d.sectors) + '</section>' +
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
  var ftip = null;
  function hideTip() { if (ftip) ftip.hidden = true; }
  document.addEventListener("click", function (e) {
    var f = e.target.closest && e.target.closest(".f[data-tip]");
    if (!f) { hideTip(); return; }
    if (!ftip) { ftip = document.createElement("div"); ftip.id = "ftip"; document.body.appendChild(ftip); }
    var same = !ftip.hidden && ftip.textContent === f.getAttribute("data-tip");
    if (same) { hideTip(); return; }
    ftip.textContent = f.getAttribute("data-tip"); ftip.hidden = false;
    var r = f.getBoundingClientRect(), w = ftip.offsetWidth, hh = ftip.offsetHeight;
    var l = Math.max(8, Math.min(r.left, window.innerWidth - w - 8)), tp = r.top - hh - 6;
    if (tp < 8) tp = r.bottom + 6;
    ftip.style.left = l + "px"; ftip.style.top = tp + "px";
  });
  window.addEventListener("scroll", hideTip, { passive: true });
  window.addEventListener("hashchange", show);
  fetch("ozet.json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { if (j && j.paragraphs) { OZ = j; if (DATA) draw(); } }).catch(function () {});
  fetch("data.json?v=" + Date.now()).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(render).catch(function (e) {
    document.getElementById("app").innerHTML = '<div class="err">Veri yüklenemedi (' + esc(e.message) + '). Birkaç dakika sonra yenile.</div>';
  });
})();
