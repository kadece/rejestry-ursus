/* ==========================================================================
   Wykazy Ursus — logika widoku
   ========================================================================== */
(function () {
  'use strict';

  var BUNDLE = JSON.parse(document.getElementById('wykazy-data').textContent);
  var YEARS = (BUNDLE.years || []).slice().sort(function (a, b) { return a - b; });
  var D = null;   // dane aktualnie wybranego rocznika

  var MONTHS = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec',
    'lipiec', 'sierpień', 'wrzesień', 'październik', 'listopad', 'grudzień'];
  var MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze',
    'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];
  var MONTHS_GEN = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
    'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

  var state = { year: BUNDLE.default, view: 'overview', month: null, q: '' };

  /* ------------------------------------------------------------- helpers -- */

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function monthOf(row) {
    if (!row.d) return 0;
    var m = parseInt(row.d.slice(5, 7), 10);
    return m >= 1 && m <= 12 ? m : 0;
  }

  function fmtDate(iso) {
    if (!iso) return '';
    var p = iso.split('-');
    return p[2] + '.' + p[1] + '.' + p[0];
  }

  function norm(s) {
    return String(s == null ? '' : s)
      .toLowerCase()
      .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
      .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
      .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');
  }

  function badgeClass(v) {
    var t = norm(v);
    if (/^ustalam|^pnb$|^udzielam|^zatwierdz/.test(t)) return 'ok';
    if (/odmawiam|^odmowa|^sprzeciw/.test(t)) return 'no';
    if (/umorz|uchylam|^brak/.test(t)) return 'neutral';
    if (/przenies|zmieniam|^pnr$/.test(t)) return 'info';
    return 'neutral';
  }

  function isBadgeCol(key) {
    return key === 'roz' || key === 'rodz';
  }

  /* --------------------------------------------------------------- index -- */

  var byMonth = {};   // registerId -> month -> rows[]
  var totals = { all: 0, byMonth: {}, byReg: {} };

  function loadYear(y) {
    D = BUNDLE.data[String(y)];
    byMonth = {};
    totals = { all: 0, byMonth: {}, byReg: {} };

    D.registers.forEach(function (reg) {
      byMonth[reg.id] = {};
      totals.byReg[reg.id] = 0;
      reg.rows.forEach(function (row) {
        var m = monthOf(row);
        (byMonth[reg.id][m] = byMonth[reg.id][m] || []).push(row);
        totals.byReg[reg.id]++;
        totals.all++;
        totals.byMonth[m] = (totals.byMonth[m] || 0) + 1;
      });
    });
  }

  function rowsFor(regId, month) {
    return (byMonth[regId] && byMonth[regId][month]) || [];
  }

  function monthTotal(m) { return totals.byMonth[m] || 0; }

  /* -------------------------------------------------------------- render -- */

  var elTabs = document.getElementById('tabs');
  var elView = document.getElementById('view');
  var elSearch = document.getElementById('q');
  var elYears = document.getElementById('years');

  function renderYears() {
    if (!elYears) return;
    if (YEARS.length < 2) { elYears.style.display = 'none'; return; }

    var html = '';
    YEARS.forEach(function (y) {
      var d = BUNDLE.data[String(y)];
      html += '<button class="yr" role="tab" data-year="' + y + '" aria-selected="' +
        (y === state.year) + '" title="' + y + ' — ' + d.total + ' pozycji">' +
        y + '<span class="c">' + d.total + '</span></button>';
    });
    elYears.innerHTML = html;
  }

  function renderTabs() {
    var html = '<button class="tab" role="tab" data-view="overview" aria-selected="' +
      (state.view === 'overview') + '">Przegląd roku</button>';

    for (var m = 1; m <= 12; m++) {
      var n = monthTotal(m);
      var sel = state.view === 'month' && state.month === m;
      html += '<button class="tab' + (n === 0 ? ' is-empty' : '') + '" role="tab" data-month="' + m +
        '" aria-selected="' + sel + '">' + MONTHS_SHORT[m - 1] +
        '<span class="c">' + n + '</span></button>';
    }

    if (monthTotal(0) > 0) {
      html += '<button class="tab" role="tab" data-month="0" aria-selected="' +
        (state.view === 'month' && state.month === 0) + '">bez daty' +
        '<span class="c">' + monthTotal(0) + '</span></button>';
    }
    elTabs.innerHTML = html;
  }

  function renderOverview() {
    var maxCell = 1;
    D.registers.forEach(function (reg) {
      for (var m = 1; m <= 12; m++) maxCell = Math.max(maxCell, rowsFor(reg.id, m).length);
    });

    var activeMonths = 0;
    for (var m = 1; m <= 12; m++) if (monthTotal(m) > 0) activeMonths++;

    var html = '';

    html += '<div class="kpis">' +
      kpi(totals.all, 'pozycji łącznie', true) +
      kpi(D.registers.length, 'rejestrów', false) +
      kpi(activeMonths, 'miesięcy z danymi', false) +
      kpi(maxMonthLabel(), 'ostatni miesiąc z wpisami', false) +
      '</div>';

    html += '<div class="panel"><div class="panel-head">' +
      '<h2>Wykazy w układzie miesięcznym</h2>' +
      '<span class="sub">kliknij liczbę, aby przejść do wpisów</span>' +
      '<span class="count">' + D.year + '</span>' +
      '</div><div class="panel-body"><div class="tbl-wrap"><table class="matrix"><thead><tr>' +
      '<th>Rejestr</th>';

    for (var i = 1; i <= 12; i++) html += '<th>' + MONTHS_SHORT[i - 1] + '</th>';
    if (monthTotal(0) > 0) html += '<th>bd.</th>';
    html += '<th class="total">Razem</th></tr></thead><tbody>';

    D.registers.forEach(function (reg) {
      html += '<tr><th scope="row">' + esc(reg.short) + '</th>';
      for (var mm = 1; mm <= 12; mm++) {
        var n = rowsFor(reg.id, mm).length;
        if (n === 0) {
          html += '<td class="zero">·</td>';
        } else {
          var a = 0.08 + 0.62 * (n / maxCell);
          html += '<td class="cell" data-goto="' + mm + '" data-reg="' + reg.id +
            '" style="background:rgba(200,16,46,' + a.toFixed(3) + ');color:' +
            (a > 0.42 ? '#fff' : '#7a1024') + '" title="' + esc(reg.name) + ' — ' +
            MONTHS[mm - 1] + ': ' + n + '">' + n + '</td>';
        }
      }
      if (monthTotal(0) > 0) {
        var n0 = rowsFor(reg.id, 0).length;
        html += n0 === 0 ? '<td class="zero">·</td>'
          : '<td class="cell" data-goto="0" data-reg="' + reg.id +
            '" style="background:#eef2f7;color:#64748b" title="bez daty: ' + n0 + '">' + n0 + '</td>';
      }
      html += '<td class="total">' + totals.byReg[reg.id] + '</td></tr>';
    });

    html += '</tbody></table></div></div></div>';

    html += '<div class="panel"><div class="panel-head"><h2>Zakres rejestrów</h2>' +
      '<span class="sub">pliki źródłowe publikowane przez Urząd Dzielnicy Ursus</span></div>' +
      '<div class="panel-body"><div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      '<th>Rejestr</th><th class="num">Pozycji</th><th>Zakres dat</th><th>Plik źródłowy</th>' +
      '</tr></thead><tbody>';

    D.registers.forEach(function (reg) {
      var dates = reg.rows.map(function (r) { return r.d; }).filter(Boolean).sort();
      var range = dates.length
        ? fmtDate(dates[0]) + ' – ' + fmtDate(dates[dates.length - 1])
        : '<span class="muted">brak dat</span>';
      html += '<tr><td><b>' + esc(reg.name) + '</b></td>' +
        '<td class="num">' + reg.rows.length + '</td>' +
        '<td class="date">' + range + '</td>' +
        '<td><a href="' + esc(reg.url) + '" target="_blank" rel="noopener">' +
        esc(reg.file) + '</a></td></tr>';
    });

    html += '</tbody></table></div></div></div>';

    html += renderYearsPanel();

    elView.innerHTML = html;
  }

  function renderYearsPanel() {
    if (YEARS.length < 2) return '';

    var html = '<div class="panel"><div class="panel-head"><h2>Roczniki</h2>' +
      '<span class="sub">kliknij rok, aby przełączyć całą stronę</span></div>' +
      '<div class="panel-body"><div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      '<th>Rok</th><th class="num">Pozycji</th><th class="num">Rejestrów</th>' +
      '<th>Zakres dat</th><th>Strona źródłowa</th></tr></thead><tbody>';

    YEARS.slice().reverse().forEach(function (y) {
      var d = BUNDLE.data[String(y)];
      var dates = [];
      d.registers.forEach(function (reg) {
        reg.rows.forEach(function (row) { if (row.d) dates.push(row.d); });
      });
      dates.sort();
      var range = dates.length
        ? fmtDate(dates[0]) + ' – ' + fmtDate(dates[dates.length - 1])
        : '<span class="muted">brak dat</span>';

      html += '<tr class="year-row" data-year="' + y + '">' +
        '<td><b>' + y + '</b>' + (y === state.year
          ? ' <span class="badge info">wybrany</span>' : '') + '</td>' +
        '<td class="num">' + d.total + '</td>' +
        '<td class="num">' + d.registers.length + '</td>' +
        '<td class="date">' + range + '</td>' +
        '<td><a href="' + esc(d.source) + '" target="_blank" rel="noopener">' +
        'wykazy-za-rok-' + y + '</a></td></tr>';
    });

    html += '</tbody></table></div></div></div>';
    return html;
  }

  function kpi(n, label, accent) {
    return '<div class="kpi' + (accent ? ' is-accent' : '') + '"><div class="n">' + n +
      '</div><div class="l">' + label + '</div></div>';
  }

  function maxMonthLabel() {
    for (var m = 12; m >= 1; m--) if (monthTotal(m) > 0) return MONTHS[m - 1];
    return '—';
  }

  function renderMonth(m) {
    var total = monthTotal(m);
    var label = m === 0 ? 'Pozycje bez daty' : MONTHS[m - 1].charAt(0).toUpperCase() +
      MONTHS[m - 1].slice(1) + ' ' + D.year;

    var html = '<div class="month-title"><h2>' + label + '</h2>' +
      '<span class="n">' + total + ' ' + plural(total, 'pozycja', 'pozycje', 'pozycji') + '</span></div>';

    if (total === 0) {
      html += '<div class="panel"><div class="empty"><b>Brak wpisów w tym miesiącu</b>' +
        'Urząd nie opublikował jeszcze danych dla tego okresu.</div></div>';
      elView.innerHTML = html;
      return;
    }

    if (m === 0) {
      html += '<div class="panel"><div class="empty" style="padding:22px">' +
        'Wpisy, dla których w pliku źródłowym nie podano daty (np. „XX.07.2026”). ' +
        'Zostaną przypisane do miesiąca, gdy urząd uzupełni rejestr.</div></div>';
    }

    D.registers.forEach(function (reg) {
      var rows = rowsFor(reg.id, m);
      if (!rows.length) return;
      html += renderRegisterPanel(reg, rows, m === 0 ? 'bez daty' : MONTHS[m - 1] + ' ' + D.year);
    });

    elView.innerHTML = html;
  }

  function renderRegisterPanel(reg, rows, periodLabel) {
    var h = '<div class="panel" id="reg-' + reg.id + '"><div class="panel-head">' +
      '<h2>' + esc(reg.name) + '</h2>' +
      '<span class="sub">' + esc(periodLabel) + '</span>' +
      '<span class="count">' + rows.length + '</span>' +
      '<button class="btn" data-csv="' + reg.id + '" style="margin-left:8px">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
      '<path d="M12 3v12m0 0l-4-4m4 4l4-4M4 19h16"/></svg>CSV</button>' +
      '</div><div class="panel-body"><div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      '<th class="num">Lp.</th><th>Data</th>';

    reg.cols.forEach(function (c) {
      h += '<th>' + esc(c.l) + '</th>';
    });
    h += '</tr></thead><tbody>';

    rows.forEach(function (row, i) {
      var dateCell;
      if (!row.d) {
        dateCell = '<span class="muted">—</span>';
      } else if (row.d.slice(0, 4) !== String(D.year)) {
        dateCell = '<span class="warn" title="Data spoza roku ' + D.year +
          ' — prawdopodobnie omyłka w pliku źródłowym">' + fmtDate(row.d) + '</span>';
      } else {
        dateCell = fmtDate(row.d);
      }

      h += '<tr><td class="num">' + (i + 1) + '</td>' +
        '<td class="date">' + dateCell + '</td>';
      reg.cols.forEach(function (c) {
        var v = row.c[c.k];
        if (v == null || v === '') { h += '<td class="muted">—</td>'; return; }
        if (isBadgeCol(c.k)) {
          h += '<td><span class="badge ' + badgeClass(v) + '">' + esc(v) + '</span></td>';
        } else if (c.k === 'nr') {
          h += '<td class="nr">' + esc(v) + '</td>';
        } else {
          var cls = c.w === 'wide' ? 'wide' : (c.w === 'mid' ? 'mid' : '');
          if (String(v).length > 150) {
            h += '<td class="' + cls + '"><div class="clamp">' + esc(v) + '</div>' +
              '<button class="more">więcej</button></td>';
          } else {
            h += '<td class="' + cls + '">' + esc(v) + '</td>';
          }
        }
      });
      h += '</tr>';
    });

    h += '</tbody></table></div></div></div>';
    return h;
  }

  function renderSearch(q) {
    var nq = norm(q);
    var hits = [];

    D.registers.forEach(function (reg) {
      reg.rows.forEach(function (row) {
        var hay = norm(reg.name + ' ' + Object.keys(row.c).map(function (k) { return row.c[k]; }).join(' '));
        if (hay.indexOf(nq) !== -1) hits.push({ reg: reg, row: row });
      });
    });

    var html = '<div class="month-title"><h2>Wyniki wyszukiwania</h2>' +
      '<span class="n">„' + esc(q) + '” — ' + hits.length + ' ' +
      plural(hits.length, 'pozycja', 'pozycje', 'pozycji') + '</span></div>';

    if (!hits.length) {
      html += '<div class="panel"><div class="empty"><b>Nic nie znaleziono</b>' +
        'Spróbuj krótszej frazy, np. nazwy ulicy lub wnioskodawcy.</div></div>';
      elView.innerHTML = html;
      return;
    }

    var grouped = {};
    hits.forEach(function (h) {
      (grouped[h.reg.id] = grouped[h.reg.id] || []).push(h.row);
    });

    D.registers.forEach(function (reg) {
      if (!grouped[reg.id]) return;
      html += renderRegisterPanel(reg, grouped[reg.id], 'wyniki wyszukiwania');
    });

    elView.innerHTML = html;
  }

  function plural(n, one, few, many) {
    if (n === 1) return one;
    var d = n % 10, h = n % 100;
    if (d >= 2 && d <= 4 && (h < 10 || h >= 20)) return few;
    return many;
  }

  /* ---------------------------------------------------------------- draw -- */

  function draw() {
    renderYears();
    renderTabs();
    if (state.q.trim().length >= 2) {
      renderSearch(state.q.trim());
    } else if (state.view === 'month') {
      renderMonth(state.month);
    } else {
      renderOverview();
    }
    syncUrl();
  }

  function syncUrl() {
    if (!window.history || !history.replaceState) return;
    var p = new URLSearchParams(location.search);
    ['y', 'm', 'q', 'view'].forEach(function (k) { p.delete(k); });
    if (state.year !== BUNDLE.default) p.set('y', state.year);
    if (state.view === 'month' && state.month !== null) p.set('m', state.month);
    if (state.q.trim()) p.set('q', state.q.trim());
    var qs = p.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
  }

  /* -------------------------------------------------------------- events -- */

  if (elYears) {
    elYears.addEventListener('click', function (e) {
      var b = e.target.closest('.yr');
      if (!b) return;
      var y = parseInt(b.dataset.year, 10);
      if (y === state.year) return;
      state.year = y;
      loadYear(y);
      state.q = '';
      elSearch.value = '';
      draw();
    });
  }

  elTabs.addEventListener('click', function (e) {
    var t = e.target.closest('.tab');
    if (!t) return;
    if (t.dataset.view === 'overview') {
      state.view = 'overview';
      state.month = null;
    } else {
      state.view = 'month';
      state.month = parseInt(t.dataset.month, 10);
    }
    state.q = '';
    elSearch.value = '';
    draw();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  elView.addEventListener('click', function (e) {
    var yr = e.target.closest('tr.year-row');
    if (yr) {
      if (e.target.closest('a')) return;
      var y = parseInt(yr.dataset.year, 10);
      if (y !== state.year) {
        state.year = y;
        loadYear(y);
        state.q = '';
        elSearch.value = '';
        state.view = 'overview';
        state.month = null;
        draw();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
      return;
    }

    var cell = e.target.closest('td.cell');
    if (cell) {
      state.view = 'month';
      state.month = parseInt(cell.dataset.goto, 10);
      state.q = '';
      elSearch.value = '';
      draw();
      var target = document.getElementById('reg-' + cell.dataset.reg);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }

    var more = e.target.closest('.more');
    if (more) {
      var box = more.previousElementSibling;
      box.classList.toggle('open');
      more.textContent = box.classList.contains('open') ? 'mniej' : 'więcej';
      return;
    }

    var csvBtn = e.target.closest('[data-csv]');
    if (csvBtn) {
      var reg = D.registers.filter(function (r) { return r.id === csvBtn.dataset.csv; })[0];
      var rows = state.view === 'month' ? rowsFor(reg.id, state.month) : reg.rows;
      downloadCsv(reg, rows);
    }
  });

  var tmr;
  elSearch.addEventListener('input', function (e) {
    clearTimeout(tmr);
    var v = e.target.value;
    tmr = setTimeout(function () { state.q = v; draw(); }, 160);
  });

  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      var cur = state.view === 'month' ? state.month : 0;
      var next = cur + (e.key === 'ArrowRight' ? 1 : -1);
      if (next < 1) next = 12;
      if (next > 12) next = 1;
      state.view = 'month';
      state.month = next;
      draw();
    }
  });

  /* ----------------------------------------------------------------- csv -- */

  function downloadCsv(reg, rows) {
    var head = ['Lp.', 'Data'].concat(reg.cols.map(function (c) { return c.l; }));
    var lines = [head.map(csvCell).join(';')];

    rows.forEach(function (row, i) {
      var line = [i + 1, row.d ? fmtDate(row.d) : ''];
      reg.cols.forEach(function (c) { line.push(row.c[c.k] || ''); });
      lines.push(line.map(csvCell).join(';'));
    });

    var blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'wykaz-' + reg.id + '-' + D.year +
      (state.view === 'month' ? '-' + String(state.month).padStart(2, '0') : '') + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  function csvCell(v) {
    var s = String(v == null ? '' : v).replace(/\s+/g, ' ').trim();
    return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /* ---------------------------------------------------------------- boot -- */

  if (/[?&]embed=1/.test(location.search)) document.body.classList.add('embed');

  // auto-wysokość dla osadzenia w <iframe> na WordPressie
  if (window.parent !== window) {
    var postHeight = function () {
      window.parent.postMessage({
        type: 'wykazy-ursus-height',
        height: Math.ceil(document.documentElement.getBoundingClientRect().height)
      }, '*');
    };
    window.addEventListener('load', postHeight);
    if (window.ResizeObserver) new ResizeObserver(postHeight).observe(document.body);
    setTimeout(postHeight, 300);
    setTimeout(postHeight, 1200);
  }

  // start: ?y=2025 -> rocznik, ?m=10 -> październik, ?view=overview -> przegląd,
  // domyślnie najnowszy miesiąc z danymi w domyślnym roczniku
  var params = new URLSearchParams(location.search);
  var py = parseInt(params.get('y'), 10);
  if (py && BUNDLE.data[String(py)]) state.year = py;

  loadYear(state.year);

  var pm = params.get('m');
  var pq = params.get('q');

  if (pq) {
    state.q = pq;
    elSearch.value = pq;
  }

  if (params.get('view') === 'overview') {
    state.view = 'overview';
  } else if (pm !== null && /^\d{1,2}$/.test(pm)) {
    state.view = 'month';
    state.month = parseInt(pm, 10);
  } else {
    for (var m = 12; m >= 1; m--) {
      if (monthTotal(m) > 0) { state.view = 'month'; state.month = m; break; }
    }
  }

  draw();
})();
