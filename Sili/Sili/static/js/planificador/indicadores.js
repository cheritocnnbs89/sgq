(function () {
  'use strict';

  var dataEl = document.getElementById('indicadoresData');
  if (!dataEl || typeof Chart === 'undefined') return;

  var data = {};
  try {
    data = JSON.parse(dataEl.dataset.chart || '{}');
  } catch (error) {
    console.error('No se pudo leer data-chart de indicadores.', error);
    data = {};
  }

  var PALETTE = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#64748b', '#db2777'];
  var COLOR_VOUCHERS = '#2563eb';
  var COLOR_COSTO    = '#16a34a';

  function colorFor(i) {
    return PALETTE[i % PALETTE.length];
  }

  function money(v) {
    return '$' + Number(v || 0).toLocaleString('es-EC', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;

  var estado = data.estado || { labels: [], values: [] };
  var elEstado = document.getElementById('chartEstado');
  if (elEstado) {
    new Chart(elEstado, {
      type: 'doughnut',
      data: {
        labels: estado.labels,
        datasets: [{
          data: estado.values,
          backgroundColor: estado.labels.map(function (_, i) { return colorFor(i); }),
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }

  var tendencia = data.tendencia || { labels: [], vouchers: [], costo: [] };
  var elTendencia = document.getElementById('chartTendencia');
  if (elTendencia) {
    new Chart(elTendencia, {
      data: {
        labels: tendencia.labels,
        datasets: [
          {
            type: 'bar',
            label: 'Vouchers',
            data: tendencia.vouchers,
            backgroundColor: COLOR_VOUCHERS,
            borderRadius: 6,
            maxBarThickness: 48,
            yAxisID: 'y',
          },
          {
            type: 'line',
            label: 'Costo ($)',
            data: tendencia.costo,
            borderColor: COLOR_COSTO,
            backgroundColor: COLOR_COSTO,
            pointRadius: 4,
            pointBackgroundColor: COLOR_COSTO,
            yAxisID: 'y1',
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.yAxisID === 'y1'
                  ? ctx.dataset.label + ': ' + money(ctx.parsed.y)
                  : ctx.dataset.label + ': ' + ctx.parsed.y;
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true, position: 'left',
            title: { display: true, text: 'Vouchers' },
            ticks: { precision: 0 },
          },
          y1: {
            beginAtZero: true, position: 'right',
            title: { display: true, text: 'Costo ($)' },
            grid: { drawOnChartArea: false },
          },
        },
      },
    });
  }

  function chartAgrupado(canvasId, agrupado) {
    var el = document.getElementById(canvasId);
    if (!el) return;
    var labels = agrupado.labels || [];

    new Chart(el, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Vouchers',
            data: agrupado.vouchers || [],
            backgroundColor: COLOR_VOUCHERS,
            borderRadius: 5,
            maxBarThickness: 28,
            xAxisID: 'xVouchers',
          },
          {
            label: 'Costo ($)',
            data: agrupado.costo || [],
            backgroundColor: COLOR_COSTO,
            borderRadius: 5,
            maxBarThickness: 28,
            xAxisID: 'xCosto',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { position: 'bottom' },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.xAxisID === 'xCosto'
                  ? ctx.dataset.label + ': ' + money(ctx.parsed.x)
                  : ctx.dataset.label + ': ' + ctx.parsed.x;
              },
            },
          },
        },
        scales: {
          xVouchers: {
            position: 'top', beginAtZero: true,
            title: { display: true, text: 'Vouchers' },
            ticks: { precision: 0 },
          },
          xCosto: {
            position: 'bottom', beginAtZero: true,
            title: { display: true, text: 'Costo ($)' },
            grid: { drawOnChartArea: false },
          },
          y: {
            grid: { display: false },
          },
        },
      },
    });
  }

  chartAgrupado('chartUsuarios', data.usuarios || {});
  chartAgrupado('chartDepartamentos', data.departamentos || {});
})();
