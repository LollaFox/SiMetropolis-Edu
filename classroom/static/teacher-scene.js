'use strict';

var svg = document.getElementById('map');
var W = 1200, H = 1000, TW = 88, TH = 44, hw = TW / 2, hh = TH / 2;
var FW = 34, FH = 17;
var STEPS = 5;
var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function rnd(a, b) { var n = Math.sin(a * 127.1 + b * 311.7 + 13.37) * 43758.5453; return n - Math.floor(n); }
function mod(n, m) { return ((n % m) + m) % m; }
function f(n) { return Math.round(n * 10) / 10; }
function dia(x, y, a, b) {
  return 'M' + f(x) + ' ' + f(y - b) + 'L' + f(x + a) + ' ' + f(y) + 'L' + f(x) + ' ' + f(y + b) + 'L' + f(x - a) + ' ' + f(y) + 'Z';
}
/* a ground tile; the matching stroke closes hairline seams between neighbours */
function flat(x, y, colour) {
  return '<path d="' + dia(x, y, hw, hh) + '" fill="' + colour + '" stroke="' + colour + '"/>';
}
function box(x, y, h, pal, a, b, floors) {
  var s =
    '<path d="M' + f(x - a) + ' ' + f(y - h) + 'L' + f(x) + ' ' + f(y + b - h) + 'V' + f(y + b) + 'L' + f(x - a) + ' ' + f(y) + 'Z" fill="' + pal[1] + '"/>' +
    '<path d="M' + f(x + a) + ' ' + f(y - h) + 'L' + f(x) + ' ' + f(y + b - h) + 'V' + f(y + b) + 'L' + f(x + a) + ' ' + f(y) + 'Z" fill="' + pal[2] + '"/>' +
    '<path d="' + dia(x, y - h, a, b) + '" fill="' + pal[0] + '"/>';
  if (floors) {
    var d = '';
    for (var k = 12; k < h - 5; k += 12) {
      d += 'M' + f(x - a) + ' ' + f(y - k) + 'L' + f(x) + ' ' + f(y + b - k) + 'L' + f(x + a) + ' ' + f(y - k);
    }
    if (d) s += '<path d="' + d + '" fill="none" stroke="#12312d" stroke-opacity=".18" stroke-width="1.2"/>';
  }
  return s;
}
function wire(x, y, h, cls) {
  return '<path class="' + cls + '" d="' +
    'M' + f(x - FW) + ' ' + f(y - h) + 'L' + f(x) + ' ' + f(y - FH - h) + 'L' + f(x + FW) + ' ' + f(y - h) + 'L' + f(x) + ' ' + f(y + FH - h) + 'Z' +
    'M' + f(x - FW) + ' ' + f(y - h) + 'V' + f(y) + 'L' + f(x) + ' ' + f(y + FH) + 'L' + f(x + FW) + ' ' + f(y) + 'V' + f(y - h) +
    'M' + f(x) + ' ' + f(y + FH - h) + 'V' + f(y + FH) + '"/>';
}

var PALS = [
  ['#f6ecd9', '#dcc8a8', '#bca383'],
  ['#fcf7ec', '#e6d9c4', '#c8b79d'],
  ['#f0c5a8', '#d99b7a', '#b67c60'],
  ['#e1e8e4', '#b7c6c2', '#94a8a4']
];
var FIELDS = ['#a8cf78', '#b8d987', '#97c56b', '#c6df93', '#8ebd68'];
var MARSH = ['#6aab8a', '#5c9f7e', '#78b693'];

function tree(x, y) {
  return '<path d="M' + x + ' ' + y + 'v-10" stroke="#6b5a45" stroke-width="2.4"/>' +
    '<circle cx="' + x + '" cy="' + (y - 16) + '" r="9.5" fill="#3f8757"/>' +
    '<circle cx="' + (x - 3) + '" cy="' + (y - 19) + '" r="5" fill="#5aa46e"/>';
}
function egret(x, y) {
  return '<g transform="translate(' + x + ' ' + y + ') scale(1.25)"><g class="fa" data-off="%OFF%">' +
    '<path d="M-2 -5v8M3 -5v8" stroke="#12312d" stroke-width="1.3"/>' +
    '<ellipse cx="0" cy="-9" rx="8" ry="5" fill="#fff"/>' +
    '<path d="M5 -11q5 -6 1 -13" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round"/>' +
    '<circle cx="6.5" cy="-25" r="3" fill="#fff"/>' +
    '<path d="M9 -25l8 1.5" stroke="#f2b33d" stroke-width="2.2" stroke-linecap="round"/>' +
    '</g></g>';
}

