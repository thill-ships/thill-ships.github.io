/* ==========================================================================
   Take Up My Cross -- what both screens share: the five habits, the stock,
   and the streaks. Loaded by the phone app (cross/) and by the kitchen wall
   (daily/), so the two can never disagree about a price.

   Written for Chromium 74 (the kitchen calendar): no ?. or ??, nothing newer
   than ES2018.
   ========================================================================== */
(function(){
  'use strict';

  // The five, in order. `key` is what is stored; rename freely, never re-key.
  // Colours are a fixed categorical order, checked for colour blindness on a
  // dark background. Every habit is always shown with its name and icon too.
  var HABITS = [
    { key:'her',   name:'Choose her',   meaning:'Do something for Kenzie', color:'#3987e5', icon:'heart' },
    { key:'him',   name:'Remember Him', meaning:'Do something spiritual',  color:'#d95926', icon:'cross' },
    { key:'own',   name:'Own it',       meaning:'Work hard at work',       color:'#199e70', icon:'brief' },
    { key:'sweat', name:'Sweat',        meaning:'Do something active',     color:'#c98500', icon:'bolt'  },
    { key:'serve', name:'Serve',        meaning:'Do some service',         color:'#d55181', icon:'hands' }
  ];

  /* The stock. Every day closes at midnight:
       each habit done     +0.25%
       each habit missed   -0.30%
       all five (perfect)  +0.25% on top
     so 5/5 = +1.50%, 4 = +0.70%, 3 = +0.15%, 2 = -0.40%, 1 = -0.95%, 0 = -1.50%.
     Three a day keeps it climbing; two lets it slide. A day with nothing
     logged is a 0/5 day. Today only counts what is done so far -- the
     misses are charged at the close, the way a market settles. */
  var STOCK = { ticker:'CROSS', ipo:100, gain:0.0025, loss:0.003, perfect:0.0025 };

  var ICONS = {
    heart:'<path d="M12 20.5s-7.5-4.6-7.5-10.1A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.8c0 5.5-7.5 10.1-7.5 10.1z"/>',
    cross:'<path d="M12 3v18M6.5 8.5h11"/>',
    brief:'<rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M9 7.5V5.8c0-.7.6-1.3 1.3-1.3h3.4c.7 0 1.3.6 1.3 1.3v1.7M3.5 12.5h17"/>',
    bolt: '<path d="M13 3L5 13.5h6l-1 7.5 8-10.5h-6z"/>',
    hands:'<circle cx="9" cy="7.5" r="3"/><path d="M3.5 20v-1.2A4.8 4.8 0 0 1 8.3 14h1.4a4.8 4.8 0 0 1 4.8 4.8V20"/><path d="M17.5 8.5v6M14.5 11.5h6"/>'
  };
  function icon(name, cls){
    return '<svg class="' + (cls || 'ico') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
           (ICONS[name] || '') + '</svg>';
  }

  /* ---- days are local calendar days, as 'YYYY-MM-DD' ---- */
  function pad(n){ return (n < 10 ? '0' : '') + n; }
  function keyOf(d){ return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function today(){ return keyOf(new Date()); }
  // Noon, so a daylight-saving change can never push a day onto its neighbour.
  function dateOf(k){ var p = k.split('-'); return new Date(+p[0], +p[1] - 1, +p[2], 12); }
  function addDays(k, n){ var d = dateOf(k); d.setDate(d.getDate() + n); return keyOf(d); }
  function daysBetween(a, b){ return Math.round((dateOf(b) - dateOf(a)) / 86400000); }

  function dayChange(n, live){
    var c = n * STOCK.gain + (n === HABITS.length ? STOCK.perfect : 0);
    if(!live) c -= (HABITS.length - n) * STOCK.loss;
    return c;
  }

  /* Every day from the start through today, oldest first.
       byDay:    { 'YYYY-MM-DD': ['her','sweat'] }
       startDay: the IPO, or null for the first day logged (or today).
     Each entry: { day, done:[keys], n, change, close, live }.
     `open` is the IPO price, the point the line starts from.        */
  function build(byDay, startDay, now){
    now = now || today();
    var start = startDay;
    if(!start){
      var logged = Object.keys(byDay).filter(function(k){ return byDay[k] && byDay[k].length; }).sort();
      start = logged.length ? logged[0] : now;
    }
    if(start > now) start = now;
    var keys = HABITS.map(function(h){ return h.key; });
    var days = [], price = STOCK.ipo;
    for(var k = start; k <= now; k = addDays(k, 1)){
      var done = (byDay[k] || []).filter(function(x){ return keys.indexOf(x) >= 0; });
      var live = k === now;
      var change = dayChange(done.length, live);
      price = price * (1 + change);
      days.push({ day:k, done:done, n:done.length, change:change, close:price, live:live });
    }
    return { start:start, open:STOCK.ipo, days:days };
  }

  /* Streaks run back from today. Today only breaks a streak once it is over,
     so a streak alive yesterday still shows this morning. */
  function streak(days, test){
    var i = days.length - 1, n = 0;
    if(i >= 0 && days[i].live && !test(days[i])) i--;
    for(; i >= 0 && test(days[i]); i--) n++;
    return n;
  }
  function best(days, test){
    var run = 0, top = 0;
    days.forEach(function(d){ run = test(d) ? run + 1 : 0; if(run > top) top = run; });
    return top;
  }
  function stats(series){
    var days = series.days;
    var perfect = function(d){ return d.n === HABITS.length; };
    var last = days[days.length - 1];
    var prevClose = days.length > 1 ? days[days.length - 2].close : series.open;
    var high = series.open;
    days.forEach(function(d){ if(d.close > high) high = d.close; });
    var recent = days.slice(-30);
    var past = recent.filter(function(d){ return !d.live; });   // rates leave today out until it's over
    var habits = HABITS.map(function(h){
      var has = function(d){ return d.done.indexOf(h.key) >= 0; };
      var hit = past.filter(has).length;
      return { key:h.key, streak:streak(days, has), best:best(days, has),
               rate: past.length ? hit / past.length : null, hit:hit, of:past.length };
    });
    return {
      price: last ? last.close : series.open,
      prevClose: prevClose,
      todayChange: last ? last.change : 0,
      allTime: last ? last.close / series.open - 1 : 0,
      high: high,
      perfectStreak: streak(days, perfect),
      bestPerfect: best(days, perfect),
      habits: habits
    };
  }

  /* ---- numbers ---- */
  function money(v){
    return v >= 10000 ? Math.round(v).toLocaleString('en-US')
                      : v.toLocaleString('en-US', { minimumFractionDigits:2, maximumFractionDigits:2 });
  }
  function pct(v, digits){
    var d = digits == null ? 2 : digits;
    var s = (Math.abs(v) * 100).toFixed(d);
    return (v > 0.000001 ? '+' : v < -0.000001 ? '−' : '') + s + '%';
  }
  function signed(v){
    return (v > 0.0000001 ? '+' : v < -0.0000001 ? '−' : '') + money(Math.abs(v));
  }

  /* The price line as SVG, drawn by hand: one 2px line, a soft fill under it,
     a dashed rule at the range's opening price, and a dot on the last point.
     Green when the range is up, red when it is down. Returns the markup and
     the geometry, so a page can put a crosshair on it.                     */
  function chart(points, base, w, h, opt){
    opt = opt || {};
    var padT = opt.padT || 8, padB = opt.padB || 8, padL = opt.padL || 0, padR = opt.padR || 10;
    var vals = points.map(function(p){ return p.v; }).concat([base]);
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    if(hi - lo < base * 0.004){ var mid = (hi + lo) / 2; lo = mid - base * 0.002; hi = mid + base * 0.002; }
    var span = hi - lo; lo -= span * 0.08; hi += span * 0.08;
    var n = points.length;
    var X = function(i){ return padL + (n < 2 ? (w - padL - padR) : i * (w - padL - padR) / (n - 1)); };
    var Y = function(v){ return padT + (hi - v) * (h - padT - padB) / (hi - lo); };
    var up = points.length ? points[n - 1].v >= base : true;
    var col = up ? (opt.up || '#0ca30c') : (opt.down || '#e5484d');
    var d = '', i;
    for(i = 0; i < n; i++) d += (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(points[i].v).toFixed(1);
    if(n === 1) d += 'L' + (w - padR) + ' ' + Y(points[0].v).toFixed(1);
    var fillEnd = n === 1 ? (w - padR) : X(n - 1);
    var area = d + 'L' + fillEnd.toFixed(1) + ' ' + (h - padB) + 'L' + X(0).toFixed(1) + ' ' + (h - padB) + 'Z';
    var gid = 'g' + Math.random().toString(36).slice(2, 8);
    var last = n ? { x: n === 1 ? fillEnd : X(n - 1), y: Y(points[n - 1].v) } : null;
    var svg =
      '<svg viewBox="0 0 ' + w + ' ' + h + '" width="100%" height="100%" preserveAspectRatio="none" class="chart">' +
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="' + col + '" stop-opacity=".28"/><stop offset="1" stop-color="' + col + '" stop-opacity="0"/>' +
      '</linearGradient></defs>' +
      '<line x1="' + padL + '" x2="' + (w - padR) + '" y1="' + Y(base).toFixed(1) + '" y2="' + Y(base).toFixed(1) + '" ' +
      'stroke="currentColor" stroke-opacity=".28" stroke-width="1" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/>' +
      (n ? '<path d="' + area + '" fill="url(#' + gid + ')"/>' +
           '<path d="' + d + '" fill="none" stroke="' + col + '" stroke-width="' + (opt.stroke || 2) + '" ' +
           'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>' : '') +
      '</svg>';
    return { svg:svg, color:col, up:up, X:X, Y:Y, last:last, lo:lo, hi:hi };
  }

  window.Cross = {
    HABITS:HABITS, STOCK:STOCK, icon:icon,
    keyOf:keyOf, today:today, dateOf:dateOf, addDays:addDays, daysBetween:daysBetween,
    dayChange:dayChange, build:build, stats:stats,
    money:money, pct:pct, signed:signed, chart:chart
  };
})();
