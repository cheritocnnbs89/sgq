(function () {
  function removeOneShotStatusAlert() {
    if (!window.location.search.includes('status=')) return;

    const u = new URL(window.location.href);
    u.searchParams.delete('status');
    u.searchParams.delete('t');
    history.replaceState({}, document.title, u.pathname + (u.search ? '?' + u.search : '') + u.hash);

    window.addEventListener('pageshow', function (e) {
      if (e.persisted) {
        document.querySelectorAll('.alert[data-once="1"]').forEach(function (n) {
          n.remove();
        });
      }
    });
  }

  function initThemeToggle() {
    const key = 'ui_theme';
    const root = document.documentElement;

    function apply(mode) {
      root.classList.toggle('theme-dark', mode === 'dark');
      localStorage.setItem(key, mode);
    }

    const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    apply(localStorage.getItem(key) || preferred);

    const toggle = document.getElementById('themeToggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
      });
    }
  }

  function initDefaultDates() {
    const pad = function (n) { return String(n).padStart(2, '0'); };
    const fmt = function (d) {
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    };

    const desde = document.querySelector('input[name="desde"]');
    const hasta = document.querySelector('input[name="hasta"]');

    const qs = new URLSearchParams(location.search);
    const special = ['ccb', 'pendientes'].some(function (k) {
      return qs.get(k) === '1';
    });

    if (!special) {
      const today = fmt(new Date());
      if (desde && !desde.value) desde.value = today;
      if (hasta && !hasta.value) hasta.value = today;
    }

    const form = desde ? desde.closest('form') : null;
    if (form && !qs.has('desde') && !qs.has('hasta') && !special) {
      form.submit();
    }
  }

  function initQuickDateRanges() {
    const pad = function (n) { return String(n).padStart(2, '0'); };
    const fmt = function (d) {
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    };

    const desde = document.querySelector('[name="desde"]');
    const hasta = document.querySelector('[name="hasta"]');
    if (!desde || !hasta) return;

    document.querySelectorAll('[data-range]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const t = new Date();
        const end = fmt(t);
        const c = new Date(t);
        let beg = end;

        if (btn.dataset.range === 'week') {
          c.setDate(c.getDate() - 6);
          beg = fmt(c);
        } else if (btn.dataset.range === 'month') {
          c.setDate(1);
          beg = fmt(c);
        } else if (btn.dataset.range === '30') {
          c.setDate(c.getDate() - 29);
          beg = fmt(c);
        }

        desde.value = beg;
        hasta.value = end;
      });
    });
  }

  function initAutoSubmitFilters() {
    ['usuario_id', 'gerente_id', 'tipo', 'ccb'].forEach(function (id) {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('change', function () {
        const form = el.closest('form');
        if (form) form.submit();
      });
    });
  }

  function initSortAndPagination() {
    const table = document.getElementById('tabla-gastos');
    if (!table) return;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    let dataRows = Array.from(tbody.querySelectorAll('tr[data-row="1"]'));

    const info = document.getElementById('tableInfo');
    const pager = document.getElementById('pagination');
    const lenBtn = document.getElementById('pageLengthBtn');
    const lenMenu = lenBtn && lenBtn.closest('.dropdown')
      ? lenBtn.closest('.dropdown').querySelector('.dropdown-menu')
      : null;
    const items = lenMenu ? lenMenu.querySelectorAll('[data-page-length]') : [];

    const hasBSDropdown = typeof window.bootstrap !== 'undefined' && bootstrap.Dropdown;

    if (!hasBSDropdown && lenBtn && lenMenu) {
      const open = function () {
        lenMenu.classList.add('show');
        lenBtn.setAttribute('aria-expanded', 'true');
      };
      const close = function () {
        lenMenu.classList.remove('show');
        lenBtn.setAttribute('aria-expanded', 'false');
      };

      lenBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (lenMenu.classList.contains('show')) close();
        else open();
      });

      document.addEventListener('click', function (e) {
        const dropdown = lenBtn.closest('.dropdown');
        if (dropdown && !dropdown.contains(e.target)) close();
      });
    }

    let pageLength = parseInt(localStorage.getItem('gastos_page_len') || '15', 10);
    let currentPage = 1;
    let sortState = { index: -1, dir: 'asc' };

    function parseSpanishNumber(s) {
      if (!s) return 0;
      const n = s.replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '');
      const v = parseFloat(n);
      return isNaN(v) ? 0 : v;
    }

    function getCellValue(row, idx, type) {
      const td = row.children[idx];
      if (!td) return '';

      const raw = (td.textContent || '').trim();

      if (type === 'num') return parseSpanishNumber(raw);

      if (type === 'date') {
        const t = Date.parse(raw.replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$3-$2-$1')) || Date.parse(raw);
        return isNaN(t) ? 0 : t;
      }

      return raw.toLocaleLowerCase();
    }

    function clearIcons() {
      thead.querySelectorAll('th').forEach(function (th) {
        th.classList.remove('sorted-asc', 'sorted-desc');
        const i = th.querySelector('.th-sortable i');
        if (i) {
          i.classList.remove('bi-chevron-up', 'bi-chevron-down');
          i.classList.add('bi-arrow-down-up');
        }
      });
    }

    function setIcon(th, dir) {
      const i = th.querySelector('.th-sortable i');
      if (!i) return;

      i.classList.remove('bi-arrow-down-up', 'bi-chevron-up', 'bi-chevron-down');
      i.classList.add(dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down');
    }

    function applySort(th, idx, type) {
      const same = idx === sortState.index;
      sortState.dir = same ? (sortState.dir === 'asc' ? 'desc' : 'asc') : 'asc';
      sortState.index = idx;

      dataRows.sort(function (a, b) {
        const va = getCellValue(a, idx, type);
        const vb = getCellValue(b, idx, type);
        let c = 0;
        if (va > vb) c = 1;
        else if (va < vb) c = -1;
        return sortState.dir === 'asc' ? c : -c;
      });

      const frag = document.createDocumentFragment();
      dataRows.forEach(function (tr) {
        frag.appendChild(tr);
      });

      const totals = tbody.querySelector('tr[data-totales="1"]');
      if (totals) tbody.insertBefore(frag, totals);
      else tbody.appendChild(frag);

      clearIcons();
      th.classList.add(sortState.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
      setIcon(th, sortState.dir);

      goTo(1);
    }

    thead.querySelectorAll('th[data-sort]').forEach(function (th) {
      const type = (th.getAttribute('data-sort') || 'text').toLowerCase();
      const clickable = th.querySelector('.th-sortable') || th;

      clickable.setAttribute('role', 'button');
      clickable.setAttribute('tabindex', '0');

      clickable.addEventListener('click', function () {
        const idx = Array.from(th.parentElement.children).indexOf(th);
        applySort(th, idx, type);
      });

      clickable.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          clickable.click();
        }
      });
    });

    clearIcons();

    function setBtnText() {
      if (lenBtn) lenBtn.textContent = 'Mostrar ' + pageLength + ' filas';
    }

    function updateInfo(s, e, t) {
      if (!info) return;
      info.textContent = 'Mostrando ' + (t ? s + 1 : 0) + ' a ' + e + ' de ' + t + ' registros';
    }

    function mkItem(label, page, disabled, active) {
      const li = document.createElement('li');
      li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');

      const a = document.createElement('a');
      a.className = 'page-link';
      a.href = '#';
      a.textContent = label;

      a.addEventListener('click', function (e) {
        e.preventDefault();
        if (!disabled) goTo(page);
      });

      li.appendChild(a);
      return li;
    }

    function renderPagination(totalPages) {
      if (!pager) return;

      pager.innerHTML = '';
      const N = Math.max(1, totalPages);
      const max = 7;

      const add = function (s, e) {
        for (let p = s; p <= e; p++) {
          pager.appendChild(mkItem(String(p), p, false, p === currentPage));
        }
      };

      pager.appendChild(mkItem('Anterior', currentPage - 1, currentPage === 1, false));

      if (N <= max) {
        add(1, N);
      } else {
        const first = 1;
        const last = N;
        const left = Math.max(first, currentPage - 2);
        const right = Math.min(last, currentPage + 2);

        pager.appendChild(mkItem('1', 1, false, currentPage === 1));

        if (left > 2) {
          const li = document.createElement('li');
          li.className = 'page-item disabled';
          li.innerHTML = '<span class="page-link">…</span>';
          pager.appendChild(li);
        }

        add(left, right);

        if (right < last - 1) {
          const li = document.createElement('li');
          li.className = 'page-item disabled';
          li.innerHTML = '<span class="page-link">…</span>';
          pager.appendChild(li);
        }

        pager.appendChild(mkItem(String(last), last, false, currentPage === last));
      }

      pager.appendChild(mkItem('Siguiente', currentPage + 1, currentPage === N, false));
    }

    function goTo(page) {
      const total = dataRows.length;
      const pages = Math.max(1, Math.ceil(total / pageLength));
      currentPage = Math.min(Math.max(1, page), pages);

      dataRows.forEach(function (row, idx) {
        const start = (currentPage - 1) * pageLength;
        const end = start + pageLength;
        row.style.display = (idx >= start && idx < end) ? '' : 'none';
      });

      const start = (currentPage - 1) * pageLength;
      const endCount = Math.min(start + pageLength, total);
      updateInfo(start, endCount, total);
      renderPagination(pages);
    }

    items.forEach(function (it) {
      it.addEventListener('click', function (e) {
        e.preventDefault();
        const len = parseInt(it.getAttribute('data-page-length'), 10);
        if (!isNaN(len) && len > 0) {
          pageLength = len;
          localStorage.setItem('gastos_page_len', String(pageLength));
          setBtnText();
          goTo(1);
          if (lenMenu) lenMenu.classList.remove('show');
          if (lenBtn) lenBtn.setAttribute('aria-expanded', 'false');
        }
      });
    });

    setBtnText();
    goTo(1);
  }

  function initExports() {
    function cleanQS(qs) {
      ['page', 'pend_view', 'accion'].forEach(function (k) {
        qs.delete(k);
      });
      return qs;
    }

    function exportAll(btnId) {
      const btn = document.getElementById(btnId);
      if (!btn) return;

      btn.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const baseUrl = btn.dataset.exportUrl;
        if (!baseUrl) return;

        const qs = cleanQS(new URLSearchParams(window.location.search));
        qs.delete('ids');
        qs.set('accion', 'buscar');
        qs.set('buscar', '1');

        window.location.href = baseUrl + '?' + qs.toString();
      }, true);
    }

    exportAll('btnExcelVisible');
    exportAll('btnReporteExcel');
  }

  document.addEventListener('DOMContentLoaded', function () {
    removeOneShotStatusAlert();
    initThemeToggle();
    initDefaultDates();
    initQuickDateRanges();
    initAutoSubmitFilters();
    initSortAndPagination();
    initExports();
  });
})();