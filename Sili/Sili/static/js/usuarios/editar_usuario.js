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

  function syncBoletosRow(row) {
    // "Solo boletos aéreos" ahora es solo una bandera adicional sobre la
    // fila -- el % se mantiene editable y sigue contando en la distribución
    // de reembolso (un mismo centro de costo puede tener % Y usarse para
    // boletos del Planificador a la vez). Antes se deshabilitaba el input
    // y se forzaba a 0.00, lo que además impedía reusar un centro de costo
    // ya en la distribución para marcarlo también como de boletos (quedaba
    // sin %, y encima la tabla usuarios_cc tiene PK (usuario_id,
    // centro_costo_id): agregarlo de nuevo en otra fila violaba la llave).
    const check = row.querySelector('.cc-boletos-check');
    const hidden = row.querySelector('.cc-boletos-hidden');

    if (!check || !hidden) {
      return;
    }

    hidden.value = check.checked ? '1' : '0';
  }

  function addCCRow() {
    const tmpl = wrap.querySelector('.cc-row');

    if (!tmpl) {
      return;
    }

    const clone = tmpl.cloneNode(true);

    clone.querySelectorAll('input[type="number"], input[type="text"]').forEach(function (input) {
      input.value = '';
    });

    clone.querySelectorAll('select').forEach(function (select) {
      select.selectedIndex = 0;
    });

    const cloneCheck = clone.querySelector('.cc-boletos-check');
    const clonePct = clone.querySelector('input[name="cc_pct[]"]');

    if (cloneCheck) {
      cloneCheck.checked = false;
    }

    if (clonePct) {
      clonePct.disabled = false;
    }

    syncBoletosRow(clone);

    wrap.appendChild(clone);
    checkCCSum();
  }

  function ccSum() {
    // Todas las filas cuentan ahora -- "Solo boletos aéreos" ya no excluye
    // la fila de la suma (ver syncBoletosRow).
    let total = 0;

    document.querySelectorAll('.cc-row').forEach(function (row) {
      const input = row.querySelector('input[name="cc_pct[]"]');

      if (!input) {
        return;
      }

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

  wrap.addEventListener('change', function (event) {
    if (event.target && event.target.classList.contains('cc-boletos-check')) {
      const row = event.target.closest('.cc-row');

      if (row) {
        syncBoletosRow(row);
        checkCCSum();
      }
    }
  });

  wrap.querySelectorAll('.cc-row').forEach(syncBoletosRow);

  // Alerta estilo Bootstrap (igual que los mensajes flash del servidor)
  // para avisar que el guardado se bloqueó -- antes era un window.alert()
  // del navegador, que se ve como un diálogo ajeno al sistema.
  const ccAlertContainer = document.getElementById('cc-alert-container');

  function showCCBlockedAlert(message) {
    if (!ccAlertContainer) {
      window.alert('No se guardaron los cambios: ' + message);
      return;
    }

    ccAlertContainer.innerHTML = '';

    const alertEl = document.createElement('div');
    alertEl.className = 'alert alert-danger alert-dismissible fade show';
    alertEl.setAttribute('role', 'alert');

    const text = document.createElement('span');
    text.textContent = 'No se guardaron los cambios: ' + message;
    alertEl.appendChild(text);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'alert');
    closeBtn.setAttribute('aria-label', 'Close');
    alertEl.appendChild(closeBtn);

    ccAlertContainer.appendChild(alertEl);
    alertEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  if (saveButton) {
    saveButton.addEventListener('click', function (event) {
      const ok = checkCCSum();

      if (!ok) {
        event.preventDefault();
        showCCBlockedAlert(hint ? hint.textContent : 'la distribución de centros de costo debe sumar 100%.');
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