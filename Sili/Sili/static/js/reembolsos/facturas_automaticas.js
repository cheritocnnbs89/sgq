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

  var btnMasivo = document.getElementById('btnEnviarSapMasivo');
  if (btnMasivo) {
    btnMasivo.addEventListener('click', function () {
      var pendientes = document.querySelectorAll('.btn-enviar-sap:not(:disabled)');
      if (!pendientes.length) {
        alert('No hay gastos pendientes de envío a SAP.');
        return;
      }
      if (!confirm('¿Enviar ' + pendientes.length + ' gasto(s) pendiente(s) a SAP?')) return;
      pendientes.forEach(function (btn) {
        enviarSap(btn.dataset.gastoId, btn);
      });
    });
  }
}());
