document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('tareaForm');
  if (!form) return;

  const depSel = document.getElementById('departamento_id');
  const userSel = document.getElementById('responsable_user_id');
  const nuevo = document.getElementById('nuevo_responsable');
  const hidResp = document.getElementById('responsable_id_hidden');
  const freqSel    = document.getElementById('frecuencia');
  const boxSem     = document.getElementById('box_dia_semana');
  const boxMes     = document.getElementById('box_dia_mes');
  const boxMesAnual = document.getElementById('box_mes_anual');

  const isEdit = form.dataset.isEdit === '1';
  const usersUrlPrefix = form.dataset.usersUrlPrefix || '/planilla-mensual/api/usuarios/by-dep/';

  function setHidden(el, hidden) {
    if (!el) return;
    el.classList.toggle('is-hidden', hidden);
  }

  function toggleDayBoxes() {
    const frecuencia = (freqSel?.value || '').toLowerCase();

    if (frecuencia === 'semanal') {
      setHidden(boxSem, false);
      setHidden(boxMes, true);
      setHidden(boxMesAnual, true);
      return;
    }

    if (frecuencia === 'mensual') {
      setHidden(boxSem, true);
      setHidden(boxMes, false);
      setHidden(boxMesAnual, true);
      return;
    }

    if (frecuencia === 'anual') {
      setHidden(boxSem, true);
      setHidden(boxMes, false);
      setHidden(boxMesAnual, false);
      return;
    }

    setHidden(boxSem, true);
    setHidden(boxMes, true);
    setHidden(boxMesAnual, true);
  }

  async function loadUsers(depid, keepSelection = false) {
    if (!userSel) return;

    if (!depid) {
      userSel.innerHTML = '<option value="">-- Seleccione --</option>';
      return;
    }

    const previousValue = keepSelection ? userSel.value : '';
    userSel.innerHTML = '<option value="">Cargando...</option>';

    try {
      const response = await fetch(`${usersUrlPrefix}${encodeURIComponent(depid)}`, {
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const users = await response.json();
      userSel.innerHTML = '<option value="">-- Seleccione --</option>';

      users.forEach(user => {
        const option = document.createElement('option');
        option.value = user.id;
        option.textContent = user.username + (user.email ? ` — ${user.email}` : '');
        userSel.appendChild(option);
      });

      if (keepSelection && previousValue) {
        userSel.value = previousValue;
      }
    } catch (error) {
      console.error(error);
      userSel.innerHTML = '<option value="">(Error al cargar)</option>';
    }
  }

  toggleDayBoxes();
  freqSel?.addEventListener('change', toggleDayBoxes);

  depSel?.addEventListener('change', () => {
    loadUsers(depSel.value, false);

    if (userSel) userSel.value = '';
    if (nuevo) nuevo.value = '';
    if (hidResp) hidResp.value = '';
  });

  userSel?.addEventListener('change', () => {
    const selectedOption = userSel.selectedOptions[0];

    if (!selectedOption || !selectedOption.value) {
      if (nuevo) nuevo.value = '';
      return;
    }

    const username = selectedOption.textContent.split('—')[0].trim();
    if (nuevo) nuevo.value = username;
    if (hidResp) hidResp.value = '';
  });

  if (!isEdit && depSel?.value) {
    loadUsers(depSel.value, false);
  }

  // ─── OKR / Resultado Clave ────────────────────────────────────────────────
  const okrSel      = document.getElementById('okr_id');
  const rcSel       = document.getElementById('resultado_clave_id');
  const btnNuevoOkr = document.getElementById('btn-nuevo-okr');
  const nuevoOkrWrap= document.getElementById('nuevo-okr-wrap');
  const nuevoOkrNom = document.getElementById('nuevo-okr-nombre');
  const btnGuarOkr  = document.getElementById('btn-guardar-okr');
  const btnCancOkr  = document.getElementById('btn-cancelar-okr');
  const btnNuevoRc  = document.getElementById('btn-nuevo-rc');
  const nuevoRcWrap = document.getElementById('nuevo-rc-wrap');
  const nuevoRcNom  = document.getElementById('nuevo-rc-nombre');
  const btnGuarRc   = document.getElementById('btn-guardar-rc');
  const btnCancRc   = document.getElementById('btn-cancelar-rc');

  function getCsrf() {
    return document.querySelector('meta[name="csrf-token"]')?.content
        || document.querySelector('input[name="csrf_token"]')?.value
        || '';
  }

  async function loadResultadosClave(okrId, selectedId) {
    if (!rcSel) return;
    if (!okrId) {
      rcSel.innerHTML = '<option value="">-- Seleccione primero un OKR --</option>';
      if (btnNuevoRc) btnNuevoRc.disabled = true;
      return;
    }
    rcSel.innerHTML = '<option value="">Cargando...</option>';
    try {
      const r = await fetch(`/planilla-mensual/api/okrs/${okrId}/resultados-clave`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const list = await r.json();
      rcSel.innerHTML = '<option value="">-- Seleccione Resultado Clave --</option>';
      list.forEach(rc => {
        const opt = document.createElement('option');
        opt.value = rc.id;
        opt.textContent = rc.nombre;
        if (selectedId && rc.id == selectedId) opt.selected = true;
        rcSel.appendChild(opt);
      });
      if (btnNuevoRc) btnNuevoRc.disabled = false;
    } catch {
      rcSel.innerHTML = '<option value="">(Error al cargar)</option>';
    }
  }

  // Al cambiar OKR → recargar resultados clave
  okrSel?.addEventListener('change', () => {
    loadResultadosClave(okrSel.value, null);
  });

  // Botón "+" Nuevo OKR
  btnNuevoOkr?.addEventListener('click', () => {
    nuevoOkrWrap?.classList.toggle('d-none');
    nuevoOkrNom?.focus();
  });
  btnCancOkr?.addEventListener('click', () => {
    nuevoOkrWrap?.classList.add('d-none');
    if (nuevoOkrNom) nuevoOkrNom.value = '';
  });
  btnGuarOkr?.addEventListener('click', async () => {
    const nombre = nuevoOkrNom?.value.trim();
    if (!nombre) { nuevoOkrNom?.focus(); return; }
    btnGuarOkr.disabled = true;
    try {
      const r = await fetch('/planilla-mensual/api/okrs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ nombre })
      });
      const data = await r.json();
      if (data.ok && data.id) {
        const opt = document.createElement('option');
        opt.value = data.id;
        opt.textContent = data.nombre;
        opt.selected = true;
        okrSel?.appendChild(opt);
        if (okrSel) okrSel.value = data.id;
        nuevoOkrWrap?.classList.add('d-none');
        if (nuevoOkrNom) nuevoOkrNom.value = '';
        loadResultadosClave(data.id, null);
      }
    } catch { /* silent */ }
    btnGuarOkr.disabled = false;
  });

  // Botón "+" Nuevo Resultado Clave
  btnNuevoRc?.addEventListener('click', () => {
    nuevoRcWrap?.classList.toggle('d-none');
    nuevoRcNom?.focus();
  });
  btnCancRc?.addEventListener('click', () => {
    nuevoRcWrap?.classList.add('d-none');
    if (nuevoRcNom) nuevoRcNom.value = '';
  });
  btnGuarRc?.addEventListener('click', async () => {
    const nombre = nuevoRcNom?.value.trim();
    const okrId  = okrSel?.value;
    if (!nombre || !okrId) { nuevoRcNom?.focus(); return; }
    btnGuarRc.disabled = true;
    try {
      const r = await fetch('/planilla-mensual/api/resultados-clave', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ nombre, okr_id: okrId })
      });
      const data = await r.json();
      if (data.ok && data.id) {
        const opt = document.createElement('option');
        opt.value = data.id;
        opt.textContent = data.nombre;
        opt.selected = true;
        rcSel?.appendChild(opt);
        if (rcSel) rcSel.value = data.id;
        nuevoRcWrap?.classList.add('d-none');
        if (nuevoRcNom) nuevoRcNom.value = '';
      }
    } catch { /* silent */ }
    btnGuarRc.disabled = false;
  });

  // Al cargar en modo editar: si ya hay OKR seleccionado, cargar sus RCs
  if (okrSel?.value) {
    const selectedRcId = rcSel?.querySelector('option[selected]')?.value
        || (rcSel?.options.length > 1 ? rcSel.value : null);
    loadResultadosClave(okrSel.value, selectedRcId);
  }
});
