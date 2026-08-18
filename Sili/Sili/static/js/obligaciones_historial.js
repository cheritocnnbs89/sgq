// 2026-08-14: Punto 8 -- modal compartido "Solicitar edición". Dispara el modal
// con la API de bootstrap.Modal directamente en vez de confiar en el atributo
// declarativo data-bs-toggle="modal" -- en esta pantalla ese atributo NO
// disparaba el listener delegado de Bootstrap (causa no identificada -- posible
// conflicto con TableKit reconstruyendo el tbody), verificado con
// bootstrap.Modal.getOrCreateInstance(...).show() invocado a mano SÍ funciona.
// Mismo patrón ya usado sin problemas en obligaciones_dashboard.js (modal de
// desglose del pastel, Punto 5).
document.addEventListener('DOMContentLoaded', function () {
  var modalEl = document.getElementById('modalSolicitarEdicion');
  if (!modalEl || typeof bootstrap === 'undefined') { return; }
  var urlTemplate = modalEl.getAttribute('data-url-template'); // termina en ".../0/solicitar-edicion"
  var form = document.getElementById('frmSolicitarEdicion');
  var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  document.addEventListener('click', function (evt) {
    var boton = evt.target.closest('.btn-solicitar-edicion');
    if (!boton) { return; }
    var obligId = boton.getAttribute('data-oblig-id');
    if (obligId && urlTemplate) {
      form.action = urlTemplate.replace('/0/solicitar-edicion', '/' + obligId + '/solicitar-edicion');
    }
    modal.show();
  });
});

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
