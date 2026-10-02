/* Campo con busqueda mientras se escribe (componente compartido: templates/partials/autocompletar.html).
   Consulta al servidor desde N letras, con espera entre teclas, y descarta respuestas viejas.
   Siempre avisa con una alerta si falla la busqueda o falta elegir de la lista. Sin codigo inline (CSP). */
(function () {
  'use strict';

  var DEMORA_MS = 250;

  function iniciar(ac) {
    if (ac.getAttribute('data-ac-listo') === '1') { return; }
    ac.setAttribute('data-ac-listo', '1');

    var url = ac.getAttribute('data-url') || '';
    var min = parseInt(ac.getAttribute('data-min'), 10) || 2;
    var etiqueta = ac.getAttribute('data-etiqueta') || 'un valor';
    var vacio = ac.getAttribute('data-vacio') || 'Sin resultados';
    var requerido = ac.getAttribute('data-requerido') === '1';
    var texto = ac.querySelector('.ac-texto');
    var idEl = ac.querySelector('.ac-id');
    var lista = ac.querySelector('.ac-lista');
    var estado = ac.querySelector('.ac-estado');
    if (!texto || !idEl || !lista || !estado) { return; }

    var temporizador = null;
    var secuencia = 0;
    var items = [];
    var activo = -1;

    function aviso(msg, tipo) {
      estado.textContent = '';
      if (!msg) { return; }
      var a = document.createElement('div');
      a.className = 'alert alert-' + (tipo || 'warning') + ' py-1 px-2 small mt-1 mb-0';
      a.setAttribute('role', 'alert');
      a.textContent = msg;
      estado.appendChild(a);
    }

    function cerrar() {
      lista.classList.add('d-none');
      lista.textContent = '';
      texto.setAttribute('aria-expanded', 'false');
      items = [];
      activo = -1;
    }

    function marcarActivo(i) {
      var nodos = lista.querySelectorAll('.list-group-item[data-i]');
      nodos.forEach(function (n) { n.classList.remove('ac-activo'); });
      activo = i;
      if (i >= 0 && nodos[i]) {
        nodos[i].classList.add('ac-activo');
        nodos[i].scrollIntoView({ block: 'nearest' });
      }
    }

    function elegir(it) {
      idEl.value = it.id;
      texto.value = it.texto;
      cerrar();
      aviso('');
      idEl.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function pintar() {
      lista.textContent = '';
      if (!items.length) {
        var v = document.createElement('li');
        v.className = 'list-group-item ac-vacio';
        v.textContent = vacio;
        lista.appendChild(v);
      }
      items.forEach(function (it, i) {
        var li = document.createElement('li');
        li.className = 'list-group-item list-group-item-action';
        li.setAttribute('role', 'option');
        li.setAttribute('data-i', String(i));
        var t = document.createElement('span');
        t.textContent = it.texto;
        li.appendChild(t);
        if (it.detalle) {
          var d = document.createElement('span');
          d.className = 'ac-detalle';
          d.textContent = it.detalle;
          li.appendChild(d);
        }
        // mousedown (no click) para elegir antes de que el campo pierda el foco
        li.addEventListener('mousedown', function (e) { e.preventDefault(); elegir(it); });
        lista.appendChild(li);
      });
      lista.classList.remove('d-none');
      texto.setAttribute('aria-expanded', 'true');
      activo = -1;
    }

    function buscar(q) {
      var mia = ++secuencia;
      fetch(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'q=' + encodeURIComponent(q), {
        credentials: 'same-origin', cache: 'no-store',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).then(function (r) {
        if (!r.ok) { throw new Error('HTTP ' + r.status); }
        return r.json();
      }).then(function (d) {
        if (mia !== secuencia) { return; }   // llego una respuesta mas nueva
        items = (d && d.items) || [];
        pintar();
      }).catch(function () {
        if (mia === secuencia) { cerrar(); aviso('No se pudo buscar. Intenta de nuevo.'); }
      });
    }

    texto.addEventListener('input', function () {
      idEl.value = '';          // al editar, la seleccion anterior deja de valer
      aviso('');
      window.clearTimeout(temporizador);
      var q = texto.value.trim();
      if (q.length < min) {
        cerrar();
        if (q.length > 0) { aviso('Escribe al menos ' + min + ' letras para buscar.', 'info'); }
        return;
      }
      temporizador = window.setTimeout(function () { buscar(q); }, DEMORA_MS);
    });

    texto.addEventListener('keydown', function (e) {
      if (lista.classList.contains('d-none')) { return; }
      if (e.key === 'ArrowDown') { e.preventDefault(); marcarActivo(Math.min(items.length - 1, activo + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); marcarActivo(Math.max(0, activo - 1)); }
      else if (e.key === 'Enter' && activo >= 0) { e.preventDefault(); elegir(items[activo]); }
      else if (e.key === 'Escape') { cerrar(); }
    });

    document.addEventListener('click', function (e) {
      if (!ac.contains(e.target)) { cerrar(); }
    });

    var form = ac.closest('form');
    if (form) {
      form.addEventListener('submit', function (ev) {
        var escrito = texto.value.trim();
        if (idEl.value) { return; }
        if (requerido || escrito) {
          ev.preventDefault();
          aviso(requerido && !escrito
            ? 'Selecciona ' + etiqueta + ' de la lista.'
            : 'Selecciona ' + etiqueta + ' de la lista o borra el texto.');
          texto.focus();
        }
      });
    }
  }

  window.Autocompletar = {
    iniciar: function (raiz) {
      (raiz || document).querySelectorAll('[data-ac]').forEach(iniciar);
    }
  };
  window.Autocompletar.iniciar(document);
})();
