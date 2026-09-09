(function () {
  // theme toggle
  var root = document.documentElement;
  var btn = document.getElementById('theme-toggle');
  function current() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (btn) btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) {}
    document.dispatchEvent(new CustomEvent('themechange'));
  });

  // BibTeX copy
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('.bib-btn');
    if (!b) return;
    var pre = document.getElementById('bib-' + b.dataset.key);
    if (!pre) return;
    var text = pre.textContent;
    function done() { b.classList.add('copied'); b.textContent = 'copied'; setTimeout(function () { b.classList.remove('copied'); b.textContent = 'BibTeX'; }, 1500); }
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { pre.hidden = !pre.hidden; });
    else pre.hidden = !pre.hidden;
  });

  // publication filters
  var filters = document.getElementById('filters');
  if (!filters) return;
  var chips = Array.prototype.slice.call(filters.querySelectorAll('.chip-filter'));
  var first = document.getElementById('f-first');
  var search = document.getElementById('f-search');
  var clear = document.getElementById('f-clear');
  var count = document.getElementById('f-count');
  var pubs = Array.prototype.slice.call(document.querySelectorAll('.year-list .pub'));
  var blocks = Array.prototype.slice.call(document.querySelectorAll('.year-block'));

  function apply() {
    var active = chips.filter(function (c) { return c.getAttribute('aria-pressed') === 'true'; }).map(function (c) { return c.dataset.group; });
    var q = (search.value || '').trim().toLowerCase();
    var shown = 0;
    pubs.forEach(function (p) {
      var ok = (!active.length || active.indexOf(p.dataset.group) >= 0) &&
               (!first.checked || p.dataset.first === 'true') &&
               (!q || p.dataset.search.indexOf(q) >= 0);
      p.classList.toggle('hidden', !ok);
      if (ok) shown++;
    });
    blocks.forEach(function (b) {
      b.classList.toggle('hidden', !b.querySelector('.pub:not(.hidden)'));
    });
    count.textContent = (active.length || first.checked || q) ? shown + ' of ' + pubs.length + ' shown' : '';
    var params = new URLSearchParams();
    if (active.length) params.set('group', active.join(','));
    if (first.checked) params.set('first', '1');
    if (q) params.set('q', q);
    var s = params.toString();
    history.replaceState(null, '', location.pathname + (s ? '?' + s : ''));
  }
  chips.forEach(function (c) {
    c.addEventListener('click', function () { c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true'); apply(); });
  });
  first.addEventListener('change', apply);
  search.addEventListener('input', apply);
  clear.addEventListener('click', function () { chips.forEach(function (c) { c.setAttribute('aria-pressed', 'false'); }); first.checked = false; search.value = ''; apply(); });

  var init = new URLSearchParams(location.search);
  (init.get('group') || '').split(',').forEach(function (g) {
    chips.forEach(function (c) { if (c.dataset.group === g) c.setAttribute('aria-pressed', 'true'); });
  });
  if (init.get('first')) first.checked = true;
  if (init.get('q')) search.value = init.get('q');
  apply();
})();
