(function () {
  const form = document.getElementById('form-garantia');
  const sel = document.getElementById('contrato_id');
  const btn = document.getElementById('btnVerContrato');
  const btnVolver = document.getElementById('btnVolver');
  const btnGuardar = document.getElementById('btnGuardar');
  const modalEl = document.getElementById('modalContrato');
  const modalSalirEl = document.getElementById('modalSalir');
  const salirConfirmado = document.getElementById('salirConfirmado');

  if (!form) {
    return;
  }

  const mode = form.dataset.mode || 'new';
  const backUrl = form.dataset.backUrl || '';

  let bsModal = null;
  let bsSalir = null;
  let initialSnapshot = null;
  let pendingNavigateTo = null;

  const STORAGE_KEY = `contab_garantia_autosave_${mode}`;

  function ensureModal() {
    if (!bsModal && modalEl) {
      bsModal = new bootstrap.Modal(modalEl);
    }

    return bsModal;
  }

  function ensureSalirModal() {
    if (!bsSalir && modalSalirEl) {
      bsSalir = new bootstrap.Modal(modalSalirEl);
    }

    return bsSalir;
  }

  function serializeForm() {
    const data = {};

    Array.from(form.elements).forEach((el) => {
      if (!el.name) {
        return;
      }

      if (el.type === 'file') {
        return;
      }

      if (el.type === 'checkbox' || el.type === 'radio') {
        data[el.name] = el.checked ? '1' : '0';
        return;
      }

      data[el.name] = el.value;
    });

    return data;
  }

  function fillForm(data) {
    if (!data) {
      return;
    }

    Array.from(form.elements).forEach((el) => {
      if (!el.name) {
        return;
      }

      if (el.type === 'file') {
        return;
      }

      const value = data[el.name];

      if (value === undefined) {
        return;
      }

      if (el.type === 'checkbox' || el.type === 'radio') {
        el.checked = value === '1' || value === true;
        return;
      }

      el.value = value;
    });
  }

  function isDirty() {
    const now = serializeForm();
    return JSON.stringify(now) !== JSON.stringify(initialSnapshot);
  }

  function updateButton() {
    if (btn) {
      btn.disabled = !(sel && sel.value);
    }
  }

  async function openContratoModal() {
    if (!sel || !sel.value) {
      return;
    }

    const url = `/contratos/ver/contrato/${encodeURIComponent(String(sel.value))}/fragment`;
    const body = document.getElementById('modalContratoBody');

    if (body) {
      body.textContent = 'Cargando…';
    }

    try {
      const resp = await fetch(url, {
        headers: {
          'X-Requested-With': 'fetch'
        }
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      if (body) {
        body.innerHTML = await resp.text();
      }
    } catch (error) {
      if (body) {
        body.innerHTML = '<div class="text-danger">No se pudo cargar el detalle del contrato.</div>';
      }
    }

    const modal = ensureModal();

    if (modal) {
      modal.show();
    }
  }

  try {
    const saved = sessionStorage.getItem(STORAGE_KEY);

    if (saved) {
      fillForm(JSON.parse(saved));
    }
  } catch (error) {
    // No hacer nada si sessionStorage falla.
  }

  initialSnapshot = serializeForm();

  form.addEventListener('input', () => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(serializeForm()));
    } catch (error) {
      // No hacer nada si sessionStorage falla.
    }
  });

  if (sel) {
    sel.addEventListener('change', updateButton);
  }

  if (btn) {
    btn.addEventListener('click', openContratoModal);
  }

  if (btnVolver) {
    btnVolver.addEventListener('click', (event) => {
      if (!isDirty()) {
        return;
      }

      event.preventDefault();
      pendingNavigateTo = btnVolver.getAttribute('href') || backUrl;

      const salirModal = ensureSalirModal();

      if (salirModal) {
        salirModal.show();
      }
    });
  }

  window.addEventListener('beforeunload', (event) => {
    if (!isDirty()) {
      return;
    }

    event.preventDefault();
    event.returnValue = '';
  });

  if (salirConfirmado) {
    salirConfirmado.addEventListener('click', () => {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        // No hacer nada si sessionStorage falla.
      }

      window.location.href = pendingNavigateTo || backUrl;
    });
  }

  if (btnGuardar) {
    btnGuardar.addEventListener('click', () => {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (error) {
        // No hacer nada si sessionStorage falla.
      }
    });
  }

  updateButton();
})();