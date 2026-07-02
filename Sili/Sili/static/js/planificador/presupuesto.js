// ── Agregar CC ────────────────────────────────────────────────
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-agregar-cc')) return;
  var sel = document.getElementById('sel-nuevo-cc');
  if (!sel || !sel.value) {
    alert('Seleccione un centro de costo para agregar.');
    return;
  }
  document.getElementById('form-agregar-cc-id').value = sel.value;
  document.getElementById('form-agregar-cc').submit();
});

// ── Abrir modal de edición mensual ───────────────────────────
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.btn-editar-cc');
  if (!btn) return;

  var ccId     = btn.dataset.ccId;
  var ccNombre = btn.dataset.ccNombre;
  var meses    = JSON.parse(btn.dataset.meses);

  document.getElementById('modal-cc-id').value    = ccId;
  document.getElementById('modal-cc-nombre').textContent = ccNombre;

  var total = 0;
  meses.forEach(function (m) {
    var input = document.getElementById('modal-mes-' + m.mes);
    if (input) {
      input.value = parseFloat(m.monto_presupuestado).toFixed(2);
      total += parseFloat(m.monto_presupuestado) || 0;
    }
  });

  var totalCell = document.querySelector('.presup-total');
  if (totalCell) totalCell.textContent = '$' + total.toFixed(2);

  var modal = new bootstrap.Modal(document.getElementById('modalEditarCC'));
  modal.show();
});

// ── Recalcular total en el modal al editar inputs ─────────────
document.addEventListener('input', function (e) {
  if (!e.target.classList.contains('presup-input')) return;
  var modal = document.getElementById('modalEditarCC');
  if (!modal) return;
  var inputs = modal.querySelectorAll('.presup-input');
  var total = 0;
  inputs.forEach(function (inp) {
    total += parseFloat(inp.value.replace(',', '.')) || 0;
  });
  var totalCell = modal.querySelector('.presup-total');
  if (totalCell) totalCell.textContent = '$' + total.toFixed(2);
});
