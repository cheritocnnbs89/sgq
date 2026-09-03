// Validación ligera del lado cliente (muestra qué falta y evita el submit)
(() => {
  const form = document.getElementById('frm-contrato');
  const alertBox = document.getElementById('client-validate-alert');
  const msgAnticipo = document.getElementById('msg-anticipo');

  if (!form || !alertBox) return;

  function showAlert(msg) {
    alertBox.replaceChildren();

    const wrapper = document.createElement('div');
    wrapper.className = 'alert alert-danger alert-dismissible fade show';
    wrapper.setAttribute('role', 'alert');

    const message = document.createElement('span');
    message.textContent = msg;

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    closeButton.setAttribute('aria-label', 'Close');

    wrapper.append(message, closeButton);
    alertBox.appendChild(wrapper);
  }

  form.addEventListener('submit', (ev) => {
    alertBox.replaceChildren();

    // limpiar estados previos
    form.querySelectorAll('.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
    if (msgAnticipo) msgAnticipo.classList.add('d-none');

    const required = form.querySelectorAll('[required]');
    const missing = [];
    let firstInvalid = null;

    required.forEach((el) => {
      const val = (el.value || '').trim();
      if (!val) {
        missing.push(el.dataset.label || el.name);
        el.classList.add('is-invalid');
        if (!firstInvalid) firstInvalid = el;
      }
    });

    if (missing.length) {
      ev.preventDefault();
      showAlert(`Campos obligatorios incompletos: ${missing.join(', ')}`);

      if (firstInvalid) {
        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstInvalid.focus();
      }
      return;
    }

    // Regla adicional: Valor anticipo <= Valor contrato
    const vContratoEl = form.elements.valor_contrato;
    const vAnticipoEl = form.elements.valor_anticipo;
    const vContrato = parseFloat((vContratoEl?.value || '0').replace(',', '')) || 0;
    const vAnticipo = parseFloat((vAnticipoEl?.value || '0').replace(',', '')) || 0;

    if (vAnticipo > vContrato) {
      ev.preventDefault();

      if (vAnticipoEl) vAnticipoEl.classList.add('is-invalid');
      if (vContratoEl) vContratoEl.classList.add('is-invalid');
      if (msgAnticipo) msgAnticipo.classList.remove('d-none');

      showAlert('El valor del anticipo no puede ser mayor que el valor del contrato.');

      const target = vAnticipoEl || vContratoEl;
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.focus();
      }
    }
  });
})();

