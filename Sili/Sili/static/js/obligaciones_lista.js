// 2026-07-27: filtro dependiente Tipo -> Entidad (AJAX, ver obligaciones_form.js
// para la version comentada de esta misma logica -- duplicada a proposito,
// cada pantalla tiene sus propios ids de select).
document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('frmFiltrosLista');
  var tipoSelect = document.getElementById('filtroTipoId');
  var entidadSelect = document.getElementById('filtroEntidadId');
  var apiUrl = form && form.dataset.apiEntidades;
  if (!apiUrl || !tipoSelect || !entidadSelect) { return; }

  function repoblar(preservarSeleccion) {
    var tipoId = tipoSelect.value;
    var seleccionActual = preservarSeleccion ? (entidadSelect.dataset.selected || entidadSelect.value) : '';
    entidadSelect.innerHTML = '<option value="">-- Entidad --</option>';
    if (!tipoId) { return; }
    fetch(apiUrl + '?tipo_id=' + encodeURIComponent(tipoId), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        (data.entidades || []).forEach(function (en) {
          var opt = document.createElement('option');
          opt.value = en.id;
          opt.textContent = en.nombre;
          if (String(en.id) === String(seleccionActual)) { opt.selected = true; }
          entidadSelect.appendChild(opt);
        });
        entidadSelect.dataset.selected = '';
      })
      .catch(function (err) { console.warn('Filtro Tipo->Entidad: fallo la carga', err); });
  }

  tipoSelect.addEventListener('change', function () { repoblar(false); });
  if (tipoSelect.value) { repoblar(true); }
});

document.addEventListener('DOMContentLoaded', function () {
  if (window.TableKit) {
    TableKit.init({
      table: '#tabla-obligaciones',
      pagerContainer: '#pagination',
      infoContainer: '#tableInfo',
      pageLenKey: 'obligaciones_page_len',
      defaultPageLen: 10,
    });
  }
});

// Feedback visual de carga al enviar el formulario de filtros (recarga nativa del navegador).
// ponytail: mismo patron que lockButton() en templates/reclamos_lista copy.html
document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('#panelFiltrosLista form');
  if (!form) return;

  form.addEventListener('submit', function () {
    var btn = form.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Filtrando...';
  });
});
