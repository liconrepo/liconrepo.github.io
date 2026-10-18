/* Site search: ONE implementation, used by the home page and every blog page.

   Pages need two things in <head>/<body>:
     <link rel="stylesheet" href="…/data/search/search.css">
     <script src="…/data/search/search.js" defer></script>          (the home page adds the attribute data-home)

   The script builds the search window and its keyboard shortcuts (Ctrl/Cmd+K, "/"), and on pages other than the
   home page it also adds a Search button to the top bar. What it searches comes from data/search/search-data.js,
   which tools/build_search_index.py generates: the full text of every article, plus the home page's own content.
   That file is loaded as a script, not fetched, so search also works when a page is opened straight from disk.

   Choosing a result:
     article            opens the article at the best matching heading
     home page item     scrolls to it and highlights it (from a blog page: opens the home page and does the same)
     link on home page  opens the link
   The home page may define window.siteSearchReveal(el), which opens whatever hides el (a closed series, say). */
(function () {
  'use strict';
  var script = document.currentScript;
  var isHome = !!(script && script.hasAttribute('data-home'));
  var base = new URL('../../', script ? script.src : location.href);          // the site root
  var homeUrl = new URL('index.html', base).href;

  var articles = null, pageItems = null, loading = null, hits = [], active = 0, lastFocus = null;

  /* ---------- the window ---------- */
  var ov = document.createElement('div');
  ov.className = 'search-overlay'; ov.id = 'searchOverlay'; ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true'); ov.setAttribute('aria-label', 'Search');
  ov.innerHTML = '<div class="search-box"><div class="sp-top"><label class="sp-input"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input id="searchInput" type="search" placeholder="Jump to a section or search…" autocomplete="off" spellcheck="false" aria-label="Search the whole site"></label></div><div class="search-results" id="searchResults" hidden></div></div>';
  document.body.appendChild(ov);
  var input = ov.querySelector('input'), res = ov.querySelector('.search-results');

  /* ---------- the top-bar button (the home page already has its own) ---------- */
  if (!isHome) {
    var nav = document.querySelector('nav');
    if (nav) {
      var back = nav.querySelector('a:not(.logo)');
      var wrap = document.createElement('div'); wrap.className = 'nav-right';
      wrap.innerHTML = '<button type="button" class="search-btn" aria-label="Search"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><span class="sb-label">Search</span><kbd>' + (/Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K') + '</kbd></button>';
      wrap.querySelectorAll('button').forEach(function (b) { b.addEventListener('click', openSearch); });
      if (back) { nav.replaceChild(wrap, back); wrap.appendChild(back); back.style.marginLeft = '6px'; } else nav.appendChild(wrap);
    }
  }

  /* ---------- data ---------- */
  function load() {
    if (loading) return loading;
    loading = new Promise(function (resolve) {
      if (window.SITE_SEARCH) return resolve(window.SITE_SEARCH);
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
      return data;
    });
    return loading;
  }

  /* ---------- searching ---------- */
  var esc = function (t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
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
  function count(hay, t) { return hay.split(t).length - 1; }
  function articleHits(terms) {
    if (!articles) return [];
    return articles.filter(function (a) { return terms.every(function (t) { return a.hay.indexOf(t) >= 0; }); }).map(function (a) {
      var best = null, bs = -1;
      a.s.forEach(function (g) {                                   // the section that matches the most words
        var h = g.h.toLowerCase(), x = (g.h + ' ' + g.x).toLowerCase();
        var sc = terms.filter(function (t) { return x.indexOf(t) >= 0; }).length * 3 + terms.filter(function (t) { return h.indexOf(t) >= 0; }).length * 2;
        if (sc > bs) { bs = sc; best = g; }
      });
      var inTitle = terms.every(function (t) { return a.tl.indexOf(t) >= 0; });
      if (inTitle) best = a.s[0];                                  // the title matches: the reader wants the article, so open it at the top
      var rank = terms.filter(function (t) { return a.tl.indexOf(t) >= 0; }).length * 100 + bs * 10 + Math.min(count(a.hay, terms[0]), 30);
      return { kind: 'article', title: a.t, section: a.label, href: new URL(a.u + (!inTitle && best && best.id ? '#' + best.id : ''), base).href, u: new URL(a.u, base).href, heading: best ? best.h : '', text: best ? best.x : '', rank: rank };
    }).sort(function (x, y) { return y.rank - x.rank; });
  }
  function run(q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    var art = terms.length ? articleHits(terms) : [], urls = {};
    art.forEach(function (a) { urls[a.u] = 1; });
    var pgAll = !terms.length || !pageItems ? [] : pageItems
      .filter(function (it) { return terms.every(function (t) { return it.hay.indexOf(t) >= 0; }); })
      .filter(function (it) { return !(it.link && urls[it.href]); })                      // the article result already covers this card
      .map(function (it) { return { it: it, score: (it.tl.indexOf(terms[0]) >= 0 ? 0 : 1) + (it.tag ? 0 : 0.5) }; })
      .sort(function (a, b) { return a.score - b.score; });
    var pg = pgAll.map(function (x) { return x.it; });
    hits = pg.map(function (it) { return { kind: it.link ? 'link' : 'item', item: it, title: it.title, section: it.section, text: it.text !== it.title ? it.text : '' }; })
      .concat(art);
    var total = hits.length;
    active = -1;                                                   // nothing is highlighted until you point at a row or press the arrow keys
    res.hidden = !terms.length;
    if (!terms.length) return;
    var waiting = (!articles || !pageItems) ? '<div class="search-empty">Searching…</div>' : '';
    if (!hits.length) { res.innerHTML = waiting || '<div class="search-empty">No results for “' + esc(q) + '”.</div>'; return; }
    var countLine = '<div class="search-count" aria-live="polite">' + total + (total === 1 ? ' result' : ' results') + (total > 6 ? ' \u00b7 scroll for more' : '') + '</div>';
    res.innerHTML = countLine + hits.map(function (it, i) {
      return '<button type="button" class="search-item" data-i="' + i + '"><div class="si-top"><span class="si-title">' + mark(it.title.slice(0, 90), terms) + '</span><span class="si-sec">' + esc(it.section) + '</span></div>' +
        (it.text ? '<div class="si-snip">' + (it.heading ? '<strong>' + esc(it.heading.slice(0, 60)) + '</strong> · ' : '') + mark(snippet(it.text, terms), terms) + '</div>' : '') + '</button>';
    }).join('') + waiting;
  }
  function setActive(n) {
    var items = res.querySelectorAll('.search-item'); if (!items.length) return;
    active = n < 0 ? items.length - 1 : n % items.length;
    items.forEach(function (e, i) { e.classList.toggle('active', i === active); });
    items[active].scrollIntoView({ block: 'nearest' });
  }

  /* ---------- going to a result ---------- */
  function reveal(it) {                                              // home page only: scroll to the item and flash it
    var el = document.querySelectorAll(it.sel)[it.n];
    if (!el) return false;
    if (window.siteSearchReveal) el = window.siteSearchReveal(el) || el;
    el.classList.add('visible');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('search-hit');
    setTimeout(function () { el.classList.remove('search-hit'); }, 2000);
    return true;
  }
  function go(h, inPlace) {
    closeSearch();
    if (h.kind === 'article') { location.href = h.href; return; }
    var it = h.item;
    if (h.kind === 'link' && !(isHome && inPlace)) {
      if (it.ext) window.open(it.href, '_blank', 'noopener'); else location.href = it.href;
      return;
    }
    if (isHome) { if (!reveal(it)) location.href = it.href; return; }    // Cmd/Ctrl+click on a link also lands here, to show it in place
    location.href = homeUrl + '#find=' + it.id;                          // from a blog page: the home page reveals it on arrival
  }
  function fromHash() {                                              // arriving on the home page with #find=<id>
    var m = /^#find=(\d+)$/.exec(location.hash);
    if (!m || !isHome) return;
    load().then(function (data) {
      var it = data.page[+m[1]] || pageItems && pageItems[+m[1]];
      if (it && it.sel) setTimeout(function () { reveal(it); }, 250);
    });
  }

  /* ---------- voice search (Web Speech API: Chrome, Edge, Safari, Android and iOS browsers; hidden where unsupported) ---------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null, listening = false, mic = null, idleHint = input.placeholder;
  if (SR) {
    mic = document.createElement('button'); mic.type = 'button'; mic.className = 'sp-mic'; mic.setAttribute('aria-label', 'Search by voice'); mic.setAttribute('aria-pressed', 'false'); mic.title = 'Search by voice';
    mic.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>';
    ov.querySelector('.sp-input').appendChild(mic);
    mic.addEventListener('click', function (e) { e.preventDefault(); listening ? stopVoice() : startVoice(); });
  }
  function setListening(on) {
    listening = on;
    if (!mic) return;
    mic.classList.toggle('on', on); mic.setAttribute('aria-pressed', String(on));
    mic.setAttribute('aria-label', on ? 'Stop listening' : 'Search by voice');
    input.placeholder = on ? 'Listening…' : idleHint;
  }
  function voiceNote(msg) { res.hidden = false; res.innerHTML = '<div class="search-empty">' + esc(msg) + '</div>'; hits = []; }
  function startVoice() {
    try {
      rec = new SR();
      rec.lang = document.documentElement.lang || navigator.language || 'en-US';
      rec.interimResults = true; rec.continuous = false; rec.maxAlternatives = 1;
      rec.onresult = function (ev) {
        var t = ''; for (var i = 0; i < ev.results.length; i++) t += ev.results[i][0].transcript;
        input.value = t.replace(/[.?!,]+$/, '').trim(); run(input.value);                 // searches while you speak
      };
      rec.onerror = function (ev) {
        var m = { 'not-allowed': 'The microphone is blocked. Allow it for this site in your browser settings, then try again.', 'service-not-allowed': 'Voice input is not allowed here. Try again on an https:// page.', 'no-speech': 'I did not hear anything. Tap the microphone and try again.', 'audio-capture': 'No microphone was found.', 'network': 'Voice search needs an internet connection.' }[ev.error];
        if (m && !input.value.trim()) voiceNote(m);
      };
      rec.onend = function () { setListening(false); rec = null; input.focus(); };
      rec.start(); setListening(true);
    } catch (err) { setListening(false); voiceNote('Voice search could not start in this browser.'); }
  }
  function stopVoice() { if (rec) { try { rec.stop(); } catch (e) {} } setListening(false); }

  /* ---------- opening and closing ---------- */
  function openSearch() {
    load();
    lastFocus = document.activeElement;
    var root = document.documentElement;
    root.style.setProperty('--sbw', Math.max(0, innerWidth - root.clientWidth) + 'px');       // keep the page from shifting when the scrollbar goes
    root.classList.add('search-lock');
    ov.classList.add('open');
    input.value = ''; run('');
    input.focus();
  }
  function closeSearch() { stopVoice(); ov.classList.remove('open'); document.documentElement.classList.remove('search-lock'); }
  window.openSearch = openSearch; window.closeSearch = closeSearch;

  input.addEventListener('input', function () { run(input.value); });
  input.addEventListener('keydown', function (e) { if (listening && e.key !== 'Enter') stopVoice(); });
  res.addEventListener('mouseover', function (e) {                   // the row under the pointer replaces any keyboard highlight
    var b = e.target.closest('.search-item'); if (!b || +b.dataset.i === active) return;
    active = +b.dataset.i;
    res.querySelectorAll('.search-item.active').forEach(function (x) { x.classList.remove('active'); });
    b.classList.add('active');
  });
  res.addEventListener('click', function (e) { var b = e.target.closest('.search-item'); if (b) go(hits[+b.dataset.i], e.metaKey || e.ctrlKey); });
  ov.addEventListener('click', function (e) { if (e.target === ov) closeSearch(); });
  document.addEventListener('keydown', function (e) {
    var el = document.activeElement, typing = el && (/INPUT|TEXTAREA|SELECT/.test(el.tagName) || el.isContentEditable);
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openSearch(); return; }
    if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); openSearch(); return; }
    if (!ov.classList.contains('open')) return;
    if (e.key === 'Escape') closeSearch();
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active < 0 ? -1 : active - 1); }
    else if (e.key === 'Enter' && hits.length) { e.preventDefault(); go(hits[active < 0 ? 0 : active], e.metaKey || e.ctrlKey); }   // nothing highlighted: open the first result
  });
  addEventListener('hashchange', fromHash);
  fromHash();
})();
