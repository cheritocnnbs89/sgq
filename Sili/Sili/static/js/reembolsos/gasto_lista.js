document.addEventListener('DOMContentLoaded', function () {
  const cfg = document.getElementById('gasto-lista-config');

  const csrfToken = cfg?.dataset.csrfToken || '';
  const listaGastosUrl = cfg?.dataset.listaGastosUrl || '';
  const bulkAprobarUrl = cfg?.dataset.aprobarGastoMasivoUrl || '';
  const bulkSapUrl = cfg?.dataset.enviarGastoSapMasivoUrl || '';
  const isCoord = (cfg?.dataset.isCoord || '0') === '1';
  const statusDeleted = (cfg?.dataset.statusDeleted || '0') === '1';

  function showToast(msg) {
    const t = document.getElementById('toast');
    if (t && window.bootstrap) {
      const body = t.querySelector('.toast-body');
      if (body) {
        body.textContent = msg;
      }
      bootstrap.Toast.getOrCreateInstance(t).show();
    } else {
      alert(msg);
    }
  }

  function showBulkOverlay() {
    const overlay = document.getElementById('bulkOverlay');
    if (overlay) {
      overlay.classList.add('is-visible');
    }
  }

  function hideBulkOverlay() {
    const overlay = document.getElementById('bulkOverlay');
    if (overlay) {
      overlay.classList.remove('is-visible');
    }
  }

  function parseSpanishNumber(value) {
    if (!value) return 0;
    const normalized = value.replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '');
    const parsed = parseFloat(normalized);
    return isNaN(parsed) ? 0 : parsed;
  }

  function isVisibleElement(el) {
    return !!(el && el.offsetParent !== null);
  }

  function submitClosestForm(el) {
    const form = el?.closest('form');
    if (form) {
      form.submit();
    }
  }

  const tipoGasto = document.getElementById('tipo_gasto');
  if (tipoGasto) {
    tipoGasto.addEventListener('change', function () {
      submitClosestForm(tipoGasto);
    });
  }

  const ccb = document.getElementById('ccb');
  if (ccb) {
    ccb.addEventListener('change', function () {
      submitClosestForm(ccb);
    });
  }

  const usuarioId = document.getElementById('usuario_id');
  if (usuarioId) {
    usuarioId.addEventListener('change', function () {
      submitClosestForm(usuarioId);
    });
  }

  const gerenteId = document.getElementById('gerente_id');
  if (gerenteId) {
    gerenteId.addEventListener('change', function () {
      submitClosestForm(gerenteId);
    });
  }

  const inpNombre = document.getElementById('proveedor_nombre');
  const hidProv = document.getElementById('proveedor');
  const hidProvId = document.getElementById('proveedor_id');

  if (inpNombre) {
    inpNombre.addEventListener('input', function () {
      if (!this.value.trim()) {
        if (hidProv) hidProv.value = '';
        if (hidProvId) hidProvId.value = '';
      }
    });
  }

  document.querySelectorAll('.js-delete-gasto-form').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      const ok = window.confirm('¿Eliminar el registro? Esta acción es irreversible.');
      if (!ok) {
        ev.preventDefault();
      }
    });
  });

  if (statusDeleted) {
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

  document.querySelectorAll('[data-range]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const desde = document.querySelector('[name="desde"]');
      const hasta = document.querySelector('[name="hasta"]');
      if (!desde || !hasta) return;

      const pad = (n) => String(n).padStart(2, '0');
      const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

      const t = new Date();
      const c = new Date(t);
      const end = fmt(t);
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

  (function initDefaultDates() {
    const pad = (n) => String(n).padStart(2, '0');
    const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const desde = document.querySelector('input[name="desde"]');
    const hasta = document.querySelector('input[name="hasta"]');

    const qs = new URLSearchParams(location.search);
    const special = ['ccb', 'pendientes'].some(k => qs.get(k) === '1');

    if (!special) {
      const today = fmt(new Date());
      if (desde && !desde.value) desde.value = today;
      if (hasta && !hasta.value) hasta.value = today;
    }

    const form = desde?.closest('form');
    if (form && !qs.has('desde') && !qs.has('hasta') && !special) {
      form.submit();
    }
  })();

  document.querySelectorAll('button[data-flag]').forEach(function (btn) {
    btn.addEventListener('click', function (ev) {
      ev.preventDefault();
      const flag = btn.dataset.flag;
      const u = new URL(listaGastosUrl, window.location.origin);
      u.searchParams.set(flag, '1');
      u.searchParams.delete('desde');
      u.searchParams.delete('hasta');
      window.location.href = u.toString();
    });
  });

  const btnPend = document.getElementById('btnPend');
  if (btnPend) {
    btnPend.addEventListener('click', function (ev) {
      ev.preventDefault();
      const u = new URL(listaGastosUrl, window.location.origin);
      u.searchParams.set('pendientes', '1');
      window.location.href = u.toString();
    });
  }

  (function initSortSimple() {
    const table = document.getElementById('tabla-gastos');
    if (!table) return;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;

    let rows = Array.from(tbody.querySelectorAll('tr[data-row="1"]'));
    let sortState = { index: -1, dir: 'asc' };

    function cellVal(tr, idx, type) {
      const txt = (tr.children[idx]?.textContent || '').trim();
      if (type === 'num') return parseSpanishNumber(txt);
      if (type === 'date') {
        const t = Date.parse(txt.replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$3-$2-$1')) || Date.parse(txt);
        return isNaN(t) ? 0 : t;
      }
      return txt.toLocaleLowerCase();
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

      rows.sort(function (a, b) {
        const va = cellVal(a, idx, type);
        const vb = cellVal(b, idx, type);
        let c = 0;
        if (va > vb) c = 1;
        else if (va < vb) c = -1;
        return sortState.dir === 'asc' ? c : -c;
      });

      const frag = document.createDocumentFragment();
      rows.forEach(function (r) {
        frag.appendChild(r);
      });

      const totals = tbody.querySelector('tr[data-totales="1"]');
      if (totals) tbody.insertBefore(frag, totals);
      else tbody.appendChild(frag);

      clearIcons();
      th.classList.add(sortState.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
      setIcon(th, sortState.dir);
    }

    thead.querySelectorAll('th[data-sort]').forEach(function (th) {
      const type = (th.getAttribute('data-sort') || 'text').toLowerCase();
      const handle = th.querySelector('.th-sortable') || th;
      handle.setAttribute('role', 'button');
      handle.setAttribute('tabindex', '0');

      handle.addEventListener('click', function () {
        const idx = Array.from(th.parentElement.children).indexOf(th);
        applySort(th, idx, type);
      });

      handle.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handle.click();
        }
      });
    });

    clearIcons();
  })();

  (function initPagination() {
    const table = document.getElementById('tabla-gastos');
    if (!table) return;

    const tbody = table.querySelector('tbody');
    const thead = table.querySelector('thead');
    const info = document.getElementById('tableInfo');
    const pager = document.getElementById('pagination');
    const lenBtn = document.getElementById('pageLengthBtn');
    const lenMenu = lenBtn?.closest('.dropdown')?.querySelector('.dropdown-menu');
    const items = lenMenu ? lenMenu.querySelectorAll('[data-page-length]') : [];
    let dataRows = Array.from(tbody.querySelectorAll('tr[data-row="1"]'));
    let pageLength = parseInt(localStorage.getItem('gastos_page_len') || '15', 10);
    let currentPage = 1;

    function setBtnText() {
      if (lenBtn) lenBtn.textContent = `Mostrar ${pageLength} filas`;
    }

    function updateInfo(start, end, total) {
      if (info) {
        info.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total} registros`;
      }
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

      pager.appendChild(mkItem('Anterior', currentPage - 1, currentPage === 1, false));
      for (let p = 1; p <= N; p++) {
        pager.appendChild(mkItem(String(p), p, false, p === currentPage));
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
        }
      });
    });

    setBtnText();
    goTo(1);
  })();

   const chkSelectAllVisible = document.getElementById('chkSelectAllVisible');
  if (chkSelectAllVisible) {
    chkSelectAllVisible.addEventListener('change', function (e) {
      const checked = e.target.checked;

      document.querySelectorAll('.row-select').forEach(function (chk) {
        const row = chk.closest('tr[data-row="1"]');

        if (!row) return;
        if (chk.disabled) return;
        if (!isVisibleElement(row)) return;
        if (row.style.display === 'none') return;

        if (!checked) {
          chk.checked = false;
          return;
        }

        if (isCoord) {
          chk.checked = (chk.dataset.canSap === '1');
          return;
        }

        const canGA = chk.dataset.canGa === '1';
        const canGG = chk.dataset.canGg === '1';
        const canGF = chk.dataset.canGf === '1';
        const free = chk.dataset.freeSelect === '1';
        chk.checked = free || canGA || canGG || canGF;
      });
    });
  }

  document.addEventListener('click', async function (ev) {
    const btn = ev.target.closest('.btn-ver-gasto');
    if (!btn) return;

    const modalEl = document.getElementById('modalVerGasto');
    const iframe = document.getElementById('iframeVerGasto');
    if (!modalEl || !iframe || !window.bootstrap) return;

    ev.preventDefault();
    iframe.src = btn.dataset.url || '';
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  });

  const modalVerGasto = document.getElementById('modalVerGasto');
  if (modalVerGasto) {
    modalVerGasto.addEventListener('hidden.bs.modal', function () {
      const iframe = document.getElementById('iframeVerGasto');
      if (iframe) iframe.src = '';
    });
  }

  document.addEventListener('click', async function (ev) {
    const btn = ev.target.closest('.js-ver-adjuntos');
    if (!btn) return;

    const modalEl = document.getElementById('modalAdjuntosGasto');
    const bodyEl = document.getElementById('adjuntos-body');
    if (!modalEl || !bodyEl || !window.bootstrap) return;

    ev.preventDefault();
    const gid = btn.getAttribute('data-gasto-id');
    if (!gid) return;

    bodyEl.innerHTML = "<div class='text-muted'>Cargando…</div>";
    bootstrap.Modal.getOrCreateInstance(modalEl).show();

    try {
      const resp = await fetch(`/reembolsos/gastos/${gid}/adjuntos`, {
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      bodyEl.innerHTML = await resp.text();
    } catch (e) {
      bodyEl.innerHTML = "<div class='alert alert-danger mb-0'>No se pudo cargar los adjuntos.</div>";
    }
  }, true);

  (function initTheme() {
    const key = 'ui_theme';
    const root = document.documentElement;
    const apply = function (mode) {
      root.classList.toggle('theme-dark', mode === 'dark');
      localStorage.setItem(key, mode);
    };

    apply(localStorage.getItem(key) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', function () {
        apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
      });
    }
  })();

  document.querySelectorAll('button.btn-sap').forEach(function (btn) {
    if (btn.dataset.bound === '1') return;
    btn.dataset.bound = '1';

    btn.addEventListener('click', async function (ev) {
      ev.preventDefault();
      ev.stopPropagation();

      if (btn.disabled || btn.hasAttribute('disabled')) {
        return;
      }

      const row = btn.closest('tr[data-row="1"]');
      const proveedor = btn.getAttribute('data-proveedor') ||
        row?.querySelector('[data-th="Proveedor"]')?.textContent.trim() || '';

      if (!window.confirm('¿Enviar el gasto a SAP' + (proveedor ? (' de "' + proveedor + '"') : '') + '?')) {
        return;
      }

      const url = btn.getAttribute('data-url');
      const prevHTML = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      try {
        const resp = await fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          }
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.ok) throw new Error(data.msg || ('HTTP ' + resp.status));

        const docCell = row?.querySelector('[data-th="Doc. SAP"]');
        if (docCell) docCell.textContent = data.doc || '';
        if (row) row.dataset.sap = '1';

        btn.title = 'Ya contabilizado en SAP';
        showToast('Enviado a SAP. Doc: ' + (data.doc || '—'));
      } catch (err) {
        showToast('Error al enviar a SAP: ' + err.message);
        btn.disabled = false;
      } finally {
        btn.innerHTML = prevHTML;
      }
    });
  });

  const btnSapMasivo = document.getElementById('btnSapMasivo');
  if (btnSapMasivo) {
    btnSapMasivo.addEventListener('click', async function () {
      const ids = Array.from(document.querySelectorAll('.row-select:checked'))
        .filter(chk => chk.dataset.canSap === '1')
        .map(chk => parseInt(chk.dataset.id, 10))
        .filter(Boolean);

      if (!ids.length) {
        return showToast('Selecciona gastos listos para SAP (GG aprobado y sin Doc SAP).');
      }

      if (!window.confirm(`¿Enviar ${ids.length} gasto(s) a SAP?`)) return;

      btnSapMasivo.disabled = true;
      showBulkOverlay();

      try {
        const resp = await fetch(bulkSapUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ ids })
        });

        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.ok) throw new Error(data.msg || `HTTP ${resp.status}`);

        (data.results || []).forEach(function (r) {
          const chk = document.querySelector(`.row-select[data-id="${r.id}"]`);
          const row = chk?.closest('tr[data-row="1"]');
          if (!row || !r.ok) return;

          const docCell = row.querySelector('[data-th="Doc. SAP"]');
          if (docCell) docCell.textContent = r.doc || '';
          row.dataset.sap = '1';

          const sapBtn = row.querySelector('.btn-sap');
          if (sapBtn) {
            sapBtn.disabled = true;
            sapBtn.title = 'Ya contabilizado en SAP';
          }

          if (chk) {
            chk.checked = false;
            chk.disabled = true;
          }
        });

        showToast(`SAP masivo: ${data.sent || 0} enviado(s), ${data.errors || 0} con error.`);
      } catch (e) {
        showToast('Error SAP masivo: ' + e.message);
      } finally {
        hideBulkOverlay();
        btnSapMasivo.disabled = false;
      }
    });
  }

  document.addEventListener('click', async function (ev) {
    const btn = ev.target.closest('.bulk-approve');
    if (!btn) return;

    ev.preventDefault();
    ev.stopPropagation();

    const area = (btn.dataset.area || '').toLowerCase();
    const ids = Array.from(document.querySelectorAll('.row-select:checked'))
      .filter(function (chk) {
        if (area === 'ga') return chk.dataset.canGa === '1';
        if (area === 'gg') return chk.dataset.canGg === '1' || chk.dataset.freeSelect === '1';
        if (area === 'gf') return chk.dataset.canGf === '1';
        return true;
      })
      .map(chk => parseInt(chk.dataset.id, 10))
      .filter(n => Number.isFinite(n) && n > 0);

    if (!ids.length) {
      return showToast('Selecciona gastos elegibles para aprobar.');
    }

    if (!window.confirm(`¿Aprobar ${ids.length} gasto(s) como ${area.toUpperCase()}?`)) {
      return;
    }

    btn.disabled = true;
    showBulkOverlay();

    try {
      const resp = await fetch(bulkAprobarUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ area, ids, value: true })
      });

      const ct = (resp.headers.get('content-type') || '').toLowerCase();
      if (!ct.includes('application/json')) {
        throw new Error('Respuesta no JSON (posible login/CSRF/error HTML).');
      }

      const data = await resp.json();
      let msg = `Aprobados: ${data.approved_count || 0}`;
      if ((data.skipped_count || 0) > 0 && data.skipped?.length) {
        msg += ` | Saltados: ${data.skipped_count} (Ej: ${data.skipped[0].id}: ${data.skipped[0].msg})`;
      }
      if ((data.failed_count || 0) > 0 && data.failed?.length) {
        msg += ` | Fallidos: ${data.failed_count} (Ej: ${data.failed[0].id}: ${data.failed[0].msg})`;
      }

      showToast(msg);
      window.setTimeout(function () {
        location.reload();
      }, 2000);
    } catch (err) {
      showToast('Error masivo: ' + err.message);
    } finally {
      hideBulkOverlay();
      btn.disabled = false;
    }
  }, true);

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
      const qs = cleanQS(new URLSearchParams(window.location.search));
      qs.delete('ids');
      qs.set('accion', 'buscar');
      qs.set('buscar', '1');

      window.location.href = `${baseUrl}?${qs.toString()}`;
    }, true);
  }

  exportAll('btnExcelVisible');
  exportAll('btnExcelFiltrado');
  exportAll('btnReporteExcel');
});