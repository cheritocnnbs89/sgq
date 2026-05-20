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
      <div class="col-md-8">
        <select name="cc_id[]" class="form-select">
          ${buildCentroCostoOptions()}
        </select>
      </div>
      <div class="col-md-3">
        <input type="number" step="0.01" min="0" max="100" name="cc_pct[]" class="form-control" placeholder="%">
      </div>
      <div class="col-md-1 d-grid">
        <button type="button" class="btn btn-outline-danger js-remove-cc-row">–</button>
      </div>
    `;

    return row;
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
});