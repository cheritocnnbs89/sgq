/* Lista de Reclamos Seguros: el detalle se abre en una ventana (modal) con las mismas acciones
   que la pagina completa (seguimiento, cerrar, combinar, eliminar) sin salir de la lista.
   Las acciones se envian por fetch y la ventana se actualiza con la respuesta. Sin codigo inline (CSP). */
(function () {
  'use strict';

  var modalEl = document.getElementById('modalCasoDetalle');
  var body = document.getElementById('modalCasoDetalleBody');
  if (!modalEl || !body || typeof bootstrap === 'undefined') { return; }

  var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  var huboCambios = false;

  function alerta(texto, tipo) {
    var a = document.createElement('div');
    a.className = 'alert alert-' + (tipo === 'message' ? 'info' : (tipo || 'danger')) + ' alert-dismissible fade show';
    a.setAttribute('role', 'alert');
    var t = document.createElement('span');
    t.textContent = texto;
    a.appendChild(t);
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn-close';
    b.setAttribute('data-bs-dismiss', 'alert');
    b.setAttribute('aria-label', 'Close');
    a.appendChild(b);
    return a;
  }

  function mostrarMensajes(lista) {
    if (!lista || !lista.length) { return; }
    var cont = document.createElement('div');
    cont.className = 'mb-2';
    lista.forEach(function (m) { cont.appendChild(alerta(m[1], m[0])); });
    body.insertBefore(cont, body.firstChild);
  }

  function pintar(html, mensajes) {
    body.innerHTML = html;
    if (window.RSEditores) { window.RSEditores.iniciar(body); }
    mostrarMensajes(mensajes);
    var cuerpo = modalEl.querySelector('.modal-body');
    if (cuerpo) { cuerpo.scrollTop = 0; }
  }

  function error(texto) {
    body.textContent = '';
    body.appendChild(alerta(texto, 'danger'));
  }

  function cargar(url) {
    fetch(url, {
      credentials: 'same-origin', cache: 'no-store',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.text();
    }).then(function (html) {
      pintar(html, null);
    }).catch(function () {
      error('No se pudo cargar el detalle del caso.');
    });
  }

  document.querySelectorAll('.js-rs-detalle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      huboCambios = false;
      body.textContent = 'Cargando\u2026';
      modal.show();
      cargar(btn.getAttribute('data-url'));
    });
  });

  // Acciones dentro de la ventana: delegado (el contenido se inyecta despues de cargar la pagina).
  body.addEventListener('submit', function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement)) { return; }
    if (ev.defaultPrevented) { return; }   // p. ej. el editor encontro el campo vacio y ya aviso
    ev.preventDefault();

    var msg = form.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) { return; }
    if (form.dataset.enviando === '1') { return; }

    window.RSForm.bloquear(form);
    fetch(form.action, {
      method: 'POST', body: new FormData(form), credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) {
      return r.json().then(function (d) { return { r: r, d: d }; },
                           function () { return { r: r, d: null }; });
    }).then(function (x) {
      if (!x.d || !x.r.ok || !x.d.ok) {
        throw new Error('No se pudo completar la acci\u00f3n (HTTP ' + x.r.status + ').');
      }
      huboCambios = true;
      if (x.d.cerrado) {
        modal.hide();
      } else {
        pintar(x.d.html, x.d.mensajes);
      }
    }).catch(function (err) {
      window.RSForm.restaurar(form);
      mostrarMensajes([['danger', err.message || 'No se pudo completar la acci\u00f3n.']]);
    });
  });

  // Al cerrar la ventana se recarga la lista (mismo filtro) si algo cambio.
  modalEl.addEventListener('hidden.bs.modal', function () {
    body.textContent = '';
    if (huboCambios) { window.location.reload(); }
  });
})();
