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
  function vpanel(s) {
    var e = s.est, hasPe = e.pe0 !== null && e.pe0 !== undefined;
    function rw(l, eps, lo, hi, an, rev, pe, ps) {
      return '<tr><td>' + l + '</td><td>' + (eps === null || eps === undefined ? "–" : num(eps, 2)) + '</td><td>' + (pe === null || pe === undefined ? "–" : num(pe, 1)) + '</td><td>' + (lo === null || lo === undefined ? "–" : num(lo, 2) + " – " + num(hi, 2)) + '</td><td>' + (an || "–") + '</td><td>' + mval(rev, e.revu) + '</td><td>' + (ps === null || ps === undefined ? "–" : num(ps, 1)) + '</td></tr>';
    }
    var out = '<div class="vgrid"><div class="blk wide"><h3>Analist tahminleri</h3><div class="tw"><table><thead><tr><th></th><th>EPS</th><th>İleri F/K</th><th>EPS aralığı</th><th>Analist</th><th>Gelir</th><th>İleri F/S</th></tr></thead><tbody>' +
      rw("Mevcut yıl", e.eps0, e.eps0_lo, e.eps0_hi, e.an0, e.rev0, e.pe0, e.ps0) + rw("Gelecek yıl", e.eps1, e.eps1_lo, e.eps1_hi, e.an1, e.rev1, e.pe1, e.ps1) + '</tbody></table></div>' +
      (e.kur_uyari ? '<p class="vn">F/K gösterilmiyor: hisse fiyatı ile EPS tahmini aynı para biriminde olmayabilir (ADR).</p>' : "") + '</div>';
    if (hasPe) {
      function r(l, p, t, f) { return '<tr><td>' + l + '</td><td class="' + cls(p) + '">' + pc(p) + '</td><td class="' + cls(t) + '">' + pc(t) + '</td><td class="' + (f === null || f === undefined ? "neu" : cls(-f)) + '">' + pc(f) + '</td></tr>'; }
      out += '<div class="blk"><h3>Son 5 ve 20 gün</h3><div class="tw"><table><thead><tr><th></th><th>Fiyat</th><th>Mevcut yıl EPS tahmini</th><th>İleri F/K</th></tr></thead><tbody>' + r("5 gün", s.d5, e.r5, e.pc5) + r("20 gün", s.d20, e.r20, e.pc20) + '</tbody></table></div><p class="vn">EPS tahmini 7 ve 30 gün önceki tahmine göre. F/K değişiminde yeşil ucuzlama, kırmızı pahalanmadır.</p></div>';
      if (e.pc20 !== null && e.pc20 !== undefined && e.r20 !== null && e.r20 !== undefined) {
        function sg2(v, top) { var wd = Math.min(Math.abs(v) / 15 * 50, 50); return '<div class="sg' + (top ? "" : " b") + '" style="left:' + (v >= 0 ? 50 : 50 - wd) + '%;width:' + wd + '%;background:' + (v > 0 ? "var(--down)" : "var(--up)") + '"></div>'; }
        out += '<div class="blk"><h3>Çarpan neden değişti (20 gün)</h3><div class="vbar" role="img" aria-label="Fiyat ve tahmin etkisi">' + sg2(s.d20, true) + sg2(-e.r20, false) + '</div><p class="vn">Üst çubuk fiyat (' + pc(s.d20) + '), alt çubuk tahmin revizyonu (' + pc(e.r20) + '). Sola giden çubuk çarpanı düşürür (ucuzlar), sağa giden artırır.</p></div>';
      }
    }
    var bl = e.bl, today = DATA.meta.ref_date, b2;
    if (hasPe && bl && bl.for && bl.for < today) { var dm = (e.pe0 / bl.pe - 1) * 100; b2 = '<div class="kv"><span>Bilanço (' + fmtShort(bl.for) + ') öncesi F/K</span><span>' + num(bl.pe, 1) + '</span></div><div class="kv"><span>Bugün</span><span>' + num(e.pe0, 1) + ' <span class="' + cls(-dm) + '">(' + pc(dm) + ')</span></span></div>'; }
    else if (hasPe && s.earn) b2 = '<p class="vn">Bilanço ' + fmtShort(s.earn) + '. Öncesi F/K bu tarihe kadar kaydedilir, bilanço sonrası bugünkü değerle kıyaslanır.</p>';
    else b2 = '<p class="vn">Bilanço öncesi F/K kaydı yok; bir sonraki bilançodan itibaren kaydedilir.</p>';
    out += '<div class="blk"><h3>Bilançodan beri</h3>' + b2 + '</div>' + vspark(e.eh) + '</div>' + bilPanel(s.symbol) + '<p class="vn">Kaynak: Yahoo Finance analist tahminleri. "Mevcut yıl", şirketin içinde bulunduğu mali yıldır; takvim yılı olmayabilir (örneğin NVDA için Ocak ayında biter).</p>';
    return out;
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
      var dl = s.date && s.date !== ref ? '<span class="eb">son kapanış ' + fmtShort(s.date) + '</span>' : "";
      return '<tr><td><div class="hc">' + vchip(s) + '<div><div class="l1"><b>' + esc(tk(s.symbol)) + '</b><span class="px ' + (s.d1 > 0 ? "up" : s.d1 < 0 ? "dn" : "nu") + '">' + esc(px(s.close, s.cur)) + (s.d1 == null ? "" : " · " + pc(s.d1)) + '</span></div><div class="l2">' + sa(s.symbol) + fb(s) + eb(s) + dl + '</div></div></div>' + '</td><td>' + cap(s.mcap) + '</td><td class="' + cls(s.d1) + '">' + pc(s.d1) + '</td><td class="hm ' + cls(s.d5) + '">' + pc(s.d5) + '</td><td class="' + cls(s.d20) + '">' + pc(s.d20) + '</td><td>' + ab(s.above50) + '</td><td>' + ab(s.above200) + '</td><td class="' + cls(s.from_high) + '">' + pc(s.from_high, 1) + '</td></tr>' + (s.est && VOPEN[s.symbol] ? '<tr class="vp"><td colspan="8">' + vpanel(s) + '</td></tr>' : "");
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
  function valuation(d) {
    var v = d.degerleme;
    if (!v || v.tarih !== d.meta.ref_date) return "";
    var out = "", z = { "ucuz": "pos", "normal": "", "pahalı": "neg", "çok pahalı": "neg" };
    (v.endeks || []).forEach(function (e) {
      var m = "ileri F/K <b>" + num(e.ileri, 1) + "</b>";
      if (e.son != null) m += " · son 12 ay " + num(e.son, 1);
      if (e.d5 != null) m += " · 5 günde " + pc(e.d5, 1);
      if (e.d20 != null) m += " · 20 günde " + pc(e.d20, 1);
      var t = "";
      if (e.ort10 != null) t = " 10 yıllık ortalama " + num(e.ort10, 1) + (e.ort5 != null ? ", 5 yıllık " + num(e.ort5, 1) : "") + "; şu an ortalamanın %" + num(Math.abs(e.ort10_oran - 1) * 100, 0) + " " + (e.ort10_oran >= 1 ? "üstünde" : "altında") + ' → <span class="' + (z[e.bolge] || "") + '"><b>' + esc(e.bolge) + "</b></span>.";
      var k = e.ilk && e.ilk.length ? " Kazançların %" + num(e.ilk.reduce(function (a, x) { return a + x[1]; }, 0), 0) + "'i ilk " + e.ilk.length + " şirkette (" + e.ilk.map(function (x) { return esc(tk(x[0])); }).join(", ") + ")." : "";
      out += "<p><b>" + esc(e.ad) + ":</b> " + m + "." + t + k + "</p>";
    });
    function sat(x, bil) {
      var why = x.fiyat != null && x.eps != null ? " Fiyat " + pc(x.fiyat, 1) + ", mevcut yıl EPS tahmini " + pc(x.eps, 1) + " (5 gün)." : "";
      return "<p><b>" + esc(tk(x.s)) + "</b> " + (bil ? "bilançodan (" + fmtShort(x.bilanco) + ") beri " : "5 günde ") + '<span class="' + (x.deg > 0 ? "neg" : "pos") + '">' + esc(x.yon) + "</span>: ileri F/K " + (bil ? num(x.once, 1) + " → " : "") + num(x.simdi, 1) + " (" + pc(x.deg, 0) + ")." + (bil ? "" : why) + "</p>";
    }
    if (v.bilanco && v.bilanco.length) out += h3q("Bilanço sonrası yeniden fiyatlanma") + v.bilanco.map(function (x) { return sat(x, true); }).join("");
    else out += '<p class="vn">Bilanço açıklayıp ileri F/K\'si bilanço öncesine göre %15 ve üstü değişen yapay zeka listesi hissesi yok.</p>';
    if (v.hareket && v.hareket.length) out += h3q("5 günde en çok değişen çarpanlar") + v.hareket.map(function (x) { return sat(x, false); }).join("");
    var al = d.altsektor;
    if (al && al.tarih === d.meta.ref_date) {
      var iyi = [], kotu = [], kar = [], dgs = [];
      al.gruplar.forEach(function (g) {
        var uu = g.uyum, k = uu && uu.karar || "";
        if (k.indexOf("iyi") >= 0) iyi.push(g.ad); else if (k.indexOf("kötü") >= 0) kotu.push(g.ad); else if (k === "karışık mesaj") kar.push(g.ad);
        if (uu && uu.onceki && uu.karar !== uu.onceki && uu.karar !== "yetersiz veri" && uu.onceki !== "yetersiz veri") dgs.push(g.ad + ": " + uu.onceki + " → " + uu.karar);
      });
      var t = "";
      if (iyi.length) t += "Bilançoları (önceki çeyreğe göre) birbirini iyi yönde doğrulayan gruplar: " + iyi.map(esc).join(", ") + ". ";
      if (kotu.length) t += "Kötü yönde doğrulayanlar: " + kotu.map(esc).join(", ") + ". ";
      if (kar.length) t += "Karışık mesaj veren gruplar: " + kar.map(esc).join(", ") + ". ";
      if (dgs.length) t += "Bir önceki güne göre değişenler: " + dgs.map(esc).join("; ") + ".";
      if (t) out += h3q("Alt sektörler") + "<p>" + t + "</p>";
    }
    if (v.ai_medyan != null) out += '<p class="vn">Yapay zeka listesinin medyan ileri F/K\'si ' + num(v.ai_medyan, 1) + " (" + v.ai_n + " hisse).</p>";
    return h2("Değerleme özeti") + '<div class="sum">' + out + "</div>";
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
  function subsector(d) {
    var al = d.altsektor;
    if (!al || al.tarih !== d.meta.ref_date) return h2("Alt sektörler") + '<p class="vn">Bu gün için alt sektör verisi henüz yayında değil; bir sonraki veri güncellemesiyle birlikte görünecek. Bu sekmede hisseler gruplara ayrılır, grupların fiyat, tahmin ve bilanço göstergeleri karşılaştırılır.</p>';
    function c(v, dec, suf) { return v == null ? '<td class="neu">–</td>' : '<td class="' + cls(v) + '">' + (v > 0 ? "+" : v < 0 ? "−" : "") + num(Math.abs(v), dec) + (suf || "%") + "</td>"; }
    function uyumHucre(u) {
      if (!u || u.karar === "yetersiz veri") return '<td class="neu">Yetersiz veri' + (u ? " (" + u.n + " bilanço)" : "") + "</td>";
      var cl = u.karar.indexOf("iyi") >= 0 ? "pos" : u.karar.indexOf("kötü") >= 0 ? "neg" : "neu";
      return '<td class="' + cl + '">' + esc(u.karar.charAt(0).toUpperCase() + u.karar.slice(1)) + "<small>" + u.iyi + " iyi · " + u.karisik + " karışık · " + u.kotu + " kötü (" + u.n + " şirket)</small></td>";
    }
    function surHucre(x) {
      if (!x || !x.n) return '<td class="neu">–</td>';
      return "<td>" + x.asti + " aştı · " + x.kacirdi + " kaçırdı" + (x.beklentide ? " · " + x.beklentide + " beklentide" : "") + "<small>medyan " + (x.medyan > 0 ? "+" : "") + num(x.medyan, 1) + "% (" + x.n + " şirket)</small></td>";
    }
    function plain(v) { return v == null ? '<td class="neu">–</td>' : "<td>" + num(v, 1) + "</td>"; }
    var rows = al.gruplar.map(function (g) {
      var o = g.ozet;
      return "<tr><td><b>" + esc(g.ad) + "</b><small>" + o.n + " hisse · 5 günde " + o.yukselen5 + " yükselen</small></td>" + c(o.d5, 1) + c(o.d20, 1) + c(o.r20, 1) + c(o.eps_b, 0) + plain(o.pe) + c(o.gelir_qoq, 0) + c(o.brut_qoq, 1, " puan") + surHucre(o.surpriz) + uyumHucre(g.uyum) + "</tr>";
    }).join("");
    var out = h2("Alt sektörler") + '<div class="tw"><table><thead><tr><th>Grup</th><th>5G</th><th>20G</th><th>EPS revizyonu 20G</th><th>EPS büyümesi (gelecek yıl)</th><th>İleri F/K</th><th>Gelir (önceki çeyreğe göre)</th><th>Brüt marj değişimi (önceki çeyreğe göre)</th><th>Beklenti sürprizi (son bilanço)</th><th>Bilançolar birbirini doğruluyor mu?</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
      '<p class="vn">Her sayı grubun medyanıdır (aşırı değerlerden etkilenmez). Fiyat hareketleri 5 ve 20 işlem günlüktür. EPS revizyonu mevcut yıl tahminlerinin son 30 günde değişimi, EPS büyümesi gelecek yıl tahmininin mevcut yıla göre artışıdır. Gelir ve brüt marj, en son bilanço çeyreğinin bir önceki çeyrekle kıyaslamasıdır (hızlı değişen alanlarda önemli olan ivmedir); hisselerin çeyrek tarihleri aynı olmayabilir.</p>';
    if (al.zincir && al.zincir.length) {
      out += h3q("Talepten üretime zincir") + '<div class="tw"><table><thead><tr><th>Halka</th><th>Yatırım harcaması (önceki çeyreğe göre)</th><th>Gelir (önceki çeyreğe göre)</th><th>Brüt marj değişimi</th><th>Fiyat 20G</th></tr></thead><tbody>' +
        al.zincir.map(function (z) { return "<tr><td><b>" + esc(z.ad) + "</b><small>" + z.bil_n + " bilanço</small></td>" + c(z.capex_qoq, 0) + c(z.gelir_qoq, 0) + c(z.brut_qoq, 1, " puan") + c(z.d20, 1) + "</tr>"; }).join("") + "</tbody></table></div>" +
        '<p class="vn">Sıra talepten üretime doğrudur: yapay zeka altyapısını kuranlar, sunucu, işlemci, bellek ve bağlantı, foundry ve ekipman. Büyük bulut şirketleri (Microsoft, Amazon, Google, Meta) listede olmadığından talep tarafındaki yatırım harcaması yalnızca listedeki bulut ve altyapı şirketlerini yansıtır; tam tablo değildir.</p>';
    }
    if (al.olaylar && al.olaylar.length) {
      var evs = al.olaylar.slice().reverse().slice(0, 10).map(function (o) {
        var gs = Object.keys(o.gunler).sort(), best = gs[0];
        gs.forEach(function (k) { if (Math.abs(o.gunler[k].d1 || 0) > Math.abs(o.gunler[best].d1 || 0)) best = k; });
        var x = o.gunler[best];
        return "<tr><td><b>" + esc(tk(o.s)) + "</b><small>" + esc(o.grup) + "</small></td><td>" + fmtShort(o.tarih) + "</td>" + c(x.d1, 1) + c(x.es, 1) + "<td>" + x.yuk + "/" + x.n + "</td></tr>";
      }).join("");
      out += h3q("Bilanço açıklayan şirket gruba ne yaptırdı?") + '<div class="tw"><table><thead><tr><th>Şirket</th><th>Bilanço</th><th>Kendi hareketi (en büyük gün)</th><th>Gruptaki diğerlerinin medyanı</th><th>Yükselen / toplam</th></tr></thead><tbody>' + evs + "</tbody></table></div>" +
        '<p class="vn">Kayıt bu özelliğin devreye girdiği günden itibaren biriktiği için geçmiş bilançolar yok. Bilanço seans sonrası açıklanırsa tepki ertesi günü görünür; bu yüzden her şirket için açıklama sonrası günlerden en büyük hareket seçilir.</p>';
    }
    al.gruplar.forEach(function (g) {
      var o = g.ozet;
      var body = g.uyeler.map(function (u) {
        var b = u.bil || {};
        return "<tr><td><b>" + esc(tk(u.s)) + "</b></td>" + c(u.d5, 1) + c(u.d20, 1) + c(u.r20, 1) + plain(u.pe) + c(b.qoq_gelir, 0) + c(b.qoq_brut, 1, " puan") + "<td>" + (b.qoq_stok == null ? "–" : (b.qoq_stok > 0 ? "+" : "") + num(b.qoq_stok, 1) + " puan") + "</td><td>" + (u.earn ? fmtShort(u.earn) : "–") + "</td></tr>";
      }).join("");
      var SA = { gelir: "gelir", brut_marj: "brüt marj", faaliyet_marj: "faaliyet marjı", net_marj: "net marj", fcf_marj: "FCF marjı", stok_oran: "stok/gelir" };
      function uyP(u, bas) {
        if (!u || u.karar === "yetersiz veri") return "";
        return '<p class="vn"><b>Bilanço uyumu (' + bas + "):</b> " + esc(u.karar) + ". " + Object.keys(u.sinyal).map(function (k) { var x = u.sinyal[k]; return SA[k] + ": " + x.iyi + " iyileşti, " + x.kotu + " kötüleşti"; }).join(" · ") + "." +
          (u.ayrisan && u.ayrisan.length ? " Ayrışanlar: " + u.ayrisan.map(function (x) { return esc(tk(x)); }).join(", ") + "." : "") + "</p>";
      }
      var uy = uyP(g.uyum, "bir önceki çeyreğe göre");
      var ok = g.okuma ? '<p class="vn"><b>Okuma:</b> ' + esc(g.okuma) + "</p>" : "";
      var ds = o.dislanan && o.dislanan.length ? '<p class="vn neg">Verisi şüpheli bulunup medyanlara alınmayanlar: ' + o.dislanan.map(function (x) { return esc(tk(x)); }).join(", ") + " (işaretli satırların üzerine gelince neden yazar).</p>" : "";
      var fc = o.fcf_n ? " · " + o.fcf_pozitif + "/" + o.fcf_n + " hissede FCF pozitif" : "";
      out += '<details class="sgd"><summary>' + esc(g.ad) + " · " + o.n + " hisse</summary>" + '<p class="vn">Bilançosu kayıtlı ' + o.bil_n + " hisse" + fc + (o.stok_qoq != null ? " · stok/gelir oranı önceki çeyreğe göre medyan " + (o.stok_qoq > 0 ? "+" : "") + num(o.stok_qoq, 1) + " puan" : "") + '.</p>' + ok + uy + ds + '<div class="tw"><table><thead><tr><th>Hisse</th><th>5G</th><th>20G</th><th>EPS rev. 20G</th><th>İleri F/K</th><th>Gelir (önceki çeyrek)</th><th>Brüt marj değişimi</th><th>Stok/gelir değişimi</th><th>EPS sürprizi</th><th>Bilanço</th></tr></thead><tbody>' + body + "</tbody></table></div></details>";
    });
    return out + (al.atanmamis && al.atanmamis.length ? '<p class="vn">Gruba atanmamış hisseler "Diğer"de: ' + al.atanmamis.map(function (x) { return esc(tk(x)); }).join(", ") + ".</p>" : "");
  }
  function tabs(d) {
    return '<section class="tab" id="t-genel">' + regime(d.regime) + summary(d) + valuation(d) + chgBox(chgFor("genel"), d.changes && d.changes.since, "ana göstergeler ve ETF'ler") + levels(d) + '</section>' +
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
    var k = th.getAttribute("data-k"), sec = th.getAttribute("data-t") === "sec";
    var cur = sec ? SEC_SORT : AI_SORT, nx = { k: k, dir: cur.k === k ? -cur.dir : (k === "symbol" || k === "status" || k === "trend" ? 1 : -1) };
    if (sec) SEC_SORT = nx; else AI_SORT = nx;
    draw();
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
