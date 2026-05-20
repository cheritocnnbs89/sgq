(() => {
  const form = document.getElementById('frmGasto');
  if (!form) return;

  const csrfToken = form.querySelector('input[name="csrf_token"]')?.value || '';

  const routes = {
    apiParamCentros: form.dataset.apiParamCentros || '',
    apiParamMotivos: form.dataset.apiParamMotivos || '',
    apiFacturasXmlSearch: form.dataset.apiFacturasXmlSearch || '',
    apiProveedoresSearch: form.dataset.apiProveedoresSearch || '',
    apiNextCajaChicaFactura: form.dataset.apiNextCajaChicaFactura || '',
    xmlIndex: form.dataset.xmlIndex || '',
    listaGastos: form.dataset.listaGastos || '',
    apiFacturaXmlResumenBase: form.dataset.apiFacturaXmlResumenBase || '/reembolsos/api/factura_xml/'
  };

  function parsePredet() {
    const raw = form.dataset.detalles || '[]';
    try {
      return JSON.parse(raw);
    } catch (_) {
      return [];
    }
  }

  const PREDET = parsePredet();
  document.addEventListener('DOMContentLoaded', function () {
    const today = new Date();

    const anio = document.querySelector('input[name="anio"]');
    const mes = document.querySelector('input[name="mes"]');
    const dia = document.querySelector('input[name="dia"]');

    if (anio && !String(anio.value || '').trim()) {
      anio.value = today.getFullYear();
    }

    if (mes && !String(mes.value || '').trim()) {
      mes.value = today.getMonth() + 1;
    }

    if (dia && !String(dia.value || '').trim()) {
      dia.value = today.getDate();
    }
  });
  window.__lastFacturaXMLPayload = null;

  window.__applyFacturaXMLPayload = function (payload) {
    const body = document.getElementById('det-body');
    if (!payload || !body || typeof window.gastosPrefillFromFacturaXML !== 'function') {
      window.__lastFacturaXMLPayload = payload || null;
      return;
    }
    window.gastosPrefillFromFacturaXML(payload);
    window.__lastFacturaXMLPayload = null;
  };

  if (window.__lastFacturaXMLPayload) {
    window.__applyFacturaXMLPayload(window.__lastFacturaXMLPayload);
  }

  function getCsrfHeaders(includeContentType = false) {
    const headers = {
      'X-CSRFToken': csrfToken,
      'X-Requested-With': 'XMLHttpRequest'
    };
    if (includeContentType) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }

  function toNum(v) {
    if (v == null) return 0;
    const s = String(v).trim().replace(/\s+/g, '').replace(',', '.');
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : 0;
  }

  function getTipoRegistro() {
    return (document.querySelector('input[name="tipo_registro"]')?.value || '').trim().toLowerCase();
  }

  function getTipoCajaChica() {
    const hidden = document.getElementById('tipo_caja_chica');
    const fromHidden = hidden ? hidden.value : '';
    const fromDataset = form.dataset.tipoCajaChica || '';
    return String(fromHidden || fromDataset || 'NINGUNA').trim().toUpperCase();
  }

  function isCajaChicaTradicionalC0() {
    return getTipoRegistro() === 'caja_chica' && getTipoCajaChica() === 'C0';
  }

  function isCajaChicaConDetalle() {
    return getTipoRegistro() === 'caja_chica' && getTipoCajaChica() === 'DETALLE_FACTURA';
  }

  window.getTipoCajaChica = getTipoCajaChica;
  window.isCajaChicaTradicionalC0 = isCajaChicaTradicionalC0;
  window.isCajaChicaConDetalle = isCajaChicaConDetalle;

  function isTarjetaSinSoporteChecked() {
    const chk = document.getElementById('tarjeta_sin_soporte');
    return !!(chk && chk.checked);
  }

  function isReembolsoVendedor() {
    const tipo = getTipoRegistro();
    const tipoCajaChica = getTipoCajaChica();
    const chkVend = document.getElementById('reembolso_vendedor');
    const esChkVend = !!(chkVend && chkVend.checked);

    if (tipo === 'caja_chica' && tipoCajaChica === 'DETALLE_FACTURA') {
      return false;
    }

    return (tipo === 'reembolso') || esChkVend || (tipo === 'caja_chica' && tipoCajaChica === 'C0');
  }

  window.isReembolsoVendedor = isReembolsoVendedor;

 
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
 

  document.addEventListener('DOMContentLoaded', function () {
    const $ = (sel) => document.querySelector(sel);
    const setVal = (sel, v) => {
      const el = $(sel);
      if (el) el.value = v || '';
    };
    const ymd = (s) => {
      if (!s) return '';
      let m = s.match(/^(\d{2})[\/\-](\d{2})[\/\-](\d{4})$/);
      if (m) return `${m[3]}-${m[2]}-${m[1]}`;
      m = s.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/);
      if (m) return `${m[1]}-${m[2]}-${m[3]}`;
      return s;
    };

    let xmlWin = null;
    const btn = document.getElementById('btnCargarXml');
    if (btn) {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        xmlWin = window.open(
          routes.xmlIndex,
          'sri_xml',
          'width=980,height=700,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes'
        );
      });
    }

    async function fillFromXml(p) {
      setVal('#proveedor_nombre', p.proveedorNombre);
      setVal('#proveedor', p.proveedorNombre);
      const ruc =
        p.proveedorRuc ||
        p.rucEmisor ||
        p.ruc_emisor ||
        p.ruc ||
        p.identificacion_emisor ||
        p.identificacion ||
        '';
      setVal('#proveedor_identificacion', ruc);

      try {
        if (window.intentarResolverProveedorId) {
          await window.intentarResolverProveedorId(p.proveedorNombre, ruc);
        }
      } catch (_) { }

      setVal('#numero_factura', p.serie || '');
      setVal('#fecha_autorizacion', ymd(p.fechaAut || ''));
      setVal('#clave_autorizacion', p.clave || '');
      if (xmlWin && !xmlWin.closed) xmlWin.close();
    }

    window.addEventListener('message', (ev) => {
      if (ev.origin !== location.origin) return;
      if (ev.data && ev.data.type === 'sri-invoice') fillFromXml(ev.data.payload);
    });

    if ('BroadcastChannel' in window) {
      const bc = new BroadcastChannel('sri-xml');
      bc.addEventListener('message', (ev) => {
        if (ev.data && ev.data.type === 'sri-invoice') fillFromXml(ev.data.payload);
      });
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    const $search = document.getElementById('factura_xml_search');
    const $dl = document.getElementById('dl-facturas-xml');
    const $idField = document.getElementById('factura_xml_id');
    const $numero = document.getElementById('numero_factura');
    const $fechaAut = document.getElementById('fecha_autorizacion');
    const $clave = document.getElementById('clave_autorizacion');

    const $provNombre = document.getElementById('proveedor_nombre');
    const $provTxt = document.getElementById('proveedor');
    const $provId = document.getElementById('proveedor_id');
    const $provIdent = document.getElementById('proveedor_identificacion');

    if (!$search || !$dl || !$idField) return;

    const MIN_CHARS = 2;
    const MAX = 3;
    let t = null;

    function normalizeDateForInput(s) {
      if (!s) return '';
      s = String(s).trim();
      if (s.length > 10 && /^\d{4}-\d{2}-\d{2}/.test(s)) {
        return s.slice(0, 10);
      }
      let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (m) return s;
      m = s.match(/^(\d{2})[\/\-](\d{2})[\/\-](\d{4})$/);
      if (m) return `${m[3]}-${m[2]}-${m[1]}`;
      return '';
    }

    function fillList(list) {
      $dl.innerHTML = '';
      (list || []).slice(0, MAX).forEach(item => {
        const opt = document.createElement('option');
        const numero = item.numero || '';
        const emisor = item.razon_social_emisor || item.proveedorNombre || '';

        const rawFecha =
          item.fecha_autorizacion ||
          item.fecha_emision ||
          '';

        const fechaNorm = normalizeDateForInput(rawFecha);

        opt.value = numero;
        opt.label = `${numero} — ${emisor} — ${rawFecha || ''}`;
        opt.dataset.id = item.id || '';
        opt.dataset.fecha_autorizacion = fechaNorm;
        opt.dataset.clave = item.clave_acceso || '';
        opt.dataset.proveedor_nombre = emisor;
        opt.dataset.proveedor_ruc =
          item.ruc_emisor ||
          item.rucEmisor ||
          item.proveedorRuc ||
          item.ruc ||
          item.emisor_ruc ||
          item.identificacion_emisor ||
          item.identificacion ||
          '';

        $dl.appendChild(opt);
      });
    }

    function fetchFacturas(q) {
      if (!routes.apiFacturasXmlSearch) return;
      const url = new URL(routes.apiFacturasXmlSearch, window.location.origin);
      if ((q || '').length >= MIN_CHARS) {
        url.searchParams.set('q', q);
      }
      url.searchParams.set('limit', String(MAX));
      fetch(url, {
        credentials: 'same-origin',
        headers: getCsrfHeaders(true)
      })
        .then(r => r.json())
        .then(fillList)
        .catch(() => { });
    }

    window.intentarResolverProveedorId = async function (nombreProveedor, identificacion) {
      if (!$provId || !routes.apiProveedoresSearch) return;

      if (($provId.value || '').trim() && $provIdent && ($provIdent.value || '').trim()) {
        return;
      }

      try {
        let url;

        if (identificacion && identificacion.trim()) {
          url = new URL(routes.apiProveedoresSearch, window.location.origin);
          url.searchParams.set('identificacion', identificacion.trim());
          url.searchParams.set('limit', '5');
        } else if (nombreProveedor && nombreProveedor.trim()) {
          url = new URL(routes.apiProveedoresSearch, window.location.origin);
          url.searchParams.set('q', nombreProveedor.trim());
          url.searchParams.set('limit', '5');
        } else {
          return;
        }

        const r = await fetch(url, {
          credentials: 'same-origin',
          headers: getCsrfHeaders(true)
        });
        const list = await r.json();
        if (!Array.isArray(list) || !list.length) return;

        const match =
          (identificacion &&
            list.find(x =>
              (x.identificacion || '').replace(/\s+/g, '') === identificacion.replace(/\s+/g, '')
            )) ||
          list.find(x => (x.nombre || '').toLowerCase().includes((nombreProveedor || '').toLowerCase())) ||
          list[0];

        if (match && match.id) {
          $provId.value = match.id;

          if ($provNombre && !($provNombre.value || '').trim()) {
            $provNombre.value = match.nombre || nombreProveedor || '';
          }
          if ($provTxt && !($provTxt.value || '').trim()) {
            $provTxt.value = $provNombre.value;
          }

          if ($provIdent) {
            const ident =
              match.identificacion ||
              match.ruc ||
              match.ruc_emisor ||
              match.rucEmisor ||
              match.proveedorRuc ||
              match.identificacion_emisor ||
              ($provIdent.value || '');
            $provIdent.value = ident;
          }
        }
      } catch (_) { }
    };

    function syncSelection() {
      const val = ($search.value || '').trim();
      if (!val) {
        $idField.value = '';
        return;
      }

      const match = Array.from($dl.options)
        .find(o => (o.value || '').toLowerCase() === val.toLowerCase());

      if (!match) {
        $idField.value = '';
        return;
      }

      $idField.value = match.dataset.id || '';

      if ($numero && !$numero.value) {
        $numero.value = match.value || '';
      }
      if ($fechaAut && match.dataset.fecha_autorizacion) {
        $fechaAut.value = match.dataset.fecha_autorizacion;
      }
      if ($clave && match.dataset.clave) {
        $clave.value = match.dataset.clave;
      }

      const provNombre = match.dataset.proveedor_nombre || '';
      const provRuc = match.dataset.proveedor_ruc || '';

      if (provNombre) {
        if ($provNombre) $provNombre.value = provNombre;
        if ($provTxt) $provTxt.value = provNombre;
      }

      if (provRuc && $provIdent) {
        $provIdent.value = provRuc;
      }

      const fid = match.dataset.id;
      if (!fid) return;

      const url = new URL(`${routes.apiFacturaXmlResumenBase}${fid}/resumen`, window.location.origin);

      fetch(url, {
        credentials: 'same-origin',
        headers: getCsrfHeaders(true)
      })
        .then(r => r.json())
        .then(data => {
          if (!data) return;

          let payload = null;

          if (data.payload) payload = data.payload;
          else if (data.resumen) payload = data.resumen;
          else if (data.factura) payload = data.factura;
          else payload = data;

          if (data.ok === false) {
            return;
          }

          if ($provIdent) {
            const ruc =
              payload.proveedorRuc ||
              payload.rucEmisor ||
              payload.ruc_emisor ||
              payload.ruc ||
              payload.identificacion_emisor ||
              payload.identificacion ||
              ($provIdent.value || '');
            if (ruc) $provIdent.value = ruc;
          }

          if (window.intentarResolverProveedorId) {
            window.intentarResolverProveedorId(
              payload.proveedorNombre || provNombre,
              $provIdent ? $provIdent.value : ''
            );
          }

          if (window.__applyFacturaXMLPayload) {
            window.__applyFacturaXMLPayload(payload);
          } else if (window.gastosPrefillFromFacturaXML) {
            window.gastosPrefillFromFacturaXML(payload);
          }
        })
        .catch(() => { });
    }

    fetchFacturas('');

    $search.addEventListener('input', (e) => {
      const q = e.target.value || '';
      clearTimeout(t);
      t = setTimeout(() => fetchFacturas(q), 220);
    });

    $search.addEventListener('change', syncSelection);
    $search.addEventListener('blur', syncSelection);
  });

  (function () {
    const $body = document.getElementById('det-body');
    if (!$body) return;

    const $btnAdd = document.getElementById('btnAddDet');

    const sumIds = {
      'det_con_soporte': 'sum_con_soporte',
      'det_sin_soporte': 'sum_sin_soporte',
      'det_subtotal_factura': 'sum_subtotal_factura',
      'det_servicios_10': 'sum_servicios_10',
      'det_subtotal_sin_iva': 'sum_subtotal_sin_iva',
      'det_iva': 'sum_iva',
      'det_total_con_iva': 'sum_total_con_iva'
    };

    function sumByName(name) {
      return Array.from($body.querySelectorAll(`input[name="${name}"]`))
        .reduce((acc, el) => acc + toNum(el.value), 0);
    }

    function recalcTotals() {
      const totals = {};

      for (const [name, id] of Object.entries(sumIds)) {
        const total = sumByName(name);
        totals[id] = total;

        const $sum = document.getElementById(id);
        if ($sum) $sum.value = total.toFixed(2);
      }

      const $hSin = document.getElementById('h_sum_sin_soporte');
      if ($hSin) $hSin.value = (totals.sum_sin_soporte ?? 0).toFixed(2);

      const $hSub = document.getElementById('h_subtotal_factura');
      if ($hSub) $hSub.value = (totals.sum_subtotal_factura ?? 0).toFixed(2);

      const $hIva = document.getElementById('h_iva');
      if ($hIva) $hIva.value = (totals.sum_iva ?? 0).toFixed(2);

      const $hTot = document.getElementById('h_total_con_iva');
      if ($hTot) $hTot.value = (totals.sum_total_con_iva ?? 0).toFixed(2);
    }

    function computeRow($tr) {
      const $con = $tr.querySelector('input[name="det_con_soporte"]');
      const $sin = $tr.querySelector('input[name="det_sin_soporte"]');
      const $subf = $tr.querySelector('input[name="det_subtotal_factura"]');
      const $s10 = $tr.querySelector('input[name="det_servicios_10"]');
      const $ssi = $tr.querySelector('input[name="det_subtotal_sin_iva"]');
      const $iva = $tr.querySelector('input[name="det_iva"]');
      const $tot = $tr.querySelector('input[name="det_total_con_iva"]');
      const $ind = $tr.querySelector('input[name="det_indicador"]');

      const con = toNum($con?.value);
      const sin = toNum($sin?.value);
      const ssi = toNum($ssi?.value);

      const subfVal = con + sin;
      if ($subf) $subf.value = subfVal.toFixed(2);

      if ($ind) {
        const tipo = getTipoRegistro();
        const tipoCajaChica = getTipoCajaChica();
        const esCajaChicaC0 = (tipo === 'caja_chica' && tipoCajaChica === 'C0');
        const esCajaChicaDetalle = (tipo === 'caja_chica' && tipoCajaChica === 'DETALLE_FACTURA');
        const esReembolso = (tipo === 'reembolso');
        const esTarjetaSinSoporte = !!document.getElementById('tarjeta_sin_soporte')?.checked;
        const esModoSinSoporteUI = esCajaChicaC0 || esReembolso || esTarjetaSinSoporte;

        const cur = ($ind.value || '').toUpperCase().trim();
        const yaEsValido = ['CE', 'CH', 'C0'].includes(cur);

        if (esModoSinSoporteUI) {
          $ind.value = 'C0';
        } else if (!yaEsValido || esCajaChicaDetalle) {
          if (sin > 0 && con === 0) {
            $ind.value = 'C0';
          } else if (con > 0 && sin === 0) {
            const ivaVal = toNum($iva?.value);
            let pct = 0;
            if (con > 0 && ivaVal > 0) pct = Math.round((ivaVal / con) * 100);

            if (pct === 8) $ind.value = 'CH';
            else if (pct === 15) $ind.value = 'CE';
            else $ind.value = '';
          } else {
            $ind.value = '';
          }
        }
      }

      if ($iva && ssi <= 0) {
        const ind = ($ind?.value || '').toUpperCase().trim();
        const rate = (ind === 'CH') ? 0.08 : (ind === 'CE') ? 0.15 : 0.00;
        $iva.value = (con * rate).toFixed(2);
      }

      const iva = toNum($iva?.value);
      const s10 = toNum($s10?.value);

      const total = subfVal + iva + ssi + s10;
      if ($tot) $tot.value = total.toFixed(2);
    }

    function bindRowEvents($tr) {
      const inputs = $tr.querySelectorAll('input,textarea');
      inputs.forEach(inp => {
        inp.addEventListener('input', () => {
          computeRow($tr);
          recalcTotals();
        });
        inp.addEventListener('change', () => {
          computeRow($tr);
          recalcTotals();
        });
      });

      const btnDel = $tr.querySelector('.btn-remove-row');
      if (btnDel) {
        btnDel.addEventListener('click', () => {
          if ($body.children.length <= 1) return;
          $tr.remove();
          recalcTotals();
        });
      }
      computeRow($tr);
    }

    function esc(v = '') {
      return String(v).replace(/"/g, '&quot;').replace(/</g, '&lt;');
    }

    function addRow(data = {}) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <textarea name="det_observacion" class="form-control" rows="1">${esc(data.observacion || '')}</textarea>
        </td>

        <td>
          <input
            name="det_motivo"
            class="form-control"
            list="dl-motivos"
            required
            placeholder="Motivo"
            value="${esc(data.motivo || '')}"
            title="">
          <input type="hidden" name="det_motivo_valido" value="${esc(data.motivo || '')}">
        </td>

        <td>
          <input
            name="det_centro_costo"
            class="form-control"
            required
            list="dl-centros"
            placeholder="Centro de costo"
            value="${esc(data.centro_costo || '')}"
            title="">
          <input type="hidden" name="det_centro_costo_valido" value="${esc(data.centro_costo || '')}">
        </td>

        <td><input name="det_indicador" class="form-control" maxlength="2" required placeholder="C0/CE" value="${esc(data.indicador || '')}"></td>
        <td class="col-hide-soporte"><input type="number" step="0.01" min="0" name="det_con_soporte" class="form-control text-end" value="${data.con_soporte ?? 0}"></td>
        <td><input type="number" step="0.01" min="0" name="det_sin_soporte" class="form-control text-end" value="${data.sin_soporte ?? 0}"></td>
        <td class="col-subtotal-fac"><input type="number" step="0.01" min="0" name="det_subtotal_factura" class="form-control text-end" value="${data.subtotal_factura ?? 0}"></td>
        <td class="col-hide-soporte">
          <input type="number" step="0.01" min="0" name="det_servicios_10" class="form-control text-end" value="${data.servicios_10 ?? 0}">
        </td>
        <td class="col-hide-soporte">
          <input type="number" step="0.01" min="0" name="det_subtotal_sin_iva" class="form-control text-end" value="${data.subtotal_sin_iva ?? 0}">
        </td>
        <td><input type="number" step="0.01" min="0" name="det_iva" class="form-control text-end" value="${data.iva ?? 0}"></td>
        <td><input type="number" step="0.01" min="0" name="det_total_con_iva" class="form-control text-end" value="${data.total_con_iva ?? 0}"></td>
        <td><input name="det_descripcion" class="form-control" value="${esc(data.descripcion || '')}"></td>

        <td class="text-end">
          <button type="button" class="btn btn-outline-danger btn-sm btn-remove-row">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      `;
      $body.appendChild(tr);
      bindRowEvents(tr);
      recalcTotals();
    }

    function pickNum(obj, keys) {
      for (const k of keys) {
        if (obj && obj[k] != null && String(obj[k]).trim() !== '') {
          const n = toNum(obj[k]);
          if (n || n === 0) return n;
        }
      }
      return 0;
    }

    function getInfo(payload) {
      return payload?.infoFactura || payload?.info_factura || payload || {};
    }

    function normalizeTotalConImpuestos(payload) {
      const info = getInfo(payload);

      const tci =
        payload?.totalConImpuestos ||
        payload?.total_con_impuestos ||
        info?.totalConImpuestos ||
        info?.total_con_impuestos ||
        null;

      if (Array.isArray(tci)) return tci;

      if (tci && Array.isArray(tci.totalImpuesto)) return tci.totalImpuesto;
      if (tci && Array.isArray(tci.total_impuesto)) return tci.total_impuesto;

      return [];
    }

    function extractIvaBaseValor(payload) {
      const items = normalizeTotalConImpuestos(payload);

      const ivaItems = items.filter(it => String(it?.codigo ?? it?.codigo_impuesto ?? '') === '2');

      let chosen = null;
      for (const it of ivaItems) {
        const val = toNum(it?.valor ?? it?.valor_impuesto ?? it?.iva ?? it?.totalImpuesto);
        if (val > 0 && (!chosen || val > toNum(chosen?.valor ?? chosen?.valor_impuesto ?? chosen?.iva))) {
          chosen = it;
        }
      }

      if (!chosen) chosen = ivaItems[0] || null;

      const base = toNum(
        chosen?.baseImponible ??
        chosen?.base_imponible ??
        chosen?.baseIva ??
        chosen?.base_iva ??
        0
      );

      const valor = toNum(
        chosen?.valor ??
        chosen?.valor_impuesto ??
        chosen?.iva ??
        0
      );

      let pct = 0;

      const tarifaDirecta = toNum(
        chosen?.tarifa ??
        chosen?.porcentaje ??
        chosen?.rate ??
        chosen?.pct ??
        chosen?.porc ??
        0
      );

      if (tarifaDirecta > 0) {
        pct = Math.round(tarifaDirecta);
      } else if (base > 0 && valor > 0) {
        pct = Math.round((valor / base) * 100);
      }

      if (pct === 8) pct = 8;
      else if (pct === 15) pct = 15;
      else if (pct === 0) pct = 0;
      else {
        if (Math.abs(pct - 8) <= 1) pct = 8;
        else if (Math.abs(pct - 15) <= 1) pct = 15;
        else pct = 0;
      }

      return { base, valor, pct };
    }

    function prefillDetalleDesdeXML(payload = {}) {
      const info = getInfo(payload);

      const baseIvaFlat = pickNum(payload, ['base_iva', 'baseIva', 'subtotal_15']);
      const sub0Flat = pickNum(payload, ['subtotal_0', 'base_0']);

      let subtotal = (
        pickNum(info, [
          'totalSinImpuestos',
          'total_sin_impuestos',
          'subtotalSinImpuestos',
          'subtotal_sin_impuestos',
          'subtotal',
          'subtotal_factura'
        ]) ||
        pickNum(payload, [
          'subtotal',
          'subtotal_factura',
          'total_sin_impuestos',
          'totalSinImpuestos'
        ])
      );

      if (!subtotal && (baseIvaFlat > 0 || sub0Flat > 0)) {
        subtotal = baseIvaFlat + sub0Flat;
      }

      const total = (
        pickNum(info, ['importeTotal', 'importe_total']) ||
        pickNum(payload, ['total', 'importeTotal', 'importe_total'])
      );

      const propina = (
        pickNum(info, ['propina']) ||
        pickNum(payload, ['propina', 'servicios_10'])
      );

      let { base, valor, pct } = extractIvaBaseValor(payload);

      const tarifaPlana =
        pickNum(payload, ['iva_tarifa', 'tarifa_iva', 'tarifa']) ||
        pickNum(info, ['iva_tarifa', 'tarifa_iva', 'tarifa']) ||
        0;

      const pctSRI = (pct === 8 || pct === 15 || pct === 0) ? pct : 0;
      let tarifaPct = (tarifaPlana > 0) ? tarifaPlana : (pctSRI > 0 ? pctSRI : 15);

      if (!base && baseIvaFlat > 0) base = baseIvaFlat;

      if (!valor) {
        valor =
          pickNum(info, ['iva', 'total_iva', 'iva_total', 'valor_iva']) ||
          pickNum(payload, ['iva', 'total_iva', 'iva_total', 'valor_iva']);
      }

      if (!valor && base > 0) {
        valor = base * (tarifaPct / 100);
      }

      if (!base && valor > 0) {
        base = valor / (tarifaPct / 100);
      }

      const sub = (subtotal > 0)
        ? subtotal
        : (total > 0 ? Math.max(total - valor - propina, 0) : 0);

      const con = Math.max(base, 0);

      const sin = (sub0Flat > 0)
        ? sub0Flat
        : Math.max(sub - con, 0);

      $body.innerHTML = '';
      if (con > 0) {
        const pctNorm = Math.round(toNum(tarifaPct));
        const ind = (pctNorm === 8) ? 'CH' : 'CE';
        const rate = (ind === 'CH') ? 0.08 : 0.15;
        const ivaCalc = +(con * rate).toFixed(2);

        addRow({
          descripcion: payload.descripcion || '',
          observacion: '',
          centro_costo: '',
          motivo: '',
          indicador: ind,
          con_soporte: con,
          sin_soporte: 0,
          servicios_10: propina,
          subtotal_sin_iva: 0,
          iva: ivaCalc,
          total_con_iva: +(con + ivaCalc + propina).toFixed(2)
        });
      }

      if (sin > 0) {
        addRow({
          descripcion: payload.descripcion || '',
          observacion: '',
          centro_costo: '',
          motivo: '',
          indicador: 'C0',
          con_soporte: 0,
          sin_soporte: sin,
          servicios_10: propina,
          subtotal_sin_iva: 0,
          iva: 0
        });
      }

      if ($body.children.length === 0) addRow();

      recalcTotals();
    }

    window.gastosPrefillFromFacturaXML = function (payload) {
      try {
        prefillDetalleDesdeXML(payload);
      } catch (e) {
        console.error('Error en gastosPrefillFromFacturaXML:', e);
      }
    };

    if ($btnAdd) {
      $btnAdd.addEventListener('click', () => addRow());
    }

    if (Array.isArray(PREDET) && PREDET.length) {
      PREDET.forEach(r => addRow(r));
    } else {
      addRow();
    }
  })();

  document.addEventListener('DOMContentLoaded', function () {
    const $tbody = document.getElementById('det-body');
    const $dlMot = document.getElementById('dl-motivos');
    if (!$tbody || !$dlMot) return;

    const MAX_MOTIVOS = 3;
    const MIN_CHARS = 2;
    let t = null;

    function fillMotivos(list) {
      $dlMot.innerHTML = '';
      (list || []).slice(0, MAX_MOTIVOS).forEach(x => {
        const opt = document.createElement('option');
        opt.value = x.valor || '';
        opt.label = x.nombre ? `${x.nombre} (${x.valor || ''})` : (x.valor || '');
        $dlMot.appendChild(opt);
      });
    }

    function fetchMotivos(q) {
      if (!routes.apiParamMotivos) return;
      const url = new URL(routes.apiParamMotivos, location.origin);
      if ((q || '').length >= MIN_CHARS) url.searchParams.set('q', q);
      url.searchParams.set('limit', String(MAX_MOTIVOS));
      fetch(url, { credentials: 'same-origin' })
        .then(r => r.json())
        .then(fillMotivos)
        .catch(() => { });
    }

    fetchMotivos('');
    $tbody.addEventListener('input', (e) => {
      const el = e.target;
      if (el && el.name === 'det_motivo') {
        el.setAttribute('list', 'dl-motivos');
        clearTimeout(t);
        t = setTimeout(() => fetchMotivos(el.value || ''), 220);
      }
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    const tbody = document.getElementById('det-body');
    const dlMotivos = document.getElementById('dl-motivos');
    const dlCentros = document.getElementById('dl-centros');

    if (!tbody) return;

    function findExactOption(datalist, value) {
      const v = (value || '').trim().toLowerCase();
      if (!v || !datalist) return null;

      return Array.from(datalist.options).find(opt =>
        ((opt.value || '').trim().toLowerCase() === v)
      ) || null;
    }

    function setFieldFeedback(inputEl, ok, msg) {
      if (!inputEl) return;
      inputEl.classList.toggle('is-invalid', !ok);

      if (ok) {
        inputEl.removeAttribute('title');
        inputEl.dataset.errmsg = '';
      } else {
        inputEl.setAttribute('title', msg || 'Campo inválido');
        inputEl.dataset.errmsg = msg || 'Campo inválido';
      }
    }

    function validateInputAgainstDatalist(inputEl, datalistEl, hiddenName, message) {
      const tr = inputEl.closest('tr');
      if (!tr) return false;

      const hidden = tr.querySelector(`input[name="${hiddenName}"]`);
      if (!hidden) return false;

      const match = findExactOption(datalistEl, inputEl.value);

      if (match) {
        hidden.value = match.value || '';
        setFieldFeedback(inputEl, true, message);
        return true;
      } else {
        hidden.value = '';
        setFieldFeedback(inputEl, false, message);
        return false;
      }
    }

    tbody.addEventListener('input', function (e) {
      const el = e.target;
      if (!el) return;

      if (el.name === 'det_motivo') {
        const tr = el.closest('tr');
        const hidden = tr?.querySelector('input[name="det_motivo_valido"]');
        if (hidden) hidden.value = '';
        setFieldFeedback(el, true, 'Debe seleccionar un motivo válido de la lista.');
      }

      if (el.name === 'det_centro_costo') {
        const tr = el.closest('tr');
        const hidden = tr?.querySelector('input[name="det_centro_costo_valido"]');
        if (hidden) hidden.value = '';
        setFieldFeedback(el, true, 'Debe seleccionar un centro de costo válido de la lista.');
      }
    });

    tbody.addEventListener('change', function (e) {
      const el = e.target;
      if (!el) return;

      if (el.name === 'det_motivo') {
        validateInputAgainstDatalist(
          el,
          dlMotivos,
          'det_motivo_valido',
          'Debe seleccionar un motivo válido de la lista.'
        );
      }

      if (el.name === 'det_centro_costo') {
        validateInputAgainstDatalist(
          el,
          dlCentros,
          'det_centro_costo_valido',
          'Debe seleccionar un centro de costo válido de la lista.'
        );
      }
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    const $input = document.getElementById('proveedor_nombre');
    const $dl = document.getElementById('dl-proveedores');
    const $idField = document.getElementById('proveedor_id');
    const $txtBack = document.getElementById('proveedor');
    const $identField = document.getElementById('proveedor_identificacion');

    if (!$input || !$dl || !$idField || !$txtBack) return;

    $input.setAttribute('autocomplete', 'new-password');
    $input.setAttribute('autocorrect', 'off');
    $input.setAttribute('autocapitalize', 'none');
    $input.setAttribute('spellcheck', 'false');

    $input.dataset.initialName = ($input.value || '').trim();
    $idField.dataset.initialId = ($idField.value || '').trim();

    const isNumericOnly = s => /^\d+$/.test((s || '').trim());

    function seedCurrentOption() {
      const name = ($input.value || '').trim();
      const id = ($idField.value || '').trim();
      if (!name || !id) return;
      const exists = Array.from($dl.options).some(
        o => o.value === name && (o.dataset.id || '') === id
      );
      if (!exists) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.label = name;
        opt.dataset.id = id;
        opt.dataset.identificacion = ($identField && $identField.value) ? $identField.value : '';
        opt.dataset.seed = '1';
        $dl.appendChild(opt);
      }
    }

    let t = null;
    const MAX = 5;

    const fetchList = (q) => {
      if (!routes.apiProveedoresSearch) return;
      const url = new URL(routes.apiProveedoresSearch, window.location.origin);
      url.searchParams.set('limit', String(MAX));
      if ((q || '').length >= 1) url.searchParams.set('q', q);

      fetch(url, {
        credentials: 'same-origin',
        headers: getCsrfHeaders(true)
      })
        .then(r => r.json())
        .then(list => {
          $dl.innerHTML = '';
          seedCurrentOption();
          (list || [])
            .filter(it => !isNumericOnly(it.nombre))
            .slice(0, MAX)
            .forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.nombre || '';
              opt.label = item.nombre || '';
              opt.dataset.id = item.id || '';
              opt.dataset.identificacion =
                item.identificacion ||
                item.ruc ||
                item.ruc_emisor ||
                item.rucEmisor ||
                item.proveedorRuc ||
                item.identificacion_emisor ||
                '';
              $dl.appendChild(opt);
            });
        })
        .catch(() => { });
    };

    function findMatchInDatalist(q) {
      const qLower = (q || '').trim().toLowerCase();
      if (!qLower) return null;
      return Array.from($dl.options)
        .find(o =>
          (o.value || '').toLowerCase() === qLower ||
          (o.label || '').toLowerCase() === qLower
        );
    }

    function applyMatch(match) {
      if (!match) return false;

      $idField.value = match.dataset.id || '';

      if ($identField) {
        $identField.value = match.dataset.identificacion || '';
      }

      return !!($idField.value || '').trim();
    }

    async function ensureProveedorResuelto() {
      const q = ($input.value || '').trim();
      $txtBack.value = q;

      if (!q) {
        $idField.value = '';
        if ($identField) $identField.value = '';
        return false;
      }

      const match = findMatchInDatalist(q);
      if (applyMatch(match)) {
        return true;
      }

      if (window.intentarResolverProveedorId) {
        await window.intentarResolverProveedorId(q, '');
      }

      const match2 = findMatchInDatalist(q);
      if (applyMatch(match2)) {
        return true;
      }

      return !!($idField.value || '').trim();
    }

    seedCurrentOption();
    fetchList('');

    $input.addEventListener('input', (e) => {
      const q = e.target.value || '';
      clearTimeout(t);
      t = setTimeout(() => fetchList(q), 220);
    });

    $input.addEventListener('change', () => {
      ensureProveedorResuelto();
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    const fileInput = document.getElementById('archivo');
    const invalidMsg = document.getElementById('archivoInvalid');

    if (!form || !fileInput) return;

    function setInvalid(on) {
      if (on) {
        fileInput.classList.add('is-invalid');
        invalidMsg?.classList.add('d-block');
      } else {
        fileInput.classList.remove('is-invalid');
        invalidMsg?.classList.remove('d-block');
      }
    }

    fileInput.addEventListener('change', () => setInvalid(false));
  });

  const Busy = (() => {
    let modal;
    let el;
    let msgEl;

    function ensure() {
      el = el || document.getElementById('busyModal');
      if (!el || typeof bootstrap === 'undefined') return null;
      modal = bootstrap.Modal.getOrCreateInstance(el);
      msgEl = msgEl || document.getElementById('busyMsg');
      return modal;
    }

    return {
      show(msg = 'Por favor, espera…') {
        if (!ensure()) return;
        if (msgEl) msgEl.textContent = msg || '';
        modal.show();
      },
      hide() {
        try { modal?.hide(); } catch (_) { }
      }
    };
  })();

  async function withBusy(promiseOrFn, msg) {
    Busy.show(msg);
    try {
      const p = (typeof promiseOrFn === 'function') ? promiseOrFn() : promiseOrFn;
      return await p;
    } finally {
      Busy.hide();
    }
  }

  function lockButton(btn, text = 'Procesando…') {
    if (!btn) return () => { };
    const html = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `${text} <span class="spinner-border spinner-border-sm ms-2" aria-hidden="true"></span>`;
    return () => {
      btn.disabled = false;
      btn.innerHTML = html;
    };
  }

  window.withBusy = withBusy;
  window.lockButton = lockButton;

  document.addEventListener('DOMContentLoaded', function () {
    const btnSubmit = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return;
      Busy.show('Guardando gasto…');
      if (btnSubmit) btnSubmit.disabled = true;
    });
  });

  function applyTipoGastoUI() {
    const tipo = getTipoRegistro();
    const tipoCajaChica = getTipoCajaChica();
    const esCajaChicaC0 = (tipo === 'caja_chica' && tipoCajaChica === 'C0');
    const esCajaChicaDetalle = (tipo === 'caja_chica' && tipoCajaChica === 'DETALLE_FACTURA');
    const esReembolso = (tipo === 'reembolso');
    const chk = document.getElementById('tarjeta_sin_soporte');
    const esTarjetaSinSoporte = !!(chk && chk.checked);
    const esModoSinSoporteUI = esCajaChicaC0 || esReembolso || esTarjetaSinSoporte;

    document.body.classList.toggle('hide-subtotal-fac', esModoSinSoporteUI);
    document.body.classList.toggle('hide-soporte', esModoSinSoporteUI);

    if (esCajaChicaDetalle) {
      document.body.classList.remove('hide-subtotal-fac');
      document.body.classList.remove('hide-soporte');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTipoGastoUI();
    const chk = document.getElementById('tarjeta_sin_soporte');
    if (chk) chk.addEventListener('change', applyTipoGastoUI);
  });

  document.addEventListener('DOMContentLoaded', function () {
    const $detalle = document.getElementById('descripcion_input');
    const $tbody = document.getElementById('det-body');
    if (!$detalle) return;

    let lastSynced = '';

    function upperKeepCaret(el, nextVal) {
      const start = el.selectionStart;
      const end = el.selectionEnd;
      el.value = nextVal;
      try { el.setSelectionRange(start, end); } catch (_) { }
    }

    function syncObservaciones(valUpper) {
      const areas = document.querySelectorAll('textarea[name="det_observacion"]');
      areas.forEach(a => {
        const cur = (a.value || '').trim();
        if (!cur || cur === lastSynced) {
          a.value = valUpper;
        }
      });
      lastSynced = valUpper;
    }

    $detalle.addEventListener('input', function () {
      const raw = $detalle.value || '';
      const up = raw.toUpperCase();

      if (raw !== up) upperKeepCaret($detalle, up);

      syncObservaciones(up.trim());
    });

    if ($tbody) {
      const obs = new MutationObserver(() => {
        const up = ($detalle.value || '').toUpperCase().trim();
        if (up) syncObservaciones(up);
      });
      obs.observe($tbody, { childList: true });
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    const chk = document.getElementById('tarjeta_sin_soporte');
    const $provNombre = document.getElementById('proveedor_nombre');
    const $provId = document.getElementById('proveedor_id');
    const $provIdent = document.getElementById('proveedor_identificacion');
    const $alert = document.getElementById('provAlert');

    if (!chk || !$provNombre || !$provIdent) return;

    function applyTarjetaSinSoporteUI() {
      const on = !!chk.checked;

      if (on) {
        $provIdent.removeAttribute('readonly');
        $provNombre.removeAttribute('list');
        if ($provId) $provId.value = '';
        if ($alert) $alert.classList.add('d-none');
      } else {
        $provIdent.setAttribute('readonly', 'readonly');
        $provNombre.setAttribute('list', 'dl-proveedores');
      }
    }

    chk.addEventListener('change', applyTarjetaSinSoporteUI);
    applyTarjetaSinSoporteUI();
  });

  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('btnGenSec');
    const inp = document.getElementById('numero_factura');
    if (!btn || !inp) return;

    function puedeGenerarSecuencia() {
      const tipo = getTipoRegistro();
      const esCajaChica = (tipo === 'caja_chica');
      const esReembolso = (tipo === 'reembolso');
      const esTarjetaSinSoporte = isTarjetaSinSoporteChecked();
      return esCajaChica || esReembolso || esTarjetaSinSoporte;
    }

    function setBusy(on) {
      btn.disabled = !!on;
    }

    function refresh() {
      btn.style.display = puedeGenerarSecuencia() ? '' : 'none';
      btn.title = puedeGenerarSecuencia()
        ? 'Generar consecutivo'
        : 'No aplica para este tipo de gasto';
    }

    refresh();

    const chk = document.getElementById('tarjeta_sin_soporte');
    if (chk) chk.addEventListener('change', refresh);

    btn.addEventListener('click', async function () {
      if (!puedeGenerarSecuencia()) {
        alert('La secuencia automática solo aplica para Caja Chica, Reembolso de vendedor o Tarjeta sin soporte.');
        return;
      }

      if ((inp.value || '').trim()) {
        const ok = confirm('Ya existe un N° factura. ¿Deseas reemplazarlo por un consecutivo?');
        if (!ok) return;
      }

      setBusy(true);
      try {
        const r = await fetch(routes.apiNextCajaChicaFactura, {
          method: 'POST',
          headers: getCsrfHeaders(false),
          body: JSON.stringify({})
        });

        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) throw new Error(data.msg || ('HTTP ' + r.status));

        inp.value = data.numero || '';
        inp.focus();
      } catch (e) {
        alert('No se pudo generar el consecutivo: ' + e.message);
      } finally {
        setBusy(false);
      }
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('descripcion_input');
    if (!el) return;

    el.addEventListener('input', () => {
      const up = (el.value || '').toUpperCase();
      if (el.value !== up) el.value = up;
    });

    el.addEventListener('invalid', () => {
      el.classList.add('is-invalid');
    }, true);

    el.addEventListener('input', () => {
      if (el.checkValidity()) el.classList.remove('is-invalid');
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    const inp = document.getElementById('numero_factura');
    if (!inp) return;

    function aplicaRequiredFactura() {
      return true;
    }

    function refreshFacturaRequired() {
      const must = aplicaRequiredFactura();
      if (must) {
        inp.setAttribute('required', 'required');
      } else {
        inp.removeAttribute('required');
        inp.classList.remove('is-invalid');
      }
    }

    inp.addEventListener('invalid', () => {
      inp.classList.add('is-invalid');
    }, true);

    inp.addEventListener('input', () => {
      if (inp.checkValidity()) inp.classList.remove('is-invalid');
    });

    refreshFacturaRequired();

    const chk = document.getElementById('tarjeta_sin_soporte');
    if (chk) chk.addEventListener('change', refreshFacturaRequired);
  });

  document.addEventListener('DOMContentLoaded', () => {
    const $totVis = document.getElementById('sum_total_con_iva');
    const $totHid = document.getElementById('h_total_con_iva');
    const $msg = document.getElementById('totInvalid');

    if (!form) return;

    function getTotal() {
      const v = ($totHid && $totHid.value != null) ? $totHid.value : ($totVis ? $totVis.value : '0');
      return toNum(v);
    }

    function setInvalid(on) {
      if (!$totVis) return;

      if (on) {
        $totVis.classList.add('is-invalid');
        $msg?.classList.add('d-block');
        try { $totVis.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) { }
      } else {
        $totVis.classList.remove('is-invalid');
        $msg?.classList.remove('d-block');
      }
    }

    function validateTotal() {
      const total = getTotal();
      const bad = (total <= 0);
      setInvalid(bad);
      return !bad;
    }

    document.getElementById('det-body')?.addEventListener('input', validateTotal);
    document.getElementById('det-body')?.addEventListener('change', validateTotal);
  });

  document.addEventListener('DOMContentLoaded', () => {
    if (!form) return;

    function focusErr(el) {
      if (!el) return;
      try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) { }
      try { el.focus({ preventScroll: true }); } catch (_) { try { el.focus(); } catch (__) { } }
    }

    function markInvalid(el, on) {
      if (!el) return;
      el.classList.toggle('is-invalid', !!on);
    }

    function setInlineFeedback(inputEl, ok, msg) {
      if (!inputEl) return;
      inputEl.classList.toggle('is-invalid', !ok);

      if (ok) {
        inputEl.removeAttribute('title');
        inputEl.dataset.errmsg = '';
      } else {
        inputEl.setAttribute('title', msg || 'Campo inválido');
        inputEl.dataset.errmsg = msg || 'Campo inválido';
      }
    }

    window.__validateDetalleRequired = function () {
      const tbody = document.getElementById('det-body');
      if (!tbody) return { ok: true };

      const skipCentro = isReembolsoVendedor();
      const rows = Array.from(tbody.querySelectorAll('tr'));

      for (const tr of rows) {
        const motivo = tr.querySelector('input[name="det_motivo"]');
        const motivoValido = tr.querySelector('input[name="det_motivo_valido"]');

        const centro = tr.querySelector('input[name="det_centro_costo"]');
        const centroValido = tr.querySelector('input[name="det_centro_costo_valido"]');

        const indicador = tr.querySelector('input[name="det_indicador"]');

        if (motivo) {
          const v = (motivo.value || '').trim();
          if (!v) {
            setInlineFeedback(motivo, false, 'Debe ingresar Motivo.');
            motivo.setCustomValidity('Debe ingresar Motivo.');
            motivo.reportValidity();
            motivo.setCustomValidity('');
            return { ok: false, el: motivo };
          }

          if (!(motivoValido && (motivoValido.value || '').trim())) {
            setInlineFeedback(motivo, false, 'Debe seleccionar un motivo válido de la lista.');
            motivo.setCustomValidity('Debe seleccionar un motivo válido de la lista.');
            motivo.reportValidity();
            motivo.setCustomValidity('');
            return { ok: false, el: motivo };
          }

          setInlineFeedback(motivo, true, '');
        }

        if (!skipCentro && centro) {
          const v = (centro.value || '').trim();
          if (!v) {
            setInlineFeedback(centro, false, 'Debe ingresar Centro de costo.');
            centro.setCustomValidity('Debe ingresar Centro de costo.');
            centro.reportValidity();
            centro.setCustomValidity('');
            return { ok: false, el: centro };
          }

          if (!(centroValido && (centroValido.value || '').trim())) {
            setInlineFeedback(centro, false, 'Debe seleccionar un centro de costo válido de la lista.');
            centro.setCustomValidity('Debe seleccionar un centro de costo válido de la lista.');
            centro.reportValidity();
            centro.setCustomValidity('');
            return { ok: false, el: centro };
          }

          setInlineFeedback(centro, true, '');
        }

        if (indicador) {
          const v = (indicador.value || '').trim();
          if (!v) {
            indicador.classList.add('is-invalid');
            indicador.setCustomValidity('Debe ingresar Indicador.');
            indicador.reportValidity();
            indicador.setCustomValidity('');
            return { ok: false, el: indicador };
          }
          indicador.classList.remove('is-invalid');
        }
      }

      return { ok: true };
    };

    window.__validateProveedor = async function () {
      const $input = document.getElementById('proveedor_nombre');
      const $idField = document.getElementById('proveedor_id');
      const $identField = document.getElementById('proveedor_identificacion');

      const tipo = getTipoRegistro();
      const tipoCajaChica = getTipoCajaChica();
      const esCajaChicaC0 = (tipo === 'caja_chica' && tipoCajaChica === 'C0');
      const esCajaChicaDetalle = (tipo === 'caja_chica' && tipoCajaChica === 'DETALLE_FACTURA');
      const esReembolso = (tipo === 'reembolso') ||
        (!!document.getElementById('reembolso_vendedor')?.checked && !esCajaChicaDetalle) ||
        esCajaChicaC0;
      const esTarjetaSinSoporte = !!document.getElementById('tarjeta_sin_soporte')?.checked;

      if (esReembolso || esTarjetaSinSoporte) {
        const nombre = ($input?.value || '').trim();
        const ruc = ($identField?.value || '').trim();
        if (!nombre) return { ok: false, el: $input, msg: 'Debe ingresar Proveedor.' };
        if (!ruc) return { ok: false, el: $identField, msg: 'Debe ingresar RUC.' };
        return { ok: true };
      }

      const nombre = ($input?.value || '').trim();
      if (!nombre) return { ok: false, el: $input, msg: 'Debe seleccionar un Proveedor.' };

      if (($idField?.value || '').trim()) return { ok: true };

      if (window.intentarResolverProveedorId) {
        await window.intentarResolverProveedorId(nombre, ($identField?.value || '').trim());
      }

      if (($idField?.value || '').trim()) return { ok: true };
      return { ok: false, el: $input, msg: 'Debe seleccionar un proveedor válido de la lista.' };
    };

    window.__validateTotal = function () {
      const $totVis = document.getElementById('sum_total_con_iva');
      const $totHid = document.getElementById('h_total_con_iva');
      const $msg = document.getElementById('totInvalid');

      const v = ($totHid && $totHid.value != null) ? $totHid.value : ($totVis ? $totVis.value : '0');
      const total = toNum(v);

      const bad = (total <= 0);

      if ($totVis) $totVis.classList.toggle('is-invalid', bad);
      if ($msg) $msg.classList.toggle('d-block', bad);

      if (bad) return { ok: false, el: $totVis, msg: 'El Total (Total con IVA) debe ser mayor a cero.' };
      return { ok: true };
    };

    window.__validateAdjuntos = function () {
      const fileInput = document.getElementById('archivo');
      const adjCountEl = document.getElementById('adj_count');
      const invalidMsg = document.getElementById('archivoInvalid');

      const already = parseInt((adjCountEl?.value || '0'), 10) || 0;
      const selected = (fileInput?.files && fileInput.files.length > 0);

      const bad = (already <= 0 && !selected);

      if (fileInput) fileInput.classList.toggle('is-invalid', bad);
      if (invalidMsg) invalidMsg.classList.toggle('d-block', bad);

      if (bad) return { ok: false, el: fileInput, msg: 'Debe adjuntar al menos un archivo para guardar.' };
      return { ok: true };
    };

    form.addEventListener('submit', async (e) => {
      if (e.defaultPrevented) return;

      const det = document.getElementById('descripcion_input');
      if (det && !(det.value || '').trim()) {
        e.preventDefault();
        e.stopPropagation();
        det.setCustomValidity('La descripción es obligatoria.');
        det.reportValidity();
        det.setCustomValidity('');
        markInvalid(det, true);
        focusErr(det);
        return;
      }
      markInvalid(det, false);

      const pr = (typeof window.__validateProveedor === 'function')
        ? await window.__validateProveedor()
        : { ok: true };

      if (!pr.ok) {
        e.preventDefault();
        e.stopPropagation();
        markInvalid(pr.el, true);
        focusErr(pr.el);
        return;
      }

      const nf = document.getElementById('numero_factura');
      if (nf && nf.hasAttribute('required') && !(nf.value || '').trim()) {
        e.preventDefault();
        e.stopPropagation();
        nf.setCustomValidity('El N° de factura es obligatorio.');
        nf.reportValidity();
        nf.setCustomValidity('');
        markInvalid(nf, true);
        focusErr(nf);
        return;
      }
      if (nf) markInvalid(nf, false);

      const det2 = (typeof window.__validateDetalleRequired === 'function')
        ? window.__validateDetalleRequired()
        : { ok: true };

      if (!det2.ok) {
        e.preventDefault();
        e.stopPropagation();
        focusErr(det2.el);
        return;
      }

      const tt = (typeof window.__validateTotal === 'function')
        ? window.__validateTotal()
        : { ok: true };

      if (!tt.ok) {
        e.preventDefault();
        e.stopPropagation();
        focusErr(tt.el);
        return;
      }

      const ad = (typeof window.__validateAdjuntos === 'function')
        ? window.__validateAdjuntos()
        : { ok: true };

      if (!ad.ok) {
        e.preventDefault();
        e.stopPropagation();
        focusErr(ad.el);
        return;
      }
    }, true);
  });

  function applyCentroCostoRequiredRule() {
    const tbody = document.getElementById('det-body');
    if (!tbody) return;

    const skip = isReembolsoVendedor();

    const centros = tbody.querySelectorAll('input[name="det_centro_costo"]');
    centros.forEach(el => {
      if (skip) {
        el.removeAttribute('required');
        el.classList.remove('is-invalid');
      } else {
        el.setAttribute('required', 'required');
      }
    });
  }

  window.applyCentroCostoRequiredRule = applyCentroCostoRequiredRule;

  document.addEventListener('DOMContentLoaded', () => {
    applyCentroCostoRequiredRule();

    const tbody = document.getElementById('det-body');
    if (tbody) {
      const obs = new MutationObserver(() => applyCentroCostoRequiredRule());
      obs.observe(tbody, { childList: true, subtree: true });
    }
  });




document.addEventListener('DOMContentLoaded', function () {
  const $tbody = document.getElementById('det-body');
  const $dlCentros = document.getElementById('dl-centros');
  if (!$tbody || !$dlCentros) return;

  const MAX_CENTROS = 10;
  const MIN_CHARS = 1;
  let t = null;

  function fillCentros(list) {
    $dlCentros.innerHTML = '';

    (list || []).slice(0, MAX_CENTROS).forEach(x => {
      const opt = document.createElement('option');
      opt.value = x.valor || '';
      opt.label = x.nombre ? `${x.nombre} (${x.valor || ''})` : (x.valor || '');
      $dlCentros.appendChild(opt);
    });
  }

  function fetchCentros(q) {
    if (!routes.apiParamCentros) return;

    const url = new URL(routes.apiParamCentros, location.origin);
    if ((q || '').length >= MIN_CHARS) {
      url.searchParams.set('q', q);
    }

    url.searchParams.set('limit', String(MAX_CENTROS));

    fetch(url, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(fillCentros)
      .catch(() => {});
  }

  fetchCentros('');

  $tbody.addEventListener('input', function (e) {
    const el = e.target;
    if (el && el.name === 'det_centro_costo') {
      el.setAttribute('list', 'dl-centros');
      clearTimeout(t);
      t = setTimeout(() => fetchCentros(el.value || ''), 220);
    }
  });
});



})();
    