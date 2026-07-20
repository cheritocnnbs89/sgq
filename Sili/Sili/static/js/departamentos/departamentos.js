(function () {
  const key = 'ui_theme';
  const root = document.documentElement;

  function apply(mode) {
    root.classList.toggle('theme-dark', mode === 'dark');
    localStorage.setItem(key, mode);
  }

  apply(
    localStorage.getItem(key) ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  );

  document.getElementById('themeToggle')?.addEventListener('click', () => {
    apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
  });
})();

(function () {
  const toolbarForm = document.getElementById('toolbarForm');
  if (toolbarForm) {
    toolbarForm.addEventListener('submit', (event) => {
      event.preventDefault();
    });
  }

  const table = document.getElementById('tabla-deptos');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr[data-row="1"]'));
  const input = document.getElementById('liveFilter');
  const countTotal = document.getElementById('countTotal');
  const countVisibles = document.getElementById('countVisibles');

  function applyFilter() {
    const term = (input?.value || '').toLowerCase().trim();

    rows.forEach((row) => {
      const text = (row.innerText || row.textContent || '').toLowerCase();
      const visible = !term || text.includes(term);
      row.classList.toggle('row-hidden', !visible);
    });

    if (countTotal) countTotal.textContent = String(rows.length);
    if (countVisibles) {
      countVisibles.textContent = String(
        rows.filter((row) => !row.classList.contains('row-hidden')).length
      );
    }
  }

  input?.addEventListener('input', applyFilter);
  document.getElementById('btnSearch')?.addEventListener('click', applyFilter);
  document.getElementById('btnClear')?.addEventListener('click', () => {
    if (input) input.value = '';
    applyFilter();
    input?.focus();
  });

  if (countTotal) countTotal.textContent = String(rows.length);
  applyFilter();
})();

(function () {
  document.querySelectorAll('.js-confirm-delete').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const ok = window.confirm('¿Eliminar departamento?');
      if (!ok) {
        event.preventDefault();
      }
    });
  });
})();

(function () {
  const triggerSelector = '[data-bs-target="#modalBulkDeptos"], [href="#modalBulkDeptos"]';
  const modal = document.getElementById('modalBulkDeptos');
  if (!modal) return;

  let opener = null;

  document.addEventListener('click', (event) => {
    const trigger = event.target.closest(triggerSelector);
    if (trigger) opener = trigger;
  });

  modal.addEventListener('hide.bs.modal', () => {
    const active = document.activeElement;
    if (active && modal.contains(active)) {
      active.blur();
    }
  });

  modal.addEventListener('hidden.bs.modal', () => {
    opener?.focus?.();
  });
})();
