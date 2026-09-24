/* Casos Legales: sin código inline (CSP). */
(function () {
  'use strict';

  // ── Nuevo caso: mostrar el formulario al elegir el tipo ──
  var campos = document.getElementById('casoCampos');
  if (campos) {
    var aviso = document.getElementById('casoAvisoPendiente');
    var avisoGestiona = aviso ? aviso.querySelector('[data-aviso-gestiona]') : null;
    var radios = document.querySelectorAll('input[name="tipo"]');

    var actualizar = function () {
      var elegido = document.querySelector('input[name="tipo"]:checked');
      campos.classList.toggle('d-none', !elegido);
      if (!elegido || !aviso) { return; }
      var pendiente = elegido.getAttribute('data-definido') !== '1';
      aviso.classList.toggle('d-none', !pendiente);
      if (avisoGestiona) { avisoGestiona.textContent = elegido.getAttribute('data-gestiona') || ''; }
    };

    radios.forEach(function (r) { r.addEventListener('change', actualizar); });
    actualizar();
  }

  // ── Confirmación antes de enviar (cerrar caso) ──
  document.querySelectorAll('form[data-casos-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      if (!window.confirm(form.getAttribute('data-casos-confirm'))) { ev.preventDefault(); }
    });
  });

  // ── Evitar doble envío ──
  document.querySelectorAll('form[enctype="multipart/form-data"]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      if (ev.defaultPrevented) { return; }
      form.querySelectorAll('button[type="submit"]').forEach(function (b) {
        window.setTimeout(function () { b.disabled = true; }, 0);
      });
    });
  });
})();
