// contrato_detalle_fragment.js
(function () {
  'use strict';

  // ── Toggle visibilidad del campo monto según el check de penalización ──
  function initPenalizacionToggle() {
    const chk  = document.getElementById('fin_con_penalizacion');
    const wrap = document.getElementById('fin_monto_wrap');
    if (!chk || !wrap) return;

    function applyVisibility() {
      wrap.style.display = chk.checked ? '' : 'none';
    }

    chk.addEventListener('change', applyVisibility);
    applyVisibility();
  }

  // ── Formulario Finanzas (POST fetch con CSRF) ──
  function initFinanzasForm() {
    const frm = document.getElementById('frmFinanzasContrato');
    if (!frm) return;

    const btn  = document.getElementById('fin_guardar_btn');
    const msg  = document.getElementById('fin_msg');
    const csrf = frm.dataset.csrf || '';
    const url  = frm.dataset.url  || '';

    frm.addEventListener('submit', async function (e) {
      e.preventDefault();

      const chkPen  = document.getElementById('fin_con_penalizacion');
      const inpMonto = document.getElementById('fin_monto');
      const chkLib  = document.getElementById('fin_garantia_liberada');

      const body = new URLSearchParams();
      body.set('con_penalizacion',  chkPen  && chkPen.checked  ? '1' : '0');
      body.set('monto_penalizacion', inpMonto ? (inpMonto.value || '') : '');
      body.set('garantia_liberada', chkLib  && chkLib.checked  ? '1' : '0');

      if (btn) { btn.disabled = true; }
      if (msg) { msg.textContent = ''; msg.className = 'small mt-2'; }

      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrf,
            'X-Requested-With': 'XMLHttpRequest'
          },
          credentials: 'same-origin',
          body: body.toString()
        });

        const data = await resp.json().catch(function () { return {}; });

        if (resp.ok && data.ok) {
          if (msg) {
            msg.textContent = 'Guardado correctamente.';
            msg.className = 'small mt-2 text-success';
          }
        } else {
          if (msg) {
            msg.textContent = data.message || ('Error ' + resp.status);
            msg.className = 'small mt-2 text-danger';
          }
        }
      } catch (err) {
        if (msg) {
          msg.textContent = 'Error de red: ' + err.message;
          msg.className = 'small mt-2 text-danger';
        }
      } finally {
        if (btn) { btn.disabled = false; }
      }
    });
  }

  // Inicializar cuando el DOM esté listo (el fragment se carga dentro de un modal)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initPenalizacionToggle();
      initFinanzasForm();
    });
  } else {
    initPenalizacionToggle();
    initFinanzasForm();
  }
})();