function build() {
  var out = '';
  var smax = Math.ceil(W / 2 / hw) + 1;
  var dmax = Math.ceil(H / hh) + 2;
  for (var d = -1; d <= dmax; d++) {
    for (var s = -smax; s <= smax; s++) {
      if ((d + s) & 1) continue;
      var x = W / 2 + s * hw, y = d * hh;
      var c = (d + s) / 2, r = (d - s) / 2;
      var u = x / W, v = y / H;
      var n1 = rnd(c, r), n2 = rnd(c + 31.5, r - 17.2), n3 = rnd(c * 1.7 + 5, r * 2.3 + 1);

      var river = 0.765 + 0.055 * Math.sin(u * 5 + 0.9) + 0.018 * Math.sin(u * 11 + 2);
      var dv = Math.abs(v - river);
      var water = dv < 0.04;
      var marsh = !water && dv < 0.112 + (n1 - 0.5) * 0.03;

      /* step at which the growing city reaches this tile */
      var b = null;
      if (!water) {
        var lobe = Math.exp(-Math.pow((u - 0.42) / 0.23, 2));
        for (var t = 0; t <= STEPS + 1; t++) {
          if (v < 0.25 + 0.016 * t + lobe * 0.072 * t + (n2 - 0.5) * 0.035) { b = t; break; }
        }
      }
      var conflict = marsh && b !== null;
      var roadC = mod(c, 6) === 0, roadR = mod(r, 5) === 0, road = roadC || roadR;
      var park = !road && n3 > 0.93;

      var g = '';

      /* land as it is before the city arrives */
      var flood = null;
      if (b !== 0) {
        if (water) {
          g += flat(x, y, n1 > 0.5 ? '#4e9fc2' : '#58a8c9');
          if (n2 > 0.45) g += '<path d="M' + (x - 16) + ' ' + (y - 3) + 'h13M' + (x + 2) + ' ' + (y + 6) + 'h15" stroke="#fff" stroke-opacity=".4" stroke-width="1.6" stroke-linecap="round"/>';
        } else if (marsh) {
          g += '<path class="t" d="' + dia(x, y, hw, hh) + '" fill="' + MARSH[Math.floor(n1 * 3)] + '"/>';
          if (n2 > 0.74) g += '<ellipse cx="' + x + '" cy="' + y + '" rx="17" ry="7" fill="#58a8c9" fill-opacity=".85"/>';
        } else {
          var pk = rnd(Math.floor(c / 2) + 100, Math.floor(r / 2) + 50);
          var fill = pk > 0.9 ? '#a5d3c4' : FIELDS[Math.floor(pk * 5.55) % 5];
          g += '<path class="t" d="' + dia(x, y, hw, hh) + '" fill="' + fill + '"/>';
          var sg = pk > 0.5 ? 1 : -1, fd = '';
          for (var k = -1; k <= 1; k++) {
            var cx = x - sg * k * hw * 0.3, cy = y + k * hh * 0.3;
            fd += 'M' + f(cx - sg * hw * 0.34) + ' ' + f(cy - hh * 0.34) + 'L' + f(cx + sg * hw * 0.34) + ' ' + f(cy + hh * 0.34);
          }
          g += '<path d="' + fd + '" stroke="#12312d" stroke-opacity=".13" stroke-width="1.3"/>';
        }

        if (!water && b === null) {
          var fs = Math.ceil((dv - 0.04) / 0.006 + (n3 - 0.5));
          if (fs < 1) fs = 1;
          if (fs <= STEPS) {
            flood = fs;
            g += '<path class="fl" data-f="' + fs + '" d="' + dia(x, y, hw, hh) + '" fill="#74bcd8" stroke="#74bcd8"/>';
          }
        }

        if (marsh && n2 < 0.5) {
          g += '<path d="M' + (x - 11) + ' ' + (y + 3) + 'l-3 -15M' + (x - 4) + ' ' + (y + 4) + 'v-19M' + (x + 4) + ' ' + (y + 3) + 'l3 -15" stroke="#2f6f58" stroke-width="2.4" stroke-linecap="round"/>';
        }
        if (!marsh && !water && b === null && n3 > 0.88 && flood === null) g += tree(x - 8, y + 2);

        if (marsh && n3 > 0.8) {
          var off = conflict ? b - 1 : (flood !== null ? flood : 99);
          g += egret(x + 6, y + 2).replace('%OFF%', off);
        }
      }

      /* what the city puts here */
      if (b !== null) {
        var pal = PALS[n1 < 0.35 ? 0 : n1 < 0.6 ? 1 : n1 < 0.82 ? 2 : 3];
        var h = 16 + 26 * n3;
        if (b === 0) h += Math.max(0, Math.min(1, (0.3 - v) / 0.3)) * 96 * n2;
        h = Math.round(h);

        if (conflict) {
          g += '<g class="cf" data-b="' + b + '"><path d="' + dia(x, y, hw, hh) + '" fill="rgba(226,87,58,.55)" stroke="#ff5b38" stroke-width="2"/>' + wire(x, y, h, 'wire-c') + '</g>';
        } else {
          if (b > 0) {
            g += '<g class="gh" data-b="' + b + '">' +
              (road ? '<path class="wire" d="' + dia(x, y, hw - 3, hh - 1.5) + '"/>' : wire(x, y, h, 'wire')) + '</g>';
          }
          if (b <= STEPS) {
            var dev = '';
            if (road) {
              dev += flat(x, y, '#5d686c');
              var ld = '';
              if (roadR) ld += 'M' + (x - hw / 2) + ' ' + (y - hh / 2) + 'L' + (x + hw / 2) + ' ' + (y + hh / 2);
              if (roadC) ld += 'M' + (x + hw / 2) + ' ' + (y - hh / 2) + 'L' + (x - hw / 2) + ' ' + (y + hh / 2);
              dev += '<path d="' + ld + '" stroke="#f6ecd9" stroke-opacity=".7" stroke-width="1.6" stroke-dasharray="7 6"/>';
            } else if (park) {
              dev += flat(x, y, '#d5cfbf') + '<path d="' + dia(x, y, FW, FH) + '" fill="#8ebd68"/>' + tree(x - 9, y + 2) + tree(x + 10, y - 1);
            } else {
              dev += flat(x, y, '#d5cfbf') + box(x, y, h, pal, FW, FH, true);
              if (h > 62) dev += box(x, y - h, 7, pal, 14, 7, false);
            }
            g += b === 0 ? dev : '<g class="dv" data-b="' + b + '">' + dev + '</g>';

            /* older blocks densify as the city keeps growing */
            if (!road && !park && b <= STEPS - 2 && n2 > 0.4) {
              var b2 = b + 2 + Math.floor(n1 * 2);
              if (b2 <= STEPS) {
                var h2 = Math.round(h + 22 + 44 * n1);
                g += '<g class="dv" data-b="' + b2 + '">' + box(x, y, h2, pal, FW, FH, true) + box(x, y - h2, 7, pal, 14, 7, false) + '</g>';
              }
            }
          }
        }
      }
      out += g;
    }
  }
  svg.innerHTML = out;
}

