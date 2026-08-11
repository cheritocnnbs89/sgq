document.addEventListener('DOMContentLoaded', function () {
  var raw = document.getElementById('dashboard-data');
  if (!raw || typeof Chart === 'undefined') { return; }

  // Mapa unico de color por estatus (clave cruda como llega de la BD) --
  // usado tanto por el donut "Por estatus" como por el bar chart apilado,
  // para que un mismo estatus se vea siempre del mismo color en todo el dashboard.
  // 2026-07-27: agregado 'por_presentar' (mismo amarillo que cumplido_fuera_plazo,
  // pedido de Matias) + 'cumplida'/'atrasada' -- claves fundidas que devuelve
  // SQL_DASHBOARD_POR_ESTATUS_TOTAL_SELECT para el chart "Por estatus (empresas)".
  var COLOR_ESTATUS = {
    'atrasado': '#dc3545',
    'cumplido': '#198754',
    'cumplido_fuera_plazo': '#ffc107',
    'por_presentar': '#ffc107',
    'activa': '#6c757d',
    'cumplida': '#198754',
    'atrasada': '#dc3545'
  };
  var ESTATUS_ETIQUETAS = {
    'atrasado': 'Atrasado',
    'cumplido': 'Cumplido',
    'cumplido_fuera_plazo': 'Cumplido fuera de plazo',
    'por_presentar': 'Por presentar a tiempo',
    'activa': 'Activa',
    'cumplida': 'Cumplida',
    'atrasada': 'Atrasada'
  };

  // Registro de instancias Chart.js vivas -> se destruyen antes de recrear en
  // cada refresco (evita fugas y "canvas already in use").
  var charts = {};
  var elGaugeLabel = document.getElementById('chartCumplimientoLabel');

  function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  }

  function doughnut(canvasId, rows, labelKey, colorMap, labelMap, animate) {
    var el = document.getElementById(canvasId);
    destroyChart(canvasId);
    if (!el || !rows || !rows.length) { return; }
    charts[canvasId] = new Chart(el, {
      type: 'doughnut',
      data: {
        labels: rows.map(function (r) { return (labelMap && labelMap[r[labelKey]]) || r[labelKey]; }),
        datasets: [{
          data: rows.map(function (r) { return r.total; }),
          backgroundColor: colorMap ? rows.map(function (r) { return colorMap[r[labelKey]] || '#0d6efd'; }) : undefined
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, animation: animate }
    });
  }

  // 2026-07-27: barra APILADA por empresa (reemplaza el bar combinado del
  // 2026-07-21, pedido de Matias). Filas vienen como {empresa, estatus, total}
  // con estatus ya fundido en 3 categorias fijas (SQL_DASHBOARD_POR_ESTATUS_TOTAL_SELECT):
  // cumplida (verde) / atrasada (rojo) / por_presentar (amarillo). Un dataset
  // por categoria -> Chart.js las apila con scales.x.stacked/y.stacked.
  var SEGMENTOS_ESTATUS_EMPRESA = ['cumplida', 'atrasada', 'por_presentar'];

  function barEstatusTotal(rows, animate) {
    var el = document.getElementById('chartEmpresa');
    destroyChart('chartEmpresa');
    if (!el || !rows || !rows.length) { return; }

    var empresas = [];
    rows.forEach(function (r) {
      if (empresas.indexOf(r.empresa) === -1) { empresas.push(r.empresa); }
    });

    var datasets = SEGMENTOS_ESTATUS_EMPRESA.map(function (estatus) {
      return {
        label: ESTATUS_ETIQUETAS[estatus],
        backgroundColor: COLOR_ESTATUS[estatus],
        data: empresas.map(function (empresa) {
          var fila = rows.find(function (r) { return r.empresa === empresa && r.estatus === estatus; });
          return fila ? fila.total : 0;
        })
      };
    });

    charts['chartEmpresa'] = new Chart(el, {
      type: 'bar',
      data: { labels: empresas, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: animate,
        plugins: { legend: { display: true, position: 'bottom' } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }
        }
      }
    });
  }

  // Posiciona el label EXACTO donde Chart.js dibujo el arco del gauge -- nunca
  // adivinar un % de CSS: canvas y el div overlay comparten origen (0,0) dentro
  // de .chart-box (position:relative), asi que meta.y es directamente el "top".
  // Recibe el chart como parametro (nunca una var externa): onComplete puede
  // disparar SINCRONICAMENTE durante new Chart(...).
  function posicionarLabelGauge(chart) {
    if (!elGaugeLabel || !chart) return;
    var meta = chart.getDatasetMeta(0).data[0];
    if (!meta) return;
    var offset = (meta.innerRadius || 0) * 0.35;
    elGaugeLabel.style.top = Math.round(meta.y - offset) + 'px';
  }

  function gauge(pctATiempo, animate) {
    var el = document.getElementById('chartCumplimiento');
    destroyChart('chartCumplimiento');
    if (!el || typeof pctATiempo !== 'number') { return; }
    var colorGauge = pctATiempo >= 70 ? '#198754' : pctATiempo >= 40 ? '#ffc107' : '#dc3545';
    charts['chartCumplimiento'] = new Chart(el, {
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
        animation: animate ? { onComplete: function (ctx) { posicionarLabelGauge(ctx.chart); } } : false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        onResize: function (chart) { posicionarLabelGauge(chart); }
      }
    });
    if (!animate) { posicionarLabelGauge(charts['chartCumplimiento']); }
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el && value !== undefined && value !== null) { el.textContent = value; }
  }

  function actualizarKpis(k, pct) {
    if (k) {
      setText('kpiTotal', k.total_obligaciones);
      setText('kpiActivas', k.total_activas);
      setText('kpiAtrasadas', k.total_atrasadas);
      setText('kpiProximas', k.proximas_vencer);
    }
    if (typeof pct === 'number') { setText('kpiPct', pct); }
  }

  function render(chartData, animate) {
    actualizarKpis(chartData.kpis, chartData.pct_cumplidas);
    // 2026-08-05: doughnut chartEstado ("Por estatus") eliminado -- pedido Matias en reunion.
    doughnut('chartTipo', chartData.por_tipo, 'etiqueta', null, null, animate);
    barEstatusTotal(chartData.por_estatus_total, animate);
    if (typeof chartData.pct_cumplidas === 'number') { gauge(chartData.pct_cumplidas, animate); }
  }

  // Render inicial (con animacion, como siempre).
  render(JSON.parse(raw.textContent), true);

  // ----------------------------------------------------------------
  // Auto-refresco cada 30s (polling AJAX). Lee los filtros ACTUALES del
  // formulario en cada tick y pide los datos frescos al endpoint. Sin
  // animacion en los refrescos para minimizar el parpadeo.
  // ----------------------------------------------------------------
  var DATA_URL = raw.getAttribute('data-endpoint');
  var form = document.querySelector('#panelFiltrosDashboard form');

  function filtrosActuales() {
    if (!form) { return ''; }
    var params = new URLSearchParams();
    // 2026-07-28: filtro usuario_id (nuevo <select name="usuario_id"> en el
    // template) ya queda cubierto por este loop generico -- no requiere linea
    // aparte, itera TODO select/input del form por name/value.
    form.querySelectorAll('select, input').forEach(function (campo) {
      if (campo.name && campo.value) { params.append(campo.name, campo.value); }
    });
    var qs = params.toString();
    return qs ? ('?' + qs) : '';
  }

  function refrescar() {
    if (!DATA_URL) { return; }
    fetch(DATA_URL + filtrosActuales(), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    })
      .then(function (resp) {
        if (!resp.ok) { throw new Error('HTTP ' + resp.status); }
        return resp.json();
      })
      .then(function (data) { render(data, false); })
      .catch(function (err) {
        // No romper la pantalla ni alertar cada 30s: loguear y reintentar en el
        // proximo tick (sesion expirada, red caida, etc.).
        console.warn('Dashboard obligaciones: fallo el auto-refresco', err);
      });
  }

  var intervalo = setInterval(refrescar, 30000);
  // Detener el polling al salir de la pantalla (evita fetches en background).
  window.addEventListener('pagehide', function () { clearInterval(intervalo); });
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

// 2026-08-11: wireFiltroTipoEntidad ahora vive en obligaciones_filtro_tipo_entidad.js (compartido)
document.addEventListener('DOMContentLoaded', function () {
  wireFiltroTipoEntidad(
    document.getElementById('frmFiltrosDashboard'),
    document.getElementById('filtroTipoId'),
    document.getElementById('filtroEntidadId'),
    '-- Entidad --'
  );
});
