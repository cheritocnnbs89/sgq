document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('tabla-encuestas');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const rows = [...tbody.querySelectorAll('tr[data-row="1"]')];

  const qInput = document.getElementById('liveFilterEncuestas');
  const estadoInput = document.getElementById('fEstadoEncuesta');
  const info = document.getElementById('tableInfoEncuestas');
  const pager = document.getElementById('paginationEncuestas');
  const noResults = document.getElementById('noResultsEncuestas');

  let pageLength = 10;
  let currentPage = 1;

  rows.forEach(row => {
    row.dataset.match = '1';
  });

  function matchedRows() {
    return rows.filter(row => row.dataset.match !== '0');
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
    pager.appendChild(makePageItem('Anterior', currentPage - 1, currentPage === 1));

    for (let page = 1; page <= total; page += 1) {
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

    if (info) {
      info.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total}`;
    }

    noResults?.classList.toggle('d-none', total !== 0);
    renderPagination(totalPages);
  }

  function applyFilters() {
    const q = (qInput?.value || '').toLowerCase().trim();
    const estado = estadoInput?.value || '';

    rows.forEach(row => {
      const rowText = row.innerText.toLowerCase();
      const rowEstado = row.querySelector('td[data-th="Estado"]')?.innerText.trim() || '';

      const okQ = !q || rowText.includes(q);
      const okEstado = !estado || rowEstado === estado;

      row.dataset.match = okQ && okEstado ? '1' : '0';
    });

    currentPage = 1;
    render();
  }

  qInput?.addEventListener('input', applyFilters);
  estadoInput?.addEventListener('change', applyFilters);

  applyFilters();

  estadoInput?.addEventListener('change', () => {
  const form = estadoInput.closest('form');
  if (form) form.submit();
});
});