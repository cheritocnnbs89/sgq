// selectedEstados / selectedTipos / selectedDeptos removed — filters moved to top-bar selects

(function initTheme() {
  const key = 'ui_theme';
  const root = document.documentElement;

  const apply = mode => {
    root.classList.toggle('theme-dark', mode === 'dark');
    localStorage.setItem(key, mode);
  };

  apply(
    localStorage.getItem(key) ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  );

  document.getElementById('themeToggle')?.addEventListener('click', () => {
    apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
  });
})();

// ── Modal detalle tarea — independiente de la tabla ──────────────────
(function initTareaModal() {
  const tdBackdrop = document.getElementById('tdModalBackdrop');
  const tdClose    = document.getElementById('tdModalClose');
  if (!tdBackdrop) return;

  function tdOpenModal(btn) {
    const d = btn.dataset;
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '—'; };

    setText('tdModalCodigo', d.tareaId);
    setText('tdModalTitulo', d.tareaTitulo);
    setText('tdModalDesc',   d.tareaDesc || '(Sin descripción)');

    const meta = document.getElementById('tdModalMeta');
    if (meta) {
      meta.innerHTML = '';
      [['bi-flag', d.tareaEstado], ['bi-tag', d.tareaTipo], ['bi-bar-chart', d.tareaAvance], ['bi-building', d.tareaEmpresa]]
        .forEach(([icon, val]) => {
          if (!val || val === '—') return;
          const sp = document.createElement('span');
          sp.innerHTML = '<i class="bi ' + icon + '"></i>';
          sp.appendChild(document.createTextNode(' ' + val));
          meta.appendChild(sp);
        });
    }

    [['tdModalPersonas', [['Responsable', d.tareaResponsable], ['Solicitante', d.tareaSolicitante], ['Departamento', d.tareaDepto]]],
     ['tdModalFechas',   [['Inicio planificado', d.tareaInicio], ['Fin planificado', d.tareaFin]]]
    ].forEach(([containerId, items]) => {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = '';
      items.forEach(([label, val]) => {
        const div = document.createElement('div');
        div.className = 'td-modal-item';
        const labelEl = document.createElement('div');
        labelEl.className = 'td-modal-label';
        labelEl.textContent = label;
        const valEl = document.createElement('div');
        valEl.className = 'td-modal-value';
        valEl.textContent = val || '—';
        div.appendChild(labelEl);
        div.appendChild(valEl);
        container.appendChild(div);
      });
    });

    const btnVer    = document.getElementById('tdBtnVer');
    const btnEditar = document.getElementById('tdBtnEditar');
    if (btnVer) btnVer.href = d.tareaUrlVer || '#';
    if (btnEditar) {
      if (d.tareaUrlEditar) { btnEditar.href = d.tareaUrlEditar; btnEditar.classList.remove('d-none'); }
      else { btnEditar.classList.add('d-none'); }
    }

    tdBackdrop.classList.add('visible');
    tdBackdrop.setAttribute('aria-hidden', 'false');
    document.body.classList.add('bs-modal-open');
  }

  function tdCloseModal() {
    tdBackdrop.classList.remove('visible');
    tdBackdrop.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('bs-modal-open');
  }

  document.querySelectorAll('.js-tarea-detalle').forEach(function(btn) {
    btn.addEventListener('click', function(e) { e.preventDefault(); tdOpenModal(btn); });
  });

  tdClose?.addEventListener('click', tdCloseModal);
  tdBackdrop.addEventListener('click', function(e) { if (e.target === tdBackdrop) tdCloseModal(); });
  document.addEventListener('keydown', function(e) { if (e.key === 'Escape' && tdBackdrop.classList.contains('visible')) tdCloseModal(); });
})();