build();

function collect(sel, key) {
  return Array.prototype.map.call(svg.querySelectorAll(sel), function (el) {
    return { el: el, n: Number(el.getAttribute(key)) };
  });
}
var devs = collect('.dv', 'data-b');
var ghosts = collect('.gh', 'data-b');
var conflicts = collect('.cf', 'data-b');
var floods = collect('.fl', 'data-f');
var fauna = collect('.fa', 'data-off');

var step = 0, timer = null;

function apply(t) {
  step = t;
  var i;
  for (i = 0; i < devs.length; i++) devs[i].el.classList.toggle('on', t >= devs[i].n);
  for (i = 0; i < ghosts.length; i++) ghosts[i].el.classList.toggle('on', t === ghosts[i].n - 1);
  for (i = 0; i < conflicts.length; i++) conflicts[i].el.classList.toggle('on', t >= conflicts[i].n - 1);
  for (i = 0; i < floods.length; i++) floods[i].el.classList.toggle('on', t >= floods[i].n);
  for (i = 0; i < fauna.length; i++) fauna[i].el.classList.toggle('off', t >= fauna[i].n);
}

function schedule() {
  clearTimeout(timer);
  if (reduce || document.hidden) return;
  timer = setTimeout(function () {
    apply(step >= STEPS ? 0 : step + 1);
    schedule();
  }, step >= STEPS ? 5200 : step === 0 ? 1900 : 1500);
}

apply(reduce ? STEPS : 0);
schedule();
document.addEventListener('visibilitychange', schedule);
