(function () {
    const configEl = document.getElementById('gastos-pendientes-config');
    if (!configEl) return;

    const csrfToken = configEl.dataset.csrfToken || '';
    const PENDIENTES_URL = configEl.dataset.pendientesUrl || '';
    const BULK_URL = configEl.dataset.aprobarMasivoUrl || '';
    const BULK_SAP_URL = configEl.dataset.sapMasivoUrl || '';
    const IS_PENDIENTES_VIEW = configEl.dataset.isPendientesView === '1';
    const ROLE_LOWER = (configEl.dataset.roleLower || '').toLowerCase();

    function getCSRFToken() {
        return document.querySelector('input[name="csrf_token"]')?.value || csrfToken || '';
    }

    function toast(msg) {
        const t = document.getElementById('toast');
        if (t && window.bootstrap) {
            t.querySelector('.toast-body').textContent = msg;
            bootstrap.Toast.getOrCreateInstance(t).show();
        } else {
            alert(msg);
        }
    }

    function showBulkOverlay() {
        const o = document.getElementById('bulkOverlay');
        if (o) o.style.display = 'flex';
    }

    function hideBulkOverlay() {
        const o = document.getElementById('bulkOverlay');
        if (o) o.style.display = 'none';
    }

    function isVisible(el) {
        return !!(el && el.offsetParent !== null);
    }

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

        document.getElementById('themeToggle')?.addEventListener('click', function () {
            apply(root.classList.contains('theme-dark') ? 'light' : 'dark');
        });
    }

    function initDefaultDates() {
        const pad = n => String(n).padStart(2, '0');
        const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

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
        if (
            form &&
            !IS_PENDIENTES_VIEW &&
            !qs.has('desde') &&
            !qs.has('hasta') &&
            !special
        ) {
            form.submit();
        }
    }

    function initQuickRanges() {
        const pad = n => String(n).padStart(2, '0');
        const fmt = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const desde = document.querySelector('[name="desde"]');
        const hasta = document.querySelector('[name="hasta"]');
        if (!desde || !hasta) return;

        document.querySelectorAll('[data-range]').forEach(btn => {
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
        ['ccb', 'usuario_id', 'gerente_id', 'tipo_gasto'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', function () {
                el.closest('form')?.submit();
            });
        });
    }

    function initFlagButtons() {
        document.querySelectorAll('button[data-flag]').forEach(btn => {
            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                const flag = btn.dataset.flag;
                const u = new URL(PENDIENTES_URL, window.location.origin);
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
                const u = new URL(PENDIENTES_URL, window.location.origin);
                u.searchParams.set('pendientes', '1');
                window.location.href = u.toString();
            });
        }
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
        const lenMenu = lenBtn?.closest('.dropdown')?.querySelector('.dropdown-menu');
        const items = lenMenu ? lenMenu.querySelectorAll('[data-page-length]') : [];
        const hasBSDropdown = typeof window.bootstrap !== 'undefined' && bootstrap.Dropdown;

        if (!hasBSDropdown && lenBtn && lenMenu) {
            const open = () => {
                lenMenu.classList.add('show');
                lenBtn.setAttribute('aria-expanded', 'true');
            };
            const close = () => {
                lenMenu.classList.remove('show');
                lenBtn.setAttribute('aria-expanded', 'false');
            };
            lenBtn.addEventListener('click', e => {
                e.preventDefault();
                lenMenu.classList.contains('show') ? close() : open();
            });
            document.addEventListener('click', e => {
                const dd = lenBtn.closest('.dropdown');
                if (dd && !dd.contains(e.target)) close();
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
            thead.querySelectorAll('th').forEach(th => {
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

            dataRows.sort((a, b) => {
                const va = getCellValue(a, idx, type);
                const vb = getCellValue(b, idx, type);
                let c = 0;
                if (va > vb) c = 1;
                else if (va < vb) c = -1;
                return sortState.dir === 'asc' ? c : -c;
            });

            const frag = document.createDocumentFragment();
            dataRows.forEach(tr => frag.appendChild(tr));
            const totals = tbody.querySelector('tr[data-totales="1"]');
            if (totals) tbody.insertBefore(frag, totals);
            else tbody.appendChild(frag);

            clearIcons();
            th.classList.add(sortState.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            setIcon(th, sortState.dir);
            goTo(1);
        }

        thead.querySelectorAll('th[data-sort]').forEach(th => {
            const type = (th.getAttribute('data-sort') || 'text').toLowerCase();
            const clickable = th.querySelector('.th-sortable') || th;
            clickable.setAttribute('role', 'button');
            clickable.setAttribute('tabindex', '0');

            clickable.addEventListener('click', () => {
                const idx = Array.from(th.parentElement.children).indexOf(th);
                applySort(th, idx, type);
            });

            clickable.addEventListener('keydown', e => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    clickable.click();
                }
            });
        });

        function setBtnText() {
            if (lenBtn) lenBtn.textContent = `Mostrar ${pageLength} filas`;
        }

        function updateInfo(s, e, t) {
            if (!info) return;
            info.textContent = `Mostrando ${t ? s + 1 : 0} a ${e} de ${t} registros`;
        }

        function mkItem(label, page, disabled = false, active = false) {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = label;
            a.addEventListener('click', e => {
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

            const add = (s, e) => {
                for (let p = s; p <= e; p++) {
                    pager.appendChild(mkItem(String(p), p, false, p === currentPage));
                }
            };

            pager.appendChild(mkItem('Anterior', currentPage - 1, currentPage === 1));

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

            pager.appendChild(mkItem('Siguiente', currentPage + 1, currentPage === N));
        }

        function goTo(page) {
            const total = dataRows.length;
            const pages = Math.max(1, Math.ceil(total / pageLength));
            currentPage = Math.min(Math.max(1, page), pages);

            dataRows.forEach((row, idx) => {
                const start = (currentPage - 1) * pageLength;
                const end = start + pageLength;
                row.style.display = (idx >= start && idx < end) ? '' : 'none';
            });

            const start = (currentPage - 1) * pageLength;
            const endCount = Math.min(start + pageLength, total);
            updateInfo(start, endCount, total);
            renderPagination(pages);
        }

        items.forEach(it => {
            it.addEventListener('click', e => {
                e.preventDefault();
                const len = parseInt(it.getAttribute('data-page-length'), 10);
                if (!isNaN(len) && len > 0) {
                    pageLength = len;
                    localStorage.setItem('gastos_page_len', String(pageLength));
                    setBtnText();
                    goTo(1);
                    lenMenu?.classList.remove('show');
                    lenBtn?.setAttribute('aria-expanded', 'false');
                }
            });
        });

        clearIcons();
        setBtnText();
        goTo(1);
    }

    function initSelectVisible() {
        const isRowVisible = chk => {
            const tr = chk.closest('tr[data-row="1"]');
            if (!tr) return false;
            return tr.style.display !== 'none' && isVisible(tr);
        };

        const selAll = document.getElementById('chkSelectAllVisible');
        if (!selAll) return;

        selAll.addEventListener('change', e => {
            const checked = e.target.checked;
            document.querySelectorAll('.row-select').forEach(chk => {
                if (chk.disabled) return;
                if (!isRowVisible(chk)) return;
                chk.checked = checked;
            });
        });

        if (IS_PENDIENTES_VIEW) {
            document.querySelectorAll('.row-select').forEach(chk => {
                if (chk.disabled) return;
                if (!isVisible(chk)) return;
                chk.checked = true;
            });

            const box = document.getElementById('chkSelectAllVisible')?.closest('.form-check');
            if (box) box.style.display = 'none';
        }
    }

    function initApprovals() {
        function setDatasets(row) {
            const gg = row.querySelector('input.aprob[data-area="gg"]');
            const gf = row.querySelector('input.aprob[data-area="gf"]');
            if (gg) row.dataset.gg = gg.checked ? '1' : '0';
            if (gf) row.dataset.gf = gf.checked ? '1' : '0';
        }

        function refreshRowLocks(row) {
            const ga = row.querySelector('input.aprob[data-area="ga"]');
            const gg = row.querySelector('input.aprob[data-area="gg"]');
            const gf = row.querySelector('input.aprob[data-area="gf"]');
            const hasSap = row.dataset.sap === '1';

            if (ga) ga.disabled = hasSap || ga.hasAttribute('data-locked');
            if (gg) gg.disabled = hasSap || gg.hasAttribute('data-locked');
            if (gf) gf.disabled = hasSap || gf.hasAttribute('data-locked');
        }

        document.querySelectorAll('tr[data-row="1"]').forEach(row => {
            setDatasets(row);
            refreshRowLocks(row);
        });

        document.querySelectorAll('input.aprob').forEach(chk => {
            chk.addEventListener('change', async () => {
                const row = chk.closest('tr');
                const url = chk.dataset.url;
                const area = (chk.dataset.area || '').toLowerCase();
                const value = chk.checked;

                chk.disabled = true;
                try {
                    const r = await fetch(url, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': getCSRFToken()
                        },
                        body: JSON.stringify({ area, value })
                    });

                    const data = await r.json().catch(() => ({}));
                    if (!r.ok || !data.ok) throw new Error(data?.msg || `HTTP ${r.status}`);

                    if (row) {
                        if (area === 'gg') row.dataset.gg = value ? '1' : '0';
                        if (area === 'gf') row.dataset.gf = value ? '1' : '0';
                        refreshRowLocks(row);
                    }

                    toast('Guardado');
                } catch (err) {
                    chk.checked = !chk.checked;
                    toast('Error: ' + err.message);
                } finally {
                    chk.disabled = false;
                }
            });
        });
    }

    function initBulkApprove() {
        const getSelectedIds = area => {
            return Array.from(document.querySelectorAll('.row-select:checked'))
                .filter(chk => {
                    if (!area) return true;
                    if (area === 'ga') return chk.dataset.canGa === '1';
                    if (area === 'gg') return chk.dataset.canGg === '1' || chk.dataset.freeSelect === '1';
                    if (area === 'gf') return chk.dataset.canGf === '1';
                    return true;
                })
                .map(chk => parseInt(chk.dataset.id, 10))
                .filter(n => Number.isFinite(n) && n > 0);
        };

        document.addEventListener('click', async e => {
            const btn = e.target.closest('.bulk-approve');
            if (!btn) return;

            e.preventDefault();
            e.stopPropagation();

            const area = (btn.dataset.area || '').toLowerCase();
            const ids = getSelectedIds(area);

            if (!ids.length) {
                return toast('Selecciona gastos elegibles para aprobar.');
            }

            if (!confirm(`¿Aprobar ${ids.length} gasto(s) como ${area.toUpperCase()}?`)) {
                return;
            }

            btn.disabled = true;
            showBulkOverlay();

            try {
                const resp = await fetch(BULK_URL, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
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

                toast(msg);
                setTimeout(() => location.reload(), 2000);
            } catch (err) {
                toast('Error masivo: ' + err.message);
            } finally {
                hideBulkOverlay();
                btn.disabled = false;
            }
        }, true);
    }

    function initSapButtons() {
        async function enviarASAP(btn) {
            const row = btn.closest('tr[data-row="1"]');
            const proveedor =
                btn.getAttribute('data-proveedor') ||
                row?.querySelector('[data-th="Proveedor"]')?.textContent.trim() ||
                '';

            if (!confirm('¿Enviar el gasto a SAP' + (proveedor ? (' de "' + proveedor + '"') : '') + '?')) {
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
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
                    }
                });

                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) throw new Error(data.msg || ('HTTP ' + resp.status));

                const docCell = row?.querySelector('[data-th="Doc. SAP"]');
                if (docCell) docCell.textContent = data.doc || '';
                if (row) row.dataset.sap = '1';
                btn.title = 'Ya contabilizado en SAP';

                toast('Enviado a SAP. Doc: ' + (data.doc || '—'));
            } catch (err) {
                toast('Error al enviar a SAP: ' + err.message);
                btn.disabled = false;
            } finally {
                btn.innerHTML = prevHTML;
            }
        }

        document.querySelectorAll('button.btn-sap').forEach(btn => {
            if (btn.dataset.bound === '1') return;
            btn.dataset.bound = '1';

            btn.addEventListener('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                if (btn.disabled || btn.hasAttribute('disabled')) return;
                enviarASAP(btn);
            });
        });
    }

    function initSapMasivo() {
        const getSelectedSapIds = () => {
            return Array.from(document.querySelectorAll('.row-select:checked'))
                .filter(chk => chk.dataset.canSap === '1')
                .map(chk => parseInt(chk.dataset.id, 10))
                .filter(Boolean);
        };

        document.getElementById('btnSapMasivo')?.addEventListener('click', async () => {
            const ids = getSelectedSapIds();
            if (!ids.length) return toast('Selecciona gastos listos para SAP (GG aprobado y sin Doc SAP).');

            if (!confirm(`¿Enviar ${ids.length} gasto(s) a SAP?`)) return;

            const btn = document.getElementById('btnSapMasivo');
            btn.disabled = true;
            showBulkOverlay();

            try {
                const resp = await fetch(BULK_SAP_URL, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify({ ids })
                });

                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) throw new Error(data.msg || `HTTP ${resp.status}`);

                (data.results || []).forEach(r => {
                    const chk = document.querySelector(`.row-select[data-id="${r.id}"]`);
                    const row = chk?.closest('tr[data-row="1"]');
                    if (!row) return;

                    if (r.ok) {
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
                    }
                });

                toast(`SAP masivo: ${data.sent || 0} enviado(s), ${data.errors || 0} con error.`);
            } catch (e) {
                toast('Error SAP masivo: ' + e.message);
            } finally {
                hideBulkOverlay();
                btn.disabled = false;
            }
        });
    }

    function initAdjuntosModal() {
        const modalEl = document.getElementById('modalAdjuntosGasto');
        const bodyEl = document.getElementById('adjuntos-body');
        if (!modalEl || !bodyEl) return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

        document.addEventListener('click', async ev => {
            const btn = ev.target.closest('.js-ver-adjuntos');
            if (!btn) return;

            ev.preventDefault();
            const gid = btn.getAttribute('data-gasto-id');
            if (!gid) return;

            bodyEl.innerHTML = "<div class='text-muted'>Cargando…</div>";
            modal.show();

            try {
                const resp = await fetch(`/reembolsos/gastos/${gid}/adjuntos`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
                    }
                });
                bodyEl.innerHTML = await resp.text();
            } catch (e) {
                bodyEl.innerHTML = "<div class='alert alert-danger mb-0'>No se pudo cargar los adjuntos.</div>";
            }
        }, true);
    }


    function initVerGastoModal() {
        const modalEl = document.getElementById('modalVerGasto');
        const iframe = document.getElementById('iframeVerGasto');
        if (!modalEl || !iframe) return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        let lastTrigger = null;

        document.addEventListener('click', e => {
            const btn = e.target.closest('.btn-ver-gasto');
            if (!btn) return;

            e.preventDefault();
            lastTrigger = btn;
            iframe.src = btn.dataset.url;
            modal.show();
        });

        modalEl.addEventListener('hidden.bs.modal', () => {
            iframe.src = '';

            if (document.activeElement && modalEl.contains(document.activeElement)) {
                document.activeElement.blur();
            }

            if (lastTrigger && typeof lastTrigger.focus === 'function') {
                lastTrigger.focus();
            }
        });
    }

    function initFacturaXmlModal() {
        const modalEl = document.getElementById('mdlFacturaXml');
        const contentEl = document.getElementById('mdlFacturaXmlContent');
        if (!modalEl || !contentEl) return;

        const modal = new bootstrap.Modal(modalEl);

        async function openFactura(fid) {
            contentEl.innerHTML = "<div class='modal-body p-4 text-center'>Cargando...</div>";
            modal.show();

            try {
                const r = await fetch(`/reembolsos/facturas-xml/${fid}/ver?popup=1`, {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": csrfToken
                    }
                });
                const html = await r.text();
                contentEl.innerHTML = html;
            } catch (e) {
                contentEl.innerHTML = "<div class='modal-body p-4 text-danger'>No se pudo cargar el detalle.</div>";
            }
        }

        document.addEventListener('click', ev => {
            const btn = ev.target.closest('.js-ver-factura-xml');
            if (!btn) return;
            const fid = btn.getAttribute('data-fid');
            if (!fid) return;
            openFactura(fid);
        });
    }

    function initRechazoModal() {
        const modalEl = document.getElementById('modalRechazoGG');
        if (!modalEl) return;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        const $gerente = document.getElementById('rechazoGGGerente');
        const $coment = document.getElementById('rechazoGGComentario');
        const $url = document.getElementById('rechazoGGUrl');
        const $gid = document.getElementById('rechazoGGGid');
        const $send = document.getElementById('btnEnviarRechazoGG');

        document.addEventListener('click', ev => {
            const btn = ev.target.closest('.js-rechazo-gg');
            if (!btn) return;

            ev.preventDefault();
            ev.stopPropagation();

            const url = btn.dataset.url || '';
            const gid = btn.dataset.gastoId || '';
            const gerente = (btn.dataset.gerente || '').trim();

            if (!url) return;

            $url.value = url;
            $gid.value = gid;
            $gerente.textContent = gerente ? `(${gerente})` : '';
            $coment.value = '';
            modal.show();

            setTimeout(() => $coment.focus(), 150);
        }, true);

        $send.addEventListener('click', async () => {
            const url = $url.value;
            const comentario = ($coment.value || '').trim();
            if (!url) return;

            const prev = $send.innerHTML;
            $send.disabled = true;
            $send.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';

            try {
                const resp = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCSRFToken()
                    },
                    body: JSON.stringify({
                        motivo: 'rechazo_gg',
                        comentario: comentario
                    })
                });

                const data = await resp.json().catch(() => ({}));
                if (!resp.ok || !data.ok) throw new Error(data.msg || `HTTP ${resp.status}`);

                modal.hide();
                toast('Notificación de rechazo encolada para envío por correo.');
            } catch (e) {
                toast('Error al encolar notificación: ' + e.message);
            } finally {
                $send.disabled = false;
                $send.innerHTML = prev;
            }
        });
    }

    function initExports() {
        function buildExportUrl(baseUrl, visibleOnly) {
            if (!baseUrl) return '';

            const qs = new URLSearchParams(window.location.search);
            ['accion', 'pend_view', 'page'].forEach(k => qs.delete(k));

            if (visibleOnly) {
                const ids = Array.from(document.querySelectorAll('tr[data-row="1"]'))
                    .filter(tr => isVisible(tr) && tr.style.display !== 'none')
                    .map(tr => parseInt(tr.getAttribute('data-id') || '0', 10))
                    .filter(n => Number.isFinite(n) && n > 0);

                if (!ids.length) {
                    alert('No hay registros visibles para exportar.');
                    return '';
                }

                qs.set('ids', ids.join(','));
            }

            return `${baseUrl}?${qs.toString()}`;
        }

        const btnReporteExcel = document.getElementById('btnReporteExcel');
        if (btnReporteExcel) {
            btnReporteExcel.addEventListener('click', ev => {
                ev.preventDefault();
                const url = buildExportUrl(btnReporteExcel.dataset.exportUrl, true);
                if (url) window.location.href = url;
            });
        }

        const btnExcelVisible = document.getElementById('btnExcelVisible');
        if (btnExcelVisible) {
            btnExcelVisible.addEventListener('click', ev => {
                ev.preventDefault();
                const url = buildExportUrl(btnExcelVisible.dataset.exportUrl, true);
                if (url) window.location.href = url;
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        removeOneShotStatusAlert();
        initThemeToggle();
        initDefaultDates();
        initQuickRanges();
        initAutoSubmitFilters();
        initFlagButtons();
        initSortAndPagination();
        initSelectVisible();
        initApprovals();
        initBulkApprove();
        initSapButtons();
        initSapMasivo();
        initAdjuntosModal();
        initVerGastoModal();
        initFacturaXmlModal();
        initRechazoModal();
        initExports();
    });
})();