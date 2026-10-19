/* Site chatbot: ONE implementation, used by the home page and every blog page.

   Pages need one line before </body>:
     <script src="…/data/chat/chat.js" defer></script>

   It answers questions from what is written on the site, using data/search/search-data.js (the same file the search
   uses; the GitHub Action keeps it current), and it always shows the blog links the answer came from.

   Two modes:
     CHAT_ENDPOINT empty   works with no server: finds the most relevant passages and quotes them, with links.
     CHAT_ENDPOINT set     the same passages are sent to the worker in tools/chat-worker.js, which has a language
                           model write a short answer from them. If the worker fails, it falls back to the first mode. */
(function () {
  'use strict';
  var CHAT_ENDPOINT = '';                       // e.g. 'https://site-chat.<you>.workers.dev'  (see tools/chat-worker.js)

  var script = document.currentScript;
  var base = new URL('../../', script ? script.src : location.href);          // the site root
  var KEY = 'siteChat.v1', MAX_TURNS = 6;
  var chunks = null, df = null, avgLen = 1, loading = null, busy = false;
  var history = [];                                                           // [{role:'user'|'assistant', content, sources}]
  try { history = JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) {}

  var esc = function (t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var url = function (p) { return new URL(p, base).href; };

  /* ---------- the window ---------- */
  var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = url('data/chat/chat.css'); document.head.appendChild(css);
  var fab = document.createElement('button');
  fab.type = 'button'; fab.className = 'chat-fab'; fab.setAttribute('aria-label', 'Ask about this site'); fab.setAttribute('aria-expanded', 'false');
  fab.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>';
  var panel = document.createElement('section');
  panel.className = 'chat-panel'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Ask about this site'); panel.hidden = true;
  panel.innerHTML = '<header class="chat-head"><div><strong>Ask about this site</strong><span>Answers come from the articles and the home page</span></div>' +
    '<button type="button" class="chat-x" aria-label="Close chat">✕</button></header>' +
    '<div class="chat-log" role="log" aria-live="polite"></div>' +
    '<form class="chat-form"><input type="text" maxlength="400" placeholder="Ask a question…" autocomplete="off" aria-label="Your question"><button type="submit" aria-label="Send">➤</button></form>';
  document.body.appendChild(fab); document.body.appendChild(panel);
  var log = panel.querySelector('.chat-log'), form = panel.querySelector('form'), input = panel.querySelector('input');

  var SUGGEST = ['What does Khairul work on?', 'Which articles cover Android architecture?', 'How do I set up Claude Code?', 'What is MVVM vs MVP?'];

  /* ---------- data ---------- */
  var STOP = {}; ('a an and are as at be but by can do does for from how i if in into is it its me my of on or so than that the their then there these this to was what when where which who why will with you your about tell show give explain use using used get got has have had not just also any all khairul alam he his him').split(' ').forEach(function (w) { STOP[w] = 1; });
  var SYN = { work: 'experience', job: 'experience', company: 'experience', employer: 'experience', career: 'experience', study: 'education', university: 'education', degree: 'education', tech: 'skills', stack: 'skills', hobby: 'interests' };
  function tokens(s) {
    return (s.toLowerCase().match(/[a-z0-9+#.]+/g) || []).map(function (w) { return w.replace(/^\.+|\.+$/g, ''); })
      .filter(function (w) { return w && !STOP[w]; })
      .map(function (w) { return w.length > 4 ? w.replace(/(ing|ed|es|s)$/, '') : w.replace(/s$/, ''); });
  }
  function load() {
    if (loading) return loading;
    loading = new Promise(function (resolve) {
      if (window.SITE_SEARCH) return resolve(window.SITE_SEARCH);
      var sc = document.createElement('script');
      sc.src = url('data/search/search-data.js');
      sc.onload = function () { resolve(window.SITE_SEARCH || { articles: [], page: [] }); };
      sc.onerror = function () { resolve({ articles: [], page: [] }); };
      document.head.appendChild(sc);
    }).then(function (data) {
      chunks = [];
      data.articles.forEach(function (a) {
        a.s.forEach(function (g) {
          if (!g.x) return;
          chunks.push({ title: a.t, head: g.h, text: g.x, href: url(a.u + (g.id ? '#' + g.id : '')), blog: true, page: url(a.u), kind: 'article' });
        });
      });
      data.page.forEach(function (it) {
        if (it.link) return;                                          // blog cards repeat the articles, which are already searched in full
        chunks.push({ title: it.title, head: it.section, text: it.text, href: url(it.href), blog: /blog\//.test(it.href), page: url(it.href.split('#')[0]), kind: 'home', ext: it.ext });
      });
      df = {}; var total = 0;
      chunks.forEach(function (c) {
        c.tf = {}; c.tt = {};
        tokens(c.title + ' ' + c.head).forEach(function (w) { c.tt[w] = 1; });
        var ts = tokens(c.head + ' ' + c.text); c.len = ts.length || 1; total += c.len;
        ts.forEach(function (w) { c.tf[w] = (c.tf[w] || 0) + 1; });
        Object.keys(c.tf).forEach(function (w) { df[w] = (df[w] || 0) + 1; });
      });
      avgLen = total / (chunks.length || 1);
      return chunks;
    });
    return loading;
  }

  /* ---------- finding the passages (BM25 with a boost for title and heading words) ---------- */
  function retrieve(q, k) {
    var terms = tokens(q).filter(function (w, i, a) { return a.indexOf(w) === i; });
    if (!terms.length) return { terms: [], top: [] };
    var N = chunks.length, scored = [];
    chunks.forEach(function (c) {
      var s = 0, hit = 0;
      terms.forEach(function (w) {
        var alt = SYN[w] && !c.tf[w] && !c.tt[w] ? SYN[w] : w;                        // "where does he work" also finds the Experience section
        var f = c.tf[alt]; if (!f && !c.tt[alt]) return;
        var idf = Math.log(1 + (N - (df[alt] || 0) + 0.5) / ((df[alt] || 0) + 0.5));
        s += idf * ((f || 0) * 2.2) / ((f || 0) + 1.2 * (0.25 + 0.75 * c.len / avgLen)) + (c.tt[alt] ? idf * 1.2 : 0);
        hit++;
      });
      if (hit >= Math.ceil(terms.length * 0.6)) scored.push({ c: c, s: s * (0.5 + 0.5 * hit / terms.length) * (c.kind === 'home' ? 1.3 : 1), hit: hit });   // most of the question's words must be there
    });
    scored.sort(function (a, b) { return b.s - a.s; });
    return { terms: terms, top: scored.slice(0, k) };
  }
  function excerpt(text, terms, max) {                                  // the part of a long passage that mentions the question's words
    if (text.length <= max) return text;
    var low = text.toLowerCase(), at = -1;
    terms.forEach(function (t) { var i = low.indexOf(t.slice(0, 5)); if (i >= 0 && (at < 0 || i < at)) at = i; });
    var start = Math.max(0, (at < 0 ? 0 : at) - 120);
    return (start ? '… ' : '') + text.slice(start, start + max) + ' …';
  }
  function bestSentences(text, terms, n) {
    var parts = text.match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [text];
    var ranked = parts.map(function (p, i) {
      var tk = tokens(p); return { i: i, p: p.trim(), s: terms.filter(function (t) { return tk.indexOf(t) >= 0; }).length };
    }).filter(function (x) { return x.p.length > 25; });
    ranked.sort(function (a, b) { return b.s - a.s || a.i - b.i; });
    return ranked.slice(0, n).sort(function (a, b) { return a.i - b.i; }).map(function (x) { return x.p; }).join(' ');
  }
  function sourcesOf(top) {                                              // up to 3 distinct pages, best first
    var seen = {}, out = [];
    top.forEach(function (r) {
      var c = r.c; if (seen[c.page] || out.length >= 3) return; seen[c.page] = 1;
      out.push({ title: c.title, href: c.href, ext: c.ext });
    });
    return out;
  }
  function relevant(top) { return top.filter(function (r) { return r.s >= top[0].s * 0.35; }); }

  /* ---------- answering ---------- */
  var GREET = /^(hi|hello|hey|yo|hola|good (morning|afternoon|evening)|thanks|thank you|thx)\b/i;
  function localAnswer(found) {
    var top = found.top;
    if (!top.length || top[0].s < 1.5) return { text: 'I could not find that on this site. Try different words, or use the search (press / on any page).', sources: [] };
    var parts = [];
    top.slice(0, 2).forEach(function (r) {
      if (r.s < top[0].s * 0.45) return;
      var t = r.c.kind === 'home' && r.c.text.length < 400 ? r.c.text : bestSentences(r.c.text, found.terms, 2) || r.c.text;
      parts.push((r.c.head && r.c.kind === 'article' ? '**' + r.c.head.replace(/^\d+\.\s*/, '') + '** — ' : '') + excerpt(t, found.terms, 320));
    });
    return { text: parts.join('\n\n'), sources: sourcesOf(relevant(top)) };
  }
  function ask(q) {
    return load().then(function () {
      if (GREET.test(q) && q.split(/\s+/).length < 4) return { text: 'Hi! Ask me anything about Khairul’s work, skills or articles.', sources: [] };
      var found = retrieve(q, 8);
      if (!CHAT_ENDPOINT || !found.top.length || found.top[0].s < 1.5) return localAnswer(found);
      var ctx = found.top.slice(0, 6).map(function (r, i) {
        return { n: i + 1, title: r.c.title + (r.c.head && r.c.kind === 'article' ? ' › ' + r.c.head : ''), url: r.c.href, text: excerpt(r.c.text, found.terms, 1200) };
      });
      var msgs = history.slice(-MAX_TURNS * 2).map(function (m) { return { role: m.role, content: m.content.slice(0, 1500) }; });
      return fetch(CHAT_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: msgs, context: ctx }) })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (j) {
          if (!j.answer) throw new Error('empty');
          var cited = {}; (j.answer.match(/\[(\d+)\]/g) || []).forEach(function (m) { cited[+m.slice(1, -1)] = 1; });
          var cites = found.top.slice(0, 6).filter(function (r, i) { return cited[i + 1]; });
          return { text: j.answer, ctx: ctx, sources: sourcesOf(cites.length ? cites : relevant(found.top)) };
        })
        .catch(function () { return localAnswer(found); });
    });
  }

  /* ---------- drawing ---------- */
  function inline(s, ctx) {                                              // **bold**, `code`, [1] citations: all after escaping
    s = esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return s.replace(/\[(\d+)\]/g, function (m, n) {
      var c = ctx && ctx[n - 1]; return c ? '<a class="chat-cite" href="' + esc(c.url) + '" title="' + esc(c.title) + '">' + n + '</a>' : m;
    });
  }
  function render(text, ctx) {
    var out = '', list = false;
    text.split('\n').forEach(function (line) {
      var li = /^\s*(?:[-*•]|\d+\.)\s+(.*)/.exec(line);
      if (li) { if (!list) { out += '<ul>'; list = true; } out += '<li>' + inline(li[1], ctx) + '</li>'; return; }
      if (list) { out += '</ul>'; list = false; }
      if (line.trim()) out += '<p>' + inline(line, ctx) + '</p>';
    });
    return out + (list ? '</ul>' : '');
  }
  function add(role, html, sources) {
    var d = document.createElement('div'); d.className = 'chat-msg ' + role;
    d.innerHTML = '<div class="chat-bubble">' + html + '</div>' + (sources && sources.length
      ? '<div class="chat-src"><span>Read more</span>' + sources.map(function (s) {
        return '<a href="' + esc(s.href) + '"' + (s.ext ? ' target="_blank" rel="noopener"' : '') + '>' + esc(s.title.slice(0, 70)) + '</a>';
      }).join('') + '</div>' : '');
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-40))); } catch (e) {} }
  function welcome() {
    var d = add('bot', '<p>Hi! I answer from the articles and pages on this site. Try one of these:</p>');
    var w = document.createElement('div'); w.className = 'chat-chips';
    SUGGEST.forEach(function (s) { var b = document.createElement('button'); b.type = 'button'; b.textContent = s; b.addEventListener('click', function () { send(s); }); w.appendChild(b); });
    d.appendChild(w);
  }
  function send(q) {
    q = q.trim(); if (!q || busy) return;
    busy = true; input.value = '';
    log.querySelectorAll('.chat-chips').forEach(function (e) { e.remove(); });
    add('user', '<p>' + esc(q) + '</p>');
    var wait = add('bot', '<p class="chat-typing"><i></i><i></i><i></i></p>');
    ask(q).then(function (a) {
      wait.remove();
      add('bot', render(a.text, a.ctx), a.sources);
      history.push({ role: 'user', content: q }, { role: 'assistant', content: a.text, sources: a.sources }); save();
    }).catch(function () {
      wait.remove(); add('bot', '<p>Something went wrong. Please try again.</p>');
    }).then(function () { busy = false; input.focus(); });
  }

  /* ---------- opening and closing ---------- */
  function open() {
    panel.hidden = false; fab.setAttribute('aria-expanded', 'true'); fab.classList.add('open');
    load();
    if (!log.children.length) {
      if (history.length) history.forEach(function (m) { m.role === 'user' ? add('user', '<p>' + esc(m.content) + '</p>') : add('bot', render(m.content), m.sources); });
      else welcome();
    }
    input.focus();
  }
  function close() { panel.hidden = true; fab.setAttribute('aria-expanded', 'false'); fab.classList.remove('open'); fab.focus(); }
  fab.addEventListener('click', function () { panel.hidden ? open() : close(); });
  panel.querySelector('.chat-x').addEventListener('click', close);
  form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden && !document.querySelector('.search-overlay.open')) close(); });
  window.openChat = open;
})();
