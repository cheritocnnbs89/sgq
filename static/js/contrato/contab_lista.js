async function openGarantiaDetalle(id) {
  const body = document.getElementById('garantiaDetalleBody');
  const modalEl = document.getElementById('modalGarantiaDetalle');

  if (!body || !modalEl) {
    return;
  }

  body.innerHTML = 'Cargando…';

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  const garantiaId = parseInt(id, 10);

  if (!garantiaId || garantiaId <= 0) {
    body.innerHTML = '<div class="alert alert-warning">ID de garantía inválido.</div>';
    return;
  }

  try {
    const url = `${window.location.origin}/contratos/ver/garantia/${encodeURIComponent(garantiaId)}/fragment?_=${Date.now()}`;

    const res = await fetch(url, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      },
      cache: 'no-store'
    });

    if (!res.ok) {
      body.innerHTML = `<div class="alert alert-danger">No se pudo cargar el detalle (HTTP ${res.status}).</div>`;
      return;
    }

    body.innerHTML = await res.text();
  } catch (error) {
    body.innerHTML = '<div class="alert alert-danger">No se pudo cargar el detalle.</div>';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.js-submit-on-change').forEach((input) => {
    input.addEventListener('change', () => {
      if (input.form) {
        input.form.submit();
      }
    });
  });

  document.querySelectorAll('.js-ver-garantia').forEach((button) => {
    button.addEventListener('click', () => {
      openGarantiaDetalle(button.dataset.garantiaId);
    });
  });

  document.querySelectorAll('.js-delete-garantia-form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const confirmed = window.confirm('¿Eliminar esta garantía? Esta acción no se puede deshacer.');

      if (!confirmed) {
        event.preventDefault();
      }
    });
  });
});