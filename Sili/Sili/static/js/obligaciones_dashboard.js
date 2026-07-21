document.addEventListener('DOMContentLoaded', function () {
  var raw = document.getElementById('dashboard-data');
  if (!raw || typeof Chart === 'undefined') { return; }
  var chartData = JSON.parse(raw.textContent);

  function toChart(canvasId, rows, labelKey) {
    var el = document.getElementById(canvasId);
    if (!el || !rows || !rows.length) { return; }
    new Chart(el, {
      type: 'doughnut',
      data: {
        labels: rows.map(function (r) { return r[labelKey]; }),
        datasets: [{ data: rows.map(function (r) { return r.total; }) }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }

  toChart('chartEstado', chartData.por_estado, 'estado');
  toChart('chartTipo', chartData.por_tipo, 'etiqueta');
  toChart('chartFrecuencia', chartData.por_frecuencia, 'etiqueta');

  // "Por empresa (por estado)": barras agrupadas Empresa x Estado, replica
  // del bar chart grande del PBIX de referencia (Estado_Corto por Empresa).
  var COLOR_ESTADO = {
    'Atrasado': '#dc3545',
    'Cumplido': '#198754',
    'Cumplido fuera de plazo': '#ffc107',
    'Activa': '#6c757d'
  };
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
            backgroundColor: COLOR_ESTADO[ds.label] || '#0d6efd'
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
  if (elGauge && typeof chartData.pct_a_tiempo === 'number') {
    var pctATiempo = chartData.pct_a_tiempo;
    var colorGauge = pctATiempo >= 70 ? '#198754' : pctATiempo >= 40 ? '#ffc107' : '#dc3545';
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
        plugins: { legend: { display: false }, tooltip: { enabled: false } }
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
