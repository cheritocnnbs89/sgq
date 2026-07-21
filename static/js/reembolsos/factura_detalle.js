document.addEventListener('DOMContentLoaded', function () {
  const dataEl = document.getElementById('factura-detalle-data');
  const el = document.getElementById('barcodeClave');
  const clave = dataEl ? (dataEl.getAttribute('data-clave-acceso') || '') : '';

  if (!el) return;
  if (!clave) return;

  function renderUnavailableMessage() {
    el.outerHTML = '<div class="text-muted small">No se pudo cargar JsBarcode. Usa una copia local del archivo si tu CSP bloquea CDNs.</div>';
  }

  function renderBarcode() {
    if (typeof window.JsBarcode !== 'function') {
      renderUnavailableMessage();
      return;
    }

    try {
      window.JsBarcode(el, clave, {
        format: 'CODE128',
        displayValue: false,
        margin: 0,
        height: 62,
        width: 1.4
      });
    } catch (e) {
      console.error('[barcode] error:', e);
    }
  }

  if (typeof window.JsBarcode === 'function') {
    renderBarcode();
    return;
  }

  const localScript = document.createElement('script');
  localScript.src = '/static/js/JsBarcode.all.min.js';
  localScript.onload = renderBarcode;
  localScript.onerror = renderUnavailableMessage;
  document.body.appendChild(localScript);
});