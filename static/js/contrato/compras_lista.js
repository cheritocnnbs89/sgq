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

function initContratoDetalleFragment(container) {
  // Toggle visibilidad del monto según check penalización
  var chk  = container.querySelector('#fin_con_penalizacion');
  var wrap = container.querySelector('#fin_monto_wrap');
  if (chk && wrap) {
    function applyVis() { wrap.style.display = chk.checked ? '' : 'none'; }
    chk.addEventListener('change', applyVis);
    applyVis();
  }

  // Formulario Finanzas (AJAX POST)
  var frm = container.querySelector('#frmFinanzasContrato');
  if (frm) {
    var btn  = container.querySelector('#fin_guardar_btn');
    var msg  = container.querySelector('#fin_msg');
    var csrf = frm.dataset.csrf || '';
    var url  = frm.dataset.url  || '';

    frm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var chkPen  = container.querySelector('#fin_con_penalizacion');
      var inpMonto = container.querySelector('#fin_monto');
      var chkLib  = container.querySelector('#fin_garantia_liberada');

      var body = new URLSearchParams();
      body.set('con_penalizacion',  chkPen  && chkPen.checked  ? '1' : '0');
      body.set('monto_penalizacion', inpMonto ? (inpMonto.value || '') : '');
      body.set('garantia_liberada', chkLib  && chkLib.checked  ? '1' : '0');

      if (btn) btn.disabled = true;
      if (msg) { msg.textContent = ''; msg.className = 'small mt-2'; }

      try {
        var resp = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrf,
            'X-Requested-With': 'XMLHttpRequest'
          },
          credentials: 'same-origin',
          body: body.toString()
        });
        var data = await resp.json().catch(function () { return {}; });
        if (resp.ok && data.ok) {
          if (msg) { msg.textContent = 'Guardado correctamente.'; msg.className = 'small mt-2 text-success'; }
        } else {
          if (msg) { msg.textContent = data.message || ('Error ' + resp.status); msg.className = 'small mt-2 text-danger'; }
        }
      } catch (err) {
        if (msg) { msg.textContent = 'Error de red: ' + err.message; msg.className = 'small mt-2 text-danger'; }
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }
}

async function openContratoDetalle(contratoId) {
  var body = document.getElementById('modalContratoDetalleBody');
  var modalEl = document.getElementById('modalContratoDetalle');

  if (!body || !modalEl) return;

  var loadingDiv = document.createElement('div');
  loadingDiv.textContent = 'Cargando…';
  while (body.firstChild) body.removeChild(body.firstChild);
  body.appendChild(loadingDiv);

  var modal = new bootstrap.Modal(modalEl);
  modal.show();

  try {
    var resp = await fetch('/contratos/ver/contrato/' + encodeURIComponent(contratoId) + '/fragment', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      cache: 'no-store'
    });

    if (!resp.ok) throw new Error('HTTP ' + resp.status);

    var html = await resp.text();
    body.innerHTML = html;
    initContratoDetalleFragment(body);
  } catch (error) {
    while (body.firstChild) body.removeChild(body.firstChild);
    var errDiv = document.createElement('div');
    errDiv.className = 'alert alert-danger mb-0';
    errDiv.textContent = 'No se pudo cargar el detalle del contrato.';
    body.appendChild(errDiv);
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