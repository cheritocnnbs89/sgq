// 2026-08-11: extraido de obligaciones_form.js (duplicado en lista/dashboard) a
// archivo compartido para reutilizar tambien en historial.html sin duplicar 4ta vez.
// wireFiltroTipoEntidad(form, tipoSelect, entidadSelect, placeholder opcional)
function wireFiltroTipoEntidad(form, tipoSelect, entidadSelect, placeholder) {
  var apiUrl = form && form.dataset.apiEntidades;
  if (!apiUrl || !tipoSelect || !entidadSelect) { return; }
  var texto = placeholder || '-- Seleccionar --';

  function repoblar(preservarSeleccion) {
    var tipoId = tipoSelect.value;
    var seleccionActual = preservarSeleccion ? (entidadSelect.dataset.selected || entidadSelect.value) : '';
    entidadSelect.innerHTML = '<option value="">' + texto + '</option>';
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
}
