function getCSRFToken() {
  const tokenInput = document.querySelector('input[name="csrf_token"]');
  return tokenInput ? tokenInput.value : '';
}

async function openAdjuntos(url, pedido, proveedor) {
  const title = document.getElementById('modalAdjuntosTitle');
  const body = document.getElementById('modalAdjuntosBody');
  const modalEl = document.getElementById('modalAdjuntos');

  if (!title || !body || !modalEl) return;

  title.textContent = `Adjuntos — Pedido ${pedido || ''} — ${proveedor || ''}`;
  body.innerHTML = 'Cargando…';

  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  try {
    const resp = await fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      cache: 'no-store'
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    body.innerHTML = await resp.text();
  } catch (error) {
    body.innerHTML = `
      <div class="alert alert-danger mb-0">
        No se pudo cargar el listado de adjuntos.
      </div>
    `;
  }
}

async function openContratoDetalle(contratoId) {
  const body = document.getElementById('modalContratoDetalleBody');
  const modalEl = document.getElementById('modalContratoDetalle');

  if (!body || !modalEl) return;

  body.innerHTML = 'Cargando…';

  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  try {
    const resp = await fetch(`/contratos/ver/contrato/${encodeURIComponent(contratoId)}/fragment`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      cache: 'no-store'
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    body.innerHTML = await resp.text();
  } catch (error) {
    body.innerHTML = `
      <div class="alert alert-danger mb-0">
        No se pudo cargar el detalle del contrato.
      </div>
    `;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.js-submit-on-change').forEach((input) => {
    input.addEventListener('change', () => {
      if (input.form) input.form.submit();
    });
  });

  document.querySelectorAll('.js-open-adjuntos').forEach((button) => {
    button.addEventListener('click', () => {
      openAdjuntos(
        button.dataset.url,
        button.dataset.pedido,
        button.dataset.proveedor
      );
    });
  });

  document.querySelectorAll('.js-open-contrato-detalle').forEach((button) => {
    button.addEventListener('click', () => {
      openContratoDetalle(button.dataset.contratoId);
    });
  });

  document.querySelectorAll('.js-delete-contrato-form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const confirmed = window.confirm('¿Eliminar este contrato? Esta acción no se puede deshacer.');
      if (!confirmed) event.preventDefault();
    });
  });
});