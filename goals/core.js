/* ==========================================================================
   Goals -- what both screens share: the goals, the stock, and the streaks.
   Loaded by the phone app (goals/) and by the kitchen wall (daily/), so the
   two can never disagree about a price.

   Written for Chromium 74 (the kitchen calendar): no ?. or ??, nothing newer
   than ES2018.
   ========================================================================== */
(function(){
  'use strict';

  /* The goals, in order. `key` is what is stored: rename freely, never re-key.
     per 'day'  -> due every day.
     per 'week' -> `target` times a week, Monday to Sunday.
     Colours are a fixed categorical order, checked for colour blindness on a
     dark background. Every goal is always shown with its name and icon too. */
  var GOALS = [
    { key:'gym',    name:'Gym',                 meaning:'4 times a week',       per:'week', target:4, color:'#3987e5', icon:'gym'   },
    { key:'pray',   name:'Prayer + scriptures', meaning:'Every day',            per:'day',            color:'#d95926', icon:'book'  },
    { key:'teeth',  name:'Brush + floss',       meaning:'Every day',            per:'day',            color:'#199e70', icon:'spark' },
    { key:'clean',  name:'Clean the apartment', meaning:'Once a week',          per:'week', target:1, color:'#c98500', icon:'home'  },
    { key:'income', name:'Third stream',        meaning:'Work on it every day', per:'day',            color:'#d55181', icon:'trend' }
  ];
  var DAILY = GOALS.filter(function(g){ return g.per === 'day'; });
  var WEEKLY = GOALS.filter(function(g){ return g.per === 'week'; });

  /* The stock. It went public at 100.
       Daily goals    +0.25% each done, -0.30% each missed (charged at midnight)
       All daily done +0.25% on top
       Weekly goals   +0.25% for each session, up to the week's target; at the
                      week's close (Sunday midnight) -0.30% for each one short.
                      Off days are never charged on their own.
     A day with nothing logged counts as nothing done. Today only counts what
     is done so far; the misses are charged at the close, the way a market
     settles. Logging a day late is fine: the price is worked out from the
     whole history every time, so a late check-off still counts in full.  */
  var STOCK = { ticker:'HILL', ipo:100, gain:0.0025, loss:0.003, perfect:0.0025 };

  var ICONS = {
    gym:  '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9.5v5M20.5 9.5v5M6.5 12h11"/>',
    book: '<path d="M12 6.5C10.5 5 8 4.5 4 4.5v13c4 0 6.5.5 8 2 1.5-1.5 4-2 8-2v-13c-4 0-6.5.5-8 2z"/><path d="M12 6.5v13"/>',
    spark:'<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    home: '<path d="M4 11l8-7 8 7"/><path d="M6 9.5V20h12V9.5"/><path d="M10 20v-5h4v5"/>',
    trend:'<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>'
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
  function weekStart(k){ return addDays(k, -((dateOf(k).getDay() + 6) % 7)); }   // the Monday
  function isSunday(k){ return dateOf(k).getDay() === 0; }

  function find(key){ for(var i = 0; i < GOALS.length; i++) if(GOALS[i].key === key) return GOALS[i]; return null; }
  function has(byDay, k, key){ return (byDay[k] || []).indexOf(key) >= 0; }

  /* A weekly goal's target for the week holding day k. The first week after
     the IPO is prorated, so starting on a Thursday doesn't charge Monday. */
  function targetFor(g, k, start){
    var ws = weekStart(k);
    if(start <= ws) return g.target;
    return Math.ceil(g.target * (7 - daysBetween(ws, start)) / 7);
  }
  // Sessions of a weekly goal from the week's start (or the IPO) through day k.
  function sessions(byDay, g, k, start){
    var n = 0;
    for(var d = weekStart(k) < start ? start : weekStart(k); d <= k; d = addDays(d, 1)) if(has(byDay, d, g.key)) n++;
    return n;
  }

  /* One day's move. `closed` charges the day's misses (and, on a Sunday, the
     week's shortfalls); a live day leaves them for the close. */
  function dayMove(byDay, k, start, closed){
    var c = 0, daily = 0;
    DAILY.forEach(function(g){ if(has(byDay, k, g.key)){ c += STOCK.gain; daily++; } else if(closed) c -= STOCK.loss; });
    if(DAILY.length && daily === DAILY.length) c += STOCK.perfect;
    WEEKLY.forEach(function(g){
      var t = targetFor(g, k, start), n = sessions(byDay, g, k, start);
      if(has(byDay, k, g.key) && n <= t) c += STOCK.gain;
      if(closed && isSunday(k)) c -= Math.max(0, t - Math.min(n, t)) * STOCK.loss;
    });
    return c;
  }

  /* Every day from the IPO through today, oldest first.
       byDay:    { 'YYYY-MM-DD': ['gym','pray'] }
       startDay: the IPO, or null for the first day logged (or today).
     Each entry: { day, done:[keys], n, daily, change, ifClosed, close, live }.
     `open` is the IPO price, the point the line starts from.               */
  function build(byDay, startDay, now){
    now = now || today();
    var start = startDay;
    if(!start){
      var logged = Object.keys(byDay).filter(function(k){ return byDay[k] && byDay[k].length; }).sort();
      start = logged.length ? logged[0] : now;
    }
    if(start > now) start = now;
    var days = [], price = STOCK.ipo;
    for(var k = start; k <= now; k = addDays(k, 1)){
      var done = (byDay[k] || []).filter(function(x){ return !!find(x); });
      var live = k === now;
      var change = dayMove(byDay, k, start, !live);
      price = price * (1 + change);
      days.push({ day:k, done:done, n:done.length,
                  daily:DAILY.filter(function(g){ return done.indexOf(g.key) >= 0; }).length,
                  change:change, ifClosed: live ? dayMove(byDay, k, start, true) : change,
                  close:price, live:live });
    }
    return { start:start, open:STOCK.ipo, days:days, byDay:byDay };
  }

  /* Streaks run back from today. Today only breaks a streak once it is over,
     so a streak alive yesterday still shows this morning. */
  function streak(list, test){
    var i = list.length - 1, n = 0;
    if(i >= 0 && list[i].live && !test(list[i])) i--;
    for(; i >= 0 && test(list[i]); i--) n++;
    return n;
  }
  function best(list, test){
    var run = 0, top = 0;
    list.forEach(function(d){ run = test(d) ? run + 1 : 0; if(run > top) top = run; });
    return top;
  }
  // The weeks since the IPO, each with every weekly goal's sessions and target.
  function weeks(series){
    var out = [], byDay = series.byDay, now = series.days.length ? series.days[series.days.length - 1].day : today();
    for(var ws = weekStart(series.start); ws <= now; ws = addDays(ws, 7)){
      var end = addDays(ws, 6), last = end < now ? end : now, w = { start:ws, live: end >= now, goals:{} };
      WEEKLY.forEach(function(g){
        w.goals[g.key] = { n:sessions(byDay, g, last, series.start), target:targetFor(g, last, series.start) };
      });
      out.push(w);
    }
    return out;
  }

  function stats(series){
    var days = series.days, wk = weeks(series);
    var perfect = function(d){ return DAILY.length > 0 && d.daily === DAILY.length; };
    var last = days[days.length - 1];
    var prevClose = days.length > 1 ? days[days.length - 2].close : series.open;
    var high = series.open;
    days.forEach(function(d){ if(d.close > high) high = d.close; });
    var past = days.slice(-30).filter(function(d){ return !d.live; });   // rates leave today out until it's over
    var goals = GOALS.map(function(g){
      if(g.per === 'week'){
        var met = function(w){ return w.goals[g.key].n >= w.goals[g.key].target; };
        var cur = wk[wk.length - 1] ? wk[wk.length - 1].goals[g.key] : { n:0, target:g.target };
        var done = wk.slice(-9).filter(function(w){ return !w.live; }).slice(-8);
        var hit = done.filter(met).length;
        return { key:g.key, per:'week', week:cur.n, target:cur.target,
                 streak:streak(wk, met), best:best(wk, met),
                 rate: done.length ? hit / done.length : null, hit:hit, of:done.length, unit:'weeks' };
      }
      var on = function(d){ return d.done.indexOf(g.key) >= 0; };
      var hitD = past.filter(on).length;
      return { key:g.key, per:'day', streak:streak(days, on), best:best(days, on),
               rate: past.length ? hitD / past.length : null, hit:hitD, of:past.length, unit:'days' };
    });
    return {
      price: last ? last.close : series.open,
      prevClose: prevClose,
      todayChange: last ? last.change : 0,
      ifClosed: last ? last.ifClosed : 0,
      allTime: last ? last.close / series.open - 1 : 0,
      high: high,
      perfectStreak: streak(days, perfect),
      bestPerfect: best(days, perfect),
      goals: goals
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

  window.Goals = {
    GOALS:GOALS, DAILY:DAILY, WEEKLY:WEEKLY, STOCK:STOCK, icon:icon, find:find,
    keyOf:keyOf, today:today, dateOf:dateOf, addDays:addDays, daysBetween:daysBetween, weekStart:weekStart,
    build:build, stats:stats, sessions:sessions, targetFor:targetFor,
    money:money, pct:pct, signed:signed, chart:chart
  };
})();
