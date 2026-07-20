// static/js/planilla/planilla_mensual.js
document.addEventListener('DOMContentLoaded', () => {
  console.log('[planilla] JS cargado');

  // ================== Filtros ==================
  const go = () => {
    const params = new URLSearchParams(location.search);
    const monthEl = document.getElementById('month');
    if (!monthEl || !monthEl.value) return;

    const dep = document.getElementById('f_dep')?.value || '';
    if (dep) params.set('departamento_id', dep); else params.delete('departamento_id');

    const [yy, mm] = monthEl.value.split('-');
    params.set('year', yy);
    params.set('month', mm);

    const rid = document.getElementById('f_res')?.value || '';
    const fr  = document.getElementById('f_freq')?.value || '';
    if (rid) params.set('responsable_id', rid); else params.delete('responsable_id');
    if (fr)  params.set('frecuencia', fr);       else params.delete('frecuencia');

    location.search = params.toString();
  };
  document.getElementById('btnFiltrar')?.addEventListener('click', go);
  document.getElementById('month')?.addEventListener('change', go);

  // ================== Modal Bootstrap ==================
  const modalEl = document.getElementById('evidenceModal');
  const form    = document.getElementById('evidenceForm');
  const obsEl   = form?.querySelector('textarea[name="obs"]');
  const fileEl  = form?.querySelector('input[name="file"]');
  let bsModal = null, activeCheckbox = null, saved = false;

  function ensureModal() {
    if (!window.bootstrap || !window.bootstrap.Modal) return null;
    if (!modalEl) return null;
    if (!bsModal) bsModal = new bootstrap.Modal(modalEl);
    return bsModal;
  }

  modalEl?.addEventListener('hidden.bs.modal', () => {
    if (!saved && activeCheckbox) activeCheckbox.checked = false;
    activeCheckbox = null;
    saved = false;
    form?.reset();
    const info = document.getElementById('ev_info');
    if (info) info.textContent = '';
  });

  const openModal = async (cb) => {
    const m = ensureModal();
    if (!m) {
      alert('No puedo abrir el modal (falta Bootstrap JS).');
      cb.checked = false;
      return;
    }
    activeCheckbox = cb;
    const tareaId = cb.closest('tr').dataset.id;
    const fecha   = cb.dataset.date;
    document.getElementById('ev_tarea').value = tareaId;
    document.getElementById('ev_fecha').value  = fecha;

    try {
      const meta = await fetch(`/planilla-mensual/evidencia/meta/${tareaId}/${fecha}`);
      if (meta.ok) {
        const data = await meta.json();
        if (obsEl) obsEl.value = data?.obs || '';
        const info = document.getElementById('ev_info');
        if (info) {
          if (data?.file_name) {
            info.innerHTML =
              `Archivo actual: <a target="_blank" ` +
              `href="/planilla-mensual/evidencia/${tareaId}/${fecha}">${data.file_name}</a>`;
          } else {
            info.textContent = 'Sin archivo previo';
          }
        }
      }
    } catch (e) {
      console.debug('[planilla] meta no disponible', e);
    }
    m.show();
  };

  // ================== Ticks (marcar / desmarcar) ==================
  const table = document.querySelector('.planilla');
  if (!table) return;

  const evidenceMode = () => (window.EVIDENCE_MODE ? 1 : 0);

  table.addEventListener('change', async (ev) => {
    const cb = ev.target.closest('input.tick');
    if (!cb) return;
    const tareaId = Number(cb.closest('tr').dataset.id);
    const fecha   = cb.dataset.date;

    if (cb.checked) {
      if (window.EVIDENCE_MODE === 1) {
        openModal(cb);
      } else {
        try {
          const r = await fetch('/planilla-mensual/check', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ tarea_id: tareaId, fecha, checked: true }),
          });
          if (!r.ok) throw new Error(await r.text());
        } catch (e) {
          alert('No se pudo marcar.\n' + (e.message || ''));
          cb.checked = false;
        }
      }
    } else {
      try {
        const r = await fetch('/planilla-mensual/check', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ tarea_id: tareaId, fecha, checked: false }),
        });
        if (!r.ok) throw new Error(await r.text());
        cb.closest('td')?.querySelector('.evi')?.remove();
      } catch (e) {
        alert('No se pudo desmarcar.\n' + (e.message || ''));
        cb.checked = true;
      }
    }
  });

  // Switch evidencia obligatoria
  document.getElementById('evidenceModeSwitch')?.addEventListener('change', async (e) => {
    const enabled = e.target.checked ? 1 : 0;
    try {
      const res = await fetch('/planilla-mensual/config/evidence-mode', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error(await res.text());
      window.EVIDENCE_MODE = enabled;
    } catch (err) {
      alert('No se pudo actualizar el modo de evidencia.\n' + (err.message || ''));
      e.target.checked = !enabled;
    }
  });

  // Prevenir que el click fuerce modal en modo OFF
  table.addEventListener('click', (ev) => {
    const cb = ev.target.closest('input.tick');
    if (!cb) return;
    if (evidenceMode() === 0) return;
    if (!cb.checked) setTimeout(() => { if (cb.checked) openModal(cb); }, 0);
  });

  // ================== Submit de evidencia ==================
  const MAX_MB = 10;
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!form) return;

    const f = fileEl?.files?.[0];
    if (f && f.size > MAX_MB * 1024 * 1024) {
      alert(`El archivo supera ${MAX_MB} MB.`);
      return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn?.setAttribute('disabled', 'disabled');

    try {
      const fd      = new FormData(form);
      const tareaId = fd.get('tarea_id');
      const fecha   = fd.get('fecha');

      const r = await fetch('/planilla-mensual/evidencia', { method: 'POST', body: fd });

      if (!r.ok) {
        const serverMsg = await r.text().catch(() => '');
        console.error('[planilla] fallo upload', r.status, serverMsg);
        if (r.status === 413) {
          alert(serverMsg || 'Archivo demasiado grande.');
        } else {
          alert(serverMsg || `No se pudo guardar la evidencia (HTTP ${r.status}).`);
        }
        return;
      }

      saved = true;
      ensureModal()?.hide();

      const cell = activeCheckbox?.closest('td');
      if (cell && !cell.querySelector('.evi')) {
        const a = document.createElement('a');
        a.className  = 'evi';
        a.target     = '_blank';
        a.textContent = '📎';
        a.href  = `/planilla-mensual/evidencia/${tareaId}/${fecha}`;
        a.title = 'Ver evidencia';
        cell.appendChild(a);
      }
    } catch (err) {
      console.error(err);
      alert('No se pudo guardar la evidencia.\n' + (err?.message || ''));
    } finally {
      btn?.removeAttribute('disabled');
    }
  });

  // ================== Botón reporte semanal (solo admin) ==================
  const btnWeekly = document.getElementById('btnSendWeeklyReport');
  if (btnWeekly) {
    btnWeekly.addEventListener('click', async () => {
      if (!confirm(
        '¿Enviar el reporte semanal de planilla ahora a todos los jefes?\n\n' +
        'Se enviarán correos con el resumen lunes–viernes de esta semana.'
      )) return;

      const originalHtml = btnWeekly.innerHTML;
      btnWeekly.disabled = true;
      btnWeekly.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
        ' Enviando…';

      try {
        // Token CSRF: busca primero el meta tag estándar de Flask-WTF,
        // luego el input oculto que ya existe en el formulario de evidencia.
        const csrfToken = (
          document.querySelector('meta[name="csrf-token"]')?.content ||
          document.querySelector('input[name="csrf_token"]')?.value  ||
          ''
        );

        // La URL viene del data attribute para no hardcodearla
        const root = document.getElementById('planillaRoot');
        const url  = root?.dataset?.weeklyReportUrl ||
                     '/planilla-mensual/admin/send-weekly-report';

        const res = await fetch(url, {
          method:  'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  csrfToken,
          },
          body: JSON.stringify({}),
        });

        let data = {};
        try { data = await res.json(); } catch (_) {}

        if (res.ok && data.ok) {
          const r = data.result || {};
          alert(
            '✅ Reporte enviado correctamente.\n\n' +
            `Correos enviados : ${r.sent   ?? '—'}\n` +
            `Errores          : ${r.errors ?? 0}\n`   +
            `Período          : ${r.periodo ?? '—'}`
          );
        } else {
          alert(
            '❌ Error al enviar el reporte:\n' +
            (data.error || `HTTP ${res.status}`)
          );
        }
      } catch (err) {
        alert('❌ Error de red:\n' + (err.message || String(err)));
      } finally {
        btnWeekly.disabled = false;
        btnWeekly.innerHTML = originalHtml;
      }
    });
  }
});
