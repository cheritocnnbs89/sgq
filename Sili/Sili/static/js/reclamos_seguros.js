/* Reclamos Seguros: sin codigo inline (CSP). */
(function () {
  'use strict';

  var TEXTO_PROCESANDO = 'Procesando\u2026';

  // Todo formulario POST: confirmacion opcional (data-confirm) y bloqueo anti doble envio.
  document.addEventListener('submit', function (ev) {
    if (ev.defaultPrevented) { return; }
    var form = ev.target;
    if (!(form instanceof HTMLFormElement)) { return; }
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') { return; }

    var msg = form.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) { ev.preventDefault(); return; }

    if (form.dataset.enviando === '1') { ev.preventDefault(); return; }
    form.dataset.enviando = '1';

    window.setTimeout(function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (b) {
        b.dataset.htmlOriginal = b.innerHTML;
        b.disabled = true;
        b.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' + TEXTO_PROCESANDO;
      });
    }, 0);
  });

  // Si el navegador restaura la pagina desde cache (boton Atras), reactivar los botones.
  window.addEventListener('pageshow', function (ev) {
    if (!ev.persisted) { return; }
    document.querySelectorAll('form[data-enviando="1"]').forEach(function (form) {
      form.dataset.enviando = '0';
      form.querySelectorAll('button[type="submit"]').forEach(function (b) {
        if (b.dataset.htmlOriginal) { b.innerHTML = b.dataset.htmlOriginal; }
        b.disabled = false;
      });
    });
  });
})();
