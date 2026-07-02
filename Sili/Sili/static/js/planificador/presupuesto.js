// ── Actualiza el total de la fila de presupuestado al editar inputs ───────
(function () {
  document.addEventListener('input', function (e) {
    if (!e.target.classList.contains('presup-input')) return;
    const form = e.target.closest('form');
    if (!form) return;
    const inputs = form.querySelectorAll('.presup-input');
    let total = 0;
    inputs.forEach(function (inp) {
      total += parseFloat(inp.value.replace(',', '.')) || 0;
    });
    const totalCell = form.querySelector('.presup-total');
    if (totalCell) {
      totalCell.textContent = '$' + total.toFixed(2);
    }
  });
})();
