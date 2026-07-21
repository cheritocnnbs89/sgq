document.addEventListener('DOMContentLoaded', function () {
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
