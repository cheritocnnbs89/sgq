document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('form[data-confirm-message]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      const ok = window.confirm(form.dataset.confirmMessage);
      if (!ok) {
        ev.preventDefault();
      }
    });
  });

  initAutoRegistroBuscadores();
});

// Reusa los mismos catálogos (proveedores, motivos, centros de costo) que
// gastos_form.html, para no obligar a memorizar/buscar el RUC en otro lado.
function initAutoRegistroBuscadores() {
  const form = document.getElementById('frmAutoRegistroRegla');
  if (!form) return;

  const apiProveedores = form.dataset.apiProveedoresSearch || '';
  const apiMotivos = form.dataset.apiParamMotivos || '';
  const apiCentros = form.dataset.apiParamCentros || '';

  function wireBuscador(inputId, datalistId, apiUrl, buildOption) {
    const input = document.getElementById(inputId);
    const datalist = document.getElementById(datalistId);
    if (!input || !datalist || !apiUrl) return;

    let timer = null;
    const fetchOptions = (q) => {
      const url = new URL(apiUrl, window.location.origin);
      if (q) url.searchParams.set('q', q);
      url.searchParams.set('limit', '10');

      fetch(url, { credentials: 'same-origin' })
        .then((r) => r.json())
        .then((list) => {
          datalist.innerHTML = '';
          (list || []).forEach((item) => {
            const opt = document.createElement('option');
            buildOption(opt, item);
            datalist.appendChild(opt);
          });
        })
        .catch(() => {});
    };

    input.addEventListener('input', function () {
      clearTimeout(timer);
      const q = input.value || '';
      timer = setTimeout(() => fetchOptions(q), 220);
    });

    input.addEventListener('focus', function () {
      if (!datalist.options.length) fetchOptions('');
    });
  }

  wireBuscador('autoreg_proveedor', 'dl-autoreg-proveedores', apiProveedores, function (opt, item) {
    opt.value = item.identificacion || '';
    opt.label = item.identificacion ? `${item.nombre} (${item.identificacion})` : (item.nombre || '');
  });

  wireBuscador('autoreg_motivo', 'dl-autoreg-motivos', apiMotivos, function (opt, item) {
    opt.value = item.valor || '';
    opt.label = item.nombre ? `${item.nombre} (${item.valor || ''})` : (item.valor || '');
  });

  wireBuscador('autoreg_centro', 'dl-autoreg-centros', apiCentros, function (opt, item) {
    opt.value = item.valor || '';
    opt.label = item.nombre ? `${item.nombre} (${item.valor || ''})` : (item.valor || '');
  });
}
