(function () {
  'use strict';

  function csrfToken() {
    var cfg = document.getElementById('facturas-automaticas-config');
    return cfg ? (cfg.dataset.csrfToken || '') : '';
  }

  function enviarSap(gastoId, btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

    fetch('/reembolsos/gastos/' + gastoId + '/enviar-sap', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      credentials: 'same-origin'
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok || data.success) {
        var row = document.getElementById('row-' + gastoId);
        if (row) {
          row.classList.add('table-success');
          var sapCell = row.querySelector('.badge.bg-warning');
          if (sapCell) {
            sapCell.className = 'badge bg-success';
            sapCell.innerHTML = '<i class="bi bi-check-circle me-1"></i>' + (data.sap_doc || 'OK');
          }
          var actionCell = btn.closest('td');
          if (actionCell) {
            actionCell.innerHTML = '<span class="text-muted small">—</span>';
          }
        }
      } else {
        alert('Error al enviar a SAP: ' + (data.error || data.message || 'Sin detalle'));
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-send"></i>';
      }
    })
    .catch(function () {
      alert('Error de conexión al enviar a SAP.');
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-send"></i>';
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.btn-enviar-sap');
    if (!btn) return;
    var gastoId = btn.dataset.gastoId;
    if (!gastoId) return;
    if (!confirm('¿Enviar gasto #' + gastoId + ' a SAP?')) return;
    enviarSap(gastoId, btn);
  });

  // "Seleccionar todas" solo marca las filas que sí tienen checkbox
  // (las ya enviadas a SAP no lo tienen, no hay nada que seleccionar ahí).
  var chkAll = document.getElementById('chkSelectAllFacturas');
  if (chkAll) {
    chkAll.addEventListener('change', function () {
      document.querySelectorAll('.row-select-factura').forEach(function (chk) {
        chk.checked = chkAll.checked;
      });
    });
  }

  var btnMasivo = document.getElementById('btnEnviarSapMasivo');
  if (btnMasivo) {
    btnMasivo.addEventListener('click', function () {
      var seleccionados = Array.from(document.querySelectorAll('.row-select-factura:checked'))
        .map(function (chk) { return chk.dataset.gastoId; })
        .filter(Boolean);

      if (!seleccionados.length) {
        alert('Selecciona al menos un gasto pendiente para enviar a SAP.');
        return;
      }
      if (!confirm('¿Enviar ' + seleccionados.length + ' gasto(s) seleccionado(s) a SAP?')) return;

      seleccionados.forEach(function (gastoId) {
        var btn = document.querySelector('.btn-enviar-sap[data-gasto-id="' + gastoId + '"]');
        if (btn && !btn.disabled) {
          enviarSap(gastoId, btn);
        }
      });
    });
  }
}());
