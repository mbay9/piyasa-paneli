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
      if (rg.days_in_state !== null && rg.days_in_state !== undefined) st += "<span>" + rg.days_in_state + " gün</span>";
      if (c.vix !== null && c.vix !== undefined) st += "<span>VIX " + num(c.vix, 1) + "</span>";
      if (c.breadth_pct200 !== null && c.breadth_pct200 !== undefined) st += "<span>Katılım %" + num(c.breadth_pct200, 0) + "</span>";
    }
    var head = '<div class="gxs"><span class="rgp ' + lab[1] + '">' + esc(lab[0]) + '</span>' + (ok ? '<span class="gxb"><b class="' + cls(rg.distance_pct) + '">' + pc(rg.distance_pct, 1) + '</b> <span class="mute">S&amp;P 500, SMA 200\'ün ' + (rg.distance_pct >= 0 ? "üzerinde" : "altında") + "</span></span>" : "") + '<span class="gxf"></span>' + st + "</div>";
    if (miss.length) head += '<p class="fine"><span class="rsk">Hesaplanamayan: ' + esc(miss.join(", ")) + '.</span></p>';
    return head;
  }
  function levels(d) {
    var rows = [], ref = d.meta.ref_date;
    Object.keys(d.indexes).forEach(function (k) { rows.push([k, d.indexes[k]]); });
    ["SPY", "QQQ", "IWM", "RSP", "QQQE", "RWJ"].forEach(function (k) { if (d.etfs[k]) rows.push([k, d.etfs[k]]); });
    var ORD = ["SPX", "SPY", "NASDAQ", "QQQ", "RUT", "IWM", "RSP", "QQQE", "RWJ", "VIX", "DXY", "BTC", "NIKKEI", "KOSPI"];
    function oi(x) { var i = ORD.indexOf(x[0]); return i < 0 ? 99 : i; }
    rows.sort(function (x, y) { return oi(x) - oi(y); });
    function cc(k, v) { return v == null ? "neu" : cls(k === "VIX" ? -v : v); }
    var last = rows.length - 1;
    var body = rows.map(function (x, i) {
      var k = x[0], m = x[1], tc = m.trend === "Yükseliş" ? "pos" : m.trend === "Düşüş" ? "neg" : "rsk";
      var nm = esc(m.name || "") + (k === "VIX" ? " · korku endeksi" : "") + esc(dtag(m, ref));
      return '<div class="gxr gxl"><span class="sxcn"><i class="' + (i === 0 ? "e" : "") + '"></i><b>' + (i + 1) + '</b><i class="' + (i === last ? "e" : "") + '"></i></span>' +
        '<span class="sxcm"><b>' + k + vtext(m) + ' <em class="gxp ' + tc + '">' + esc(m.trend || "–") + '</em></b><small class="neu">' + num(m.close, 2) + " · " + nm + '</small>' +
        '<small class="gxm neu"><span class="nw">5G <span class="' + cc(k, m.d5) + '">' + pc(m.d5) + '</span></span> · <span class="nw">20G <span class="' + cc(k, m.d20) + '">' + pc(m.d20) + '</span></span>' + (k === "VIX" ? "" : ' · <span class="nw">zirve <span class="' + cls(m.from_high) + '">' + pc(m.from_high, 1) + "</span></span>") + '<br><span class="nw">SMA 50 <span class="' + (m.above50 ? "pos" : "neg") + '">' + pc(m.dist50, 1) + '</span></span> · <span class="nw">SMA 200 <span class="' + (m.above200 ? "pos" : "neg") + '">' + pc(m.dist200, 1) + '</span></span>' + "</small></span>" +
        '<span class="gxd r ' + cc(k, m.d1) + '">' + pc(m.d1) + "</span>" +
        '<span class="gxd r ' + cc(k, m.d5) + '">' + pc(m.d5) + '</span><span class="gxd r ' + cc(k, m.d20) + '">' + pc(m.d20) + "</span>" +
        '<span class="gxd r ' + (k === "VIX" ? "neu" : cls(m.from_high)) + '">' + (k === "VIX" ? "–" : pc(m.from_high, 1)) + "</span>" +
        '<span class="gxd r ' + (m.above50 == null ? "neu" : m.above50 ? "pos" : "neg") + '">' + (m.dist50 == null ? "–" : pc(m.dist50, 1)) + '</span><span class="gxd r ' + (m.above200 == null ? "neu" : m.above200 ? "pos" : "neg") + '">' + (m.dist200 == null ? "–" : pc(m.dist200, 1)) + "</span>" +
        '<span class="gxd r ' + tc + '">' + esc(m.trend || "–") + "</span>" +
        '<span class="gxt r ' + cc(k, m.d1) + '">' + pc(m.d1) + "<small>bugün</small></span></div>";
    }).join("");
    return '<div class="gxh gxr gxl"><span></span><span>Gösterge</span><span class="r">Bugün</span><span class="r">5G</span><span class="r">20G</span><span class="r">Zirveye uzaklık</span><span class="r">SMA 50</span><span class="r">SMA 200</span><span class="r">Trend</span></div>' + body +
      '<p class="fine">Önce ABD borsaları, sonra ABD piyasasını en çok etkileyenden en aza doğru diğerleri: korku endeksi, dolar, Bitcoin, Asya. SMA sütunları fiyatın o ortalamaya uzaklığıdır. VIX\'te yükseliş kırmızı gösterilir.</p>';
  }

  function chainRows(list) {
    var last = list.length - 1;
    return list.map(function (x, i) {
      return '<div class="sxcr"><span class="sxcn"><i class="' + (i === 0 ? "e" : "") + '"></i><b>' + (i + 1) + '</b><i class="' + (i === last ? "e" : "") + '"></i></span>' +
        '<span class="sxcm"><b>' + x.ad + '</b><small class="' + (x.sc || "neu") + '">' + x.alt + '</small></span>' +
        '<span class="sxcv">' + x.bar + '<span class="' + (x.vc || "") + '">' + x.v + '</span></span>' +
        '<span class="sxcx ' + (x.c1c || "") + '">' + x.c1 + '</span><span class="sxcx hm ' + (x.c2c || "") + '">' + x.c2 + '</span></div>';
    }).join("");
  }
  function gauge(p) { return '<span class="sxcb"><i class="g" style="left:0;width:' + Math.max(0, Math.min(100, p)).toFixed(1) + '%"></i></span>'; }
  function centered(v, mx) { var w = (Math.min(Math.abs(v || 0), mx) / mx * 50).toFixed(1); return '<span class="sxcb"><i class="' + (v >= 0 ? "g" : "r") + '" style="width:' + w + "%;" + (v >= 0 ? "left:50%" : "right:50%") + '"></i></span>'; }
  function breadth(b) {
    if (!b || !b.ma50) return h2("Piyasa genişliği") + sub("Hisse listesi alınamadığı için hesaplanmadı.");
    var list = [50, 200].map(function (n) {
      var m = b["ma" + n]; if (!m) return null;
      return { ad: n + " günlük ortalamanın üstünde", alt: m.above + " / " + m.total + " hisse", bar: gauge(m.pct), v: "%" + num(m.pct, 0), c1: pt(m.d1), c1c: cls(m.d1), c2: pt(m.d5), c2c: cls(m.d5) };
    }).filter(Boolean);
    var tot = (b.new_highs || 0) + (b.new_lows || 0);
    list.push({ ad: "52 haftanın zirvesi / dibi", alt: "yeni zirve yapan / yeni dip yapan hisse", bar: gauge(tot ? b.new_highs / tot * 100 : 0), v: '<span class="pos">' + num(b.new_highs, 0) + '</span> / <span class="neg">' + num(b.new_lows, 0) + "</span>", c1: "", c2: "" });
    return h2("Yükseliş ne kadar geniş?") + sub("Endeks yükselirken hisselerin çoğu da yükseliyor mu, yoksa az sayıda büyük hisse mi taşıyor? S&amp;P 500'ün 500 hissesi üzerinden, " + fmtDate(b.date) + ".") +
      '<div class="sxch"><span></span><span>Ölçü</span><span>Oran</span><span>1 gün</span><span class="hm">5 gün</span></div>' + chainRows(list) +
      '<p class="fine">Oran yüksekse yükselişe katılan hisse çoktur. Endeks yükselirken oran düşüyorsa yükseliş inceliyor demektir. Zirve sayısı dipten fazlaysa piyasa güçlüdür.</p>';
  }

  function pairs(p) {
    var ok = p.filter(function (x) { return x.available; });
    var mx = Math.max.apply(null, ok.map(function (x) { return Math.abs(x.ret20_diff || 0); }).concat([2]));
    var list = p.map(function (x) {
      var nm = esc((x.label || "").split(":")[0]);
      if (!x.available) return { ad: nm, alt: "Veri alınamadı", bar: "", v: "–", c1: "", c2: "" };
      var vc = x.verdict === "GENİŞ" ? "pos" : x.verdict === "DAR" ? "rsk" : "neu";
      var vt = x.verdict === "GENİŞ" ? "GENİŞ · herkes yükseliyor" : x.verdict === "DAR" ? "DAR · büyükler taşıyor" : esc(x.verdict || "–");
      return { ad: nm, alt: vt, sc: vc, bar: centered(x.ret20_diff, mx), v: pt(x.ret20_diff, 1), vc: cls(x.ret20_diff), c1: pc(x.ret20_a, 1), c1c: cls(x.ret20_a), c2: pc(x.ret20_b, 1), c2c: cls(x.ret20_b) };
    });
    return h3q("Büyük hisseler mi taşıyor, herkes mi?") +
      '<div class="sxch"><span></span><span>Endeks</span><span>Eşit − ağırlıklı, 20G</span><span>Eşit ağırlıklı</span><span class="hm">Ağırlıklı</span></div>' + chainRows(list) +
      '<p class="fine">Aynı hisseler iki şekilde tartılır: eşit ağırlıklı ETF\'te her hisse aynıdır, ağırlıklı ETF\'te büyük şirketler daha çok etki eder. Eşit ağırlıklı ETF 20 günde 1 puan veya daha fazla gerideyse DAR, 1 puan veya daha fazla öndeyse GENİŞ.</p>';
  }

  function sectors(rows) {
    if (!rows || !rows.length) return "";
    var sorted = rows.slice().sort(function (x, y) { return (y.rel20 == null ? -1e9 : y.rel20) - (x.rel20 == null ? -1e9 : x.rel20); });
    var mx = Math.max.apply(null, sorted.map(function (s) { return Math.abs(s.rel20 || 0); }).concat([1]));
    var last = sorted.length - 1;
    var body = sorted.map(function (s, i) {
      var sc = { "Lider": "pos", "Güçlü": "pos", "Toparlanıyor": "neu", "Zayıflıyor": "rsk", "Geride": "neg" }[s.status] || "neu";
      var r = s.rel20 || 0, w = (Math.abs(r) / mx * 50).toFixed(1);
      var bar = '<span class="sxcb"><i class="' + (r >= 0 ? "g" : "r") + '" style="width:' + w + "%;" + (r >= 0 ? "left:50%" : "right:50%") + '"></i></span>';
      return '<div class="sxcr"><span class="sxcn"><i class="' + (i === 0 ? "e" : "") + '"></i><b>' + (i + 1) + '</b><i class="' + (i === last ? "e" : "") + '"></i></span>' +
        '<span class="sxcm"><b>' + esc(s.symbol) + " " + esc(s.name) + '</b><small class="' + sc + '">' + esc(s.status) + " · " + esc(s.trend || "–") + "</small></span>" +
        '<span class="sxcv">' + bar + '<span class="' + cls(s.rel20) + '">' + pt(s.rel20, 1) + '</span></span>' +
        '<span class="sxcx ' + cls(s.d20) + '">' + pc(s.d20, 1) + '</span><span class="sxcx hm ' + cls(s.d5) + '">' + pc(s.d5, 1) + "</span></div>";
    }).join("");
    return h2("Sektör liderliği") + sub("SPY'a göre son 20 günde en çok önde olandan en çok geride olana doğru sıralı. Puan: sektörün SPY'dan kaç puan fazla ya da az getiri sağladığıdır.") +
      '<div class="sxch"><span></span><span>Sektör</span><span>SPY\'a göre 20G</span><span>20G</span><span class="hm">5G</span></div>' + body + '<p class="fine">Lider: SPY\'dan iyi ve SMA 50 üstünde olan sektörlerin en güçlü 3\'ü. Aynı eşiği geçen diğerleri "Güçlü" olarak gösterilir.</p>';
  }

  var AI_SORT = { k: "mcap", dir: -1 }, AI_Q = "";
  var VOPEN = {};
  function mval(v, cu) { if (v === null || v === undefined) return "–"; return money(v, cu).replace(/^[+−]/, ""); }
  function vchip(s) {
    if (!s.est) return '<span class="vb ph" aria-hidden="true"></span>';
    return '<button type="button" class="vb" data-s="' + esc(s.symbol) + '" aria-expanded="' + (VOPEN[s.symbol] ? "true" : "false") + '" aria-label="' + esc(tk(s.symbol)) + ' değerleme ayrıntısı"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5"/></svg></button>';
  }
  function vspark(h) {
    if (!h || h.length < 5) return "";
    var v = h.map(function (p) { return p[1]; }), w = 300, ht = 56, pad = 5, mn = Math.min.apply(null, v), mx = Math.max.apply(null, v);
    var pts = v.map(function (y, i) { return [pad + i * (w - 2 * pad) / (v.length - 1), pad + (1 - (y - mn) / ((mx - mn) || 1)) * (ht - 2 * pad)]; });
    var d = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" "), l = pts[pts.length - 1];
    return '<div class="blk"><h3>İleri F/K seyri</h3><svg class="sp" viewBox="0 0 ' + w + " " + ht + '" preserveAspectRatio="none" role="img" aria-label="İleri F/K çizgisi"><path d="' + d + '" fill="none" stroke="var(--mute)" stroke-width="1.5" vector-effect="non-scaling-stroke"/><circle cx="' + l[0].toFixed(1) + '" cy="' + l[1].toFixed(1) + '" r="3" fill="var(--ink)"/></svg><div class="ev"><span>' + fmtShort(h[0][0]) + " · " + num(v[0], 1) + '</span><span>' + fmtShort(h[h.length - 1][0]) + " · " + num(v[v.length - 1], 1) + '</span></div></div>';
  }
  var VTAB = {};
  function vchart(s) {
    var h = (s.h || []).filter(function (v) { return v !== null && v !== undefined; });
    if (h.length < 25) return '<p class="vn">Fiyat geçmişi bir sonraki güncellemeden sonra gelir.</p>';
    var R = VRNG[s.symbol] || 63, n = Math.min(R, h.length);
    function sma(k, idx) { if (idx + 1 < k) return null; var t = 0; for (var q = idx - k + 1; q <= idx; q++) t += h[q]; return t / k; }
    var L = h.length, from = L - n, pr = [], s50 = [], s200 = [];
    for (var q = from; q < L; q++) { pr.push(h[q]); s50.push(sma(50, q)); s200.push(sma(200, q)); }
    var all = pr.concat(s50.filter(function (v) { return v !== null; }), s200.filter(function (v) { return v !== null; }));
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
    function X(i) { return (i / (n - 1) * 1000).toFixed(1); }
    function Y(v) { return ((1 - (v - lo) / (hi - lo)) * 200).toFixed(1); }
    function line(arr) { var d = "", on = false; arr.forEach(function (v, i) { if (v === null) { on = false; return; } d += (on ? "L" : "M") + X(i) + " " + Y(v); on = true; }); return d; }
    var chg = pr[pr.length - 1] / pr[0] - 1, col = chg >= 0 ? "var(--up)" : "var(--down)";
    var grid = [0, 1, 2, 3].map(function (k) { var v = lo + (hi - lo) * k / 3; return '<line x1="0" x2="1000" y1="' + Y(v) + '" y2="' + Y(v) + '" class="gl" vector-effect="non-scaling-stroke"/>'; }).join("");
    var ylab = [3, 2, 1, 0].map(function (k) { var v = lo + (hi - lo) * k / 3; return '<span style="top:' + ((1 - (v - lo) / (hi - lo)) * 100).toFixed(1) + '%">' + num(v, v >= 100 ? 0 : 2) + "</span>"; }).join("");
    var rng = [[21, "1A"], [63, "3A"], [120, "6A"]].map(function (x) { return '<button type="button" class="vr' + (R === x[0] ? " on" : "") + '" data-vr="' + x[0] + '" data-s="' + esc(s.symbol) + '">' + x[1] + "</button>"; }).join("");
    var last = pr[pr.length - 1], l50 = s50[s50.length - 1], l200 = s200[s200.length - 1];
    function dist(m) { return m === null ? '<span class="neu">–</span>' : '<span class="' + (last > m ? "pos" : "neg") + '">' + (last > m ? "üstünde" : "altında") + " (" + pc((last / m - 1) * 100, 1) + ")</span>"; }
    return '<div class="vch"><div class="vrh"><span>Son ' + n + ' işlem günü ' + '<b class="' + cls(chg * 100) + '">' + pc(chg * 100, 1) + '</b></span><span class="vrs">' + rng + '</span></div>' +
      '<div class="vpl"><svg viewBox="0 0 1000 200" preserveAspectRatio="none" role="img" aria-label="' + esc(tk(s.symbol)) + ' fiyat grafiği">' + grid +
      '<path d="' + line(s200) + '" class="s200" vector-effect="non-scaling-stroke"/><path d="' + line(s50) + '" class="s50" vector-effect="non-scaling-stroke"/>' +
      '<path d="' + line(pr) + '" fill="none" stroke="' + col + '" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg><div class="yl">' + ylab + '</div></div>' +
      '<div class="vleg"><span><i class="lp" style="background:' + col + '"></i>Fiyat</span><span><i class="l50"></i>SMA 50</span><span><i class="l200"></i>SMA 200</span></div>' +
      '<div class="vsm"><span>1G <b class="' + cls(s.d1) + '">' + pc(s.d1) + '</b></span><span>5G <b class="' + cls(s.d5) + '">' + pc(s.d5) + '</b></span><span>20G <b class="' + cls(s.d20) + '">' + pc(s.d20) + '</b></span><span>Zirve <b class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</b></span><span>SMA 50 ' + dist(l50) + '</span><span>SMA 200 ' + dist(l200) + '</span></div></div>';
  }
  var VRNG = {};
  function vpanel(s) {
    var e = s.est, hasPe = e.pe0 !== null && e.pe0 !== undefined;
    function rw(l, eps, lo, hi, an, rev, pe, ps) {
      return '<tr><td>' + l + '</td><td>' + (eps === null || eps === undefined ? "–" : num(eps, 2)) + '</td><td>' + (pe === null || pe === undefined ? "–" : num(pe, 1)) + '</td><td>' + (lo === null || lo === undefined ? "–" : num(lo, 2) + " – " + num(hi, 2)) + '</td><td>' + (an || "–") + '</td><td>' + mval(rev, e.revu) + '</td><td>' + (ps === null || ps === undefined ? "–" : num(ps, 1)) + '</td></tr>';
    }
    var tah = '<div class="vgrid"><div class="blk wide"><h3>Analist tahminleri</h3><div class="tw"><table><thead><tr><th></th><th>EPS</th><th>İleri F/K</th><th>EPS aralığı</th><th>Analist</th><th>Gelir</th><th>İleri F/S</th></tr></thead><tbody>' +
      rw("Mevcut yıl", e.eps0, e.eps0_lo, e.eps0_hi, e.an0, e.rev0, e.pe0, e.ps0) + rw("Gelecek yıl", e.eps1, e.eps1_lo, e.eps1_hi, e.an1, e.rev1, e.pe1, e.ps1) + '</tbody></table></div>' +
      (e.kur_uyari ? '<p class="vn">F/K gösterilmiyor: hisse fiyatı ile EPS tahmini aynı para biriminde olmayabilir (ADR).</p>' : "") + '</div>';
    var fk = '<div class="vgrid">';
    if (hasPe) {
      function r(l, p, t, f) { return '<tr><td>' + l + '</td><td class="' + cls(p) + '">' + pc(p) + '</td><td class="' + cls(t) + '">' + pc(t) + '</td><td class="' + (f === null || f === undefined ? "neu" : cls(-f)) + '">' + pc(f) + '</td></tr>'; }
      tah += '<div class="blk"><h3>Son 5 ve 20 gün</h3><div class="tw"><table><thead><tr><th></th><th>Fiyat</th><th>Mevcut yıl EPS tahmini</th><th>İleri F/K</th></tr></thead><tbody>' + r("5 gün", s.d5, e.r5, e.pc5) + r("20 gün", s.d20, e.r20, e.pc20) + '</tbody></table></div><p class="vn">EPS tahmini 7 ve 30 gün önceki tahmine göre. F/K değişiminde yeşil ucuzlama, kırmızı pahalanmadır.</p></div>';
      if (e.pc20 !== null && e.pc20 !== undefined && e.r20 !== null && e.r20 !== undefined) {
        function sg2(v, top) { var wd = Math.min(Math.abs(v) / 15 * 50, 50); return '<div class="sg' + (top ? "" : " b") + '" style="left:' + (v >= 0 ? 50 : 50 - wd) + '%;width:' + wd + '%;background:' + (v > 0 ? "var(--down)" : "var(--up)") + '"></div>'; }
        fk += '<div class="blk"><h3>Çarpan neden değişti (20 gün)</h3><div class="vbar" role="img" aria-label="Fiyat ve tahmin etkisi">' + sg2(s.d20, true) + sg2(-e.r20, false) + '</div><p class="vn">Üst çubuk fiyat (' + pc(s.d20) + '), alt çubuk tahmin revizyonu (' + pc(e.r20) + '). Sola giden çubuk çarpanı düşürür (ucuzlar), sağa giden artırır.</p></div>';
      }
    }
    var bl = e.bl, today = DATA.meta.ref_date, b2;
    if (hasPe && bl && bl.for && bl.for < today) { var dm = (e.pe0 / bl.pe - 1) * 100; b2 = '<div class="kv"><span>Bilanço (' + fmtShort(bl.for) + ') öncesi F/K</span><span>' + num(bl.pe, 1) + '</span></div><div class="kv"><span>Bugün</span><span>' + num(e.pe0, 1) + ' <span class="' + cls(-dm) + '">(' + pc(dm) + ')</span></span></div>'; }
    else if (hasPe && s.earn) b2 = '<p class="vn">Bilanço ' + fmtShort(s.earn) + '. Öncesi F/K bu tarihe kadar kaydedilir, bilanço sonrası bugünkü değerle kıyaslanır.</p>';
    else b2 = '<p class="vn">Bilanço öncesi F/K kaydı yok; bir sonraki bilançodan itibaren kaydedilir.</p>';
    fk += '<div class="blk"><h3>Bilançodan beri</h3>' + b2 + '</div>' + vspark(e.eh) + '</div>';
    tah += '</div>';
    var cur = VTAB[s.symbol] || ((s.h && s.h.length >= 25) ? "fiyat" : "tahmin");
    var tabs = [["fiyat", "Fiyat", vchart(s)], ["tahmin", "Tahminler", tah], ["fk", "F/K", fk], ["bilanco", "Bilanço", cur === "bilanco" ? btable(s.symbol) + bilPanel(s.symbol) : ""]];
    var bar = tabs.map(function (t) { return '<button type="button" class="vt' + (cur === t[0] ? " on" : "") + '" data-vt="' + t[0] + '" data-s="' + esc(s.symbol) + '">' + t[1] + "</button>"; }).join("");
    var body = tabs.filter(function (t) { return t[0] === cur; })[0][2];
    return '<div class="vtabs">' + bar + "</div>" + body + '<p class="vn">Kaynak: Yahoo Finance fiyat ve analist tahminleri. "Mevcut yıl", şirketin içinde bulunduğu mali yıldır; takvim yılı olmayabilir (örneğin NVDA için Ocak ayında biter).</p>';
  }
  var TAB = null, TABLOAD = false;
  function tabYukle() {  // tablolar.json (~240 KB) sayfa açılışında değil, ilk kez bir hissenin Bilanço sekmesi açılınca indirilir
    if (TAB || TABLOAD) return;
    TABLOAD = true;
    fetch("tablolar.json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (j) { TAB = (j && j.tablolar) ? j : { tablolar: {} }; if (DATA) draw(); });
  }
  function btable(sym) {
    if (!TAB) { tabYukle(); return ""; }
    var t = TAB.tablolar && TAB.tablolar[sym];
    if (!t) return "";
    function f(v, m) {
      if (v === null || v === undefined) return "–";
      var us = function (x, d) { return x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }); };  // tablo İngilizce biçimde: 1,149.5
      if (m === "p") return us(v, 1) + "%";
      if (m === "d") return us(v, 2);
      return us(v, 1);
    }
    var out = '<div class="btw">';
    t.bolumler.forEach(function (b, i) {
      out += '<table class="bt"><colgroup><col style="width:46%"><col style="width:18%"><col style="width:18%"><col style="width:18%"></colgroup><thead><tr><th>' + esc(b.baslik) + "</th><th></th><th>" + esc(b.etiket || "") + "</th><th></th></tr>" +
        (i === 0 ? "<tr><th>Metric</th><th>Estimate</th><th>Actual</th><th>Result</th></tr>" : "") + "</thead><tbody>" +
        b.satirlar.map(function (r) {
          return '<tr' + (r.vurgu ? ' class="y"' : "") + "><td>" + esc(r.ad) + "</td><td>" + f(r.bek, r.fmt) + (r.bg ? "†" : "") + "</td><td>" + f(r.ger, r.fmt) + "</td><td" + (r.sonuc === "Beat" ? ' class="bb"' : r.sonuc === "Miss" ? ' class="bm"' : "") + ">" + esc(r.sonuc || "") + "</td></tr>";
        }).join("") + "</tbody></table>";
    });
    return out + '<p class="vn">' + esc(fmtShort(t.tarih)) + " · " + (t.dipnot ? esc(t.dipnot) + " " : "") + 'Source: company press release (<a href="' + esc(t.kaynak) + '" target="_blank" rel="noopener">SEC 8-K</a>).</p></div>';
  }
  var BIL = {};
  function bilTable(a, cur) {
    if (!a || !a.satirlar) return "";
    var o = a.ozet;
    var rows = a.satirlar.map(function (x) {
      var oran = x.tur === "puan", c = x.sonuc === "iyileşti" ? "pos" : x.sonuc === "kötüleşti" ? "neg" : "";
      var f = function (v) { return oran ? "%" + num(v, 1) : (x.k === "eps" ? num(v, 2) : money(v / 1e6, cur).replace(/^\+/, "")); };
      var d = x.fark == null ? (x.isaret ? "işaret değişti" : "–") : oran ? (x.fark > 0 ? "+" : "") + num(x.fark, 1) + " puan" : pc(x.fark, 1);
      return "<tr><td>" + esc(x.ad) + "</td><td>" + f(x.once) + "</td><td>" + f(x.simdi) + "</td><td>" + d + '</td><td class="' + c + '">' + esc(x.sonuc) + "</td></tr>";
    }).join("");
    return '<p class="vn">' + fmtShort(a.donem) + " ile karşılaştırma: <b>" + o.iyi + "</b> kalem iyileşti, <b>" + o.kotu + "</b> kalem kötüleşti (" + o.n + " kalem).</p>" +
      '<div class="tw"><table><thead><tr><th>Kalem</th><th>Önce</th><th>Şimdi</th><th>Değişim</th><th>Sonuç</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
  }
  function bilBody(sym) {
    var b = BIL[sym];
    if (b === undefined) return '<p class="vn">Yükleniyor…</p>';
    if (!b || !b.analiz) return '<p class="vn">Bu hisse için bilanço kaydı yok.</p>';
    var a = b.analiz, cur = b.para || null;
    return '<p class="vn">Son çeyrek: dönem sonu ' + fmtShort(a.donem) + ' ' + esc(a.donem.slice(0, 4)) + (cur ? " · para birimi " + esc(cur) : "") + ". Kaynak: Yahoo Finance tabloları; kayıtta " + Object.keys(b.ceyrekler).length + " çeyrek var.</p>" +
      (a.qoq ? '<h3 class="qh">Bir önceki çeyreğe göre</h3>' + bilTable(a.qoq, cur) : '<p class="vn">Bir önceki çeyrek kayıtta yok.</p>');
  }
  function bilPanel(sym) {
    return '<details class="bil" data-s="' + esc(sym) + '"' + (BOPEN[sym] ? " open" : "") + '><summary>Bilanço analizi</summary><div class="bb">' + (BOPEN[sym] ? bilBody(sym) : "") + "</div></details>";
  }
  var BOPEN = {};
  document.addEventListener("toggle", function (e) {
    var d = e.target;
    if (!d || !d.classList || !d.classList.contains("bil")) return;
    var sym = d.getAttribute("data-s");
    if (d.open) BOPEN[sym] = 1; else { delete BOPEN[sym]; return; }
    var box = d.querySelector(".bb"); box.innerHTML = bilBody(sym);
    if (BIL[sym] !== undefined) return;
    fetch("bilanco/" + encodeURIComponent(sym) + ".json?v=" + DATA.meta.ref_date).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (j) { BIL[sym] = j; if (d.open) box.innerHTML = bilBody(sym); });
  }, true);
  function aiTable(a) {
    var ref = DATA.meta.ref_date, hmk = { d5: 1 };
    var cols = [["symbol", "Hisse"], ["mcap", "Piyasa değeri"], ["d1", "1G"], ["d5", "5G"], ["d20", "20G"], ["above50", "SMA 50"], ["above200", "SMA 200"], ["from_high", "Zirveye uzaklık"]];
    var q = AI_Q.trim().toLowerCase();
    var rows = a.stocks.filter(function (s) { if (!q) return true; var nm = (s.name || "").toLowerCase(); return s.symbol.toLowerCase().indexOf(q) === 0 || tk(s.symbol).toLowerCase().indexOf(q) === 0 || (" " + nm).indexOf(" " + q) >= 0; }).sort(function (x, y) {
      var k = AI_SORT.k, u = x[k], v = y[k];
      if (typeof u === "boolean") { u = u ? 1 : 0; v = v ? 1 : 0; }
      if (u === null || u === undefined) return 1; if (v === null || v === undefined) return -1;
      if (typeof u === "string") return u.localeCompare(v) * AI_SORT.dir;
      return (u - v) * AI_SORT.dir;
    });
    var head = cols.map(function (c) { return '<th class="s' + (hmk[c[0]] ? " hm" : "") + '" data-k="' + c[0] + '" tabindex="0" role="button" aria-sort="' + (AI_SORT.k === c[0] ? (AI_SORT.dir > 0 ? "ascending" : "descending") : "none") + '">' + c[1] + (AI_SORT.k === c[0] ? (AI_SORT.dir > 0 ? " ↑" : " ↓") : "") + '</th>'; }).join("");
    function ab(f) { return f === null || f === undefined ? "–" : '<span class="' + (f ? "pos" : "neg") + '">' + (f ? "üstünde" : "altında") + '</span>'; }
    function rowHtml(s) {
      var dl = s.date && s.date !== ref ? '<span class="eb">son kapanış ' + fmtShort(s.date) + '</span>' : "";
      return '<tr><td><div class="hc">' + vchip(s) + '<div><div class="l1"><b>' + esc(tk(s.symbol)) + '</b><span class="px ' + (s.d1 > 0 ? "up" : s.d1 < 0 ? "dn" : "nu") + '">' + esc(px(s.close, s.cur)) + (s.d1 == null ? "" : " · " + pc(s.d1)) + '</span></div><div class="l2">' + sa(s.symbol) + fb(s) + eb(s) + dl + '</div></div></div>' + '</td><td>' + cap(s.mcap) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td>' + ab(s.above50) + '</td><td>' + ab(s.above200) + '</td><td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + zg(s.from_high) + '</td></tr>' + (s.est && VOPEN[s.symbol] ? '<tr class="vp"><td colspan="8">' + vpanel(s) + '</td></tr>' : "");
    }
    function zg(v) { return v == null ? "" : '<span class="zg" aria-hidden="true"><span style="width:' + Math.max(0, Math.min(100, (v + 50) * 2)).toFixed(0) + '%"></span></span>'; }
    var body = rows.map(rowHtml).join("");

    var noMob = { symbol: 1, above50: 1, above200: 1 };
    var mc = cols.filter(function (c) { return !noMob[c[0]]; }), curLabel = (mc.filter(function (c) { return c[0] === AI_SORT.k; })[0] || mc[0])[1];
    var opts = mc.map(function (c) { return '<li role="option" tabindex="0" data-k="' + c[0] + '" aria-selected="' + (AI_SORT.k === c[0]) + '">' + c[1] + '</li>'; }).join("");
    var sb = '<div class="srch"><input type="search" id="aiq" value="' + esc(AI_Q) + '" placeholder="Hisse ara: NVDA, Micron, TSM…" autocomplete="off" aria-label="Hisse ara">' + (q ? '<span>' + rows.length + ' / ' + a.stocks.length + '</span>' : "") + '</div>';
    if (q && !rows.length) return sb + '<p class="fine">Eşleşen hisse yok.</p>';
    return sb + '<div class="sortbar"><span>Sırala</span><div class="dd"><button type="button" class="ddb" id="aisort" aria-haspopup="listbox" aria-expanded="false">' + esc(curLabel) + '</button><ul class="ddl" role="listbox" hidden>' + opts + '</ul></div></div><div class="tw"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
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
      var ps = OZ.paragraphs, last = ps[ps.length - 1], rest = ps.slice(0, -1);
      var as = OZ.asya && OZ.asya.length ? '<div class="sum"><h3 class="qh">Gece: Asya ve Bitcoin</h3>' + OZ.asya.map(function (x) { return "<p>" + esc(x) + "</p>"; }).join("") + "</div>" : "";
      var more = rest.length || as ? '<details class="sgd"><summary>Tüm özet</summary><div class="sum">' + rest.map(function (x) { return "<p>" + esc(x) + "</p>"; }).join("") + "</div>" + as + "</details>" : "";
      return h2("Günün özeti") + '<div class="sum"><p>' + esc(last).replace(/^Özetle:/, "<b>Özetle:</b>") + "</p></div>" + more;
    }
    return "";
  }
  function valuation(d) {
    var v = d.degerleme;
    if (!v || v.tarih !== d.meta.ref_date) return "";
    var zc = { "ucuz": "pos", "normal": "", "pahalı": "neg", "çok pahalı": "neg" };
    function sg(x, dec) { return x == null ? "" : ' · 20 günde <span class="' + cls(x) + '">' + (x > 0 ? "+" : x < 0 ? "−" : "") + num(Math.abs(x), dec) + "%</span>"; }
    var out = h2("Değerleme özeti");
    var er = (v.endeks || []).map(function (e) {
      var ort = e.ort10 != null ? ' · <span class="' + (zc[e.bolge] || "") + '"><b>' + esc(e.bolge.charAt(0).toUpperCase() + e.bolge.slice(1)) + "</b></span> (10 yıllık ortalama " + num(e.ort10, 1) + ")" : "";
      return '<div class="gxrow"><span><b>' + esc(e.ad) + "</b><small>son 12 ay " + num(e.son, 1) + ort + sg(e.d20, 1) + "</small></span><big>" + num(e.ileri, 1) + "x</big></div>";
    }).join("");
    if (er) out += '<div class="gxlist">' + er + "</div>";
    function neden(x) { return x.fiyat == null || x.eps == null ? "" : Math.abs(x.fiyat) >= Math.abs(x.eps) ? "fiyat " + (x.fiyat > 0 ? "arttı" : "düştü") + " (" + pc(x.fiyat, 0) + ")" : "tahmin " + (x.eps > 0 ? "yükseldi" : "düştü") + " (" + pc(x.eps, 0) + ")"; }
    function liste(L, bil) {
      var mx = Math.max.apply(null, L.map(function (x) { return Math.abs(x.deg || 0); }).concat([20]));
      return '<div class="sxch"><span></span><span>Hisse</span><span>F/K değişimi</span><span>İleri F/K</span><span class="hm"></span></div>' + chainRows(L.map(function (x) {
        return { ad: esc(tk(x.s)), alt: (bil ? "bilanço " + fmtShort(x.bilanco) + " · " + num(x.once, 1) + " → " + num(x.simdi, 1) + " · " : (x.deg > 0 ? "pahalandı · " : "ucuzladı · ")) + neden(x), sc: "neu",
          bar: centered(x.deg, mx), v: (x.deg > 0 ? "+" : "−") + num(Math.abs(x.deg), 0) + "%", vc: x.deg > 0 ? "neg" : "pos", c1: num(x.simdi, 1) + "x", c2: "" };
      }));
    }
    out += h3q("Bilanço sonrası yeniden fiyatlanma");
    out += v.bilanco && v.bilanco.length ? liste(v.bilanco, true) : '<p class="fine">Bilanço açıklayıp ileri F/K\'si %15 ve üstü değişen hisse yok.</p>';
    if (v.hareket && v.hareket.length) out += h3q("5 günde çarpanı en çok değişenler") + liste(v.hareket.slice(0, 6), false) + '<p class="fine">Çubuk, F/K\'nin kaç yüzde değiştiğini gösterir: sola ucuzladı, sağa pahalandı.</p>';
    var al = d.altsektor;
    if (al && al.tarih === d.meta.ref_date) {
      var iyi = [], kotu = [], kar = [], dg = [];
      al.gruplar.forEach(function (g) {
        var u = g.uyum || {}, k = u.karar || "";
        if (k.indexOf("iyi") >= 0) iyi.push(g.ad); else if (k.indexOf("kötü") >= 0) kotu.push(g.ad); else if (k === "karışık mesaj") kar.push(g.ad);
        if (u.onceki && u.karar !== u.onceki && u.karar !== "yetersiz veri" && u.onceki !== "yetersiz veri" && u.karar.indexOf("karma") !== 0) dg.push(g.ad);
      });
      function sat(et, cl, L) { return L.length ? '<div class="gxlab"><b class="' + cl + '">' + et + "</b><span>" + L.map(esc).join(", ") + "</span></div>" : ""; }
      var alt = sat("İyi yönde", "pos", iyi) + sat("Kötü yönde", "neg", kotu) + sat("Karışık", "neu", kar) + sat("Dünden değişen", "", dg);
      if (alt) out += h3q("Alt sektörlerde bilanço (önceki çeyreğe göre)") + alt + '<p class="fine">Ayrıntı için Alt Sektörler sekmesine bakın.</p>';
    }
    if (v.ai_medyan != null) out += '<p class="fine">Yapay zeka listesinin medyan ileri F/K\'si ' + num(v.ai_medyan, 1) + ".</p>";
    return out;
  }
  function chgBox(items, since, note) {
    items = (items || []).filter(function (i) { return i.k !== "sma" && i.k !== "sma50"; });
    if (!items.length) return "";
    var arrow = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 6h8M7 3l3 3-3 3"/></svg>';
    function tc(t) { return t === "Yükseliş" || t === "Lider" || t === "Güçlü" || t === "Risk-on" || t === "GENİŞ" ? "pos" : t === "Düşüş" || t === "Geride" || t === "Risk-off" || t === "DAR" ? "neg" : ""; }
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
    var ok = a.etfs.filter(function (m) { return m.available; }).sort(function (x, y) { return (y.rel.spy[20] == null ? -1e9 : y.rel.spy[20]) - (x.rel.spy[20] == null ? -1e9 : x.rel.spy[20]); });
    var mx = Math.max.apply(null, ok.map(function (m) { return Math.abs(m.rel.spy[20] || 0); }).concat([2]));
    function smaTxt(n, flag) { return n + (flag == null ? " –" : flag ? " ↑" : " ↓"); }
    var list = ok.map(function (m) {
      var r = m.rel.spy[20];
      return { ad: m.symbol + ' <span class="mute" style="font-weight:400">' + esc(m.name) + "</span>", alt: "QQQ'ya göre " + pt(m.rel.qqq[20], 1) + " · SMA " + smaTxt(50, m.above50) + " · " + smaTxt(200, m.above200), sc: "neu",
        bar: centered(r, mx), v: pt(r, 1), vc: cls(r), c1: pc(m.d20, 1), c1c: cls(m.d20), c2: pc(m.d5, 1), c2c: cls(m.d5) };
    });
    var miss = a.etfs.filter(function (m) { return !m.available; }).map(function (m) { return m.symbol; });
    var e = '<div class="sxch"><span></span><span>ETF</span><span>SPY\'a göre 20G</span><span>20G</span><span class="hm">5G</span></div>' + chainRows(list) + (miss.length ? '<p class="fine neu">Veri alınamadı: ' + miss.join(", ") + ".</p>" : "");
    var ca = (a.changes && a.changes.items) || [], cs = chgFor("ai"), out = chgBox(ca.concat(cs), (a.changes && a.changes.since) || (DATA.changes && DATA.changes.since), "AI hisseleri ve ETF'leri") + h2("Yapay zeka ve yarı iletken") +
      sub("ETF'ler SPY'a göre son 20 günde en iyiden en kötüye sıralı. Puan, ETF'in SPY'dan kaç puan fazla ya da az getiri sağladığıdır.") + e +
      '<p class="fine">SMA 50 ve 200: fiyatın o günlük ortalamanın üstünde (↑) ya da altında (↓) olduğunu gösterir. Çubuk SPY\'dan fazla (sağa) ya da az (sola) getiriyi gösterir.</p>';
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
  function subsector(d) {
    var al = d.altsektor;
    if (!al || al.tarih !== d.meta.ref_date) return h2("Alt sektörler") + '<p class="vn">Bu gün için alt sektör verisi henüz yayında değil; bir sonraki veri güncellemesiyle birlikte görünecek. Bu sekmede hisseler gruplara ayrılır, grupların fiyat, tahmin ve bilanço göstergeleri karşılaştırılır.</p>';
    function pc(v, dec, suf) { return v == null ? '<span class="neu">–</span>' : '<span class="' + cls(v) + '">' + (v > 0 ? "+" : v < 0 ? "−" : "") + num(Math.abs(v), dec) + (suf || "%") + "</span>"; }
    function bar(u) {
      if (!u || !u.n) return '<span class="neu">–</span>';
      var w = function (x) { return (x / u.n * 100).toFixed(1) + "%"; };
      return '<span class="sbar" title="' + u.iyi + " iyi · " + u.karisik + " karışık · " + u.kotu + " zayıf (" + u.n + ' şirket)"><i class="g" style="width:' + w(u.iyi) + '"></i><i class="y" style="width:' + w(u.karisik) + '"></i><i class="r" style="width:' + w(u.kotu) + '"></i></span>';
    }
    var head = '<div class="sh"><span>Grup</span><span>5 gün</span><span>20 gün</span><span>Gelir, çeyrek</span><span>Bilançolar</span><span>İleri F/K</span></div>';
    var SA = { gelir: "gelir", brut_marj: "brüt marj", faaliyet_marj: "faaliyet marjı", net_marj: "net marj", fcf_marj: "FCF marjı", stok_oran: "stok/gelir" };
    var rows = al.gruplar.map(function (g) {
      var o = g.ozet, u = g.uyum;
      var body = g.uyeler.map(function (m) {
        var b = m.bil || {};
        return "<tr><td><b>" + esc(tk(m.s)) + "</b></td><td>" + pc(m.d5, 1) + "</td><td>" + pc(m.d20, 1) + "</td><td>" + pc(b.qoq_gelir, 0) + "</td><td>" + pc(b.qoq_brut, 1, " puan") + "</td><td>" + (m.pe == null ? "–" : num(m.pe, 1) + "x") + "</td><td>" + (m.earn ? fmtShort(m.earn) : "–") + "</td></tr>";
      }).join("");
      var karar = u && u.karar.indexOf("karma") !== 0 && u.karar !== "yetersiz veri" ? "<p class=\"vn\"><b>Bilançolar:</b> " + esc(u.karar) + ". " + Object.keys(u.sinyal).map(function (k) { var x = u.sinyal[k]; return SA[k] + " " + x.iyi + "↑ " + x.kotu + "↓"; }).join(" · ") + (u.ayrisan && u.ayrisan.length ? ". Ayrışanlar: " + u.ayrisan.map(function (x) { return esc(tk(x)); }).join(", ") : "") + ".</p>" : "";
      var ok = g.okuma ? '<p class="vn">' + esc(g.okuma) + "</p>" : "";
      var ds = o.dislanan && o.dislanan.length ? '<p class="vn neg">Verisi şüpheli, medyana alınmayan: ' + o.dislanan.map(function (x) { return esc(tk(x)); }).join(", ") + ".</p>" : "";
      return '<details class="sr"><summary class="sh"><span><b>' + esc(g.ad) + "</b> <small>" + o.n + "</small></span><span>" + pc(o.d5, 1) + "</span><span>" + pc(o.d20, 1) + "</span><span>" + pc(o.gelir_qoq, 0) + "</span><span>" + bar(u) + "</span><span>" + (o.pe == null ? "–" : num(o.pe, 1) + "x") + "</span></summary>" +
        '<div class="sd">' + ok + karar + ds + '<div class="tw"><table><thead><tr><th>Hisse</th><th>5G</th><th>20G</th><th>Gelir, çeyrek</th><th>Brüt marj</th><th>İleri F/K</th><th>Bilanço tarihi</th></tr></thead><tbody>' + body + "</tbody></table></div></div></details>";
    }).join("");
    var out = h2("Alt sektörler") + sub("Her satır bir grup, medyan değerlerle. Çubuk gruptaki bilançoların iyi (yeşil), karışık (sarı) ve zayıf (kırmızı) oranını gösterir. Satıra tıklayınca hisseler açılır.") + '<div class="stb">' + head + rows + "</div>" +
      '<p class="fine">Gelir, en son bilanço çeyreğinin bir önceki çeyreğe göre değişimidir. Fiyat hareketleri 5 ve 20 işlem günlüktür.</p>';
    if (al.zincir && al.zincir.length) {
      out += '<details class="sgd"><summary>Talepten üretime sıra</summary><div class="tw"><table><thead><tr><th>Halka</th><th>Yatırım harcaması</th><th>Gelir</th><th>Brüt marj</th><th>20G</th></tr></thead><tbody>' +
        al.zincir.map(function (z) { return "<tr><td><b>" + esc(z.ad) + "</b></td><td>" + pc(z.capex_qoq, 0) + "</td><td>" + pc(z.gelir_qoq, 0) + "</td><td>" + pc(z.brut_qoq, 1, " puan") + "</td><td>" + pc(z.d20, 1) + "</td></tr>"; }).join("") + "</tbody></table></div>" +
        '<p class="fine">Hepsi önceki çeyreğe göre. Yatırım harcaması Yahoo nakit akış tablosundaki maddi duran varlık alımıdır; finansal kiralama dahil değildir. Büyük bulut şirketleri listede yoktur.</p></details>';
    }
    if (al.olaylar && al.olaylar.length) {
      var evs = al.olaylar.slice().reverse().slice(0, 10).map(function (o) {
        var gs = Object.keys(o.gunler).sort(), best = gs[0];
        gs.forEach(function (k) { if (Math.abs(o.gunler[k].d1 || 0) > Math.abs(o.gunler[best].d1 || 0)) best = k; });
        var x = o.gunler[best];
        return "<tr><td><b>" + esc(tk(o.s)) + "</b></td><td>" + fmtShort(o.tarih) + "</td><td>" + pc(x.d1, 1) + "</td><td>" + pc(x.es, 1) + "</td><td>" + x.yuk + "/" + x.n + "</td></tr>";
      }).join("");
      out += '<details class="sgd"><summary>Bilanço açıklayan şirket gruba ne yaptırdı?</summary><div class="tw"><table><thead><tr><th>Şirket</th><th>Bilanço</th><th>Kendi hareketi</th><th>Grubun medyanı</th><th>Yükselen</th></tr></thead><tbody>' + evs + "</tbody></table></div></details>";
    }
    return out + (al.atanmamis && al.atanmamis.length ? '<p class="vn">Gruba atanmamış hisseler "Diğer"de: ' + al.atanmamis.map(function (x) { return esc(tk(x)); }).join(", ") + ".</p>" : "");
  }
  function tabs(d) {
    return '<section class="tab" id="t-genel">' + regime(d.regime) + summary(d) + chgBox(chgFor("genel"), d.changes && d.changes.since, "ana göstergeler ve ETF'ler") + h2("Göstergeler") + levels(d) + valuation(d) + '</section>' +
      '<section class="tab" id="t-genislik">' + chgBox(chgFor("genislik"), d.changes && d.changes.since, "S&P 500 genişliği") + breadth(d.breadth) + pairs(d.pairs) + '</section>' +
      '<section class="tab" id="t-sektor">' + chgBox(chgFor("sektor"), d.changes && d.changes.since, "sektör ETF'leri") + sectors(d.sectors) + '</section>' +
      '<section class="tab" id="t-ai">' + ai(d.ai) + '</section>' +
      '<section class="tab" id="t-aihisse">' + aiStocks(d.ai) + '</section>' +
      '<section class="tab" id="t-altsektor">' + subsector(d) + '</section>';
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
      var hs = Array.prototype.map.call(t.querySelectorAll(":scope > thead th"), function (h) { return h.textContent.replace(/[↑↓]/g, "").trim(); });
      if (!hs.length) return;
      Array.prototype.forEach.call(t.querySelectorAll(":scope > tbody > tr"), function (tr) {
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
    var k = th.getAttribute("data-k");
    AI_SORT = { k: k, dir: AI_SORT.k === k ? -AI_SORT.dir : (k === "symbol" || k === "status" || k === "trend" ? 1 : -1) };
    draw();
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-vt],[data-vr]") : null;
    if (!t || !DATA) return;
    var sy = t.getAttribute("data-s");
    if (t.hasAttribute("data-vt")) VTAB[sy] = t.getAttribute("data-vt"); else VRNG[sy] = parseInt(t.getAttribute("data-vr"), 10);
    draw();
  });
  document.addEventListener("input", function (e) {
    var t = e.target; if (!t || t.id !== "aiq" || !DATA) return;
    var pos = t.selectionStart; AI_Q = t.value; draw();
    var n = document.querySelector("#aiq"); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (x) {} }
  });
  document.addEventListener("keydown", function (e) {
    if ((e.key === "Enter" || e.key === " ") && e.target && e.target.matches && e.target.matches("th.s, .ddl li")) { e.preventDefault(); e.target.click(); }
    if (e.key === "Escape") closeDd();
  });
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".vb");
    if (!b || !DATA) return;
    var sym = b.getAttribute("data-s"), row = b.closest("tr"), nx = row.nextElementSibling;
    if (nx && nx.classList.contains("vp")) { nx.parentNode.removeChild(nx); delete VOPEN[sym]; b.setAttribute("aria-expanded", "false"); return; }
    var s = DATA.ai.stocks.filter(function (x) { return x.symbol === sym; })[0];
    if (!s || !s.est) return;
    var tr = document.createElement("tr"); tr.className = "vp"; tr.innerHTML = '<td colspan="8">' + vpanel(s) + '</td>';
    row.parentNode.insertBefore(tr, row.nextSibling); labels(); VOPEN[sym] = 1; b.setAttribute("aria-expanded", "true");
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
