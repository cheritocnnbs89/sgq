document.addEventListener('DOMContentLoaded', function () {
  const cfg = document.getElementById('gastos-detalle-config');
  if (!cfg) return;

  const isPopup = String(cfg.getAttribute('data-popup') || '') === '1';
  if (!isPopup) return;

  document.documentElement.classList.add('gd-popup-html');
});