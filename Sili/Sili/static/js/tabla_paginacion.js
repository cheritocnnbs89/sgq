/* Paginacion del lado del cliente con selector de registros (5, 10, 15, 50; por defecto 15).
   Uso: agregar data-paginar a la <table> y cargar este script. Filas que no deben paginarse
   (p. ej. "No hay datos"): data-no-paginar. Sin codigo inline (CSP): solo clases, nunca style. */
(function () {
  'use strict';

  var OPCIONES = [5, 10, 15, 50];
  var POR_DEFECTO = 15;

  function el(tag, clase, texto) {
    var e = document.createElement(tag);
    if (clase) { e.className = clase; }
    if (texto !== undefined) { e.textContent = texto; }
    return e;
  }

  function iniciar(table) {
    var tbody = table.tBodies[0];
    if (!tbody) { return; }
    var filas = Array.prototype.filter.call(tbody.rows, function (r) {
      return !r.hasAttribute('data-no-paginar');
    });
    var largo = POR_DEFECTO;
    var pagina = 1;

    var barra = el('div', 'd-flex flex-wrap align-items-center justify-content-between gap-2 p-2 border-top');
    var izq = el('div', 'd-flex align-items-center gap-2 small text-muted');
    izq.appendChild(el('span', '', 'Mostrar'));
    var sel = el('select', 'form-select form-select-sm w-auto');
    OPCIONES.forEach(function (n) {
      var o = el('option', '', String(n));
      o.value = String(n);
      if (n === POR_DEFECTO) { o.selected = true; }
      sel.appendChild(o);
    });
    izq.appendChild(sel);
    izq.appendChild(el('span', '', 'registros'));
    var info = el('span', 'ms-2');
    izq.appendChild(info);
    var nav = el('ul', 'pagination pagination-sm mb-0');
    barra.appendChild(izq);
    barra.appendChild(nav);

    var contenedor = table.closest('.table-responsive') || table;
    contenedor.insertAdjacentElement('afterend', barra);

    function item(texto, destino, deshabilitado, activo) {
      var li = el('li', 'page-item' + (deshabilitado ? ' disabled' : '') + (activo ? ' active' : ''));
      var a = el('a', 'page-link', texto);
      a.href = '#';
      a.addEventListener('click', function (e) {
        e.preventDefault();
        if (!deshabilitado) { ir(destino); }
      });
      li.appendChild(a);
      return li;
    }

    function ir(p) {
      var total = filas.length;
      var paginas = Math.max(1, Math.ceil(total / largo));
      pagina = Math.min(Math.max(1, p), paginas);
      var ini = (pagina - 1) * largo;
      var fin = ini + largo;
      filas.forEach(function (r, i) { r.classList.toggle('d-none', i < ini || i >= fin); });
      info.textContent = total ? ('Mostrando ' + (ini + 1) + ' a ' + Math.min(fin, total) + ' de ' + total) : 'Sin registros';

      nav.innerHTML = '';
      nav.appendChild(item('Anterior', pagina - 1, pagina === 1, false));
      for (var n = 1; n <= paginas; n++) {
        if (n === 1 || n === paginas || Math.abs(n - pagina) <= 2) {
          nav.appendChild(item(String(n), n, false, n === pagina));
        } else if (Math.abs(n - pagina) === 3) {
          nav.appendChild(item('\u2026', n, true, false));
        }
      }
      nav.appendChild(item('Siguiente', pagina + 1, pagina === paginas, false));
    }

    sel.addEventListener('change', function () {
      largo = parseInt(sel.value, 10) || POR_DEFECTO;
      ir(1);
    });
    ir(1);
  }

  document.querySelectorAll('table[data-paginar]').forEach(iniciar);
})();
