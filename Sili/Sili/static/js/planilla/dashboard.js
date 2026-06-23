(() => {
  'use strict';

  const configEl = document.getElementById('dashboardConfig');
  if (!configEl) return;

  const ym = configEl.dataset.ym || '';
  let CHART = {};

  try {
    CHART = JSON.parse(configEl.dataset.chart || '{}');
  } catch (error) {
    console.error('No se pudo leer data-chart del dashboard.', error);
    CHART = {};
  }

  const rgba = (hex, alpha) => {
    const fallback = `rgba(37,99,235,${alpha})`;
    if (!/^#[0-9a-f]{6}$/i.test(hex || '')) return fallback;

    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  };

  const download = (name, content, mime = 'text/plain') => {
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([content], { type: mime }));
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 500);
  };

  const toCSV = (labels, sets) => {
    const head = ['label', ...labels].join(',');
    const rows = sets.map(set => [set.label, ...set.data].join(',')).join('\n');
    return `${head}\n${rows}`;
  };

  const tableToCSV = table => {
    if (!table) return '';

    const rows = [];
    const headers = [...table.querySelectorAll('thead th')].map(th => (th.innerText || '').replace(/,/g, ' ').trim());
    if (headers.length) rows.push(headers.join(','));

    table.querySelectorAll('tbody tr').forEach(row => {
      const cells = [...row.querySelectorAll('td')].map(td => (td.innerText || '').replace(/,/g, ' ').trim());
      if (cells.length) rows.push(cells.join(','));
    });

    return rows.join('\n');
  };

  const cssVar = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  let gDep = null;
  let gRep = null;
  let gTrend = null;


  function setChartTheme() {
    if (!window.Chart) return;

    const ink = cssVar('--ink') || '#111827';
    const muted = cssVar('--muted') || '#6B7280';
    const line = cssVar('--line') || '#E5E7EB';

    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;

    [gDep, gRep, gTrend].forEach(chart => {
      if (!chart?.options?.scales) return;
      chart.options.scales.x.ticks.color = muted;
      chart.options.scales.y.ticks.color = muted;
      chart.options.scales.x.grid.color = line;
      chart.options.scales.y.grid.color = line;
      chart.update();
    });
  }

  function initTheme() {
    const key = 'ui_theme';
    const root = document.documentElement;

    const apply = mode => {
      root.classList.toggle('theme-dark', mode === 'dark');
      localStorage.setItem(key, mode);
      setTimeout(setChartTheme, 0);
    };

    apply(localStorage.getItem(key) || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

    document.getElementById('themeToggle')?.addEventListener('click', () => {
      apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
    });
  }

  const mmKey = 'ui.dashboard.state';

  function restoreState() {
    try {
      const state = JSON.parse(localStorage.getItem(mmKey) || '{}');
      if (state.month) document.getElementById('month').value = state.month;
      if (state.freq) document.getElementById('freqFilter').value = state.freq;
      if (state.area !== undefined) document.getElementById('areaFilter') && (document.getElementById('areaFilter').value = state.area);
      if (state.depto !== undefined) document.getElementById('deptoFilter').value = state.depto;
      if (state.resp !== undefined) document.getElementById('respFilter').value = state.resp;
    } catch (_) {}
  }

  function saveState() {
    const state = {
      month: document.getElementById('month')?.value || '',
      freq: document.getElementById('freqFilter')?.value || '',
      area: document.getElementById('areaFilter')?.value || '',
      depto: document.getElementById('deptoFilter')?.value || '',
      resp: document.getElementById('respFilter')?.value || ''
    };
    localStorage.setItem(mmKey, JSON.stringify(state));
  }

  function setParam(url, key, value) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }

  function initFilters() {
    document.getElementById('freqFilter')?.addEventListener('change', event => {
      const url = new URL(window.location.href);
      setParam(url, 'freq', event.target.value);
      saveState();
      window.location.href = url.toString();
    });

    document.getElementById('month')?.addEventListener('change', event => {
      const [year, month] = event.target.value.split('-');
      const url = new URL(window.location.href);
      setParam(url, 'year', year);
      setParam(url, 'month', parseInt(month, 10));
      saveState();
      window.location.href = url.toString();
    });

    document.getElementById('areaFilter')?.addEventListener('change', event => {
      const url = new URL(window.location.href);
      setParam(url, 'area', event.target.value);
      url.searchParams.delete('depto');
      url.searchParams.delete('resp');
      saveState();
      window.location.href = url.toString();
    });

    document.getElementById('deptoFilter')?.addEventListener('change', event => {
      const url = new URL(window.location.href);
      setParam(url, 'depto', event.target.value);
      saveState();
      window.location.href = url.toString();
    });

    document.getElementById('respFilter')?.addEventListener('change', event => {
      const url = new URL(window.location.href);
      setParam(url, 'resp', event.target.value);
      saveState();
      window.location.href = url.toString();
    });
  }

  function buildBaseLineOptions() {
    return {
      type: 'line',
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top' },
          tooltip: { intersect: false },
          zoom: {
            pan: { enabled: true, mode: 'xy' },
            zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' }
          }
        },
        elements: {
          line: { tension: .35, borderWidth: 2 },
          point: { radius: 0, hitRadius: 6, hoverRadius: 4 }
        },
        scales: {
          y: { beginAtZero: true, grid: { drawBorder: false } },
          x: { grid: { display: false } }
        }
      }
    };
  }

  function getTodayIndex(labels) {
    const now = new Date();
    const currentYm = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    if (ym !== currentYm) return null;

    const idx = labels.indexOf(now.toISOString().slice(0, 10));
    return idx >= 0 ? idx : null;
  }

  function initCharts() {
    if (!window.Chart) {
      console.error('Chart.js no está cargado.');
      return;
    }

    const todayLinePlugin = {
      id: 'todayLine',
      afterDraw(chart, args, opts) {
        if (opts?.index === null || opts?.index === undefined) return;
        const { ctx, chartArea, scales } = chart;
        const x = scales.x.getPixelForValue(opts.index);
        ctx.save();
        ctx.strokeStyle = '#1d4ed8';
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();
        ctx.restore();
      }
    };
    Chart.register(todayLinePlugin);

    const baseLineOpts = buildBaseLineOptions();
    document.querySelectorAll('.chart-box').forEach(box => box.classList.add('loading'));

    const cDep = document.getElementById('chartDep');
    if (cDep) {
      gDep = new Chart(cDep, {
        ...baseLineOpts,
        data: {
          labels: CHART.deps?.labels || [],
          datasets: [
            { label: 'Realizadas', data: CHART.deps?.realizadas || [], borderColor: '#3b82f6', backgroundColor: rgba('#3b82f6', .18), fill: true },
            { label: 'Planeadas', data: CHART.deps?.planeadas || [], borderColor: '#ec4899', backgroundColor: rgba('#ec4899', .18), fill: true }
          ]
        }
      });
    }

    const cRep = document.getElementById('chartRep');
    if (cRep) {
      gRep = new Chart(cRep, {
        ...baseLineOpts,
        data: {
          labels: CHART.reps?.labels || [],
          datasets: [
            { label: 'Realizadas', data: CHART.reps?.realizadas || [], borderColor: '#22c55e', backgroundColor: rgba('#22c55e', .18), fill: true },
            { label: 'Planeadas', data: CHART.reps?.planeadas || [], borderColor: '#f59e0b', backgroundColor: rgba('#f59e0b', .18), fill: true }
          ]
        }
      });
    }

    const cTrend = document.getElementById('chartTrend');
    if (cTrend) {
      const labels = CHART.trend?.labels || [];
      gTrend = new Chart(cTrend, {
        ...baseLineOpts,
        data: {
          labels,
          datasets: [
            { label: 'Checks por día', data: CHART.trend?.realizadas || [], borderColor: '#0ea5e9', backgroundColor: rgba('#0ea5e9', .16), fill: true }
          ]
        },
        options: {
          ...baseLineOpts.options,
          plugins: {
            ...baseLineOpts.options.plugins,
            todayLine: { index: getTodayIndex(labels) }
          }
        }
      });
    }

    [cDep, cRep, cTrend].forEach(canvas => canvas?.closest('.chart-box')?.classList.remove('loading'));

    initChartToolbars();
    initSparklines();
    initPointDetails();
    setChartTheme();
    ensureEmptyStates();
    initAnimations();
  }

  function initChartToolbars() {
    const charts = { chartDep: gDep, chartRep: gRep, chartTrend: gTrend };

    document.querySelectorAll('.chart-toolbar').forEach(toolbar => {
      const id = toolbar.dataset.for;
      const chart = charts[id];
      const canvas = document.getElementById(id);
      if (!chart || !canvas) return;

      toolbar.querySelector('.ct-full')?.addEventListener('click', () => canvas.closest('.section')?.requestFullscreen?.());

      toolbar.querySelector('.ct-zoom')?.addEventListener('click', () => {
        const zoomConfig = chart.options.plugins?.zoom?.zoom?.wheel;
        if (!zoomConfig) return;

        zoomConfig.enabled = !zoomConfig.enabled;
        chart.update();
        toolbar.querySelector('.ct-zoom')?.classList.toggle('active', zoomConfig.enabled);
      });

      toolbar.querySelector('.ct-reset')?.addEventListener('click', () => chart.resetZoom?.());
      toolbar.querySelector('.ct-png')?.addEventListener('click', () => download(`${id}_${ym}.png`, canvas.toDataURL('image/png'), 'image/png'));
      toolbar.querySelector('.ct-csv')?.addEventListener('click', () => {
        const csv = toCSV(chart.data.labels, chart.data.datasets.map(dataset => ({ label: dataset.label, data: dataset.data })));
        download(`${id}_${ym}.csv`, csv, 'text/csv');
      });

      const ma7Btn = toolbar.querySelector('.ct-ma7');
      if (ma7Btn && chart === gTrend) {
        let enabled = false;
        let dsIndex = null;

        ma7Btn.addEventListener('click', () => {
          if (!enabled) {
            const arr = gTrend.data.datasets[0].data.map(Number);
            const ma = arr.map((_, idx, src) => {
              if (idx < 6) return null;
              const avg = src.slice(idx - 6, idx + 1).reduce((sum, val) => sum + (+val || 0), 0) / 7;
              return Math.round(avg * 100) / 100;
            });
            gTrend.data.datasets.push({ label: 'MA7', data: ma, borderColor: '#64748b', borderDash: [6, 4], pointRadius: 0, fill: false });
            dsIndex = gTrend.data.datasets.length - 1;
            ma7Btn.classList.add('active');
          } else if (dsIndex !== null) {
            gTrend.data.datasets.splice(dsIndex, 1);
            ma7Btn.classList.remove('active');
          }

          enabled = !enabled;
          gTrend.update();
        });
      }
    });

    document.getElementById('btnExportAll')?.addEventListener('click', () => {
      ['chartDep', 'chartRep', 'chartTrend'].forEach(id => {
        const canvas = document.getElementById(id);
        if (canvas) download(`${id}_${ym}.png`, canvas.toDataURL('image/png'), 'image/png');
      });
    });
  }

  function initSparklines() {
    const spark = (id, data, color) => {
      const canvas = document.getElementById(id);
      if (!canvas) return;

      new Chart(canvas, {
        type: 'line',
        data: {
          labels: data.map((_, idx) => idx + 1),
          datasets: [{ data, borderColor: color, backgroundColor: rgba(color, .15), tension: .35, pointRadius: 0, borderWidth: 1.2, fill: true }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false } } }
      });
    };

    const arr = CHART.trend?.realizadas || [];
    const last = arr[arr.length - 1] || 0;
    const prev = arr[arr.length - 2] || 0;
    const deltaPct = prev ? ((last - prev) / prev) * 100 : (last ? 100 : 0);
    const tag = document.getElementById('kpiCumplDelta');

    if (tag) {
      if (deltaPct > 0) {
        tag.classList.add('up');
        tag.textContent = `+${deltaPct.toFixed(1)}%`;
      } else if (deltaPct < 0) {
        tag.classList.add('down');
        tag.textContent = `${deltaPct.toFixed(1)}%`;
      } else {
        tag.textContent = '—';
      }
    }

    spark('sparkCumpl', arr, '#3b82f6');
    spark('sparkPunt', arr.map(value => value * 0.6), '#22c55e');
    spark('sparkArch', arr.map(value => value * 0.4), '#f59e0b');
    spark('sparkPend', arr.map(value => Math.max(0, 5 - value)), '#ef4444');
  }

  function initPointDetails() {
    const openDetailModal = (label, pairs) => {
      const modal = document.getElementById('detailModal');
      if (!modal) return;

      modal.querySelector('#detailLabel').textContent = label || '—';
      const list = modal.querySelector('#detailList');
      list.innerHTML = '';

      pairs.forEach(pair => {
        const item = document.createElement('li');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        item.innerHTML = `<span>${pair.label}</span><span class="fw-semibold">${pair.value}</span>`;
        list.appendChild(item);
      });

      bootstrap.Modal.getOrCreateInstance(modal).show();
    };

    [gDep, gRep, gTrend].forEach(chart => {
      if (!chart?.canvas) return;
      chart.canvas.addEventListener('click', event => {
        const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);
        if (!points.length) return;

        const index = points[0].index;
        const label = chart.data.labels[index];
        const pairs = chart.data.datasets.map(dataset => ({ label: dataset.label, value: dataset.data[index] ?? 0 }));
        openDetailModal(label, pairs);
      });
    });
  }

  function ensureEmptyStates() {
    [
      [document.getElementById('chartDep'), gDep],
      [document.getElementById('chartRep'), gRep],
      [document.getElementById('chartTrend'), gTrend]
    ].forEach(([canvas, chart]) => {
      if (!canvas || !chart) return;
      const total = chart.data.datasets.reduce((outer, dataset) => outer + dataset.data.reduce((inner, value) => inner + (+value || 0), 0), 0);
      if (total === 0) {
        const box = canvas.closest('.chart-box');
        if (box) box.innerHTML = '<div class="empty-state">Sin datos para este período</div>';
      }
    });
  }

  function animateTodayLine(chart, stepMs = 300, loop = true) {
    const opts = chart?.options?.plugins?.todayLine;
    if (!opts || opts.index === null || opts.index === undefined || opts.index <= 0) return;

    const target = opts.index;
    let current = 0;
    opts.index = 0;
    chart.update('none');

    const timer = setInterval(() => {
      if (!chart.canvas?.isConnected) {
        clearInterval(timer);
        return;
      }

      current += 1;

      if (current >= target) {
        opts.index = target;
        chart.update('none');
        if (loop) {
          current = 0;
          opts.index = 0;
          chart.update('none');
          return;
        }
        clearInterval(timer);
        return;
      }

      opts.index = current;
      chart.update('none');
    }, stepMs);
  }

  function initAnimations() {
    animateTodayLine(gTrend, 300, true);
  }

  function initTableExportAndSort() {
    document.getElementById('btnExpSummaryCsv')?.addEventListener('click', () => {
      download(`resumen_usuario_depto_${ym}.csv`, tableToCSV(document.getElementById('summary-table')), 'text/csv');
    });

    document.getElementById('btnExpQ4Csv')?.addEventListener('click', () => {
      download(`proyeccion_resto_anio_${ym}.csv`, tableToCSV(document.getElementById('tblQ4')), 'text/csv');
    });

    ['summary-table', 'tblQ4'].forEach(initSortableTable);
  }

  function initSortableTable(tableId) {
    const table = document.getElementById(tableId);
    if (!table?.tHead?.rows?.length || !table.tBodies.length) return;

    const tbody = table.tBodies[0];
    const headers = [...table.tHead.rows[0].cells];
    let lastIndex = -1;
    let lastDir = 1;

    headers.forEach(header => {
      if (!header.querySelector('.sort-ind')) {
        const span = document.createElement('span');
        span.className = 'sort-ind';
        header.appendChild(span);
      }
    });

    const parseCell = (cell, type) => {
      const text = (cell?.textContent || '').trim();
      if (type === 'int') {
        const num = parseFloat(text.replace(/[^\d.-]/g, ''));
        return Number.isNaN(num) ? -Infinity : num;
      }
      if (type === 'pct') {
        const num = parseFloat(text.replace('%', ''));
        return Number.isNaN(num) ? -Infinity : num;
      }
      return text.toLowerCase();
    };

    headers.forEach((header, index) => {
      header.addEventListener('click', () => {
        const type = header.getAttribute('data-type') || 'text';
        const dir = index === lastIndex ? -lastDir : 1;
        lastIndex = index;
        lastDir = dir;

        headers.forEach(item => item.classList.remove('sorted-asc', 'sorted-desc'));
        header.classList.add(dir === 1 ? 'sorted-asc' : 'sorted-desc');

        const rows = [...tbody.rows];
        rows.sort((a, b) => {
          const av = parseCell(a.cells[index], type);
          const bv = parseCell(b.cells[index], type);
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        });

        const fragment = document.createDocumentFragment();
        rows.forEach(row => fragment.appendChild(row));
        tbody.appendChild(fragment);
      });
    });
  }

  function initFeriados() {
    const btnFeriados = document.getElementById('btnFeriados');
    const modalEl = document.getElementById('feriadosModal');
    const fechaInput = document.getElementById('feriadoFecha');
    const nombreInput = document.getElementById('feriadoNombre');
    const paisInput = document.getElementById('feriadoPais');
    const listEl = document.getElementById('feriadosList');
    const btnAdd = document.getElementById('btnAddFeriado');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    if (!btnFeriados || !modalEl || !listEl || !btnAdd) return;

    const apiList = configEl.dataset.apiListFeriados || '';
    const apiAdd = configEl.dataset.apiAddFeriado || '';
    const apiDelBase = (configEl.dataset.apiDelFeriado || '').replace(/0$/, '');

    const getYearMonth = () => {
      const value = document.getElementById('month')?.value || '';
      const [year, month] = value.split('-');
      return { year: parseInt(year, 10), month: parseInt(month, 10) };
    };

    const renderList = items => {
      listEl.innerHTML = '';
      if (!items.length) {
        listEl.innerHTML = '<li class="list-group-item text-muted">Sin feriados registrados</li>';
        return;
      }

      items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'list-group-item d-flex justify-content-between align-items-center';
        li.innerHTML = `
          <div>
            <div class="fw-semibold">${item.fecha}</div>
            <small class="text-muted">${item.nombre || 'Sin nombre'} · ${item.pais || ''}</small>
          </div>
          <button type="button" class="btn btn-sm btn-outline-danger" title="Eliminar">&times;</button>
        `;

        li.querySelector('button')?.addEventListener('click', async () => {
          if (!confirm('¿Eliminar este feriado?')) return;

          try {
            const response = await fetch(apiDelBase + item.id, {
              method: 'DELETE',
              headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (!response.ok) {
              alert(`Error eliminando feriado (HTTP ${response.status})`);
              return;
            }
            await loadFeriados();
          } catch (error) {
            console.error(error);
            alert('Error de red eliminando feriado');
          }
        });

        listEl.appendChild(li);
      });
    };

    async function loadFeriados() {
      const { year, month } = getYearMonth();
      if (!year || !month || !apiList) return;

      listEl.innerHTML = '<li class="list-group-item text-muted">Cargando…</li>';

      try {
        const url = `${apiList}?year=${encodeURIComponent(year)}&month=${encodeURIComponent(month)}`;
        const response = await fetch(url);
        if (!response.ok) {
          listEl.innerHTML = '<li class="list-group-item text-danger">Error cargando feriados</li>';
          return;
        }
        renderList(await response.json() || []);
      } catch (error) {
        console.error(error);
        listEl.innerHTML = '<li class="list-group-item text-danger">Error de red</li>';
      }
    }

    btnFeriados.addEventListener('click', () => {
      bootstrap.Modal.getOrCreateInstance(modalEl).show();
      loadFeriados();
    });

    btnAdd.addEventListener('click', async event => {
      event.preventDefault();

      const fecha = (fechaInput.value || '').trim();
      const nombre = (nombreInput.value || '').trim();
      const pais = (paisInput.value || 'EC').trim() || 'EC';

      if (!fecha) {
        alert('Selecciona una fecha');
        return;
      }

      try {
        const response = await fetch(apiAdd, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ fecha, nombre, pais })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.ok === false) {
          alert(`Error guardando feriado: ${data.error || `HTTP ${response.status}`}`);
          return;
        }
        nombreInput.value = '';
        await loadFeriados();
      } catch (error) {
        console.error(error);
        alert('Error de red guardando feriado');
      }
    });
  }

  function initShortcuts() {
    document.addEventListener('keydown', event => {
      if (event.altKey && event.key.toLowerCase() === 'e') {
        event.preventDefault();
        document.getElementById('btnExportAll')?.click();
      }
      if (event.altKey && event.key === '0') {
        [gDep, gRep, gTrend].forEach(chart => chart?.resetZoom?.());
      }
    });
  }

  function initOkrBars() {
    document.querySelectorAll('.okr-bar-fill[data-pct]').forEach(el => {
      const pct = Math.min(parseFloat(el.dataset.pct) || 0, 100);
      el.style.width = pct + '%';
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    restoreState();
    initFilters();
    initCharts();
    initTableExportAndSort();
    initFeriados();
    initShortcuts();
    initOkrBars();
  });
})();
