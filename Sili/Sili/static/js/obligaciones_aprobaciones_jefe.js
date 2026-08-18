// 2026-08-15 (2): rechazar cumplimiento exige motivo (pedido de Matías, el
// usuario debe recibir el porqué por email). Mismo patrón que
// obligaciones_historial.js (Punto 8) -- dispara el modal a mano en vez de
// confiar en data-bs-toggle, que no dispara el listener delegado en esta app.
document.addEventListener('DOMContentLoaded', function () {
  var modalEl = document.getElementById('modalRechazarCumplimiento');
  if (!modalEl || typeof bootstrap === 'undefined') { return; }
  var urlTemplate = modalEl.getAttribute('data-url-template'); // termina en ".../0/aprobar-jefe"
  var form = document.getElementById('frmRechazarCumplimiento');
  var modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  document.addEventListener('click', function (evt) {
    var boton = evt.target.closest('.btn-rechazar-cumplimiento');
    if (!boton) { return; }
    var obligId = boton.getAttribute('data-oblig-id');
    if (obligId && urlTemplate) {
      form.action = urlTemplate.replace('/0/aprobar-jefe', '/' + obligId + '/aprobar-jefe');
    }
    modal.show();
  });
});
