// 2026-08-11: wireFiltroTipoEntidad ahora vive en obligaciones_filtro_tipo_entidad.js (compartido)
document.addEventListener('DOMContentLoaded', function () {
  wireFiltroTipoEntidad(
    document.getElementById('frmFiltrosLista'),
    document.getElementById('filtroTipoId'),
    document.getElementById('filtroEntidadId'),
    '-- Entidad --'
  );
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
