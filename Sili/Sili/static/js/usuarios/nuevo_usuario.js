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
      tipoCajaChica.required = true;
    } else {
      boxTipoCajaChica.classList.add('d-none');
      tipoCajaChica.disabled = true;
      tipoCajaChica.required = false;
      tipoCajaChica.value = '';
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

  if (!wrap || !addButton) {
    return;
  }

  let centrosCosto = [];

  try {
    centrosCosto = JSON.parse(wrap.dataset.ccOptions || '[]');
  } catch (error) {
    console.error('No se pudo leer data-cc-options', error);
    centrosCosto = [];
  }

  function buildCentroCostoOptions() {
    let options = '<option value="">-- Seleccione centro de costo --</option>';

    centrosCosto.forEach(function (item) {
      options += `<option value="${item.id}">${item.nombre}</option>`;
    });

    return options;
  }

  function createCCRow() {
    const row = document.createElement('div');
    row.className = 'row g-2 mt-1';

    row.innerHTML = `
      <div class="col-md-6">
        <select name="cc_id[]" class="form-select">
          ${buildCentroCostoOptions()}
        </select>
      </div>
      <div class="col-md-2">
        <input type="number" step="0.01" min="0" max="100" name="cc_pct[]" class="form-control" placeholder="%">
      </div>
      <div class="col-md-3 form-check">
        <input type="hidden" name="cc_boletos[]" class="cc-boletos-hidden" value="0">
        <input type="checkbox" class="form-check-input cc-boletos-check">
        <label class="form-check-label small">Solo boletos aéreos (Planificador)</label>
      </div>
      <div class="col-md-1 d-grid">
        <button type="button" class="btn btn-outline-danger js-remove-cc-row">–</button>
      </div>
    `;

    return row;
  }

  function syncBoletosRow(row) {
    const check = row.querySelector('.cc-boletos-check');
    const hidden = row.querySelector('.cc-boletos-hidden');
    const pctInput = row.querySelector('input[name="cc_pct[]"]');

    if (!check || !hidden) {
      return;
    }

    hidden.value = check.checked ? '1' : '0';

    if (pctInput) {
      pctInput.disabled = check.checked;

      if (check.checked) {
        pctInput.value = '0.00';
      }
    }
  }

  addButton.addEventListener('click', function () {
    wrap.appendChild(createCCRow());
  });

  wrap.addEventListener('click', function (event) {
    const removeButton = event.target.closest('.js-remove-cc-row');

    if (!removeButton) {
      return;
    }

    const row = removeButton.closest('.row');

    if (row) {
      row.remove();
    }
  });

  wrap.addEventListener('change', function (event) {
    if (event.target && event.target.classList.contains('cc-boletos-check')) {
      const row = event.target.closest('.row');

      if (row) {
        syncBoletosRow(row);
      }
    }
  });
});