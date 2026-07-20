document.addEventListener('DOMContentLoaded', function () {
  // ==========================================================
  // Caja Chica - Tipo
  // ==========================================================
  const chkCajaChica = document.getElementById('chkCajaChica');
  const boxTipoCajaChica = document.getElementById('boxTipoCajaChica');
  const tipoCajaChica = document.getElementById('tipoCajaChica');

  function syncTipoCajaChica() {
    if (!chkCajaChica || !boxTipoCajaChica || !tipoCajaChica) {
      return;
    }

    if (chkCajaChica.checked) {
      boxTipoCajaChica.classList.remove('d-none');
      tipoCajaChica.disabled = false;

      if (!tipoCajaChica.value || tipoCajaChica.value === 'NINGUNA') {
        tipoCajaChica.value = 'C0';
      }
    } else {
      boxTipoCajaChica.classList.add('d-none');
      tipoCajaChica.disabled = true;
    }
  }

  if (chkCajaChica) {
    chkCajaChica.addEventListener('change', syncTipoCajaChica);
    syncTipoCajaChica();
  }

  // ==========================================================
  // Distribución de Centro de Costo
  // ==========================================================
  const wrap = document.getElementById('cc-rows');
  const addButton = document.getElementById('btn-add-cc');
  const saveButton = document.getElementById('btn-save');
  const hint = document.getElementById('cc-hint');

  if (!wrap) {
    return;
  }

  function addCCRow() {
    const tmpl = wrap.querySelector('.cc-row');

    if (!tmpl) {
      return;
    }

    const clone = tmpl.cloneNode(true);

    clone.querySelectorAll('input').forEach(function (input) {
      input.value = '';
    });

    clone.querySelectorAll('select').forEach(function (select) {
      select.selectedIndex = 0;
    });

    wrap.appendChild(clone);
    checkCCSum();
  }

  function ccSum() {
    let total = 0;

    document.querySelectorAll('input[name="cc_pct[]"]').forEach(function (input) {
      const raw = (input.value || '').replace(',', '.');
      const value = parseFloat(raw);

      if (!isNaN(value)) {
        total += value;
      }
    });

    return total;
  }

  function checkCCSum() {
    if (!hint) {
      return true;
    }

    const total = ccSum();
    const ok = Math.abs(total - 100) <= 0.01 || total === 0;

    hint.textContent = 'La suma debe ser 100%. Actual: ' + total.toFixed(2) + '%';
    hint.classList.remove('cc-hint-ok', 'cc-hint-error');
    hint.classList.add(ok ? 'cc-hint-ok' : 'cc-hint-error');

    return ok;
  }

  if (addButton) {
    addButton.addEventListener('click', function () {
      addCCRow();
    });
  }

  wrap.addEventListener('click', function (event) {
    const btn = event.target.closest('.btn-remove-cc');

    if (!btn) {
      return;
    }

    const rows = wrap.querySelectorAll('.cc-row');

    if (rows.length > 1) {
      const row = btn.closest('.cc-row');

      if (row) {
        row.remove();
        checkCCSum();
      }
    }
  });

  document.addEventListener('input', function (event) {
    if (event.target && event.target.name === 'cc_pct[]') {
      checkCCSum();
    }
  });

  if (saveButton) {
    saveButton.addEventListener('click', function (event) {
      const ok = checkCCSum();

      if (!ok) {
        event.preventDefault();

        if (hint) {
          hint.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    });
  }

  checkCCSum();

  // ==========================================================
  // Cerrar alertas automáticamente
  // ==========================================================
  window.setTimeout(function () {
    if (typeof bootstrap === 'undefined' || !bootstrap.Alert) {
      return;
    }

    document.querySelectorAll('.alert').forEach(function (alertElement) {
      const instance = bootstrap.Alert.getOrCreateInstance(alertElement);
      instance.close();
    });
  }, 2500);
});