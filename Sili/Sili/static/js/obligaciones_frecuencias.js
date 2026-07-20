// Pantalla de Frecuencias (Obligaciones) -- Correccion de arquitectura #3, 2026-07-15.
// Sin dependencias externas (sin jQuery/axios), solo JS vanilla. CSP del
// proyecto prohibe JS inline -- por eso este archivo va aparte y se referencia
// con <script src="..."> en obligaciones_frecuencia_form.html.
document.addEventListener('DOMContentLoaded', function () {
  var recalculoTipo = document.getElementById('recalculo_tipo');
  var recalculoCantidad = document.getElementById('recalculo_cantidad');

  function actualizarRecalculoCantidad() {
    var sinRecalculo = recalculoTipo.value === 'NINGUNA';
    recalculoCantidad.disabled = sinRecalculo;
    recalculoCantidad.required = !sinRecalculo;
    if (sinRecalculo) { recalculoCantidad.value = ''; }
  }

  if (recalculoTipo && recalculoCantidad) {
    recalculoTipo.addEventListener('change', actualizarRecalculoCantidad);
    actualizarRecalculoCantidad();
  }

  document.querySelectorAll('.notif-block').forEach(function (block) {
    var tipoTrigger = block.querySelector('.notif-tipo-trigger');
    var diasAntesWrap = block.querySelector('.notif-dias-antes-wrap');
    var diaFijoWrap = block.querySelector('.notif-dia-fijo-wrap');

    function actualizarVisibilidad() {
      var valor = tipoTrigger.value;
      diasAntesWrap.style.display = (valor === 'dias_antes') ? '' : 'none';
      diaFijoWrap.style.display = (valor === 'fecha_exacta') ? '' : 'none';
    }

    if (tipoTrigger) {
      tipoTrigger.addEventListener('change', actualizarVisibilidad);
      actualizarVisibilidad();
    }

    // ponytail: filtro client-side sobre la lista de usuarios ya cargada --
    // suficiente mientras la tabla `usuarios` sea chica; si crece mucho,
    // subir a un endpoint de busqueda con AJAX (patron ya usado en otros
    // modulos de SGQ para selects grandes).
    // No mostrar la lista completa por defecto (son cientos de usuarios) --
    // solo aparecen los que coinciden con lo que se escribe. Los que ya
    // estaban marcados (editar) se muestran igual aunque el filtro este vacio.
    var filtro = block.querySelector('.notif-usuario-filtro');
    var items = block.querySelectorAll('.notif-usuario-item');

    function aplicarFiltro() {
      var texto = filtro.value.trim().toLowerCase();
      items.forEach(function (item) {
        var checkbox = item.querySelector('input[type="checkbox"]');
        var label = item.querySelector('.notif-usuario-label');
        var yaMarcado = checkbox && checkbox.checked;
        var coincide = texto && label && label.textContent.toLowerCase().indexOf(texto) !== -1;
        item.style.display = (yaMarcado || coincide) ? '' : 'none';
      });
    }

    if (filtro) {
      filtro.addEventListener('input', aplicarFiltro);
      aplicarFiltro();
    }
  });
});
