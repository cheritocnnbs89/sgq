// static/js/planilla_mensual.js
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
    const fr = document.getElementById('f_freq')?.value || '';
    if (rid) params.set('responsable_id', rid); else params.delete('responsable_id');
    if (fr) params.set('frecuencia', fr); else params.delete('frecuencia');

    location.search = params.toString();
  };
  document.getElementById('btnFiltrar')?.addEventListener('click', go);
  document.getElementById('month')?.addEventListener('change', go);

  // ================== Modal Bootstrap ==================
  const modalEl = document.getElementById('evidenceModal');
  const form = document.getElementById('evidenceForm');
  const obsEl = form?.querySelector('textarea[name="obs"]');
  const fileEl = document.getElementById('ev_file_input') || form?.querySelector('input[name="file"]');
  const dropZone = document.getElementById('ev_drop_zone');
  const dropLabel = document.getElementById('ev_drop_label');
  let bsModal = null, activeCheckbox = null, saved = false;

  // ──────────────────────────────────────────────
  // Helper: asignar un File al input de archivo
  // ──────────────────────────────────────────────
  function setDroppedFile(file) {
    if (!file || !fileEl) return;
    if (!file.type.startsWith('image/') && file.type !== 'application/pdf') {
      alert('Solo se permiten imágenes o PDF.');
      return;
    }
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileEl.files = dt.files;
    } catch (_) { /* navegadores sin DataTransfer constructor */ }
    if (dropLabel) dropLabel.textContent = '✅ ' + (file.name || 'imagen pegada');
    if (dropZone) dropZone.classList.add('has-file');
  }

  // ── Drag & drop sobre la zona ──
  dropZone?.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer?.files?.[0];
    if (file) setDroppedFile(file);
  });

  // ── Pegar con Ctrl+V (modal abierto) ──
  modalEl?.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) { setDroppedFile(file); break; }
      }
    }
  });

  function ensureModal() {
    if (!window.bootstrap || !window.bootstrap.Modal) return null;
    if (!modalEl) return null;
    if (!bsModal) bsModal = new bootstrap.Modal(modalEl);
    return bsModal;
  }

  modalEl?.addEventListener('hidden.bs.modal', () => {
    if (!saved && activeCheckbox) activeCheckbox.checked = false;
    activeCheckbox = null; saved = false;
    form?.reset();
    obsEl?.classList.remove('is-invalid');
    const obsErrEl = document.getElementById('obs_error');
    if (obsErrEl) obsErrEl.style.display = '';
    if (dropZone) dropZone.classList.remove('has-file', 'drag-over');
    if (dropLabel) dropLabel.textContent = 'Selecciona, arrastra o pega una imagen/PDF aquí (Ctrl+V)';
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
    const fecha = cb.dataset.date;
    document.getElementById('ev_tarea').value = tareaId;
    document.getElementById('ev_fecha').value = fecha;

    try {
      const meta = await fetch(`/planilla-mensual/evidencia/meta/${tareaId}/${fecha}`);
      if (meta.ok) {
        const data = await meta.json();
        if (obsEl) obsEl.value = data?.obs || '';
        if (data?.file_name) {
          if (dropLabel) dropLabel.innerHTML = `📎 Archivo actual: <a target="_blank" href="/planilla-mensual/evidencia/${tareaId}/${fecha}">${data.file_name}</a>`;
          if (dropZone) dropZone.classList.add('has-file');
        } else {
          if (dropLabel) dropLabel.textContent = 'Selecciona, arrastra o pega una imagen/PDF aquí (Ctrl+V)';
          if (dropZone) dropZone.classList.remove('has-file');
        }
      }
    } catch (e) {
      console.debug('[planilla] meta no disponible', e);
    }
    m.show();
  };

  // ================== Ticks (marcar / desmarcar) ==================
  // ================== Ticks (marcar / desmarcar) ==================
  const table = document.querySelector('.planilla');
  if (!table) return;

  // helper para leer la bandera (inyectada por el template)
  const evidenceMode = () => (window.EVIDENCE_MODE ? 1 : 0);

table.addEventListener('change', async (ev) => {
  const cb = ev.target.closest('input.tick'); if (!cb) return;
  const tareaId = Number(cb.closest('tr').dataset.id);
  const fecha   = cb.dataset.date;

  if (cb.checked) {
    if (window.EVIDENCE_MODE === 1) {
      openModal(cb); // obligatorio con evidencia
    } else {
      // modo ligero: marcar directo
      try {
        const r = await fetch('/planilla-mensual/check', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tarea_id: tareaId, fecha, checked: true })
        });
        if (!r.ok) throw new Error(await r.text());
        // opcional: añadir clip si quieres marcar visualmente, pero no hay evidencia
      } catch (e) {
        alert('No se pudo marcar.\n' + (e.message || ''));
        cb.checked = false;
      }
    }
  } else {
    // desmarcar (igual que tenías)
    try {
      const r = await fetch('/planilla-mensual/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tarea_id: tareaId, fecha, checked: false })
      });
      if (!r.ok) throw new Error(await r.text());
      cb.closest('td')?.querySelector('.evi')?.remove();
    } catch (e) {
      alert('No se pudo desmarcar.\n' + (e.message || ''));
      cb.checked = true;
    }
  }
});


  // (OPCIONAL) Si el template tiene un switch para la bandera, refleja cambios sin recargar:
