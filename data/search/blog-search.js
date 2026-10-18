/* Site search for the pages in blog/.
   Adds a Search button to the top bar (also Ctrl/Cmd+K, or "/") and searches the full text of every
   article, using search-index.json (built by tools/build_search_index.py). Styles are injected here, so
   a page only needs: <script src="../data/search/blog-search.js" defer></script> */
(function () {
  'use strict';
  var script = document.currentScript;
  var base = new URL('../../', script ? script.src : location.href);   // site root
  var nav = document.querySelector('nav');
  if (!nav) return;

  /* Same look as the home page search (see index.html), so the two feel identical */
  var css = '\
.nav-right{display:flex;align-items:center;gap:8px}\
.search-btn{display:flex;align-items:center;gap:8px;cursor:pointer;background:var(--card);border:1px solid var(--border);border-radius:9px;color:var(--muted);font:inherit;font-size:calc(13px * var(--fs, 1));padding:6px 10px;transition:border-color .18s,color .18s}\
.search-btn:hover{border-color:var(--border-h);color:var(--text)}\
.search-btn kbd{font:inherit;font-size:calc(11px * var(--fs, 1));padding:1px 6px;border-radius:5px;border:1px solid var(--border-h);color:var(--muted)}\
.hamburger{display:none;background:none;border:none;cursor:pointer;color:var(--muted);font-size:calc(20px * var(--fs, 1))}\
.search-overlay{display:none;position:fixed;inset:0;z-index:300;background:rgba(0,0,0,0.35);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);align-items:flex-start;justify-content:center;padding:12vh 16px 0}\
.search-overlay.open{display:flex}\
.search-box{width:100%;max-width:600px;background:var(--card);border:1px solid var(--border-h);border-radius:16px;box-shadow:0 24px 80px rgba(0,0,0,0.25);overflow:hidden}\
.search-box input{width:100%;border:0;outline:0;background:transparent;font:inherit;font-size:calc(16px * var(--fs, 1));color:var(--text);padding:18px 20px;border-bottom:1px solid var(--border)}\
.search-results{max-height:52vh;overflow-y:auto;padding:8px}\
.search-item{display:block;width:100%;text-align:left;cursor:pointer;background:none;border:0;font:inherit;color:inherit;padding:10px 12px;border-radius:10px}\
.search-item.active{background:var(--card-h);outline:1px solid var(--border-h)}\
.search-item .si-top{display:flex;justify-content:space-between;gap:12px;align-items:baseline}\
.search-item .si-title{font-size:calc(14px * var(--fs, 1));font-weight:600;color:var(--text)}\
.search-item .si-sec{font-size:calc(11px * var(--fs, 1));color:var(--muted);text-transform:uppercase;letter-spacing:.6px;white-space:nowrap}\
.search-item .si-snip{font-size:calc(12px * var(--fs, 1));color:var(--sub);margin-top:2px;line-height:1.5}\
.search-item mark{background:rgba(250,204,21,0.45);color:inherit;border-radius:3px}\
.search-empty{padding:24px;text-align:center;color:var(--muted);font-size:calc(13px * var(--fs, 1))}\
.sp-top{display:flex;gap:8px;padding:14px 14px 12px;border-bottom:1px solid var(--border)}\
.sp-input{flex:1;min-width:0;display:flex;align-items:center;gap:10px;color:var(--muted);background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:0 12px}\
.sp-input:focus-within{border-color:var(--border-h)}\
.sp-input input{border:0;padding:11px 0;border-bottom:0;font-size:calc(14px * var(--fs, 1))}\
.search-btn:focus-visible,.search-item:focus-visible,.hamburger:focus-visible{outline:2px solid var(--accent);outline-offset:2px}\
[data-theme="dark"] .search-overlay{background:rgba(0,0,0,0.6)}\
[data-theme="dark"] .search-box{box-shadow:0 24px 80px rgba(0,0,0,0.6)}\
@media(max-width:720px){\
.hamburger{display:block}.search-btn{display:none}\
.search-overlay{padding:max(env(safe-area-inset-top),12px) 10px 0}\
.search-box{max-height:calc(100vh - 24px);max-height:calc(100dvh - 24px);display:flex;flex-direction:column;border-radius:14px}\
.sp-top{flex:0 0 auto;padding:10px}\
.sp-input input{font-size:max(16px,calc(14px * var(--fs, 1)))}\
.search-box .search-results{flex:1 1 auto;min-height:0;max-height:none;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:6px 6px calc(10px + env(safe-area-inset-bottom))}\
.search-item{padding:12px}.search-item .si-top{flex-wrap:wrap;gap:2px 12px}.search-item .si-title{overflow-wrap:anywhere}}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  /* Top-bar button, with the existing "All writing" link kept to its right */
  var back = nav.querySelector('a:not(.logo)');
  var wrap = document.createElement('div'); wrap.className = 'nav-right';
  wrap.innerHTML = '<button type="button" class="search-btn" aria-label="Search"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><span class="sb-label">Search</span><kbd>' + (/Mac|iPhone|iPad/.test(navigator.platform) ? '\u2318K' : 'Ctrl K') + '</kbd></button><button type="button" class="hamburger" aria-label="Search">&#9776;</button>';
  var btns = wrap.querySelectorAll('button');
  if (back) { nav.replaceChild(wrap, back); wrap.appendChild(back); back.style.marginLeft = '6px'; } else nav.appendChild(wrap);

  var ov = document.createElement('div'); ov.className = 'search-overlay'; ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true'); ov.setAttribute('aria-label', 'Search');
  ov.innerHTML = '<div class="search-box"><div class="sp-top"><label class="sp-input"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input type="search" placeholder="Jump to a section or search\u2026" autocomplete="off" spellcheck="false" aria-label="Search the whole site"></label></div><div class="search-results" hidden></div></div>';
  document.body.appendChild(ov);
  var input = ov.querySelector('input'), res = ov.querySelector('.search-results');

  var articles = null, loading = null, hits = [], active = 0, lastFocus = null;
  var esc = function (t) { return t.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  function mark(text, terms) {
    var out = esc(text);
    terms.forEach(function (t) { out = out.replace(new RegExp('(' + esc(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'), '<mark>$1</mark>'); });
    return out;
  }
  function snippet(text, terms) {
    var low = text.toLowerCase(), found = terms.map(function (t) { return low.indexOf(t); }).filter(function (i) { return i >= 0; });
    var i = found.length ? Math.min.apply(null, found) : 0, start = Math.max(0, i - 40);
    return (start ? '…' : '') + text.slice(start, start + 120) + (text.length > start + 120 ? '…' : '');
  }
  /* Everything searchable (articles + the home page's own content) comes from data/search/search-data.js,
     built by tools/build_search_index.py. It is a script, not JSON, so it also loads when a page is opened from disk. */
  var pageItems = null;
  function load() {
    if (articles || loading) return;
    loading = new Promise(function (resolve) {
      var sc = document.createElement('script');
      sc.src = new URL('data/search/search-data.js', base).href;
      sc.onload = function () { resolve(window.SITE_SEARCH || { articles: [], page: [] }); };
      sc.onerror = function () { resolve({ articles: [], page: [] }); };
      document.head.appendChild(sc);
    }).then(function (data) {
      articles = data.articles.map(function (a) {
        var series = /series/i.test(a.k || '') ? 'Series · ' + a.k.split('·').pop().trim() : 'Article';
        return { u: a.u, t: a.t, label: series, s: a.s, tl: a.t.toLowerCase(), hay: (a.t + ' ' + a.k + ' ' + a.s.map(function (g) { return g.h + ' ' + g.x; }).join(' ')).toLowerCase() };
      });
      pageItems = data.page.map(function (it) {
        it.href = new URL(it.href, base).href; it.tl = it.title.toLowerCase();
        it.hay = (it.title + ' ' + it.text + ' ' + it.section).toLowerCase(); return it;
      });
      if (ov.classList.contains('open') && input.value.trim()) run(input.value);
    });
  }
  function count(hay, t) { return hay.split(t).length - 1; }
  function find(terms) {
    if (!articles) return [];
    return articles.filter(function (a) { return terms.every(function (t) { return a.hay.indexOf(t) >= 0; }); }).map(function (a) {
      var best = null, bs = -1;
      a.s.forEach(function (g) {
        var h = g.h.toLowerCase(), x = (g.h + ' ' + g.x).toLowerCase();
        var sc = terms.filter(function (t) { return x.indexOf(t) >= 0; }).length * 3 + terms.filter(function (t) { return h.indexOf(t) >= 0; }).length * 2;
        if (sc > bs) { bs = sc; best = g; }
      });
      var rank = terms.filter(function (t) { return a.tl.indexOf(t) >= 0; }).length * 100 + bs * 10 + Math.min(count(a.hay, terms[0]), 30);
      return { title: a.t, section: a.label, href: new URL(a.u + (best && best.id ? '#' + best.id : ''), base).href, heading: best ? best.h : '', text: best ? best.x : '', rank: rank };
    }).sort(function (x, y) { return y.rank - x.rank; }).slice(0, 30);
  }
  function run(q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    var art = terms.length ? find(terms) : [];
    var urls = {};
    art.forEach(function (a) { urls[a.href.split('#')[0]] = 1; });
    var pg = !terms.length || !pageItems ? [] : pageItems
      .filter(function (it) { return terms.every(function (t) { return it.hay.indexOf(t) >= 0; }); })
      .filter(function (it) { return !(it.link && urls[it.href]); })                          // the article result already covers this card
      .map(function (it) { return { it: it, score: (it.tl.indexOf(terms[0]) >= 0 ? 0 : 1) + (it.tag ? 0 : 0.5) }; })
      .sort(function (a, b) { return a.score - b.score; }).slice(0, 12).map(function (x) { return x.it; });
    hits = pg.map(function (it) { return { title: it.title, section: it.section, href: it.href, ext: it.ext, heading: '', text: it.text !== it.title ? it.text : '' }; })
      .concat(art.slice(0, 30 - pg.length));
    active = 0;
    res.hidden = !terms.length;
    if (!terms.length) return;
    var waiting = (!articles || !pageItems) ? '<div class="search-empty">Searching…</div>' : '';
    if (!hits.length) { res.innerHTML = waiting || '<div class="search-empty">No results for “' + esc(q) + '”.</div>'; return; }
    res.innerHTML = hits.map(function (it, i) {
      return '<button class="search-item' + (i ? '' : ' active') + '" data-i="' + i + '"><div class="si-top"><span class="si-title">' + mark(it.title.slice(0, 90), terms) + '</span><span class="si-sec">' + esc(it.section) + '</span></div>' +
        (it.text ? '<div class="si-snip">' + (it.heading ? '<strong>' + esc(it.heading.slice(0, 60)) + '</strong> \u00b7 ' : '') + mark(snippet(it.text, terms), terms) + '</div>' : '') + '</button>';
    }).join('') + waiting;
  }
  function setActive(n) {
    var items = res.querySelectorAll('.search-item'); if (!items.length) return;
    active = (n + items.length) % items.length;
    items.forEach(function (e, i) { e.classList.toggle('active', i === active); });
    items[active].scrollIntoView({ block: 'nearest' });
  }
  function open() { load(); lastFocus = document.activeElement; ov.classList.add('open'); input.value = ''; run(''); input.focus(); }
  function close() { ov.classList.remove('open'); if (lastFocus && lastFocus.focus) lastFocus.focus(); }
  function go(it) { close(); if (it.ext) window.open(it.href, '_blank', 'noopener'); else location.href = it.href; }

  btns.forEach(function (b) { b.addEventListener('click', open); });
  input.addEventListener('input', function () { run(input.value); });
  res.addEventListener('click', function (e) { var b = e.target.closest('.search-item'); if (b) go(hits[+b.dataset.i]); });
  ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
  document.addEventListener('keydown', function (e) {
    var tag = document.activeElement && document.activeElement.tagName, typing = /INPUT|TEXTAREA|SELECT/.test(tag) || (document.activeElement && document.activeElement.isContentEditable);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); return; }
    if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); open(); return; }
    if (!ov.classList.contains('open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Enter' && hits[active]) { e.preventDefault(); go(hits[active]); }
  });
})();
