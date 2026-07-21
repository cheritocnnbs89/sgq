document.addEventListener('DOMContentLoaded', function () {
  const table = document.getElementById('tabla-terceros');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr[data-row="1"]'));
  const info = document.getElementById('tableInfo');
  const pager = document.getElementById('pagination');
  const countTotal = document.getElementById('countTotal');
  const countVisibles = document.getElementById('countVisibles');
  const q = document.getElementById('liveFilter');
  const toolbar = document.getElementById('toolbarForm');

  let pageLength = parseInt(localStorage.getItem('terceros_page_len') || '10', 10);
  let currentPage = 1;

  rows.forEach(function (row) {
    row.dataset.match = '1';
  });

  function matched() {
    return rows.filter(function (row) {
      return row.dataset.match !== '0';
    });
  }

  function updateInfo(start, end, total) {
    if (info) {
      info.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total}`;
    }
  }

  function mk(label, page, disabled = false, active = false) {
    const li = document.createElement('li');
    li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');

    const a = document.createElement('a');
    a.className = 'page-link';
    a.href = '#';
    a.textContent = label;

    a.addEventListener('click', function (e) {
      e.preventDefault();
      if (!disabled) {
        currentPage = page;
        render();
      }
    });

    li.appendChild(a);
    return li;
  }

  function renderPagination(totalPages) {
    if (!pager) return;

    pager.innerHTML = '';
    const tp = Math.max(1, totalPages);
    const max = 7;
    const start = Math.max(1, currentPage - 3);
    const end = Math.min(tp, start + max - 1);

    pager.appendChild(mk('Anterior', currentPage - 1, currentPage === 1));

    for (let p = start; p <= end; p += 1) {
      pager.appendChild(mk(String(p), p, false, p === currentPage));
    }

    pager.appendChild(mk('Siguiente', currentPage + 1, currentPage === tp));
  }

  function render() {
    const list = matched();
    const total = list.length;
    const totalPages = Math.max(1, Math.ceil(total / pageLength));
    currentPage = Math.min(Math.max(1, currentPage), totalPages);

    rows.forEach(function (row) {
      row.style.display = 'none';
    });

    const start = (currentPage - 1) * pageLength;
    const end = Math.min(start + pageLength, total);

    for (let i = start; i < end; i += 1) {
      list[i].style.display = '';
    }

    updateInfo(start, end, total);

    if (countTotal) {
      countTotal.textContent = String(rows.length);
    }

    if (countVisibles) {
      countVisibles.textContent = String(total);
    }

    renderPagination(totalPages);
  }

  document.getElementById('densityNormal')?.addEventListener('click', function () {
    table.classList.remove('table-compact');
  });

  document.getElementById('densityCompact')?.addEventListener('click', function () {
    table.classList.add('table-compact');
  });

  toolbar?.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
    }
  });

  function applyFilter() {
    const term = (q?.value || '').toLowerCase().trim();

    rows.forEach(function (row) {
      const txt = (row.innerText || '').toLowerCase();
      const ok = !term || txt.includes(term);
      row.dataset.match = ok ? '1' : '0';
    });

    currentPage = 1;
    render();
  }

  document.getElementById('btnSearch')?.addEventListener('click', applyFilter);

  document.getElementById('btnClear')?.addEventListener('click', function () {
    if (q) {
      q.value = '';
      applyFilter();
      q.focus();
    }
  });

  q?.addEventListener('input', applyFilter);

  document.querySelectorAll('.tercero-delete-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      const ok = window.confirm('¿Eliminar?');
      if (!ok) {
        e.preventDefault();
      }
    });
  });

  document.addEventListener('keydown', function (e) {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    if (e.key === '/') {
      e.preventDefault();
      q?.focus();
    }

    if (e.key === 'n') {
      e.preventDefault();
      document.querySelector('a[href*="tercero_nuevo"]')?.click();
    }
  });

  applyFilter();
});