document.getElementById('evidenceModeSwitch')?.addEventListener('change', async (e) => {
  const enabled = e.target.checked ? 1 : 0;
  try {
    const res = await fetch('/planilla-mensual/config/evidence-mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
    if (!res.ok) throw new Error(await res.text());
    window.EVIDENCE_MODE = enabled;
  } catch (err) {
    alert('No se pudo actualizar el modo de evidencia.\n' + (err.message || ''));
    e.target.checked = !enabled; // revertir UI
  }
});

  // ================== (IMPORTANTE) Desactiva el "abrir modal al click" en modo OFF ==================
  table.addEventListener('click', (ev) => {
    const cb = ev.target.closest('input.tick'); if (!cb) return;
    if (evidenceMode() === 0) return; // en modo OFF nunca fuerces modal
    if (!cb.checked) setTimeout(() => { if (cb.checked) openModal(cb); }, 0);
  });

  // ================== Submit de evidencia ==================
  const MAX_MB = 10; // validación rápida en cliente (el servidor valida de nuevo)
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!form) return;

    // Validación: observación obligatoria
    const obsVal = obsEl?.value?.trim() || '';
    const obsErrEl = document.getElementById('obs_error');
    if (!obsVal) {
      obsEl?.classList.add('is-invalid');
      if (obsErrEl) obsErrEl.style.display = 'block';
      obsEl?.focus();
      return;
    }
    obsEl?.classList.remove('is-invalid');
    if (obsErrEl) obsErrEl.style.display = '';

    const f = fileEl?.files?.[0];
    if (f && f.size > MAX_MB * 1024 * 1024) {
      alert(`El archivo supera ${MAX_MB} MB.`);
      return;
    }

    const btn = form.querySelector('button[type="submit"]');
    btn?.setAttribute('disabled', 'disabled');

    try {
      const fd = new FormData(form);
      const tareaId = fd.get('tarea_id');
      const fecha = fd.get('fecha');

      const r = await fetch('/planilla-mensual/evidencia', { method: 'POST', body: fd });

      if (!r.ok) {
        // lee el texto devuelto por Flask para mostrar el motivo real
        const serverMsg = await r.text().catch(() => '');
        console.error('[planilla] fallo upload', r.status, serverMsg);
        // mensajes más amables para códigos comunes
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
        a.className = 'evi';
        a.target = '_blank';
        a.textContent = '📎';
        a.href = `/planilla-mensual/evidencia/${tareaId}/${fecha}`;
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
});
