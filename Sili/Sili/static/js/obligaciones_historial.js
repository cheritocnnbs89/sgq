document.addEventListener('DOMContentLoaded', function () {
  if (window.TableKit) {
    TableKit.init({
      table: '#tabla-historial',
      pagerContainer: '#paginationHist',
      infoContainer: '#tableInfoHist',
      pageLenKey: 'obligaciones_historial_page_len',
      defaultPageLen: 10,
    });
  }
});

// 2026-08-11: filtro dependiente Tipo -> Entidad (AJAX), faltaba en Historial
// (ya existia en form/lista/dashboard). wireFiltroTipoEntidad viene de
// obligaciones_filtro_tipo_entidad.js.
document.addEventListener('DOMContentLoaded', function () {
  wireFiltroTipoEntidad(
    document.getElementById('frmFiltrosHistorial'),
    document.getElementById('filtroTipoId'),
    document.getElementById('filtroEntidadId'),
    '-- Entidad --'
  );
});