document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('tabla-tareas');
  if (!table) return;

  const tbody = table.querySelector('tbody:last-of-type');
  const rows = [...tbody.querySelectorAll('tr[data-row="1"]')];

  const info = document.getElementById('tableInfo');
  const pager = document.getElementById('pagination');
  const countTotal = document.getElementById('countTotal');
  const countVisibles = document.getElementById('countVisibles');
  const noResultsDiv = document.getElementById('noResults');

  const qInp   = document.getElementById('liveFilter');
  const fEstado = document.getElementById('fEstado');
  const fTipo   = document.getElementById('fTipo');
  const fProp   = document.getElementById('fProp');
  const fDepto  = document.getElementById('fDepto');

  let pageLength = parseInt(localStorage.getItem('tareas_page_len') || '10', 10);
  let currentPage = 1;
  let currentSortCol = null;
  let currentSortDir = null;

  rows.forEach(row => { row.dataset.match = '1'; });

  // ── Helpers ─────────────────────────────────────────────────

  function textOf(row, dataTh) {
    return (row.querySelector(`td[data-th="${dataTh}"]`)?.innerText || '').trim();
  }

  function matchedRows() {
    return rows.filter(row => row.dataset.match !== '0');
  }

  function updateInfo(start, end, total) {
    if (info) info.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total}`;
    if (countTotal) countTotal.textContent = rows.length;
    if (countVisibles) countVisibles.textContent = total;
    noResultsDiv?.classList.toggle('d-none', total !== 0);
  }

  function makePageItem(label, page, disabled = false, active = false) {
    const li = document.createElement('li');
    li.className = `page-item${disabled ? ' disabled' : ''}${active ? ' active' : ''}`;
    const link = document.createElement('a');
    link.className = 'page-link';
    link.href = '#';
    link.textContent = label;
    link.addEventListener('click', event => {
      event.preventDefault();
      if (!disabled) { currentPage = page; render(); }
    });
    li.appendChild(link);
    return li;
  }

  function renderPagination(totalPages) {
    if (!pager) return;
    pager.innerHTML = '';
    const total = Math.max(1, totalPages);
    const start = Math.max(1, currentPage - 3);
    const end = Math.min(total, start + 6);
    pager.appendChild(makePageItem('Anterior', currentPage - 1, currentPage === 1));
    for (let page = start; page <= end; page += 1) {
      pager.appendChild(makePageItem(String(page), page, false, page === currentPage));
    }
    pager.appendChild(makePageItem('Siguiente', currentPage + 1, currentPage === total));
  }

  function render() {
    const list = matchedRows();
    const total = list.length;
    const totalPages = Math.max(1, Math.ceil(total / pageLength));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);
    rows.forEach(row => row.classList.add('d-none'));
    const start = (currentPage - 1) * pageLength;
    const end = Math.min(start + pageLength, total);
    for (let i = start; i < end; i += 1) list[i].classList.remove('d-none');
    updateInfo(start, end, total);
    renderPagination(totalPages);
  }

  // ── Filtrado ─────────────────────────────────────────────────

  function applyFilters() {
    const q        = (qInp?.value    || '').toLowerCase().trim();
    const estadoVal = fEstado?.value || '';
    const tipoVal   = fTipo?.value   || '';
    const propVal   = (fProp?.value  || '').toLowerCase().trim();
    const deptoVal  = fDepto?.value  || '';

    rows.forEach(row => {
      const rowText      = row.innerText.toLowerCase();
      const estado       = textOf(row, 'Estado');
      const tipo         = textOf(row, 'Tipo');
      const responsable  = textOf(row, 'Responsable').toLowerCase();
      const departamento = textOf(row, 'Departamento');

      const okQ      = !q        || rowText.includes(q);
      const okEstado = !estadoVal || estado       === estadoVal;
      const okTipo   = !tipoVal  || tipo          === tipoVal;
      const okProp   = !propVal  || responsable.includes(propVal);
      const okDepto  = !deptoVal || departamento  === deptoVal;

      row.dataset.match = (okQ && okEstado && okTipo && okProp && okDepto) ? '1' : '0';
    });

    currentPage = 1;
    render();
  }

  // ── Ordenamiento ─────────────────────────────────────────────

  function parseDate(value) {
    if (!value) return null;
    const normalized = value.replace(/\s+/g, 'T');
    const d = new Date(normalized);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function cellText(row, index) {
    return (row.querySelector(`td:nth-child(${index})`)?.innerText || '').trim();
  }

  function updateSortButtons() {
    document.querySelectorAll('.sort-btn').forEach(button => {
      const active = (
        button.dataset.sortCol === currentSortCol &&
        button.dataset.sortDir === currentSortDir
      );
      button.classList.toggle('disabled', active);
      button.setAttribute('aria-disabled', active ? 'true' : 'false');
    });
  }

  function sortRows(col, dir) {
    currentSortCol = col;
    currentSortDir = dir;

    const idxMap = {
      id: 1, titulo: 2, tipo: 4, avance: 6,
      inicio: 7, 'inicio Real': 8, fin: 9, 'Fin Real': 10,
      horas: 11,          // Horas de atención (col nueva)
      propietario: 14,    // Responsable (posición corregida)
      depto: 15,          // Departamento (posición corregida)
    };

    const idx = idxMap[col] || 1;
    const multiplier = dir === 'asc' ? 1 : -1;

    rows.sort((a, b) => {
      let va, vb;
      if (col === 'id' || col === 'avance') {
        va = parseInt(cellText(a, idx), 10) || 0;
        vb = parseInt(cellText(b, idx), 10) || 0;
      } else if (col === 'horas') {
        va = parseFloat(cellText(a, idx).replace('h', '').replace('min', '')) || 0;
        vb = parseFloat(cellText(b, idx).replace('h', '').replace('min', '')) || 0;
      } else if (['inicio', 'inicio Real', 'fin', 'Fin Real'].includes(col)) {
        va = parseDate(cellText(a, idx))?.getTime() || 0;
        vb = parseDate(cellText(b, idx))?.getTime() || 0;
      } else {
        va = cellText(a, idx).toLowerCase();
        vb = cellText(b, idx).toLowerCase();
      }
      if (va < vb) return -1 * multiplier;
      if (va > vb) return 1 * multiplier;
      return 0;
    });

    rows.forEach(row => tbody.appendChild(row));
    updateSortButtons();
    render();
  }

  // ── Poblar selects desde las filas del DOM ────────────────────

  function populateSelect(selectEl, values, allLabel) {
    if (!selectEl) return;
    const current = selectEl.value;
    selectEl.innerHTML = `<option value="">${allLabel}</option>`;
    [...new Set(values)].filter(Boolean).sort().forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      if (v === current) opt.selected = true;
      selectEl.appendChild(opt);
    });
  }

  function populateTipoFilter() {
    populateSelect(
      fTipo,
      rows.map(row => textOf(row, 'Tipo')),
      'Tipo: Todos'
    );
  }

  function populateDeptoFilter() {
    populateSelect(
      fDepto,
      rows.map(row => textOf(row, 'Departamento')),
      'Departamento: Todos'
    );
  }

  // ── Limpiar todo ─────────────────────────────────────────────

  function limpiarTodo() {
    if (window.location.search.includes('due=')) {
      window.location.href = '/tareas';
      return;
    }
    if (qInp)   qInp.value   = '';
    if (fEstado) fEstado.value = '';
    if (fTipo)   fTipo.value  = '';
    if (fProp)   fProp.value  = '';
    if (fDepto)  fDepto.value = '';
    document.querySelector('input[name="fecha_desde"]')?.setAttribute('value', '');
    document.querySelector('input[name="fecha_hasta"]')?.setAttribute('value', '');
    applyFilters();
  }

  // ── Inicializar ──────────────────────────────────────────────

  populateTipoFilter();
  populateDeptoFilter();

  [qInp, fEstado, fTipo, fProp, fDepto].forEach(el => {
    el?.addEventListener('input',  applyFilters);
    el?.addEventListener('change', applyFilters);
  });

  document.querySelectorAll('.sort-btn').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      sortRows(button.dataset.sortCol, button.dataset.sortDir);
    });
  });

  document.getElementById('btnLimpiarTodo')?.addEventListener('click', limpiarTodo);

  document.getElementById('btnAdv')?.addEventListener('click', () => {
    document.getElementById('advBox')?.classList.toggle('show');
  });

  document.getElementById('densityNormal')?.addEventListener('click', () => {
    table.classList.remove('table-compact', 'table-supercompact');
  });

  document.getElementById('densityCompact')?.addEventListener('click', () => {
    table.classList.add('table-compact', 'table-supercompact');
  });

  document.getElementById('btnGerencial')?.addEventListener('click', event => {
    const button = event.currentTarget;
    table.classList.toggle('table-gerencial');
    if (table.classList.contains('table-gerencial')) {
      button.classList.replace('btn-outline-primary', 'btn-primary');
      document.getElementById('densityCompact')?.click();
    } else {
      button.classList.replace('btn-primary', 'btn-outline-primary');
    }
  });

  document.querySelectorAll('[data-alert]').forEach(button => {
    button.addEventListener('click', () => { alert(button.dataset.alert); });
  });

  document.querySelectorAll('.js-delete-tarea-form').forEach(form => {
    form.addEventListener('submit', event => {
      if (!confirm('¿Eliminar tarea?')) event.preventDefault();
    });
  });

  document.getElementById('btnExportarExcel')?.addEventListener('click', event => {
    event.preventDefault();
    const vista = document.querySelector('.tasks-page')?.dataset.vista || '';
    const fechaDesde = document.querySelector('input[name="fecha_desde"]')?.value || '';
    const fechaHasta = document.querySelector('input[name="fecha_hasta"]')?.value || '';
    const params = new URLSearchParams({
      vista,
      q:           qInp?.value    || '',
      estado:      fEstado?.value || '',
      tipo:        fTipo?.value   || '',
      prop:        fProp?.value   || '',
      depto:       fDepto?.value  || '',
      fecha_desde: fechaDesde,
      fecha_hasta: fechaHasta
    });
    window.location.href = `/tareas/reporte/excel?${params.toString()}`;
  });

  document.addEventListener('keydown', event => {
    const tag = event.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (event.key === '/') {
      event.preventDefault();
      document.getElementById('advBox')?.classList.add('show');
      qInp?.focus();
    }
    if (event.key === 'n') {
      event.preventDefault();
      document.querySelector('a[href*="nueva_tarea"]')?.click();
    }
  });

  // Vista compacta por defecto
  document.getElementById('densityCompact')?.click();

  applyFilters();
  updateSortButtons();
});

// ======================================================
// NUEVA TAREA - compatible con CSP, sin scripts inline
// ======================================================
document.addEventListener('DOMContentLoaded', () => {
  const nuevaTareaForm = document.querySelector('form input[name="modo"]')?.closest('form');

  const responsableSearch = document.getElementById('responsableSearch');
  const responsableSelect = document.getElementById('responsableSelect');
  const btnAgregarResp = document.getElementById('btnAgregarResp');
  const responsablesSeleccionados = document.getElementById('responsablesSeleccionados');
  const responsablesHidden = document.getElementById('responsablesHidden');

  const solicitanteSearch = document.getElementById('solicitanteSearch');
  const solicitanteSelect = document.getElementById('solicitanteSelect');

  if (
    !nuevaTareaForm &&
    !responsableSearch &&
    !responsableSelect &&
    !solicitanteSearch &&
    !solicitanteSelect
  ) {
    return;
  }

  function filtrarSelect(searchInput, selectInput) {
    if (!searchInput || !selectInput) return;

    const allOptions = Array.from(selectInput.options);

    searchInput.addEventListener('input', function () {
      const q = this.value.toLowerCase().trim();

      selectInput.innerHTML = '';

      allOptions.forEach((opt) => {
        const text = (opt.dataset.search || opt.textContent || '').toLowerCase();

        if (!q || text.includes(q)) {
          selectInput.appendChild(opt);
        }
      });
    });
  }

  filtrarSelect(responsableSearch, responsableSelect);
  filtrarSelect(solicitanteSearch, solicitanteSelect);

  if (responsableSelect && btnAgregarResp && responsablesSeleccionados && responsablesHidden) {
    const selectedMap = {};

    function crearHidden(id) {
      const inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = 'responsable_ids';
      inp.value = id;
      responsablesHidden.appendChild(inp);
    }

    function crearChip(id, label) {
      const chip = document.createElement('span');
      chip.className = 'badge bg-primary me-1 mb-1 d-inline-flex align-items-center gap-1';
      chip.dataset.id = id;

      chip.appendChild(document.createTextNode(label));

      const btnClose = document.createElement('button');
      btnClose.type = 'button';
      btnClose.className = 'btn-close btn-close-white btn-sm ms-1';
      btnClose.setAttribute('aria-label', 'Quitar responsable');

      btnClose.addEventListener('click', function () {
        chip.remove();

        const inp = responsablesHidden.querySelector(
          'input[name="responsable_ids"][value="' + CSS.escape(id) + '"]'
        );

        if (inp) inp.remove();

        delete selectedMap[id];
      });

      chip.appendChild(btnClose);
      responsablesSeleccionados.appendChild(chip);
    }

    btnAgregarResp.addEventListener('click', function () {
      const opt = responsableSelect.options[responsableSelect.selectedIndex];
      if (!opt) return;

      const id = opt.value;
      const label = opt.textContent.trim();

      if (!id || selectedMap[id]) return;

      selectedMap[id] = label;
      crearChip(id, label);
      crearHidden(id);
    });

    nuevaTareaForm?.addEventListener('submit', function (event) {
      const count = responsablesHidden.querySelectorAll('input[name="responsable_ids"]').length;
      const hasSingleResponsible = Boolean(document.querySelector('input[name="responsable_id"]'));

      if (count === 0 && !hasSingleResponsible) {
        event.preventDefault();
        alert('Selecciona al menos un responsable y pulsa "+".');
      }
    });
  }

});

// ======================================================
// MEJORAR DESCRIPCIÓN CON IA
// ======================================================
document.addEventListener('DOMContentLoaded', () => {
  const btnMejorar = document.getElementById('btnMejorarDescripcion');
  const textarea   = document.getElementById('descripcionTarea');
  const panel      = document.getElementById('mejora-descripcion-panel');

  if (!btnMejorar || !textarea || !panel) return;

  const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';

  btnMejorar.addEventListener('click', async () => {
    const texto = textarea.value.trim();
    if (!texto) {
      alert('Escribe una descripción antes de mejorarla con IA.');
      return;
    }

    btnMejorar.disabled = true;
    btnMejorar.textContent = 'Mejorando…';
    panel.className = 'om-ia-mejora mt-2';
    panel.innerHTML = '';

    const loadMsg = document.createElement('span');
    loadMsg.className = 'ia-msg-info';
    loadMsg.textContent = '✨ Generando versión mejorada…';
    panel.appendChild(loadMsg);

    try {
      const resp = await fetch('/api/om/mejorar-descripcion', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ texto }),
      });
      const data = await resp.json();

      panel.innerHTML = '';

      if (!data.ok) {
        const errEl = document.createElement('span');
        errEl.className = 'ia-msg-error';
        errEl.textContent = data.error || 'Error al mejorar.';
        panel.appendChild(errEl);
        return;
      }

      const descMejorada = data.descripcion_mejorada || '';
      const cambios      = data.cambios || [];

      const lbl = document.createElement('div');
      lbl.className = 'ia-mejora-label';
      const icon = document.createElement('i');
      icon.className = 'bi bi-stars';
      lbl.appendChild(icon);
      lbl.appendChild(document.createTextNode(' Versión mejorada'));
      panel.appendChild(lbl);

      const txEl = document.createElement('div');
      txEl.className = 'ia-mejora-texto';
      txEl.textContent = descMejorada;
      panel.appendChild(txEl);

      if (cambios.length) {
        const camDiv = document.createElement('div');
        camDiv.className = 'ia-cambios';
        cambios.forEach(c => {
          const ci = document.createElement('div');
          ci.className = 'ia-cambio-item';
          ci.textContent = '• ' + c;
          camDiv.appendChild(ci);
        });
        panel.appendChild(camDiv);
      }

      const mbtns = document.createElement('div');
      mbtns.className = 'ia-mejora-btns';

      const btnUsar = document.createElement('button');
      btnUsar.type = 'button';
      btnUsar.className = 'btn-om-ia-usar btn-om-ia-usar-si';
      btnUsar.textContent = '✅ Usar esta descripción';
      btnUsar.addEventListener('click', () => {
        textarea.value = descMejorada;
        panel.className = 'om-ia-mejora d-none';
      });

      const btnDesc = document.createElement('button');
      btnDesc.type = 'button';
      btnDesc.className = 'btn-om-ia-usar btn-om-ia-usar-no';
      btnDesc.textContent = '✖ Descartar';
      btnDesc.addEventListener('click', () => {
        panel.className = 'om-ia-mejora d-none';
      });

      mbtns.appendChild(btnUsar);
      mbtns.appendChild(btnDesc);
      panel.appendChild(mbtns);

    } catch {
      panel.innerHTML = '';
      const errEl = document.createElement('span');
      errEl.className = 'ia-msg-error';
      errEl.textContent = 'Error de conexión al mejorar.';
      panel.appendChild(errEl);
    } finally {
      btnMejorar.disabled = false;
      btnMejorar.innerHTML = '';
      const icon2 = document.createElement('i');
      icon2.className = 'bi bi-stars me-1';
      btnMejorar.appendChild(icon2);
      btnMejorar.appendChild(document.createTextNode('Mejorar con IA'));
    }
  });
});

// ── Modal detalle completo — historial + agregar acción ──────────────
(function initDetalleModal() {
  const backdrop = document.getElementById('tdDetalleBackdrop');
  if (!backdrop) return;

  let currentTaskId = null;
  let respPopulated = false;

  const loading    = document.getElementById('tdDetLoading');
  const content    = document.getElementById('tdDetContent');
  const infoDiv    = document.getElementById('tdDetInfo');
  const histDiv    = document.getElementById('tdDetHistorial');
  const formCard   = document.getElementById('tdDetFormCard');
  const form       = document.getElementById('tdDetForm');
  const formMsg    = document.getElementById('tdDetFormMsg');
  const respSearch = document.getElementById('tdDetRespSearch');
  const respSelect = document.getElementById('tdDetRespSelect');
  const fzWarning  = document.getElementById('tdDetFinalizadoWarning');

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function fmtDt(v) {
    if (!v) return '-';
    const s = String(v).replace('T',' ');
    if (s.length < 10) return s;
    return s.slice(8,10)+'/'+s.slice(5,7)+'/'+s.slice(0,4)+(s.length>10 ? ' '+s.slice(11,16) : '');
  }

  function estadoBadge(e) {
    const map = { 'Terminado':'bg-success','Cerrado por sistema':'bg-secondary',
                  'En desarrollo':'bg-warning text-dark','Atrasada':'bg-danger','Por iniciar':'bg-info text-dark' };
    return `<span class="badge ${map[e]||'bg-secondary'}">${esc(e)}</span>`;
  }

  function accionBadge(e) {
    const map = { 'Finalizado':'bg-success','Bloqueado':'bg-danger','Pendiente':'bg-secondary' };
    return `<span class="badge td-badge-sm ${map[e]||'bg-info text-dark'}">${esc(e||'En proceso')}</span>`;
  }

  function renderInfo(t) {
    infoDiv.innerHTML = `
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
        <div class="small text-muted">
          Responsable: <strong class="text-body">${esc(t.propietario||'-')}</strong>
          &nbsp;·&nbsp; Creada por: <strong class="text-body">${esc(t.creador_nombre||t.creador_username||'-')}</strong>
        </div>
        ${estadoBadge(t.estado)}
      </div>
      ${t.descripcion ? `<div class="td-modal-desc mb-3">${esc(t.descripcion)}</div>` : ''}
      <div class="td-detalle-fechas">
        ${[['Creación',t.fecha_creacion],['Inicio',t.fecha_inicio],['Compromiso',t.fecha_compromiso],['Fin Real',t.fecha_fin]]
          .map(([l,v])=>`<div><div class="td-modal-label">${l}</div><div class="td-modal-value td-fecha-val">${fmtDt(v)}</div></div>`).join('')}
      </div>`;
  }

  function renderHistorial(acciones) {
    if (!acciones || acciones.length === 0) {
      histDiv.innerHTML = '<p class="text-muted small mb-0">Aún no se han registrado acciones para esta tarea.</p>';
      return;
    }
    const rows = acciones.map(a => {
      const csrf = document.getElementById('td-csrf-token')?.dataset.token || '';
      const btnTerminar = a.estado_accion !== 'Finalizado'
        ? `<button class="btn btn-outline-success btn-sm p-0 px-1 td-badge-sm js-det-fin-accion"
             data-accion-id="${a.id}" data-csrf="${esc(csrf)}">
             <i class="bi bi-check2-all"></i> Terminar
           </button>` : '';
      return `<tr>
        <td class="small">${fmtDt(a.fecha_accion)}</td>
        <td class="small">${esc(a.nombre_completo||a.username||'-')}</td>
        <td>
          <div class="fw-bold small">${esc(a.nombre_asignado||'Sin asignar')}</div>
          <div class="d-flex gap-1 flex-wrap mt-1">${accionBadge(a.estado_accion)} ${btnTerminar}</div>
        </td>
        <td>
          <div class="fw-semibold small">${esc(a.observacion||'')}</div>
          <div class="text-muted small td-det-pretext">${esc(a.detalles||'')}</div>
        </td>
        <td class="small text-primary">${fmtDt(a.fecha_fin_tentativa)}</td>
      </tr>`;
    }).join('');

    histDiv.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm align-middle table-hover mb-0">
          <thead class="table-light">
            <tr>
              <th class="td-col-fecha">Fecha</th>
              <th class="td-col-reg">Registrado por</th>
              <th class="td-col-asig">Asignado / Estado</th>
              <th>Actividad</th>
              <th class="td-col-fintent">Fin Tent.</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;

    histDiv.querySelectorAll('.js-det-fin-accion').forEach(btn => {
      btn.addEventListener('click', () => {
        const fd = new FormData();
        fd.append('csrf_token', btn.dataset.csrf);
        btn.disabled = true;
        fetch(`/tareas/accion/${btn.dataset.accionId}/finalizar`, { method:'POST', body:fd })
          .then(() => recargarHistorial(currentTaskId))
          .catch(() => { btn.disabled = false; });
      });
    });
  }

  function recargarHistorial(taskId) {
    fetch(`/tareas/${taskId}/detalle-json`)
      .then(r => r.json())
      .then(data => { if (data.ok) renderHistorial(data.acciones); });
  }

  function populateResp(responsables) {
    if (respPopulated || !respSelect) return;
    (responsables || []).forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = r.label || r.username;
      opt.dataset.search = ((r.label||'') + ' ' + r.username).toLowerCase();
      respSelect.appendChild(opt);
    });
    respPopulated = true;
  }

  function openModal(taskId) {
    currentTaskId = taskId;
    loading.classList.remove('d-none');
    content.classList.add('d-none');
    formMsg.classList.add('d-none');
    backdrop.classList.add('visible');
    backdrop.setAttribute('aria-hidden','false');
    document.body.classList.add('bs-modal-open');

    fetch(`/tareas/${taskId}/detalle-json`)
      .then(r => r.json())
      .then(data => {
        loading.classList.add('d-none');
        if (!data.ok) {
          content.innerHTML = `<div class="alert alert-danger m-3">${esc(data.error||'Error al cargar')}</div>`;
          content.classList.remove('d-none');
          return;
        }
        const t = data.tarea;
        document.getElementById('tdDetCodigo').textContent = String(t.id||'').padStart(8,'0');
        document.getElementById('tdDetTitulo').textContent = t.titulo||'';
        renderInfo(t);
        renderHistorial(data.acciones);
        populateResp(data.responsables);

        if (data.puede_anotar) {
          formCard.classList.remove('d-none');
          document.getElementById('tdDetCsrf').value =
            document.getElementById('td-csrf-token')?.dataset.token || '';
        } else {
          formCard.classList.add('d-none');
        }
        content.classList.remove('d-none');
      })
      .catch(() => {
        loading.classList.add('d-none');
        content.innerHTML = '<div class="alert alert-danger m-3">Error de red al cargar la tarea.</div>';
        content.classList.remove('d-none');
      });
  }

  function closeModal() {
    backdrop.classList.remove('visible');
    backdrop.setAttribute('aria-hidden','true');
    document.body.classList.remove('bs-modal-open');
    currentTaskId = null;
  }

  document.querySelectorAll('.js-abrir-detalle-modal').forEach(btn => {
    btn.addEventListener('click', () => openModal(parseInt(btn.dataset.taskId, 10)));
  });

  form?.addEventListener('submit', function(e) {
    e.preventDefault();
    if (!currentTaskId) return;
    const detalles = document.getElementById('tdDetDetalles')?.value.trim();
    if (!detalles) {
      formMsg.className = 'alert alert-warning mt-2 py-2';
      formMsg.textContent = 'Escribe al menos una observación.';
      formMsg.classList.remove('d-none');
      return;
    }

    const btn = document.getElementById('tdDetBtnGuardar');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Guardando...'; }
    formMsg.classList.add('d-none');

    fetch(`/tareas/${currentTaskId}/accion-ajax`, { method:'POST', body: new FormData(form) })
      .then(r => r.json())
      .then(data => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Guardar avance'; }
        formMsg.className = `alert alert-${data.ok ? 'success' : 'danger'} mt-2 py-2`;
        formMsg.textContent = data.message || (data.ok ? 'Acción registrada.' : 'Error al guardar.');
        formMsg.classList.remove('d-none');
        if (data.ok) {
          form.reset();
          if (data.task_closed) {
            setTimeout(() => { closeModal(); window.location.reload(); }, 1800);
          } else {
            recargarHistorial(currentTaskId);
            setTimeout(() => formMsg.classList.add('d-none'), 3000);
          }
        }
      })
      .catch(() => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Guardar avance'; }
        formMsg.className = 'alert alert-danger mt-2 py-2';
        formMsg.textContent = 'Error de red al guardar.';
        formMsg.classList.remove('d-none');
      });
  });

  document.getElementById('tdDetClose')?.addEventListener('click', closeModal);
  backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && backdrop.classList.contains('visible')) closeModal();
  });

  window.tdDetalleModal = { open: openModal, close: closeModal };
})();