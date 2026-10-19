/* Builds a sticky side table of contents from the article's h2/h3 headings and highlights the section being read */
(function () {
  var art = document.querySelector('article');
  if (!art || !art.querySelector('.toc')) return;
  var heads = [].slice.call(art.querySelectorAll('h2, h3')).filter(function (h) { return !h.closest('.toc'); });
  var used = {};
  heads.forEach(function (h) {
    if (!h.id) {
      var id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'section';
      while (used[id] || document.getElementById(id)) id += '-x';
      h.id = id;
    }
    used[h.id] = 1;
  });

  var panel = document.createElement('aside');
  panel.className = 'side-toc';
  panel.setAttribute('aria-label', 'Table of contents');
  var html = '<strong>Contents</strong><ul>', open = false;
  function esc(t) { return t.replace(/&/g, '&amp;').replace(/</g, '&lt;'); }
  heads.forEach(function (h) {
    var a = '<a href="#' + h.id + '">' + esc(h.textContent.trim()) + '</a>';
    if (h.tagName === 'H2') {
      html += (open ? '</ul></li>' : '') + '<li>' + a + '<ul class="sub">';
      open = true;
    } else if (open) html += '<li>' + a + '</li>';
  });
  panel.innerHTML = html + (open ? '</ul></li>' : '') + '</ul>';
  document.body.appendChild(panel);

  var links = [].slice.call(panel.querySelectorAll('a'));
  var targets = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  function update() {
    var cur = -1;
    targets.forEach(function (h, i) { if (h.getBoundingClientRect().top <= 120) cur = i; });
    panel.querySelectorAll('li.open').forEach(function (li) { li.classList.remove('open'); });
    links.forEach(function (a, i) {
      var on = i === cur;
      a.classList.toggle('active', on);
      if (on) {
        var top = a.closest('ul.sub') ? a.closest('ul.sub').parentNode : a.parentNode;
        top.classList.add('open');
        var r = a.getBoundingClientRect(), p = panel.getBoundingClientRect();
        if (r.top < p.top || r.bottom > p.bottom) a.scrollIntoView({ block: 'nearest' });
      }
    });
  }
  addEventListener('scroll', update, { passive: true });
  update();
})();
