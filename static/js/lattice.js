/* ABC-stacked (rhombohedral) graphene lattice drifting slowly behind the hero.
   Three honeycomb layers, each shifted by one bond length, drawn on a low-res
   canvas; pointer position adds a small parallax. Respects reduced motion. */
(function () {
  var canvas = document.getElementById('lattice');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W, H, dpr, t = 0, px = 0, py = 0, tx = 0, ty = 0, raf = null, visible = true;

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function colors() {
    var dark = document.documentElement.dataset.theme === 'dark' ||
      (!document.documentElement.dataset.theme && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var a = dark ? [0.34, 0.26, 0.22] : [0.30, 0.22, 0.18];
    return [
      'rgba(' + css('--lattice-1') + ',' + a[0] + ')',
      'rgba(' + css('--lattice-2') + ',' + a[1] + ')',
      'rgba(' + css('--lattice-3') + ',' + a[2] + ')'
    ];
  }
  var COLS = colors();
  document.addEventListener('themechange', function () { COLS = colors(); if (reduce) draw(); });

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (reduce) draw();
  }

  // honeycomb with bond length a; layer k shifted by k*a along the armchair direction
  function layer(a, ox, oy, color, width) {
    var h = a * Math.sqrt(3);          // row height (between hexagon rows)
    var cols = Math.ceil(W / (3 * a)) + 3, rows = Math.ceil(2 * H / h) + 4;
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath();
    for (var r = -2; r < rows; r++) {
      for (var c = -2; c < cols; c++) {
        // A sites sit on rows h/2 apart, alternate rows shifted by 1.5a;
        // the three bonds of each A site tile the honeycomb without duplicates
        var x = ox + c * 3 * a + (r % 2 ? 1.5 * a : 0);
        var y = oy + r * h * 0.5;
        ctx.moveTo(x, y); ctx.lineTo(x + a, y);
        ctx.moveTo(x, y); ctx.lineTo(x - a * 0.5, y + h * 0.5);
        ctx.moveTo(x, y); ctx.lineTo(x - a * 0.5, y - h * 0.5);
      }
    }
    ctx.stroke();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    var a = Math.max(22, Math.min(34, W / 36));
    var h = a * Math.sqrt(3);
    var drift = reduce ? 0 : t * 0.15;
    var par = [1.0, 0.6, 0.3];
    for (var k = 0; k < 3; k++) {
      var ox = W * 0.45 + k * a + drift * (0.5 + 0.25 * k) + px * 14 * par[k];
      var oy = -h + (drift * 0.3) % h + py * 10 * par[k];
      layer(a, ox % (3 * a) + W * 0.2, oy, COLS[k], k === 0 ? 1.1 : 0.9);
    }
    // soft radial fade so the lattice dissolves towards the left text column
    var R = Math.max(W, H);
    var g = ctx.createRadialGradient(W * 0.72, H * 0.5, R * 0.08, W * 0.72, H * 0.5, R * 0.75);
    g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, css('--bg'));
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  }

  function frame() {
    t += 1;
    px += (tx - px) * 0.05; py += (ty - py) * 0.05;
    draw();
    raf = visible ? requestAnimationFrame(frame) : null;
  }

  window.addEventListener('resize', resize);
  window.addEventListener('pointermove', function (e) {
    var r = canvas.getBoundingClientRect();
    tx = (e.clientX - r.left) / r.width - 0.5;
    ty = (e.clientY - r.top) / r.height - 0.5;
  }, { passive: true });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (es) {
      visible = es[0].isIntersecting;
      if (visible && !raf && !reduce) raf = requestAnimationFrame(frame);
    }).observe(canvas);
  }
  resize();
  if (!reduce) raf = requestAnimationFrame(frame);
})();
