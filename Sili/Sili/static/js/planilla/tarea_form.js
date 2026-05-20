document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('tareaForm');
  if (!form) return;

  const depSel = document.getElementById('departamento_id');
  const userSel = document.getElementById('responsable_user_id');
  const nuevo = document.getElementById('nuevo_responsable');
  const hidResp = document.getElementById('responsable_id_hidden');
  const freqSel = document.getElementById('frecuencia');
  const boxSem = document.getElementById('box_dia_semana');
  const boxMes = document.getElementById('box_dia_mes');

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
      return;
    }

    if (frecuencia === 'mensual') {
      setHidden(boxSem, true);
      setHidden(boxMes, false);
      return;
    }

    setHidden(boxSem, true);
    setHidden(boxMes, true);
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
});
