document.addEventListener('DOMContentLoaded', function () {
  var raw = document.getElementById('dashboard-data');
  if (!raw || typeof Chart === 'undefined') { return; }

  // Registro de instancias Chart.js vivas -> se destruyen antes de recrear en
  // cada refresco (evita fugas y "canvas already in use").
  var charts = {};

  function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  }

  // 2026-08-16: gauge (chartCumplimiento), barEstatusTotal (chartEmpresa),
  // doughnut chartTipo genérico y sus mapas COLOR_ESTATUS/ESTATUS_ETIQUETAS
  // eliminados -- rediseño pedido por Matías, dashboard principal queda solo
  // con el pastel "Cumplimiento — detalle" grande.

  // 2026-08-14: pastel de 4 secciones pedido en reunión. Etiquetas/colores fijos
  // (no vienen de la BD como los otros charts, son las 4 categorías del negocio).
  // click en sección -> Punto 5 (pendiente, modal con desglose Tipo/Entidad/Área).
  var PASTEL_ORDEN = ['cumplida_a_tiempo', 'cumplida_fuera_plazo', 'pendiente_en_plazo', 'pendiente_atrasada'];
  // 2026-08-16: etiquetas alineadas a los estatus reales que ya usa el sistema
  // (Consultas/Historial/KPI "Total Presentar a Tiempo") -- pedido Matías, evitar
  // nombres propios del pastel que no coinciden y confunden al usuario.
  var PASTEL_ETIQUETAS = {
    'cumplida_a_tiempo':    'Cumplido',
    'cumplida_fuera_plazo': 'Cumplido fuera de plazo',
    'pendiente_en_plazo':   'Por presentar a tiempo',
    'pendiente_atrasada':   'Atrasado'
  };
  var PASTEL_COLORES = {
    'cumplida_a_tiempo':    '#198754',
    'cumplida_fuera_plazo': '#ffc107',
    'pendiente_en_plazo':   '#0dcaf0',
    'pendiente_atrasada':   '#dc3545'
  };

  function pastel(p, animate) {
    var el = document.getElementById('chartPastel');
    destroyChart('chartPastel');
    if (!el || !p) { return; }
    charts['chartPastel'] = new Chart(el, {
      type: 'pie',
      data: {
        labels: PASTEL_ORDEN.map(function (k) { return PASTEL_ETIQUETAS[k]; }),
        datasets: [{
          data: PASTEL_ORDEN.map(function (k) { return p[k] || 0; }),
          backgroundColor: PASTEL_ORDEN.map(function (k) { return PASTEL_COLORES[k]; })
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: animate,
        plugins: { legend: { display: true, position: 'bottom' } },
        onClick: function (evt, elements) {
          if (!elements || !elements.length) { return; }
          abrirDesgloseSeccion(PASTEL_ORDEN[elements[0].index]);
        },
        onHover: function (evt, elements) {
          el.style.cursor = elements && elements.length ? 'pointer' : 'default';
        }
      }
    });
  }

  // 2026-08-14: Punto 5 -- click en seccion del pastel abre modal con 3 tablas
  // (Tipo/Entidad/Area), filtradas a esa seccion + filtros actuales del dashboard.
  var DESGLOSE_URL = raw.getAttribute('data-endpoint-desglose');
  var modalDesgloseEl = document.getElementById('modalDesglosePastel');
  var modalDesglose = (modalDesgloseEl && window.bootstrap) ? new bootstrap.Modal(modalDesgloseEl) : null;
  var URL_CONSULTAS = modalDesgloseEl ? modalDesgloseEl.getAttribute('data-url-consultas') : null;
  var URL_HISTORIAL = modalDesgloseEl ? modalDesgloseEl.getAttribute('data-url-historial') : null;
  // 2026-08-14: Punto 6 -- secciones "cumplida_*" son activa=0 (viven en Historial),
  // "pendiente_*" son activa=1 (viven en Consultas). Mismo mapeo que
  // SECCION_PASTEL_WHERE del backend, solo para decidir a DONDE navegar.
  var SECCION_ES_HISTORIAL = { 'cumplida_a_tiempo': true, 'cumplida_fuera_plazo': true };
  var seccionActual = null;

  function renderTablaDesglose(tbodyId, rows, campoFiltro) {
    var tbody = document.getElementById(tbodyId);
    if (!tbody) { return; }
    tbody.innerHTML = '';
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td class="text-muted small">Sin datos</td></tr>';
      return;
    }
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.style.cursor = 'pointer';
      tr.innerHTML = '<td>' + r.etiqueta + '</td><td class="text-end fw-bold">' + r.total + '</td>';
      tr.addEventListener('click', function () { irAListadoFiltrado(campoFiltro, r.id); });
      tbody.appendChild(tr);
    });
  }

  // 2026-08-16: doughnut Tipo/Area del modal -- click en porcion navega igual
  // que click en fila de tabla (mismo irAListadoFiltrado, mismo campoFiltro).
  function doughnutDesglose(canvasId, rows, campoFiltro) {
    var el = document.getElementById(canvasId);
    destroyChart(canvasId);
    if (!el || !rows || !rows.length) { return; }
    charts[canvasId] = new Chart(el, {
      type: 'doughnut',
      data: {
        labels: rows.map(function (r) { return r.etiqueta; }),
        datasets: [{ data: rows.map(function (r) { return r.total; }) }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'bottom' } },
        onClick: function (evt, elements) {
          if (!elements || !elements.length) { return; }
          irAListadoFiltrado(campoFiltro, rows[elements[0].index].id);
        },
        onHover: function (evt, elements) {
          el.style.cursor = elements && elements.length ? 'pointer' : 'default';
        }
      }
    });
  }

  function irAListadoFiltrado(campoFiltro, id) {
    if (!seccionActual) { return; }
    var esHistorial = !!SECCION_ES_HISTORIAL[seccionActual];
    var base = esHistorial ? URL_HISTORIAL : URL_CONSULTAS;
    if (!base) { return; }
    var params = new URLSearchParams();
    params.set(campoFiltro, id);
    params.set('seccion', seccionActual);
    window.location.href = base + '?' + params.toString();
  }

  function abrirDesgloseSeccion(seccion) {
    if (!DESGLOSE_URL || !modalDesglose) { return; }
    seccionActual = seccion;
    var titulo = document.getElementById('modalDesgloseTitulo');
    if (titulo) { titulo.textContent = 'Desglose — ' + (PASTEL_ETIQUETAS[seccion] || seccion); }
    var qs = filtrosActuales();
    var sep = qs ? '&' : '?';
    fetch(DESGLOSE_URL + qs + sep + 'seccion=' + encodeURIComponent(seccion), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    })
      .then(function (resp) {
        if (!resp.ok) { throw new Error('HTTP ' + resp.status); }
        return resp.json();
      })
      .then(function (data) {
        renderTablaDesglose('tablaDesgloseTipo', data.por_tipo, 'tipo_id');
        renderTablaDesglose('tablaDesgloseArea', data.por_area, 'area_id');
        // 2026-08-16: 2 graficos del modal, pedido Matías -- mismo click-through que las tablas.
        doughnutDesglose('chartDesgloseTipo', data.por_tipo, 'tipo_id');
        doughnutDesglose('chartDesgloseArea', data.por_area, 'area_id');
        modalDesglose.show();
      })
      .catch(function (err) { console.error('Error cargando desglose de sección:', err); });
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
      // 2026-08-14: recuadro Cumplidas (a_tiempo + fuera_plazo), pedido en reunión
      setText('kpiCumplidas', (k.a_tiempo || 0) + (k.fuera_plazo || 0));
      setText('kpiCumplidasATiempo', k.a_tiempo);
      setText('kpiCumplidasFueraPlazo', k.fuera_plazo);
    }
    if (typeof pct === 'number') { setText('kpiPct', pct); }
  }

  function render(chartData, animate) {
    actualizarKpis(chartData.kpis, chartData.pct_cumplidas);
    // 2026-08-16: chartTipo/chartEmpresa/chartCumplimiento eliminados -- rediseño Matías, queda solo pastel.
    pastel(chartData.pastel_cumplimiento, animate);
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
