/* ==========================================================================
   Site gate — a private curtain over the personal pages on this site.

   Any page that includes this script in its <head> is hidden behind one
   password. The hub (/) shows the password box; every other gated page
   bounces to the hub and comes straight back once the password is in.
   Unlocking is remembered per browser, so you type it once per device.

   What this is:   a way to keep the personal pages out of sight from people
                   who were sent a link to one of the public apps and trim the
                   URL back to the root.
   What this is NOT: real security. The site is a public GitHub Pages repo, so
                   the pages themselves are readable by anyone who goes looking.
                   Anything that actually needs protecting (picks, predictions,
                   golf data) lives in Supabase behind real logins and Row Level
                   Security, not behind this.

   Setting the password
     1. Open https://thill-ships.github.io/#newpass
     2. Type the new password; copy the two lines it gives you.
     3. Paste them over SALT and HASH below and push.
   The password itself is never stored anywhere — only its salted SHA-256.

   Per-page options (attributes on the <script> tag):
     data-allow-query="share"   let the page through when that query parameter
                                is present (the golf coach link, for example).

   Visit /?lock on the hub to lock this browser again.
   ========================================================================== */
(function () {
  'use strict';

  var SALT = '5da003f9c17b6d53';
  var HASH = 'a71cf8fa809a679b8ba28e02b270295559fb2bbd9427a84b01c5a03b2825861f';
  var KEY  = 'site_gate_v1';
  var HUB  = '/';

  var me     = document.currentScript || {};
  var path   = location.pathname;
  var isHub  = path === '/' || path === '/index.html';
  var params = new URLSearchParams(location.search);

  function unlocked() {
    try { return localStorage.getItem(KEY) === HASH; } catch (e) { return false; }
  }
  function remember() {
    try { localStorage.setItem(KEY, HASH); } catch (e) { /* private mode: unlock lasts the page */ }
  }
  /* Only same-site paths may be bounced to, never another origin. */
  function safeNext(n) {
    return (typeof n === 'string' && /^\/(?![\/\\])/.test(n)) ? n : null;
  }

  /* A page can let a specific query parameter through, e.g. the golf coach link. */
  var allow = me.dataset && me.dataset.allowQuery;
  if (!isHub && allow && params.has(allow)) return;

  if (isHub && params.has('lock')) {
    try { localStorage.removeItem(KEY); } catch (e) {}
    history.replaceState(null, '', HUB);
    params.delete('lock');
  }

  if (unlocked()) {
    if (isHub && params.has('next')) {
      var n = safeNext(params.get('next'));
      if (n) location.replace(n);
    }
    return;
  }

  if (!isHub) {
    location.replace(HUB + '?next=' + encodeURIComponent(path + location.search + location.hash));
    return;
  }

  /* The hub, locked: hide everything on the page and put the gate up. */
  document.documentElement.classList.add('gated');
  var css = document.createElement('style');
  css.textContent =
    'html.gated body>:not(#siteGate){display:none!important}' +
    'html.gated body{background:#111315!important;margin:0}' +
    '#siteGate{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;' +
      'padding:24px;background:#111315;color:#E4E6EA;font-family:Inter,-apple-system,BlinkMacSystemFont,' +
      '"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;z-index:2147483647}' +
    '#siteGate form{width:100%;max-width:340px}' +
    '#siteGate .mark{width:44px;height:44px;border-radius:12px;background:#1B1F24;display:flex;' +
      'align-items:center;justify-content:center;margin-bottom:18px}' +
    '#siteGate .mark svg{width:22px;height:22px}' +
    '#siteGate h1{font-size:20px;font-weight:800;letter-spacing:-.01em;margin:0 0 6px}' +
    '#siteGate p{margin:0 0 18px;font-size:14px;color:#8B93A1;line-height:1.5}' +
    '#siteGate input{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:13px 14px;' +
      'border-radius:12px;border:1.5px solid #2A2F36;background:#1B1F24;color:#fff;outline:none}' +
    '#siteGate input:focus{border-color:#2E6BFF}' +
    '#siteGate button{width:100%;margin-top:10px;font:inherit;font-size:15px;font-weight:700;padding:13px;' +
      'border:0;border-radius:12px;background:#2E6BFF;color:#fff;cursor:pointer}' +
    '#siteGate button:disabled{opacity:.6}' +
    '#siteGate .msg{min-height:18px;margin-top:10px;font-size:13px;color:#F0716A}' +
    '#siteGate.shake form{animation:gateShake .35s}' +
    '@keyframes gateShake{20%{transform:translateX(-6px)}40%{transform:translateX(6px)}' +
      '60%{transform:translateX(-4px)}80%{transform:translateX(4px)}}' +
    '#siteGate pre{margin:12px 0 0;padding:12px;border-radius:10px;background:#1B1F24;color:#B6C2FF;' +
      'font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-all;user-select:all}';
  document.head.appendChild(css);

  function hex(buf) {
    return Array.prototype.map.call(new Uint8Array(buf), function (b) {
      return ('0' + b.toString(16)).slice(-2);
    }).join('');
  }
  function digest(pw) {
    if (!(window.crypto && crypto.subtle)) return Promise.reject(new Error('no-crypto'));
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(SALT + ':' + pw)).then(hex);
  }
  function randomSalt() {
    var a = new Uint8Array(8);
    crypto.getRandomValues(a);
    return hex(a.buffer);
  }

  function mount() {
    var setup = location.hash === '#newpass';
    var gate = document.createElement('div');
    gate.id = 'siteGate';
    gate.innerHTML =
      '<form autocomplete="off">' +
        '<div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="#8B93A1" stroke-width="2">' +
          '<rect x="4" y="10" width="16" height="11" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg></div>' +
        (setup
          ? '<h1>New password</h1><p>Type the password you want. Paste the two lines that appear ' +
            'over <b>SALT</b> and <b>HASH</b> in <b>gate.js</b>, then push.</p>'
          : '<h1>Private</h1><p>This part of the site is not public.</p>') +
        '<input type="password" name="pw" placeholder="Password" autocomplete="current-password" autofocus />' +
        '<button type="submit">' + (setup ? 'Make the lines' : 'Continue') + '</button>' +
        '<div class="msg"></div>' +
        (setup ? '<pre hidden></pre>' : '') +
      '</form>';
    document.body.appendChild(gate);

    var form = gate.querySelector('form'), input = gate.querySelector('input'),
        btn = gate.querySelector('button'), msg = gate.querySelector('.msg'),
        out = gate.querySelector('pre');
    input.focus();

    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var pw = input.value;
      if (!pw) return;
      btn.disabled = true; msg.textContent = '';

      if (setup) {
        var salt = randomSalt();
        crypto.subtle.digest('SHA-256', new TextEncoder().encode(salt + ':' + pw)).then(function (h) {
          out.hidden = false;
          out.textContent = "  var SALT = '" + salt + "';\n  var HASH = '" + hex(h) + "';";
          btn.disabled = false;
        });
        return;
      }

      digest(pw).then(function (h) {
        if (h !== HASH) {
          input.value = ''; input.focus(); btn.disabled = false;
          msg.textContent = 'That is not it.';
          gate.classList.remove('shake'); void gate.offsetWidth; gate.classList.add('shake');
          return;
        }
        remember();
        var n = safeNext(params.get('next'));
        if (n) { location.replace(n); return; }
        history.replaceState(null, '', HUB);
        gate.remove();
        document.documentElement.classList.remove('gated');
      }).catch(function () {
        btn.disabled = false;
        msg.textContent = 'This browser cannot check the password here. Open the site over https.';
      });
    });
  }

  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
}());
