document.addEventListener('change', function (e) {
  if (e.target && e.target.id === 'chk-select-all') {
    const checked = e.target.checked;
    document.querySelectorAll('.chk-user').forEach(ch => {
      ch.checked = checked;
    });
  }
});

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
