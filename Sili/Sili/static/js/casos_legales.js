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

  // ── Cliente / Proveedor: el check elige qué lista se muestra ──
  var radiosTercero = document.querySelectorAll('input[name="tercero_tipo"]');
  var selCliente = document.getElementById('selCliente');
  var selProveedor = document.getElementById('selProveedor');
  var selVacio = document.getElementById('selTerceroVacio');
  if (radiosTercero.length && selCliente && selProveedor && selVacio) {
    var mostrar = function (el, si) {
      el.classList.toggle('d-none', !si);
      el.disabled = !si;
    };
    var actualizarTercero = function () {
      var r = document.querySelector('input[name="tercero_tipo"]:checked');
      var t = r ? r.value : '';
      mostrar(selCliente, t === 'C');
      mostrar(selProveedor, t === 'P');
      mostrar(selVacio, t === '');
      selVacio.disabled = true;
    };
    radiosTercero.forEach(function (r) { r.addEventListener('change', actualizarTercero); });
    var limpiar = document.getElementById('terceroLimpiar');
    if (limpiar) {
      limpiar.addEventListener('click', function () {
        radiosTercero.forEach(function (r) { r.checked = false; });
        selCliente.value = ''; selProveedor.value = '';
        actualizarTercero();
      });
    }
    actualizarTercero();
  }

  // ── Formularios: validación por botón, confirmación y evitar doble envío ──
  // Delegado en document (no por-formulario): el detalle de un caso se puede inyectar
  // dentro del popup de la lista DESPUÉS de que este script ya corrió, así que un
  // listener puesto directo en cada <form> en ese momento no vería los formularios
  // que llegan más tarde. Un mismo <form> puede además tener varios botones "submit"
  // (p. ej. "Agregar avance" y "Cerrar caso" con formaction distinto) — ev.submitter
  // identifica cuál se pulsó.
  document.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement)) { return; }
    if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post') { return; }

    var btn = ev.submitter || null;

    if (btn && btn.hasAttribute('data-requiere-observacion')) {
      var obs = form.querySelector('[name="observacion"]');
      if (obs && !obs.value.trim()) {
        ev.preventDefault();
        window.alert('Escribe la observación del avance.');
        obs.focus();
        return;
      }
    }

    var msg = (btn && btn.getAttribute('data-confirm')) || form.getAttribute('data-casos-confirm');
    if (msg && !window.confirm(msg)) { ev.preventDefault(); return; }

    window.setTimeout(function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (b) { b.disabled = true; });
    }, 0);
  });

  // ── Lista: botón "Detalle" abre el caso en un popup (sin salir de la lista) ──
  function abrirCasoDetalle(casoId) {
    var body = document.getElementById('modalCasoDetalleBody');
    var modalEl = document.getElementById('modalCasoDetalle');
    if (!body || !modalEl || typeof bootstrap === 'undefined') { return; }

    while (body.firstChild) { body.removeChild(body.firstChild); }
    body.textContent = 'Cargando…';

    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    fetch('/casos-legales/' + encodeURIComponent(casoId) + '/fragment', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      cache: 'no-store'
    }).then(function (resp) {
      if (!resp.ok) { throw new Error('HTTP ' + resp.status); }
      return resp.text();
    }).then(function (html) {
      body.innerHTML = html;
    }).catch(function () {
      body.innerHTML = '';
      var errDiv = document.createElement('div');
      errDiv.className = 'alert alert-danger mb-0';
      errDiv.textContent = 'No se pudo cargar el detalle del caso.';
      body.appendChild(errDiv);
    });
  }

  document.querySelectorAll('.js-open-caso-detalle').forEach(function (btn) {
    btn.addEventListener('click', function () { abrirCasoDetalle(btn.dataset.casoId); });
  });
})();
