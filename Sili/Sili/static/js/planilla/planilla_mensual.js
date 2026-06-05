(() => {
  const root = document.getElementById('planillaRoot');
  if (!root) return;

  window.Planilla = window.Planilla || {};
  if (!('pendingCheck' in window.Planilla)) window.Planilla.pendingCheck = null;

  window.Planilla.setPendingCheck = obj => {
    window.Planilla.pendingCheck = obj || null;
  };

  window.Planilla.getPendingCheck = () => window.Planilla.pendingCheck;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

  const urls = {
    toggleCheck: root.dataset.toggleCheckUrl || '',
    toggleEvidenceMode: root.dataset.toggleEvidenceModeUrl || '',
    evidencePost: root.dataset.evidencePostUrl || '',
    planillaBase: root.dataset.planillaBaseUrl || '',
    weeklyReport: root.dataset.weeklyReportUrl || ''
  };

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(payload),
      credentials: 'same-origin'
    });

    const contentType = res.headers.get('content-type') || '';

    if (res.redirected) {
      throw new Error(`La petición fue redirigida a ${res.url}. Revisa sesión/permisos.`);
    }

    if (!contentType.toLowerCase().includes('application/json')) {
      const text = await res.text();
      throw new Error(text || 'El servidor no devolvió JSON.');
    }

    const data = await res.json();

    if (!res.ok || data.ok === false) {
      throw new Error(data?.error || `Error HTTP ${res.status}`);
    }

    return data;
  }

  async function markCheck(tareaId, fecha, value, cbToReflect) {
    try {
      await postJSON(urls.toggleCheck, {
        tarea_id: tareaId,
        fecha: fecha,
        checked: Boolean(value)
      });

      if (cbToReflect) cbToReflect.checked = Boolean(value);
    } catch (error) {
      if (cbToReflect) cbToReflect.checked = !value;
      alert(`No se pudo marcar.\n${error.message}`);
    }
  }

  function initEvidenceModeSwitch() {
    const sw = document.getElementById('evidenceModeSwitch');
    if (!sw) return;

    sw.addEventListener('change', async () => {
      try {
        await postJSON(urls.toggleEvidenceMode, {
          enabled: sw.checked ? 1 : 0
        });

        root.dataset.evidenceMode = sw.checked ? '1' : '0';
      } catch (error) {
        alert(`No se pudo cambiar el modo de evidencia.\n${error.message}`);
        sw.checked = !sw.checked;
      }
    });
  }

  function initCheckToggles() {
    document.querySelectorAll('.planilla input.tick[data-date]').forEach(checkbox => {
      checkbox.addEventListener('change', event => {
        const el = event.currentTarget;
        const tr = el.closest('tr');
        const tareaId = tr?.dataset?.id;
        const fecha = el.dataset.date;
        const evidenceMode = parseInt(root.dataset.evidenceMode || '0', 10) === 1;

        if (!el.checked) {
          markCheck(tareaId, fecha, false, el);
          return;
        }

        if (evidenceMode) {
          event.preventDefault();
          el.checked = false;
          window.Planilla.setPendingCheck({ cb: el, tareaId, fecha });

          const tareaInput = document.getElementById('ev_tarea');
          const fechaInput = document.getElementById('ev_fecha');

          if (tareaInput) tareaInput.value = tareaId;
          if (fechaInput) fechaInput.value = fecha;

          new bootstrap.Modal(document.getElementById('evidenceModal')).show();
        } else {
          markCheck(tareaId, fecha, true, el);
        }
      });
    });
  }

  function initEvidenceForm() {
    const form = document.getElementById('evidenceForm');
    if (!form) return;

    form.addEventListener('submit', async event => {
      event.preventDefault();
      event.stopPropagation();

      try {
        const fd = new FormData(form);
        const res = await fetch(urls.evidencePost, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: fd,
          cache: 'no-store',
          credentials: 'same-origin'
        });

        const contentType = res.headers.get('content-type') || '';

        if (res.redirected) {
          throw new Error(`La petición fue redirigida a ${res.url}. Revisa sesión/permisos.`);
        }

        if (!contentType.toLowerCase().includes('application/json')) {
          const text = await res.text();
          throw new Error(text || 'El servidor no devolvió JSON.');
        }

        const data = await res.json();
        if (!res.ok || data.ok === false) {
          throw new Error(data?.error || 'Error al guardar evidencia');
        }

        const modalEl = document.getElementById('evidenceModal');
        (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)).hide();

        const pendingCheck = window.Planilla.getPendingCheck();
        if (pendingCheck?.cb) pendingCheck.cb.checked = true;

        window.Planilla.setPendingCheck(null);
        form.reset();
      } catch (error) {
        alert(`No se pudo guardar la evidencia.\n${error.message}`);
      }
    }, { capture: true });
  }

  function initFilters() {
    const form = document.getElementById('filtrosForm') || document.querySelector('.filter-bar');
    const month = document.getElementById('month');
    const res = document.getElementById('f_res');
    const freq = document.getElementById('f_freq');
    const dep = document.getElementById('f_dep');

    function computeYM() {
      const monthValue = (month?.value || '').trim();
      let year = root.dataset.year || '';
      let monthNumber = root.dataset.month || '';

      if (monthValue && monthValue.includes('-')) {
        const [yy, mm] = monthValue.split('-');
        if (/^\d{4}$/.test(yy)) year = yy;
        if (/^\d{1,2}$/.test(mm)) monthNumber = String(parseInt(mm, 10)).padStart(2, '0');
      }

      return { year, monthNumber };
    }

    function buildUrl() {
      const { year, monthNumber } = computeYM();
      const url = new URL(urls.planillaBase, window.location.origin);

      url.searchParams.set('year', year);
      url.searchParams.set('month', monthNumber);

      if (res?.value) url.searchParams.set('responsable_id', res.value);
      if (freq?.value) url.searchParams.set('frecuencia', freq.value);
      if (dep?.value) url.searchParams.set('departamento_id', dep.value);

      return url.toString();
    }

    function go(event) {
      event?.preventDefault();
      window.location.assign(buildUrl());
    }

    form?.addEventListener('submit', go);
    [res, freq, dep].forEach(element => element?.addEventListener('change', go));
    document.querySelector('.filter-bar')?.addEventListener('keydown', event => {
      if (event.key === 'Enter') {
        event.preventDefault();
        go(event);
      }
    });
  }

  function lockPastDays() {
    const lookbackDays = 30;

    function formatDate(date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    let todayStr = (root.dataset.today || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(todayStr)) {
      todayStr = formatDate(new Date());
    }

    const cutoff = new Date(`${todayStr}T00:00:00`);
    cutoff.setDate(cutoff.getDate() - lookbackDays);
    const cutoffStr = formatDate(cutoff);

    document.querySelectorAll('.planilla input.tick[data-date]').forEach(checkbox => {
      const checkboxDate = checkbox.getAttribute('data-date');
      const cell = checkbox.closest('td');

      if (checkboxDate < cutoffStr) {
        checkbox.disabled = true;
        checkbox.title = 'Cerrado por vencimiento';
        cell?.classList.add('is-locked');
      } else {
        checkbox.disabled = false;
        checkbox.removeAttribute('title');
        cell?.classList.remove('is-locked');
      }
    });
  }

  function initSendWeeklyReport() {
    const btn = document.getElementById('btnSendWeeklyReport');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      if (!urls.weeklyReport) {
        alert('URL del reporte no configurada.');
        return;
      }

      btn.disabled = true;
      const original = btn.innerHTML;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Enviando…';

      try {
        const data = await postJSON(urls.weeklyReport, {});
        btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Enviado';
        setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 3000);
      } catch (err) {
        alert(`Error al enviar reporte:\n${err.message}`);
        btn.innerHTML = original;
        btn.disabled = false;
      }
    });
  }

  initEvidenceModeSwitch();
  initCheckToggles();
  initEvidenceForm();
  initFilters();
  lockPastDays();
  initSendWeeklyReport();
})();
