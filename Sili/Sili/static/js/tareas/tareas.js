let selectedEstados = [];
let selectedTipos = [];
let selectedDeptos = [];

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

  const qInp = document.getElementById('liveFilter');
  const fEstado = document.getElementById('fEstado');
  const fProp = document.getElementById('fProp');
  const fDepto = document.getElementById('fDepto');

  const estadoMenu = document.getElementById('estadoMenu');
  const tipoMenu = document.getElementById('tipoMenu');
  const deptoMenu = document.getElementById('deptoMenu');

  const quickFilters = { titulo: '', prop: '', depto: '' };

  let pageLength = parseInt(localStorage.getItem('tareas_page_len') || '10', 10);
  let currentPage = 1;
  let currentSortCol = null;
  let currentSortDir = null;

  rows.forEach(row => {
    row.dataset.match = '1';
  });

  function textOf(row, dataTh) {
    return (row.querySelector(`td[data-th="${dataTh}"]`)?.innerText || '').trim();
  }

  function matchedRows() {
    return rows.filter(row => row.dataset.match !== '0');
  }

  function updateInfo(start, end, total) {
    if (info) {
      info.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total}`;
    }

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
      if (!disabled) {
        currentPage = page;
        render();
      }
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

    for (let i = start; i < end; i += 1) {
      list[i].classList.remove('d-none');
    }

    updateInfo(start, end, total);
    renderPagination(totalPages);
  }

  function applyFilters() {
    const q = (qInp?.value || '').toLowerCase().trim();
    const estadoSelect = fEstado?.value || '';
    const prop = (fProp?.value || '').toLowerCase().trim();
    const deptoTexto = (fDepto?.value || '').toLowerCase().trim();

    rows.forEach(row => {
      const rowText = row.innerText.toLowerCase();

      const tipo = textOf(row, 'Tipo');
      const estado = textOf(row, 'Estado');
      const responsable = textOf(row, 'Responsable').toLowerCase();
      const departamento = textOf(row, 'Departamento');
      const departamentoLower = departamento.toLowerCase();
      const titulo = textOf(row, 'Título').toLowerCase();

      const okQ = !q || rowText.includes(q);
      const okProp = !prop || responsable.includes(prop);
      const okDeptoTexto = !deptoTexto || departamentoLower.includes(deptoTexto);

      const okTituloRapido = !quickFilters.titulo || titulo.includes(quickFilters.titulo);
      const okPropRapido = !quickFilters.prop || responsable.includes(quickFilters.prop);
      const okDeptoRapido = !quickFilters.depto || departamentoLower.includes(quickFilters.depto);

      const okEstadoSelect = !estadoSelect || estado === estadoSelect;
      const okEstadoMulti = selectedEstados.length === 0 || selectedEstados.includes(estado);
      const okTipoMulti = selectedTipos.length === 0 || selectedTipos.includes(tipo);
      const okDeptoMulti = selectedDeptos.length === 0 || selectedDeptos.includes(departamento);

      row.dataset.match = (
        okQ &&
        okProp &&
        okDeptoTexto &&
        okTituloRapido &&
        okPropRapido &&
        okDeptoRapido &&
        okEstadoSelect &&
        okEstadoMulti &&
        okTipoMulti &&
        okDeptoMulti
      ) ? '1' : '0';
    });

    currentPage = 1;
    render();
  }

  function parseDate(value) {
    if (!value) return null;

    const normalized = value.replace(/\s+/g, 'T');
    const date = new Date(normalized);

    return Number.isNaN(date.getTime()) ? null : date;
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
      id: 1,
      titulo: 2,
      tipo: 4,
      inicio: 7,
      'inicio Real': 8,
      fin: 9,
      'Fin Real': 10,
      propietario: 12,
      depto: 13
    };

    const idx = idxMap[col] || 1;
    const multiplier = dir === 'asc' ? 1 : -1;

    rows.sort((a, b) => {
      let va;
      let vb;

      if (col === 'id') {
        va = parseInt(cellText(a, idx), 10) || 0;
        vb = parseInt(cellText(b, idx), 10) || 0;
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

  function closeMenus(exceptMenu = null) {
    [estadoMenu, tipoMenu, deptoMenu].forEach(menu => {
      if (menu && menu !== exceptMenu) menu.classList.remove('show');
    });

    document.querySelectorAll('.col-search-box').forEach(box => {
      if (box !== exceptMenu) box.classList.remove('show');
    });
  }

  function toggleMenu(menu) {
    if (!menu) return;

    const willShow = !menu.classList.contains('show');
    closeMenus(menu);
    menu.classList.toggle('show', willShow);
  }

  function populateTipoFilter() {
    const container = document.getElementById('tipoChecklist');
    if (!container) return;

    const tipos = rows.map(row => textOf(row, 'Tipo')).filter(Boolean);
    const tiposUnicos = [...new Set(tipos)];

    if (!tiposUnicos.length) {
      container.innerHTML = '<div class="small text-muted p-2">No hay tipos detectados</div>';
      return;
    }

    container.innerHTML = tiposUnicos
      .map(tipo => `
        <label class="estado-check">
          <input type="checkbox" value="${tipo}"> ${tipo}
        </label>
      `)
      .join('');
  }

  function clearDeptoFilter() {
    selectedDeptos = [];

    document.querySelectorAll('#deptoChecklist input[type="checkbox"]').forEach(checkbox => {
      checkbox.checked = false;
    });

    deptoMenu?.classList.remove('show');
    applyFilters();
  }

  function limpiarTodo() {
    if (window.location.search.includes('due=')) {
      window.location.href = '/tareas';
      return;
    }

    if (qInp) qInp.value = '';
    if (fEstado) fEstado.value = '';
    if (fProp) fProp.value = '';
    if (fDepto) fDepto.value = '';

    document.querySelector('input[name="fecha_desde"]')?.setAttribute('value', '');
    document.querySelector('input[name="fecha_hasta"]')?.setAttribute('value', '');

    Object.keys(quickFilters).forEach(key => {
      quickFilters[key] = '';
    });

    document.querySelectorAll('.col-search-box input').forEach(input => {
      input.value = '';
    });

    selectedEstados = [];
    selectedTipos = [];
    selectedDeptos = [];

    document.querySelectorAll('#estadoMenu input[type="checkbox"], #tipoChecklist input[type="checkbox"], #deptoChecklist input[type="checkbox"]')
      .forEach(checkbox => {
        checkbox.checked = false;
      });

    closeMenus();
    applyFilters();
  }

  populateTipoFilter();

  document.getElementById('btnTipoFilter')?.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    toggleMenu(tipoMenu);
  });

  document.getElementById('btnTipoBuscar')?.addEventListener('click', event => {
    event.preventDefault();
    selectedTipos = [...document.querySelectorAll('#tipoChecklist input:checked')].map(input => input.value);
    tipoMenu?.classList.remove('show');
    applyFilters();
  });

  document.getElementById('btnTipoLimpiar')?.addEventListener('click', event => {
    event.preventDefault();
    selectedTipos = [];
    document.querySelectorAll('#tipoChecklist input').forEach(input => {
      input.checked = false;
    });
    tipoMenu?.classList.remove('show');
    applyFilters();
  });

  document.getElementById('btnEstadoFilter')?.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    toggleMenu(estadoMenu);
  });

  document.getElementById('btnEstadoBuscar')?.addEventListener('click', event => {
    event.preventDefault();
    selectedEstados = [...document.querySelectorAll('#estadoMenu input:checked')].map(input => input.value);
    estadoMenu?.classList.remove('show');
    applyFilters();
  });

  document.getElementById('btnEstadoLimpiar')?.addEventListener('click', event => {
    event.preventDefault();
    selectedEstados = [];
    document.querySelectorAll('#estadoMenu input').forEach(input => {
      input.checked = false;
    });
    estadoMenu?.classList.remove('show');
    applyFilters();
  });

  document.querySelectorAll('[data-menu-target]').forEach(button => {
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      toggleMenu(document.getElementById(button.dataset.menuTarget));
    });
  });

  document.getElementById('btnDeptoBuscar')?.addEventListener('click', event => {
    event.preventDefault();
    selectedDeptos = [...document.querySelectorAll('#deptoChecklist input:checked')].map(input => input.value);
    deptoMenu?.classList.remove('show');
    applyFilters();
  });

  document.getElementById('btnDeptoLimpiar')?.addEventListener('click', event => {
    event.preventDefault();
    clearDeptoFilter();
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

  [qInp, fEstado, fProp, fDepto].forEach(element => {
    element?.addEventListener('input', applyFilters);
    element?.addEventListener('change', applyFilters);
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

  document.querySelectorAll('.magnify-btn[data-target]').forEach(button => {
    button.addEventListener('click', event => {
      event.stopPropagation();

      const box = document.querySelector(`.col-search-box[data-col="${button.dataset.target}"]`);
      if (!box) return;

      const willShow = !box.classList.contains('show');
      closeMenus(box);
      box.classList.toggle('show', willShow);

      if (willShow) {
        const input = box.querySelector('input');
        input?.focus();
        input?.select();
      }
    });
  });

  document.querySelectorAll('.col-search-box').forEach(box => {
    const col = box.dataset.col;
    const input = box.querySelector('input');

    input?.addEventListener('input', () => {
      quickFilters[col] = input.value.toLowerCase().trim();
      applyFilters();
    });

    input?.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        input.value = '';
        quickFilters[col] = '';
        box.classList.remove('show');
        applyFilters();
      }
    });
  });

  document.querySelectorAll('[data-alert]').forEach(button => {
    button.addEventListener('click', () => {
      alert(button.dataset.alert);
    });
  });

  document.querySelectorAll('.js-delete-tarea-form').forEach(form => {
    form.addEventListener('submit', event => {
      if (!confirm('¿Eliminar tarea?')) {
        event.preventDefault();
      }
    });
  });

  document.getElementById('btnExportarExcel')?.addEventListener('click', event => {
    event.preventDefault();

    const vista = document.querySelector('.tasks-page')?.dataset.vista || '';
    const fechaDesde = document.querySelector('input[name="fecha_desde"]')?.value || '';
    const fechaHasta = document.querySelector('input[name="fecha_hasta"]')?.value || '';

    const params = new URLSearchParams({
      vista,
      q: qInp?.value || '',
      estado: fEstado?.value || '',
      prop: fProp?.value || '',
      depto: fDepto?.value || '',
      fecha_desde: fechaDesde,
      fecha_hasta: fechaHasta
    });

    window.location.href = `/tareas/reporte/excel?${params.toString()}`;
  });

  document.addEventListener('keydown', event => {
    const tag = event.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

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

  document.addEventListener('click', event => {
    if (
      !event.target.closest('.estado-menu') &&
      !event.target.closest('.magnify-btn') &&
      !event.target.closest('.col-search-box')
    ) {
      closeMenus();
    }
  });

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