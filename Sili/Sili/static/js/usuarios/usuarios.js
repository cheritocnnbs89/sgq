// ── Seleccionar todos los visibles ───────────────────────────────────────
document.addEventListener('change', function (e) {
  if (e.target && e.target.id === 'chk-select-all') {
    const checked = e.target.checked;
    // Solo marca los checkboxes de filas visibles (paginación activa)
    document.querySelectorAll('tbody tr:not([style*="display: none"]) .chk-user').forEach(ch => {
      ch.checked = checked;
    });
  }
});

// ── Eliminar usuario (fetch) ──────────────────────────────────────────────
document.addEventListener('click', function (e) {
  const btn = e.target.closest('.js-user-eliminar');
  if (!btn) return;

  const userId = btn.dataset.userId;
  const nombre = btn.dataset.nombre || '';

  if (!confirm(`¿Eliminar al usuario "${nombre}"?\n\nEsta acción NO se puede deshacer.`)) {
    return;
  }

  const csrf = (document.getElementById('csrfToken') || {}).value || '';

  fetch(`/usuarios/${userId}/eliminar`, {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      ...(csrf ? { 'X-CSRFToken': csrf } : {})
    },
    credentials: 'same-origin'
  })
    .then(async (r) => {
      if (!r.ok) {
        const txt = await r.text();
        console.error('Error eliminar usuario:', r.status, txt);
        alert(`No se pudo eliminar (HTTP ${r.status}). Revisa consola.`);
        return;
      }
      window.location.reload();
    })
    .catch(err => {
      console.error(err);
      alert('Error inesperado al eliminar el usuario.');
    });
});

// ── Asignar jefe a seleccionados ─────────────────────────────────────────
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-asignar-jefe')) return;

  const jefeId = document.getElementById('bulk-jefe-id').value;
  if (!jefeId) {
    alert('Debe seleccionar un jefe antes de asignar.');
    return;
  }

  const seleccionados = Array.from(document.querySelectorAll('.chk-user:checked'));
  if (seleccionados.length === 0) {
    alert('Debe seleccionar al menos un usuario.');
    return;
  }

  document.getElementById('form-jefe-id-hidden').value = jefeId;

  const container = document.getElementById('form-asignar-jefe-ids');
  container.innerHTML = '';
  seleccionados.forEach(ch => {
    const inp = document.createElement('input');
    inp.type = 'hidden';
    inp.name = 'user_ids';
    inp.value = ch.value;
    container.appendChild(inp);
  });

  document.getElementById('form-asignar-jefe').submit();
});

// ── Deshabilitar seleccionados ────────────────────────────────────────────
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-deshabilitar-masivo')) return;

  const seleccionados = Array.from(document.querySelectorAll('.chk-user:checked'));
  if (seleccionados.length === 0) {
    alert('Debe seleccionar al menos un usuario.');
    return;
  }

  if (!confirm(`¿Deshabilitar ${seleccionados.length} usuario(s) seleccionado(s)?`)) return;

  const container = document.getElementById('form-deshabilitar-ids');
  container.innerHTML = '';
  seleccionados.forEach(ch => {
    const inp = document.createElement('input');
    inp.type = 'hidden';
    inp.name = 'user_ids';
    inp.value = ch.value;
    container.appendChild(inp);
  });

  document.getElementById('form-deshabilitar').submit();
});

// ── Paginación ────────────────────────────────────────────────────────────
(function () {
  const table = document.querySelector('.table tbody');
  const pager = document.querySelector('.recl-pagination');
  if (!table || !pager) return;

  const sizeSelect = pager.querySelector('.js-page-size');
  const btnPrev    = pager.querySelector('.js-page-prev');
  const btnNext    = pager.querySelector('.js-page-next');
  const info       = pager.querySelector('.js-page-info');

  let currentPage = 1;

  function render() {
    const rows = Array.from(table.querySelectorAll('tr'));
    const pageSize   = Number(sizeSelect.value || 10);
    const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1)          currentPage = 1;

    const start = (currentPage - 1) * pageSize;
    const end   = start + pageSize;

    rows.forEach((tr, i) => {
      tr.style.display = (i >= start && i < end) ? '' : 'none';
    });

    info.textContent = `Página ${currentPage} de ${totalPages}`;
    btnPrev.disabled = currentPage <= 1;
    btnNext.disabled = currentPage >= totalPages;
    pager.classList.toggle('d-none', rows.length === 0);
  }

  sizeSelect.addEventListener('change', function () {
    currentPage = 1;
    render();
  });

  btnPrev.addEventListener('click', function () {
    currentPage--;
    render();
  });

  btnNext.addEventListener('click', function () {
    currentPage++;
    render();
  });

  render();
})();
