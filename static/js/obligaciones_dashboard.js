document.addEventListener('DOMContentLoaded', function () {
  var raw = document.getElementById('dashboard-data');
  if (!raw || typeof Chart === 'undefined') { return; }
  var chartData = JSON.parse(raw.textContent);

  // Mapa unico de color por estado (clave cruda como llega de la BD) --
  // usado tanto por el donut "Por estado" como por el bar chart "Por empresa",
  // para que un mismo estado se vea siempre del mismo color en todo el dashboard.
  var COLOR_ESTADO = {
    'atrasado': '#dc3545',
    'cumplido': '#198754',
    'cumplido_fuera_plazo': '#ffc107',
    'activa': '#6c757d'
  };
  var ESTADO_ETIQUETAS = {
    'atrasado': 'Atrasado',
    'cumplido': 'Cumplido',
    'cumplido_fuera_plazo': 'Cumplido fuera de plazo',
    'activa': 'Activa'
  };

  function toChart(canvasId, rows, labelKey, colorMap, labelMap) {
    var el = document.getElementById(canvasId);
    if (!el || !rows || !rows.length) { return; }
    new Chart(el, {
      type: 'doughnut',
      data: {
        labels: rows.map(function (r) { return (labelMap && labelMap[r[labelKey]]) || r[labelKey]; }),
        datasets: [{
          data: rows.map(function (r) { return r.total; }),
          backgroundColor: colorMap ? rows.map(function (r) { return colorMap[r[labelKey]] || '#0d6efd'; }) : undefined
        }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  toChart('chartEstado', chartData.por_estado, 'estado', COLOR_ESTADO, ESTADO_ETIQUETAS);
  toChart('chartTipo', chartData.por_tipo, 'etiqueta');
  toChart('chartFrecuencia', chartData.por_frecuencia, 'etiqueta');

  // "Por empresa (por estado)": barras agrupadas Empresa x Estado, replica
  // del bar chart grande del PBIX de referencia (Estado_Corto por Empresa).
  var elEmpresa = document.getElementById('chartEmpresa');
  var dataEmpresa = chartData.por_empresa_estado;
  if (elEmpresa && dataEmpresa && dataEmpresa.labels && dataEmpresa.labels.length) {
    new Chart(elEmpresa, {
      type: 'bar',
      data: {
        labels: dataEmpresa.labels,
        datasets: dataEmpresa.datasets.map(function (ds) {
          return {
            label: ds.label,
            data: ds.data,
            backgroundColor: COLOR_ESTADO[ds.estado] || '#0d6efd'
          };
        })
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: false },
          y: { stacked: false, beginAtZero: true, ticks: { precision: 0 } }
        }
      }
    });
  }

  // Gauge semicircular "GRADO DE AVANCE" (replica visual del Power BI de referencia)
  var elGauge = document.getElementById('chartCumplimiento');
  var elGaugeLabel = document.getElementById('chartCumplimientoLabel');
  if (elGauge && typeof chartData.pct_a_tiempo === 'number') {
    var pctATiempo = chartData.pct_a_tiempo;
    var colorGauge = pctATiempo >= 70 ? '#198754' : pctATiempo >= 40 ? '#ffc107' : '#dc3545';

    // Posiciona el label EXACTO donde Chart.js dibujo el arco -- nunca adivinar
    // un % de CSS: canvas y el div overlay comparten el mismo origen (0,0) dentro
    // de .chart-box (position:relative), asi que meta.y (linea plana del semicirculo,
    // en px de canvas) es directamente el "top" correcto para el div.
    // Recibe el chart como parametro (nunca una var externa): onComplete puede
    // disparar SINCRONICAMENTE durante new Chart(...), antes de que la asignacion
    // a una variable externa termine -- referenciarla ahi rompe el render entero.
    function posicionarLabelGauge(chart) {
      if (!elGaugeLabel || !chart) return;
      var meta = chart.getDatasetMeta(0).data[0];
      if (!meta) return;
      var offset = (meta.innerRadius || 0) * 0.35; // nudge hacia arriba, dentro del hueco
      elGaugeLabel.style.top = Math.round(meta.y - offset) + 'px';
    }

    new Chart(elGauge, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [pctATiempo, 100 - pctATiempo],
          backgroundColor: [colorGauge, '#e9ecef'],
          borderWidth: 0
        }]
      },
      options: {
        rotation: -90,
        circumference: 180,
        cutout: '75%',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { onComplete: function (ctx) { posicionarLabelGauge(ctx.chart); } },
        onResize: function (chart) { posicionarLabelGauge(chart); }
      }
    });
  }
});

// Feedback visual de carga al enviar el formulario de filtros (recarga nativa del navegador).
// ponytail: mismo patron que lockButton() en templates/reclamos_lista copy.html
document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('#panelFiltrosDashboard form');
  if (!form) return;

  form.addEventListener('submit', function () {
    var btn = form.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Filtrando...';
  });
});
