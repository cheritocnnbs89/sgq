// 2026-07-27: filtro dependiente Tipo -> Entidad (usa oblig_tipo_entidad via
// GET /obligaciones/api/entidades?tipo_id=X). Repuebla el select de Entidad
// cada vez que cambia Tipo, preservando la seleccion actual si sigue valida
// (necesario al editar una obligacion existente).
function wireFiltroTipoEntidad(form, tipoSelect, entidadSelect) {
  var apiUrl = form && form.dataset.apiEntidades;
  if (!apiUrl || !tipoSelect || !entidadSelect) { return; }

  function repoblar(preservarSeleccion) {
    var tipoId = tipoSelect.value;
    var seleccionActual = preservarSeleccion ? (entidadSelect.dataset.selected || entidadSelect.value) : '';
    entidadSelect.innerHTML = '<option value="">-- Seleccionar --</option>';
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

document.addEventListener('DOMContentLoaded', function () {
  wireFiltroTipoEntidad(
    document.getElementById('frmObligacion'),
    document.getElementById('tipo_id'),
    document.getElementById('entidad_id')
  );

  var frecuencia = document.getElementById('frecuencia_id');
  var fecha = document.getElementById('fecha_vencimiento');

  // 2026-07-15 (Corrección #3): ya no hay un valor fijo 'sin_fecha_fin' -- cualquier
  // frecuencia cuya oblig_frecuencia tenga recalculo_tipo='NINGUNA' no recalcula/no exige fecha.
  function actualizarFecha() {
    var opcion = frecuencia.options[frecuencia.selectedIndex];
    var sinFecha = !!opcion && opcion.dataset.recalculo === 'NINGUNA';
    fecha.disabled = sinFecha;
    fecha.required = !sinFecha;
    if (sinFecha) { fecha.value = ''; }
  }

  if (frecuencia && fecha) {
    frecuencia.addEventListener('change', actualizarFecha);
    actualizarFecha();
  }
});
