document.addEventListener("DOMContentLoaded", function () {
    const today = new Date().toISOString().split("T")[0];
    document.getElementById("fechaEvento")?.setAttribute("max", today);
});



function getMetaUrl(name) {
    return document.querySelector(`meta[name="${name}"]`)?.getAttribute('content') || '';
}

function getCSRFToken() {
    return (
        document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
        document.querySelector('input[name="csrf_token"]')?.value ||
        ''
    );
}

const csrfToken = getCSRFToken();
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formNuevoReclamo');
    if (!form) return;

    const btnSubmit = form.querySelector('button[type="submit"]');

    const motivo = document.getElementById('recl-tipo-reclamo');

    const selProceso = document.getElementById('recl-proceso');

    // Set con los proceso_id actualmente seleccionados
    let _selectedProcesos = new Set();

    function _removeSponsorsByProceso(procesoId) {
        const chips = document.getElementById('recl-imputados-chips');
        if (!chips) return;
        // Recolectar las keys únicas de este proceso antes de iterar
        const keysToRemove = new Set();
        chips.querySelectorAll('.badge[data-auto="1"]').forEach(chip => {
            (chip.dataset.autoKeys || '').split('|').filter(Boolean).forEach(k => {
                if (k.startsWith(`proceso-${procesoId}-`)) keysToRemove.add(k);
            });
        });
        // Usar _omRemoveAutoSponsorByKey para que también limpie el Map `selected`
        keysToRemove.forEach(k => window._omRemoveAutoSponsorByKey?.(k));
    }

    async function _loadSponsorsByProceso(procesoId) {
        const urlTpl = getMetaUrl('api-proceso-sponsors-url');
        const url = urlTpl.replace('__ID__', encodeURIComponent(procesoId));
        const resp = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken }
        });
        const data = await resp.json();
        (data.items || []).forEach(s => {
            window.agregarImputadoDesdeProceso?.(s, `proceso-${procesoId}-${s.tipo}`);
        });
    }

    function _syncProcesoText() {
        const hidPT = document.getElementById('recl-proceso-text');
        if (!hidPT) return;
        const selected = [...selProceso.selectedOptions].map(o => o.dataset.text || o.textContent.trim());
        hidPT.value = selected.join(', ');
    }

    selProceso?.addEventListener('change', async () => {
        // Limpiar hidden inputs legados
        document.querySelectorAll('.js-sponsor-hidden').forEach(x => x.remove());

        const currentSet = new Set([...selProceso.selectedOptions].map(o => o.value).filter(Boolean));

        // Procesos que se quitaron → eliminar sus sponsors
        for (const pid of _selectedProcesos) {
            if (!currentSet.has(pid)) _removeSponsorsByProceso(pid);
        }

        // Procesos que se añadieron → cargar sus sponsors
        const toLoad = [...currentSet].filter(pid => !_selectedProcesos.has(pid));
        _selectedProcesos = currentSet;

        _syncProcesoText();

        await Promise.all(toLoad.map(_loadSponsorsByProceso));
    });

    const hidProceso = document.getElementById('recl-proceso-text');


    const selSub = document.getElementById('recl-subtipo');
    const inpSubOtro = document.getElementById('recl-subtipo-otro');
    const hidAnte = document.getElementById('recl-antecedente');

    const txtObs = form.querySelector('textarea[name="observacion"]');
    const inpFactura = form.querySelector('input[name="factura"]');
    const inpFechaEv = document.getElementById('fechaEvento');
    const selMaterial = document.getElementById('recl-material');

    const inpAdj = document.getElementById('recl-adjuntos');
    const adjInvalid = document.getElementById('recl-adjuntos-invalid');

    function isVisible(el) {
        // visible real en layout + no d-none
        return !!(el && el.offsetParent !== null && !el.classList.contains('d-none'));
    }

    function busyOff() {
        try { if (window.Busy && typeof window.Busy.hide === 'function') window.Busy.hide(); } catch (e) { }
    }

    function unlock() {
        try { if (typeof unlockButton === 'function') unlockButton(btnSubmit); } catch (e) { }
        // fallback simple
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.classList.remove('disabled');
        }
    }

    function lock() {
        try { if (typeof lockButton === 'function') lockButton(btnSubmit, 'Guardando…'); } catch (e) {
            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.classList.add('disabled');
            }
        }
    }

    function setInvalid(el, msg) {
        if (!el) return;
        try { el.setCustomValidity(msg || ''); } catch (e) { }
        el.classList.add('is-invalid');
        // para inputs/select normales, esto muestra el tooltip nativo si llamas reportValidity()
    }

    function clearInvalid(el) {
        if (!el) return;
        try { el.setCustomValidity(''); } catch (e) { }
        el.classList.remove('is-invalid');
    }

    // Limpia invalid al interactuar
    [motivo, selProceso, selSub, inpSubOtro, txtObs, inpFactura, inpFechaEv, selMaterial, inpAdj].forEach(el => {
        if (!el) return;
        el.addEventListener('input', () => { clearInvalid(el); });
        el.addEventListener('change', () => { clearInvalid(el); });
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault(); // control total del orden

        // Siempre aseguramos que NO quede “pegado”
        busyOff();
        unlock();

        // 0) Validación HTML5 base (cliente, motivo required, observación required, factura required, etc.)
        //    OJO: tu "cliente_id" hidden required puede no disparar UI, pero checkValidity sí lo evalúa.
        if (!form.checkValidity()) {
            // muestra el primer error nativo (por ejemplo motivo)
            form.reportValidity();
            return;
        }

        // 1) Proceso (solo si está visible y habilitado)
        if (selProceso && hidProceso && isVisible(selProceso) && !selProceso.disabled) {
            const selectedProc = Array.from(selProceso.options)
                .filter(o => o.selected)
                .map(o => (o.value || '').trim())
                .filter(Boolean);

            if (selectedProc.length === 0) {
                setInvalid(selProceso, 'Debe seleccionar al menos un Proceso.');
                // Tip: esto te abre el tooltip nativo
                try { selProceso.reportValidity(); } catch (e) { }
                selProceso.focus();
                return;
            }
            const selectedProcText = Array.from(selProceso.options)
                .filter(o => o.selected)
                .map(o => (o.dataset.text || o.textContent || '').trim())
                .filter(Boolean);

            hidProceso.value = selectedProcText.join(', ');
            clearInvalid(selProceso);
        }

        // 2) Sub Motivo (solo si el bloque está visible)
        if (isVisible(selSub)) {
            const otroVisible = inpSubOtro && !inpSubOtro.classList.contains('d-none');

            if (otroVisible) {
                const v = (inpSubOtro.value || '').trim();
                if (!v) {
                    setInvalid(inpSubOtro, 'Debe especificar el Sub Motivo.');
                    try { inpSubOtro.reportValidity(); } catch (e) { }
                    inpSubOtro.focus();
                    return;
                }
                if (hidAnte) hidAnte.value = v;
                clearInvalid(inpSubOtro);
                clearInvalid(selSub);
            } else {
                const v = (selSub && !selSub.disabled) ? (selSub.value || '').trim() : '';
                if (!v) {
                    setInvalid(selSub, 'Debe seleccionar el Sub Motivo.');
                    try { selSub.reportValidity(); } catch (e) { }
                    selSub.focus();
                    return;
                }
                if (hidAnte) hidAnte.value = v;
                clearInvalid(selSub);
            }
        }

        // 3) Observación (ya es required, pero si quieres asegurar orden estricto)
        if (txtObs && isVisible(txtObs)) {
            const v = (txtObs.value || '').trim();
            if (!v) {
                setInvalid(txtObs, 'Debe ingresar la Observación.');
                try { txtObs.reportValidity(); } catch (e) { }
                txtObs.focus();
                return;
            }
            clearInvalid(txtObs);
        }

        // 4) Factura/Guía (ya es required, pero orden estricto)
        if (inpFactura && isVisible(inpFactura)) {
            const v = (inpFactura.value || '').trim();
            if (!v) {
                setInvalid(inpFactura, 'Debe ingresar Factura / Guía.');
                try { inpFactura.reportValidity(); } catch (e) { }
                inpFactura.focus();
                return;
            }
            clearInvalid(inpFactura);
        }

        // 5) Fecha del evento (si quieres que sea obligatorio, aquí lo forzamos)
        if (inpFechaEv && isVisible(inpFechaEv)) {
            const v = (inpFechaEv.value || '').trim();
            if (!v) {
                setInvalid(inpFechaEv, 'Debe seleccionar la Fecha del Evento.');
                try { inpFechaEv.reportValidity(); } catch (e) { }
                inpFechaEv.focus();
                return;
            }
            clearInvalid(inpFechaEv);
        }

        // 6) Producto/Material (si quieres que sea obligatorio, aquí lo forzamos)
        if (selMaterial && isVisible(selMaterial) && !selMaterial.disabled) {
            const v = (selMaterial.value || '').trim();
            if (!v) {
                setInvalid(selMaterial, 'Debe seleccionar Producto / Material.');
                try { selMaterial.reportValidity(); } catch (e) { }
                selMaterial.focus();
                return;
            }
            clearInvalid(selMaterial);
        }

        // 7) Adjuntos (obligatorio mínimo 1)
        if (inpAdj && isVisible(inpAdj)) {
            const n = (inpAdj.files && inpAdj.files.length) ? inpAdj.files.length : 0;
            if (n === 0) {
                inpAdj.classList.add('is-invalid');
                if (adjInvalid) adjInvalid.classList.add('d-block');
                inpAdj.focus();
                return;
            } else {
                inpAdj.classList.remove('is-invalid');
                if (adjInvalid) adjInvalid.classList.remove('d-block');
            }
        }

        // ✅ Si llegamos aquí, TODO OK => ahora sí busy + lock y enviamos
        try {
            if (window.Busy && typeof window.Busy.show === 'function') {
                window.Busy.show('Guardando OM…');
            }
        } catch (e) { }

        lock();

        // enviar
        form.submit();
    });
});

function bloquearBtn(btn, texto = 'Guardando...') {
    if (!btn) return;
    btn.dataset.originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
            ${texto}
        `;
}

function desbloquearBtn(btn) {
    if (!btn) return;
    btn.disabled = false;
    if (btn.dataset.originalHtml) {
        btn.innerHTML = btn.dataset.originalHtml;
        delete btn.dataset.originalHtml;
    }
}

(function () {
    const key = 'ui_theme', root = document.documentElement;

    function applyTheme(m) {
        root.classList.toggle('theme-dark', m === 'dark');
        localStorage.setItem(key, m);
    }

    applyTheme(localStorage.getItem(key) || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

    document.getElementById('themeToggle')?.addEventListener('click', () => {
        applyTheme(root.classList.contains('theme-dark') ? 'light' : 'dark');
    });

    window.showToast = function (msg) {
        const t = document.getElementById('toast');
        if (!t) return;
        t.querySelector('.toast-body').textContent = msg;
        bootstrap.Toast.getOrCreateInstance(t).show();
    };

    window.renderAnalisisDetalle = function (data) {
        const el5 = document.getElementById("det-5why");
        const elF = document.getElementById("det-fishbone");

        el5?.classList.add("d-none");
        elF?.classList.add("d-none");

        const clearIds = [
            "det-why1", "det-why2", "det-why3", "det-why4", "det-why5",
            "det-fish-metodo", "det-fish-maquinas", "det-fish-materiales",
            "det-fish-personas", "det-fish-entorno", "det-fish-medicion"
        ];

        clearIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = "";
        });

        const metodo = ((data?.metodo_analisis || "") + "").trim().toUpperCase();

        if (metodo === "5WHYS") {
            el5?.classList.remove("d-none");
            document.getElementById("det-why1").textContent = data.why1 || "";
            document.getElementById("det-why2").textContent = data.why2 || "";
            document.getElementById("det-why3").textContent = data.why3 || "";
            document.getElementById("det-why4").textContent = data.why4 || "";
            document.getElementById("det-why5").textContent = data.why5 || "";
        } else if (metodo === "FISHBONE") {
            elF?.classList.remove("d-none");
            document.getElementById("det-fish-metodo").textContent = data.fish_metodo || "";
            document.getElementById("det-fish-maquinas").textContent = data.fish_maquinas || "";
            document.getElementById("det-fish-materiales").textContent = data.fish_materiales || "";
            document.getElementById("det-fish-personas").textContent = data.fish_personas || "";
            document.getElementById("det-fish-entorno").textContent = data.fish_entorno || "";
            document.getElementById("det-fish-medicion").textContent = data.fish_medicion || "";
        }
    };

    function fmtDMY(s) {
        if (!s) return '';
        const t = String(s).trim();
        if (t.length >= 10 && t[4] === '-' && t[7] === '-') {
            const y = t.slice(0, 4), m = t.slice(5, 7), d = t.slice(8, 10);
            return `${d}/${m}/${y}`;
        }
        return t;
    }

    function fmtDMYHMS(s) {
        if (!s) return '';
        const t = String(s).trim();
        if (t.length >= 19 && t[4] === '-' && t[7] === '-') {
            const y = t.slice(0, 4), m = t.slice(5, 7), d = t.slice(8, 10);
            const hh = t.slice(11, 13), mm = t.slice(14, 16), ss = t.slice(17, 19);
            return `${d}/${m}/${y} ${hh}:${mm}:${ss}`;
        }
        return fmtDMY(t);
    }

    function escapeHtml(str) {
        return String(str || '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", "&#039;");
    }

    function renderChips(el, csvText, icon) {
        if (!el) return;
        const txt = String(csvText || '').trim();
        if (!txt) {
            el.innerHTML = `<span class="text-muted small">—</span>`;
            return;
        }
        const parts = txt.split(',').map(s => s.trim()).filter(Boolean);
        el.innerHTML = parts.map(n => `
                <span class="det-chip">
                    <i class="bi ${icon}"></i>${escapeHtml(n)}
                </span>
            `).join('');
    }

    function limpiarSeguimientoAcciones() {
        const wrap = document.getElementById('det-seguimiento-acciones-list');
        if (wrap) {
            wrap.innerHTML = `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
        }
    }

    function resaltarRespuestaTecnica() {
        const bloque = document.querySelector('#modalDetalle .det-rt-wrap');
        if (!bloque) return;

        bloque.classList.add('border', 'border-primary', 'shadow');
        setTimeout(() => {
            bloque.classList.remove('border', 'border-primary', 'shadow');
        }, 1200);

        bloque.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }

    function badgeTipoAccion(tipo) {
        const t = String(tipo || '').toUpperCase();
        if (t === 'CORRECTIVA') {
            return `<span class="det-badge-soft det-badge-correctiva">Correctiva</span>`;
        }
        return `<span class="det-badge-soft det-badge-control">Control</span>`;
    }

    function badgeEstadoAccion(cumplido) {
        return Number(cumplido || 0) === 1
            ? `<span class="det-badge-soft det-badge-cumplido">
                <i class="bi bi-check-circle-fill me-1"></i>Cumplido
           </span>`
            : `<span class="det-badge-soft det-badge-pendiente">
                <i class="bi bi-hourglass-split me-1"></i>Pendiente
           </span>`;
    }

    function renderEvidenciasHtml(evidencias, cumplido) {
        if (!Array.isArray(evidencias) || !evidencias.length) {
            return `<div class="small text-muted mt-2">Sin evidencias.</div>`;
        }

        const puedeEliminar = Number(cumplido || 0) !== 1;

        return `
        <ul class="det-seg-evid-list small mb-0">
            ${evidencias.map(ev => {
            const url = buildEvidenciaDownloadUrl(ev);
            const evId = ev?.id ?? '';

            return `
                    <li class="d-flex align-items-center gap-2 flex-wrap">
                        <a href="${url}"
                           class="link-primary text-decoration-none"
                           target="_blank"
                           rel="noopener">
                            <i class="bi bi-paperclip me-1"></i>${escapeHtml(ev.original_name || ev.filename || 'Archivo')}
                        </a>

                        ${ev.created_at ? `<span class="text-muted">(${escapeHtml(ev.created_at)})</span>` : ''}

                        ${puedeEliminar ? `
                            <button type="button"
                                    class="btn btn-sm btn-outline-danger js-eliminar-evidencia"
                                    data-evidencia-id="${evId}"
                                    title="Eliminar evidencia">
                                <i class="bi bi-trash"></i>
                            </button>
                        ` : ''}
                    </li>
                `;
        }).join('')}
        </ul>
    `;
    }

    function renderEvidenciasHtmlSponsor(evidencias, cumplido) {
        if (!Array.isArray(evidencias) || !evidencias.length) {
            return `<div class="small text-muted mt-2">Sin evidencias.</div>`;
        }

        const puedeEliminar = Number(cumplido || 0) !== 1;

        return `
        <ul class="det-seg-evid-list small mb-0">
            ${evidencias.map(ev => {
            const url = ev?.download_url && String(ev.download_url).trim() !== ''
                ? ev.download_url
                : '#';

            const evId = ev?.id ?? '';

            return `
                    <li class="d-flex align-items-center gap-2 flex-wrap">
                        <a href="${url}"
                           class="link-primary text-decoration-none"
                           target="_blank"
                           rel="noopener">
                            <i class="bi bi-paperclip me-1"></i>${escapeHtml(ev.original_name || ev.filename || 'Archivo')}
                        </a>

                        ${ev.created_at ? `<span class="text-muted">(${escapeHtml(ev.created_at)})</span>` : ''}

                        ${puedeEliminar ? `
                            <button type="button"
                                    class="btn btn-sm btn-outline-danger js-eliminar-evidencia-sponsor"
                                    data-evidencia-id="${evId}"
                                    title="Eliminar evidencia">
                                <i class="bi bi-trash"></i>
                            </button>
                        ` : ''}
                    </li>
                `;
        }).join('')}
        </ul>
    `;
    }


    function renderEvidenciasHtmlReadonly(evidencias) {
        if (!Array.isArray(evidencias) || !evidencias.length) {
            return `<div class="small text-muted mt-2">Sin evidencias.</div>`;
        }

        return `
        <ul class="det-seg-evid-list small mb-0">
            ${evidencias.map(ev => `
                <li class="d-flex align-items-center gap-2 flex-wrap">
                    <a href="${ev.download_url || '#'}"
                       class="link-primary text-decoration-none"
                       target="_blank"
                       rel="noopener">
                        <i class="bi bi-paperclip me-1"></i>${escapeHtml(ev.original_name || ev.filename || 'Archivo')}
                    </a>
                    ${ev.created_at ? `<span class="text-muted">(${escapeHtml(ev.created_at)})</span>` : ''}
                </li>
            `).join('')}
        </ul>
    `;
    }
    function renderSeguimientoAccionesReadonly(items) {
        const wrap = document.getElementById('det-seguimiento-acciones-list');
        if (!wrap) return;

        if (!Array.isArray(items) || !items.length) {
            wrap.innerHTML = `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
            return;
        }

        wrap.innerHTML = items.map(x => {
            const tipo = String(x.tipo || '').toUpperCase();
            const soloSeguimiento = (tipo === 'CONTROL' || tipo === 'CORRECTIVA');
            if (!soloSeguimiento) return '';

            const requiereEvidencia = Number(x.requiere_evidencia || 0) === 1;
            const cumplido = Number(x.cumplido || 0) === 1;
            const observacion = x.observacion_cumplimiento || '';
            const evidencias = Array.isArray(x.evidencias) ? x.evidencias : [];
            const tieneEvidencia = evidencias.length > 0;

            return `
            <div class="det-seg-card mb-2">
                <div class="det-seg-top">
                    <div class="flex-grow-1">
                        <div class="mb-1">
                            ${badgeTipoAccion(tipo)}
                        </div>

                        <div class="det-seg-desc">${escapeHtml(x.descripcion || '')}</div>
                        <div class="mt-2 small fw-semibold ${cumplido ? 'text-success' : 'text-warning'}">
                            <i class="bi ${cumplido ? 'bi-check2-circle' : 'bi-hourglass-split'} me-1"></i>
                            ${cumplido ? 'Acción completada' : 'Acción pendiente de cumplimiento'}
                        </div>
                        <div class="det-seg-meta mt-1">
                            Fecha compromiso: ${x.fecha_compromiso ? fmtDMY(x.fecha_compromiso) : '—'}
                        </div>

                        <div class="det-seg-meta">
                            Fecha cumplimiento: ${x.fecha_cumplimiento ? fmtDMY(x.fecha_cumplimiento) : '—'}
                        </div>

                        <div class="mt-2">
                            ${badgeEstadoAccion(cumplido ? 1 : 0)}
                            ${requiereEvidencia
                    ? (
                        tieneEvidencia
                            ? `<span class="badge text-bg-success ms-2">
                    <i class="bi bi-paperclip me-1"></i>Con evidencia
               </span>`
                            : `<span class="badge bg-light text-dark border ms-2">
                    <i class="bi bi-exclamation-circle me-1"></i>Requiere evidencia
               </span>`
                    )
                    : ''}
                        </div>

                        <div class="mt-2">
                            <div class="small fw-semibold">Observación</div>
                            <div class="small text-muted ws-pre-wrap">${escapeHtml(observacion || '—')}</div>
                        </div>

                        <div class="mt-3">
                            ${renderEvidenciasHtmlReadonly(x.evidencias || [])}
                        </div>
                    </div>
                </div>
            </div>
        `;
        }).filter(Boolean).join('') || `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
    }
    function renderSeguimientoAccionesSponsor(acciones) {
        const box = document.getElementById('det-seguimiento-acciones-list');
        if (!box) return;

        box.innerHTML = (Array.isArray(acciones) ? acciones : []).map(x => {
            const esControl = (x.tipo || '').toLowerCase() === 'control';
            const badgeClase = esControl ? 'det-badge-control' : 'det-badge-correctiva';
            const badgeTexto = esControl ? 'Control' : 'Correctiva';
            const cumplido = Number(x.cumplido || 0) === 1;
            const observacion = x.observacion_cumplimiento || '';
            const requiereEvidencia = Number(x.requiere_evidencia || 0) === 1;

            return `
            <div class="det-seg-card mb-2">
                <div class="det-seg-top">
                    <div class="flex-grow-1">
                        <div class="mb-1">
                            <span class="det-badge-soft ${badgeClase}">${badgeTexto}</span>
                        </div>

                        <div class="det-seg-desc">${escapeHtml(x.descripcion || '')}</div>

                        <div class="det-seg-meta mt-1">
                            Fecha compromiso: ${x.fecha_compromiso ? fmtDMY(x.fecha_compromiso) : '—'}
                        </div>

                        <div class="det-seg-meta">
                            Fecha cumplimiento: ${x.fecha_cumplimiento ? fmtDMY(x.fecha_cumplimiento) : '—'}
                        </div>

                        <div class="mt-2">
                            ${badgeEstadoAccion(x.cumplido)}
                            ${requiereEvidencia ? `<span class="badge bg-light text-dark border ms-2">Requiere evidencia</span>` : ''}
                        </div>

                        <div class="mt-3">
                            <label class="form-label small fw-semibold mb-1">Observación</label>
                            <textarea class="form-control form-control-sm js-observacion-accion-sponsor"
                                      data-accion-id="${x.id}"
                                      rows="2"
                                      ${cumplido ? 'disabled' : ''}
                                      placeholder="Ingrese una observación sobre el cumplimiento o avance...">${escapeHtml(observacion)}</textarea>

                            ${cumplido ? `
                                <div class="small text-muted mt-1">La acción está cumplida. La observación quedó en solo lectura.</div>
                            ` : `
                                <div class="mt-2">
                                    <button type="button"
                                            class="btn btn-sm btn-outline-primary js-guardar-observacion-sponsor"
                                            data-accion-id="${x.id}">
                                        <i class="bi bi-save me-1"></i>Guardar observación
                                    </button>
                                </div>
                            `}
                        </div>

                        <div class="mt-3">
                            ${renderEvidenciasHtmlSponsor(x.evidencias || [], x.cumplido)}
                        </div>
                    </div>

                    <div class="det-seg-actions">
                        ${cumplido ? '' : `
                            <button type="button"
                                    class="btn btn-sm btn-success js-cumplir-accion-sponsor"
                                    data-accion-id="${x.id}">
                                <i class="bi bi-check2-circle me-1"></i>Cumplido
                            </button>
                        `}

                        <input type="file"
                               class="form-control form-control-sm js-evidencia-accion-sponsor seg-evidencia-input"
                               data-accion-id="${x.id}"
                               ${cumplido ? 'disabled' : ''}>
                    </div>
                </div>
            </div>
        `;
        }).filter(Boolean).join('') || `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
    }


    function renderSeguimientoAccionesEquipo(items) {
        const wrap = document.getElementById('det-seguimiento-acciones-list');
        if (!wrap) return;

        if (!Array.isArray(items) || !items.length) {
            wrap.innerHTML = `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
            return;
        }

        wrap.innerHTML = items.map(x => {
            const tipo = String(x.tipo || '').toUpperCase();
            const soloSeguimiento = (tipo === 'CONTROL' || tipo === 'CORRECTIVA');
            if (!soloSeguimiento) return '';

            const cumplido = Number(x.cumplido || 0) === 1;
            const requiereEvidencia = Number(x.requiere_evidencia || 0) === 1;
            const observacion = x.observacion_cumplimiento || '';

            return `
            <div class="det-seg-card mb-2">
                <div class="det-seg-top">
                    <div class="flex-grow-1">
                        <div class="mb-1">
                            ${badgeTipoAccion(tipo)}
                        </div>

                        <div class="det-seg-desc">${escapeHtml(x.descripcion || '')}</div>

                        <div class="det-seg-meta mt-1">
                            Fecha compromiso: ${x.fecha_compromiso ? fmtDMY(x.fecha_compromiso) : '—'}
                        </div>

                        <div class="det-seg-meta">
                            Fecha cumplimiento: ${x.fecha_cumplimiento ? fmtDMY(x.fecha_cumplimiento) : '—'}
                        </div>

                        <div class="mt-2">
                            ${badgeEstadoAccion(x.cumplido)}
                            ${requiereEvidencia ? `<span class="badge bg-light text-dark border ms-2">Requiere evidencia</span>` : ''}
                        </div>

                        <div class="mt-3">
                            <label class="form-label small fw-semibold mb-1">Observación</label>
                            <textarea class="form-control form-control-sm js-observacion-accion"
                                      data-accion-id="${x.id}"
                                      rows="2"
                                      ${cumplido ? 'disabled' : ''}
                                      placeholder="Ingrese una observación sobre el cumplimiento o avance...">${escapeHtml(observacion)}</textarea>

                            ${cumplido ? `
                                <div class="small text-muted mt-1">La acción está cumplida. La observación quedó en solo lectura.</div>
                            ` : `
                                <div class="mt-2">
                                    <button type="button"
                                            class="btn btn-sm btn-outline-primary js-guardar-observacion"
                                            data-accion-id="${x.id}">
                                        <i class="bi bi-save me-1"></i>Guardar observación
                                    </button>
                                </div>
                            `}
                        </div>

                        <div class="mt-3">
                            ${renderEvidenciasHtml(x.evidencias || [], x.cumplido)}
                        </div>
                    </div>

                    <div class="det-seg-actions">
                        ${cumplido ? '' : `
                            <button type="button"
                                    class="btn btn-sm btn-success js-cumplir-accion"
                                    data-accion-id="${x.id}">
                                <i class="bi bi-check2-circle me-1"></i>Cumplido
                            </button>
                        `}

                        <input type="file"
                               class="form-control form-control-sm js-evidencia-accion seg-evidencia-input"
                               data-accion-id="${x.id}"
                               ${cumplido ? 'disabled' : ''}>
                    </div>
                </div>
            </div>
        `;
        }).filter(Boolean).join('') || `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
    }
    async function cargarSeguimientoEquipo(reclamoId, imputacionId, miembroId) {
        limpiarSeguimientoAcciones();

        try {
            const resp = await fetch(
                `/reclamos/${reclamoId}/equipo-respuestas/aporte?imputacion_id=${encodeURIComponent(imputacionId)}&miembro_id=${encodeURIComponent(miembroId)}`,
                {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                }
            );

            if (!resp.ok) throw new Error('HTTP ' + resp.status);

            const data = await resp.json();
            const item = data.item || null;

            if (!item) {
                limpiarSeguimientoAcciones();
                return;
            }

            const acciones = [
                ...(Array.isArray(item.control) ? item.control : []),
                ...(Array.isArray(item.correctiva_items) ? item.correctiva_items : [])
            ];

            renderSeguimientoAccionesEquipo(acciones);

        } catch (err) {
            console.error('Error cargando seguimiento:', err);
            const wrap = document.getElementById('det-seguimiento-acciones-list');
            if (wrap) {
                wrap.innerHTML = `<div class="text-danger small">Error al cargar seguimiento de acciones.</div>`;
            }
        }
    }
    window.__detEquipoCtx = null;

    window.recargarDetalleEquipoActual = async function () {
        if (!window.__detEquipoCtx) return;

        const { reclamoId, imputacionId, miembroId } = window.__detEquipoCtx;


        const filaUnica = document.querySelector('#modalDetalle .row-respuesta-unica');
        const elFC = document.getElementById("det-fecha-causa");
        const elFP = document.getElementById("det-fecha-preventiva");
        const elFF = document.getElementById("det-fecha-correctiva");

        try {
            const resp = await fetch(
                `/reclamos/${reclamoId}/equipo-respuestas/aporte?imputacion_id=${encodeURIComponent(imputacionId)}&miembro_id=${encodeURIComponent(miembroId)}`,
                {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                }
            );

            if (!resp.ok) throw new Error('HTTP ' + resp.status);

            const data = await resp.json();
            const item = data.item || null;

            filaUnica?.classList.remove('d-none');

            if (!item) {
                document.getElementById('det-causa').innerHTML = '<span class="text-muted">Sin respuesta técnica registrada.</span>';
                document.getElementById('det-preventiva').innerHTML = '<span class="text-muted">—</span>';
                document.getElementById('det-correctiva').innerHTML = '<span class="text-muted">—</span>';
                limpiarSeguimientoAcciones();
                return;
            }

            function renderDetalleListaApi(elId, lista) {
                const el = document.getElementById(elId);
                if (!el) return;

                if (!Array.isArray(lista) || !lista.length) {
                    el.innerHTML = '<span class="text-muted">—</span>';
                    return;
                }

                el.innerHTML = lista.map(x => {
                    const desc = escapeHtml(x.descripcion || '');
                    const fecha = x.fecha_compromiso ? ` <span class="text-muted">(${fmtDMY(x.fecha_compromiso)})</span>` : '';
                    return `<div class="mb-1">• ${desc}${fecha}</div>`;
                }).join('');
            }

            renderDetalleListaApi('det-causa', item.causas || []);
            renderDetalleListaApi('det-preventiva', item.control || []);
            renderDetalleListaApi('det-correctiva', item.correctiva_items || []);

            const accionesSeguimiento = [
                ...(Array.isArray(item.control) ? item.control : []),
                ...(Array.isArray(item.correctiva_items) ? item.correctiva_items : [])
            ];
            renderSeguimientoAccionesEquipo(accionesSeguimiento);

            if (elFC) elFC.textContent = '';
            if (elFP) elFP.textContent = '';
            if (elFF) elFF.textContent = '';

            if (window.renderAnalisisDetalle) {
                window.renderAnalisisDetalle({
                    metodo_analisis: item.metodo_analisis || '',
                    why1: item.why1 || '',
                    why2: item.why2 || '',
                    why3: item.why3 || '',
                    why4: item.why4 || '',
                    why5: item.why5 || '',
                    fish_metodo: item.fish_metodo || '',
                    fish_maquinas: item.fish_maquinas || '',
                    fish_materiales: item.fish_materiales || '',
                    fish_personas: item.fish_personas || '',
                    fish_entorno: item.fish_entorno || '',
                    fish_medicion: item.fish_medicion || '',
                });
            }

        } catch (err) {
            console.error('Error recargando detalle del equipo:', err);
            showToast?.('No se pudo refrescar el detalle');
        }
    }


    window.__detSponsorCtx = null;

    window.recargarDetalleSponsorActual = async function () {
        if (!window.__detSponsorCtx) return;

        const { imputacionId } = window.__detSponsorCtx;

        const filaUnica = document.querySelector('#modalDetalle .row-respuesta-unica');
        const elFC = document.getElementById("det-fecha-causa");
        const elFP = document.getElementById("det-fecha-preventiva");
        const elFF = document.getElementById("det-fecha-correctiva");

        try {
            const resp = await fetch(
                `/reclamos/imputacion/${encodeURIComponent(imputacionId)}/respuesta-detalle`,
                {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                }
            );

            if (!resp.ok) throw new Error('HTTP ' + resp.status);

            const data = await resp.json();
            const item = data.item || null;

            filaUnica?.classList.remove('d-none');

            if (!item) {
                document.getElementById('det-causa').innerHTML = '<span class="text-muted">Sin respuesta técnica registrada.</span>';
                document.getElementById('det-preventiva').innerHTML = '<span class="text-muted">—</span>';
                document.getElementById('det-correctiva').innerHTML = '<span class="text-muted">—</span>';
                limpiarSeguimientoAcciones();
                return;
            }

            function renderDetalleListaApi(elId, lista) {
                const el = document.getElementById(elId);
                if (!el) return;

                if (!Array.isArray(lista) || !lista.length) {
                    el.innerHTML = '<span class="text-muted">—</span>';
                    return;
                }

                el.innerHTML = lista.map(x => {
                    const desc = escapeHtml(x.descripcion || '');
                    const fecha = x.fecha_compromiso ? ` <span class="text-muted">(${fmtDMY(x.fecha_compromiso)})</span>` : '';
                    return `<div class="mb-1">• ${desc}${fecha}</div>`;
                }).join('');
            }

            renderDetalleListaApi('det-causa', item.causas || []);
            renderDetalleListaApi('det-preventiva', item.control || []);
            renderDetalleListaApi('det-correctiva', item.correctiva_items || []);

            const accionesSeguimiento = [
                ...(Array.isArray(item.control) ? item.control : []),
                ...(Array.isArray(item.correctiva_items) ? item.correctiva_items : [])
            ];
            renderSeguimientoAccionesSponsor(accionesSeguimiento);

            if (elFC) elFC.textContent = '';
            if (elFP) elFP.textContent = '';
            if (elFF) elFF.textContent = '';

            if (window.renderAnalisisDetalle) {
                window.renderAnalisisDetalle({
                    metodo_analisis: item.metodo_analisis || '',
                    why1: item.why1 || '',
                    why2: item.why2 || '',
                    why3: item.why3 || '',
                    why4: item.why4 || '',
                    why5: item.why5 || '',
                    fish_metodo: item.fish_metodo || '',
                    fish_maquinas: item.fish_maquinas || '',
                    fish_materiales: item.fish_materiales || '',
                    fish_personas: item.fish_personas || '',
                    fish_entorno: item.fish_entorno || '',
                    fish_medicion: item.fish_medicion || '',
                });
            }

        } catch (err) {
            console.error('Error recargando detalle sponsor:', err);
            showToast?.('No se pudo refrescar el detalle del sponsor');
        }
    };
    function buildEvidenciaDownloadUrlSponsor(ev) {
        if (!ev) return '#';
        if (ev.download_url && String(ev.download_url).trim() !== '') {
            return ev.download_url;
        }
        if (ev.id !== undefined && ev.id !== null && String(ev.id).trim() !== '') {
            return `/reclamos/imputado-acciones/evidencias/${encodeURIComponent(ev.id)}/download`;
        }
        return '#';
    }

    function buildEvidenciaDownloadUrl(ev) {
        console.log("EVIDENCIA DOWNLOAD URL ->", ev);

        if (!ev) return '#';

        if (ev.download_url && String(ev.download_url).trim() !== '') {
            return ev.download_url;
        }

        if (ev.id !== undefined && ev.id !== null && String(ev.id).trim() !== '') {
            return `/reclamos/equipo-acciones/evidencias/${encodeURIComponent(ev.id)}/download`;
        }

        return '#';
    }
    document.querySelectorAll('.js-ver-detalle').forEach(btn => {
        btn.addEventListener('click', async () => {
            const tr = btn.closest('tr');
            if (!tr) return;

            const tipoRow = tr.dataset.row || '';
            const reclamoId = tr.dataset.reclamoId || tr.dataset.reclamoid || '';

            if (window.renderAnalisisDetalle) {
                window.renderAnalisisDetalle({ metodo_analisis: "" });
            }

            limpiarSeguimientoAcciones();

            const detId = document.getElementById('det-reclamo-id');
            if (detId) detId.value = reclamoId || '';

            if (reclamoId) {
                cargarAdjuntosDetalle();
            } else {
                const tbodyAdj = document.getElementById('det-adjuntos-body');
                if (tbodyAdj) {
                    tbodyAdj.innerHTML = `
                            <tr>
                                <td colspan="5" class="text-muted small">Sin adjuntos.</td>
                            </tr>`;
                }
            }

            document.getElementById('det-codigo').textContent = tr.dataset.codigo || '';

            const fRaw = tr.dataset.fechaReclamo || tr.dataset['fecha-reclamo'] || '';
            document.getElementById('det-fecha').textContent = fmtDMYHMS(fRaw);

            document.getElementById('det-cliente').textContent = tr.dataset.cliente || '';
            document.getElementById('det-proceso').textContent = tr.dataset.proceso || '';
            document.getElementById('det-tipo-reclamo').textContent =
                tr.dataset.tipoReclamo || tr.dataset.tipoReclamoTxt || '';

            document.getElementById('det-antecedente').textContent = tr.dataset.antecedente || '';
            document.getElementById('det-material').textContent = tr.dataset.material || '';

            const creadoPor = (tr.dataset.creadoPor || '').trim();
            const creadoPorWrap = document.getElementById('det-creado-por-wrap');
            const creadoPorEl  = document.getElementById('det-creado-por');
            if (creadoPorWrap && creadoPorEl) {
                creadoPorEl.textContent = creadoPor;
                creadoPorWrap.classList.toggle('d-none', !creadoPor);
            }

            renderChips(
                document.getElementById('det-imputados'),
                (tr.dataset.imputados || tr.dataset.imputado || ''),
                'bi-person-badge'
            );

            const equipoWrap = document.getElementById('det-equipo-wrap');
            const equipoTxt = (tr.dataset.equipo || '').trim();

            if (equipoWrap) {
                const equipoEl = document.getElementById('det-equipo');

                if (!equipoTxt) {
                    equipoWrap.classList.add('d-none');
                    if (equipoEl) equipoEl.innerHTML = '';
                } else {
                    equipoWrap.classList.remove('d-none');
                    renderChips(equipoEl, equipoTxt, 'bi-person-check');
                }
            }
            document.getElementById('det-observacion').textContent = tr.dataset.observacion || '';
            document.getElementById('det-estado').textContent =
                tr.dataset.estado || tr.dataset.estadoImputacion || '';
            document.getElementById('det-procede').textContent = tr.dataset.procede || '';
            document.getElementById('det-fcreacion').textContent =
                tr.dataset.fechaCreacion || tr.dataset['fecha-creacion'] || '';

            const filaUnica = document.querySelector('#modalDetalle .row-respuesta-unica');
            const contMult = document.getElementById('det-respuestas-multiples');
            const listMult = document.getElementById('det-respuestas-list');

            document.getElementById('det-causa').textContent = '';
            document.getElementById('det-preventiva').textContent = '';
            document.getElementById('det-correctiva').textContent = '';

            const elFC = document.getElementById("det-fecha-causa");
            const elFP = document.getElementById("det-fecha-preventiva");
            const elFF = document.getElementById("det-fecha-correctiva");

            if (elFC) elFC.textContent = "";
            if (elFP) elFP.textContent = "";
            if (elFF) elFF.textContent = "";

            filaUnica?.classList.add('d-none');
            contMult?.classList.add('d-none');
            if (listMult) listMult.innerHTML = '';

            if (tipoRow === 'aprobar') {
                filaUnica?.classList.remove('d-none');

                const causasDetalle =
                    (tr.getAttribute('data-causas-detalle') || tr.dataset.causasDetalle || '').trim();

                const controlDetalle =
                    (tr.getAttribute('data-control-detalle') || tr.dataset.controlDetalle || '').trim();

                const correctivaDetalle =
                    (tr.getAttribute('data-correctiva-detalle') || tr.dataset.correctivaDetalle || '').trim();

                function renderDetalleLista(elId, textoFallback) {
                    const el = document.getElementById(elId);
                    if (!el) return;

                    const txt = String(textoFallback || '').trim();
                    if (!txt) {
                        el.innerHTML = '<span class="text-muted">—</span>';
                        return;
                    }

                    const items = txt.split('|').map(x => x.trim()).filter(Boolean);

                    el.innerHTML = items.map(item => `
                            <div class="mb-1">• ${escapeHtml(item)}</div>
                        `).join('');
                }

                renderDetalleLista('det-causa', causasDetalle || tr.dataset.causa || '');
                renderDetalleLista('det-preventiva', controlDetalle || tr.dataset.preventiva || '');
                renderDetalleLista('det-correctiva', correctivaDetalle || tr.dataset.correctiva || '');

                if (elFC) elFC.textContent = tr.dataset.fechaCausa ? `Fecha: ${fmtDMY(tr.dataset.fechaCausa)}` : "";
                if (elFP) elFP.textContent = tr.dataset.fechaPreventiva ? `Fecha: ${fmtDMY(tr.dataset.fechaPreventiva)}` : "";
                if (elFF) elFF.textContent = tr.dataset.fechaCorrectiva ? `Fecha: ${fmtDMY(tr.dataset.fechaCorrectiva)}` : "";

                if (window.renderAnalisisDetalle) {
                    window.renderAnalisisDetalle({
                        metodo_analisis: tr.dataset.metodoAnalisis || '',
                        why1: tr.dataset.why1 || '',
                        why2: tr.dataset.why2 || '',
                        why3: tr.dataset.why3 || '',
                        why4: tr.dataset.why4 || '',
                        why5: tr.dataset.why5 || '',
                        fish_metodo: tr.dataset.fishMetodo || '',
                        fish_maquinas: tr.dataset.fishMaquinas || '',
                        fish_materiales: tr.dataset.fishMateriales || '',
                        fish_personas: tr.dataset.fishPersonas || '',
                        fish_entorno: tr.dataset.fishEntorno || '',
                        fish_medicion: tr.dataset.fishMedicion || '',
                    });
                }

                return;
            }

            if (tipoRow === 'imputado' && reclamoId) {
                try {
                    const imputacionId = (tr.dataset.imputacionId || '').trim();
                    if (!imputacionId) {
                        throw new Error('Falta imputacion_id en la fila');
                    }

                    window.__detSponsorCtx = { imputacionId };

                    const resp = await fetch(
                        `/reclamos/imputacion/${encodeURIComponent(imputacionId)}/respuesta-detalle`,
                        {
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken

                            }
                        }
                    );

                    if (!resp.ok) throw new Error('HTTP ' + resp.status);

                    const data = await resp.json();
                    const item = data.item || null;

                    filaUnica?.classList.remove('d-none');

                    if (!item) {
                        document.getElementById('det-causa').innerHTML = '<span class="text-muted">Sin respuesta técnica registrada.</span>';
                        document.getElementById('det-preventiva').innerHTML = '<span class="text-muted">—</span>';
                        document.getElementById('det-correctiva').innerHTML = '<span class="text-muted">—</span>';
                        limpiarSeguimientoAcciones();
                        return;
                    }

                    function renderDetalleListaApi(elId, lista) {
                        const el = document.getElementById(elId);
                        if (!el) return;

                        if (!Array.isArray(lista) || !lista.length) {
                            el.innerHTML = '<span class="text-muted">—</span>';
                            return;
                        }

                        el.innerHTML = lista.map(x => {
                            const desc = escapeHtml(x.descripcion || '');
                            const fecha = x.fecha_compromiso ? ` <span class="text-muted">(${fmtDMY(x.fecha_compromiso)})</span>` : '';
                            return `<div class="mb-1">• ${desc}${fecha}</div>`;
                        }).join('');
                    }

                    renderDetalleListaApi('det-causa', item.causas || []);
                    renderDetalleListaApi('det-preventiva', item.control || []);
                    renderDetalleListaApi('det-correctiva', item.correctiva_items || []);

                    const accionesSeguimiento = [
                        ...(Array.isArray(item.control) ? item.control : []),
                        ...(Array.isArray(item.correctiva_items) ? item.correctiva_items : [])
                    ];

                    //renderSeguimientoAccionesEquipo(accionesSeguimiento);
                    renderSeguimientoAccionesSponsor(accionesSeguimiento);

                    if (elFC) elFC.textContent = '';
                    if (elFP) elFP.textContent = '';
                    if (elFF) elFF.textContent = '';

                    if (window.renderAnalisisDetalle) {
                        window.renderAnalisisDetalle({
                            metodo_analisis: item.metodo_analisis || '',
                            why1: item.why1 || '',
                            why2: item.why2 || '',
                            why3: item.why3 || '',
                            why4: item.why4 || '',
                            why5: item.why5 || '',
                            fish_metodo: item.fish_metodo || '',
                            fish_maquinas: item.fish_maquinas || '',
                            fish_materiales: item.fish_materiales || '',
                            fish_personas: item.fish_personas || '',
                            fish_entorno: item.fish_entorno || '',
                            fish_medicion: item.fish_medicion || '',
                        });
                    }

                } catch (err) {
                    console.error('Error cargando respuesta sponsor:', err);
                    filaUnica?.classList.remove('d-none');
                    document.getElementById('det-causa').textContent = 'Error al cargar respuesta técnica.';
                    document.getElementById('det-preventiva').textContent = '';
                    document.getElementById('det-correctiva').textContent = '';
                    limpiarSeguimientoAcciones();
                }

                return;
            }

            if (tipoRow === 'equipo' && reclamoId) {
                try {
                    const imputacionId = (tr.dataset.imputacionId || '').trim();
                    const miembroId = (tr.dataset.miembroId || '').trim();
                    window.__detEquipoCtx = {
                        reclamoId,
                        imputacionId,
                        miembroId
                    };

                    if (!imputacionId || !miembroId) {
                        throw new Error('Falta imputacion_id o miembro_id en la fila');
                    }

                    const resp = await fetch(
                        `/reclamos/${reclamoId}/equipo-respuestas/aporte?imputacion_id=${encodeURIComponent(imputacionId)}&miembro_id=${encodeURIComponent(miembroId)}`,
                        {
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRFToken': csrfToken
                            }
                        }
                    );

                    if (!resp.ok) throw new Error('HTTP ' + resp.status);

                    const data = await resp.json();
                    const item = data.item || null;

                    filaUnica?.classList.remove('d-none');

                    if (!item) {
                        document.getElementById('det-causa').innerHTML = '<span class="text-muted">Sin respuesta técnica registrada.</span>';
                        document.getElementById('det-preventiva').innerHTML = '<span class="text-muted">—</span>';
                        document.getElementById('det-correctiva').innerHTML = '<span class="text-muted">—</span>';
                        limpiarSeguimientoAcciones();
                        return;
                    }

                    function renderDetalleListaApi(elId, lista) {
                        const el = document.getElementById(elId);
                        if (!el) return;

                        if (!Array.isArray(lista) || !lista.length) {
                            el.innerHTML = '<span class="text-muted">—</span>';
                            return;
                        }

                        el.innerHTML = lista.map(x => {
                            const desc = escapeHtml(x.descripcion || '');
                            const fecha = x.fecha_compromiso ? ` <span class="text-muted">(${fmtDMY(x.fecha_compromiso)})</span>` : '';
                            return `<div class="mb-1">• ${desc}${fecha}</div>`;
                        }).join('');
                    }

                    renderDetalleListaApi('det-causa', item.causas || []);
                    renderDetalleListaApi('det-preventiva', item.control || []);
                    renderDetalleListaApi('det-correctiva', item.correctiva_items || []);

                    const accionesSeguimiento = [
                        ...(Array.isArray(item.control) ? item.control : []),
                        ...(Array.isArray(item.correctiva_items) ? item.correctiva_items : [])
                    ];
                    renderSeguimientoAccionesEquipo(accionesSeguimiento);

                    if (elFC) elFC.textContent = '';
                    if (elFP) elFP.textContent = '';
                    if (elFF) elFF.textContent = '';

                    if (window.renderAnalisisDetalle) {
                        window.renderAnalisisDetalle({
                            metodo_analisis: item.metodo_analisis || '',
                            why1: item.why1 || '',
                            why2: item.why2 || '',
                            why3: item.why3 || '',
                            why4: item.why4 || '',
                            why5: item.why5 || '',
                            fish_metodo: item.fish_metodo || '',
                            fish_maquinas: item.fish_maquinas || '',
                            fish_materiales: item.fish_materiales || '',
                            fish_personas: item.fish_personas || '',
                            fish_entorno: item.fish_entorno || '',
                            fish_medicion: item.fish_medicion || '',
                        });
                    }

                } catch (err) {
                    console.error('Error cargando respuesta del equipo:', err);
                    filaUnica?.classList.remove('d-none');
                    document.getElementById('det-causa').textContent = 'Error al cargar respuesta del miembro del equipo.';
                    document.getElementById('det-preventiva').textContent = '';
                    document.getElementById('det-correctiva').textContent = '';
                    limpiarSeguimientoAcciones();
                }

                return;
            }

            if (tipoRow === 'created' && reclamoId) {
                try {
                    const resp = await fetch(`/reclamos/api/${reclamoId}/respuestas-detalle`, {
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken
                        }
                    });

                    if (!resp.ok) throw new Error('HTTP ' + resp.status);

                    const data = await resp.json();
                    const items = Array.isArray(data.items) ? data.items : [];

                    // Solo respuestas oficiales de sponsors/imputados.
                    const sponsorItems = items.filter(x => x.origen === 'imputado');

                    filaUnica?.classList.add('d-none');
                    contMult?.classList.remove('d-none');

                    if (!listMult) return;

                    if (!sponsorItems.length) {
                        listMult.innerHTML = `
                <div class="text-muted small border rounded-3 p-3">
                    No hay respuestas técnicas registradas.
                </div>
            `;
                        limpiarSeguimientoAcciones();

                        if (window.renderAnalisisDetalle) {
                            window.renderAnalisisDetalle({ metodo_analisis: "" });
                        }

                        return;
                    }

                    function renderListaAcciones(lista, fallbackTexto = '') {
                        if (Array.isArray(lista) && lista.length) {
                            return lista.map(x => {
                                const desc = escapeHtml(x.descripcion || '');
                                const fecha = x.fecha_compromiso
                                    ? ` <span class="text-muted">(${fmtDMY(x.fecha_compromiso)})</span>`
                                    : '';

                                return `<div class="mb-1">• ${desc}${fecha}</div>`;
                            }).join('');
                        }

                        const txt = String(fallbackTexto || '').trim();

                        if (txt) {
                            return `<div class="mb-1">${escapeHtml(txt)}</div>`;
                        }

                        return '<span class="text-muted">—</span>';
                    }

                    function renderSeguimientoAccionesReadonlyHtml(itemsAcciones) {
                        if (!Array.isArray(itemsAcciones) || !itemsAcciones.length) {
                            return `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
                        }

                        const html = itemsAcciones.map(x => {
                            const tipo = String(x.tipo || '').toUpperCase();
                            const soloSeguimiento = (tipo === 'CONTROL' || tipo === 'CORRECTIVA');
                            if (!soloSeguimiento) return '';

                            const requiereEvidencia = Number(x.requiere_evidencia || 0) === 1;
                            const cumplido = Number(x.cumplido || 0) === 1;
                            const observacion = x.observacion_cumplimiento || '';
                            const evidencias = Array.isArray(x.evidencias) ? x.evidencias : [];
                            const tieneEvidencia = evidencias.length > 0;

                            return `
                    <div class="det-seg-card mb-2">
                        <div class="det-seg-top">
                            <div class="flex-grow-1">
                                <div class="mb-1">
                                    ${badgeTipoAccion(tipo)}
                                </div>

                                <div class="det-seg-desc">${escapeHtml(x.descripcion || '')}</div>

                                <div class="mt-2 small fw-semibold ${cumplido ? 'text-success' : 'text-warning'}">
                                    <i class="bi ${cumplido ? 'bi-check2-circle' : 'bi-hourglass-split'} me-1"></i>
                                    ${cumplido ? 'Acción completada' : 'Acción pendiente de cumplimiento'}
                                </div>

                                <div class="det-seg-meta mt-1">
                                    Fecha compromiso: ${x.fecha_compromiso ? fmtDMY(x.fecha_compromiso) : '—'}
                                </div>

                                <div class="det-seg-meta">
                                    Fecha cumplimiento: ${x.fecha_cumplimiento ? fmtDMY(x.fecha_cumplimiento) : '—'}
                                </div>

                                <div class="mt-2">
                                    ${badgeEstadoAccion(cumplido ? 1 : 0)}
                                    ${requiereEvidencia
                                    ? (
                                        tieneEvidencia
                                            ? `<span class="badge text-bg-success ms-2">
                                                    <i class="bi bi-paperclip me-1"></i>Con evidencia
                                                   </span>`
                                            : `<span class="badge bg-light text-dark border ms-2">
                                                    <i class="bi bi-exclamation-circle me-1"></i>Requiere evidencia
                                                   </span>`
                                    )
                                    : ''}
                                </div>

                                <div class="mt-2">
                                    <div class="small fw-semibold">Observación</div>
                                    <div class="small text-muted ws-pre-wrap">${escapeHtml(observacion || '—')}</div>
                                </div>

                                <div class="mt-3">
                                    ${renderEvidenciasHtmlReadonly(evidencias)}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                        }).filter(Boolean).join('');

                        return html || `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
                    }

                    function renderAnalisisSponsor(item) {
                        const metodo = String(item.metodo_analisis || '').toUpperCase();

                        if (metodo === '5WHYS') {
                            return `
                    <div class="detail-card mt-3">
                        <div class="detail-section-title">Análisis de Causa Raíz</div>
                        <div class="fw-semibold mb-2">Metodología: 5 Por Qué</div>
                        <ol class="mb-0">
                            <li>${escapeHtml(item.why1 || '')}</li>
                            <li>${escapeHtml(item.why2 || '')}</li>
                            <li>${escapeHtml(item.why3 || '')}</li>
                            <li>${escapeHtml(item.why4 || '')}</li>
                            <li>${escapeHtml(item.why5 || '')}</li>
                        </ol>
                    </div>
                `;
                        }

                        if (metodo === 'FISHBONE') {
                            return `
                    <div class="detail-card mt-3">
                        <div class="detail-section-title">Análisis de Causa Raíz</div>
                        <div class="fw-semibold mb-2">Metodología: Espina de Pez</div>

                        <div class="row g-2">
                            <div class="col-md-4">
                                <div class="small fw-semibold">Método</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_metodo || '—')}</div>
                            </div>

                            <div class="col-md-4">
                                <div class="small fw-semibold">Máquinas</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_maquinas || '—')}</div>
                            </div>

                            <div class="col-md-4">
                                <div class="small fw-semibold">Materiales</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_materiales || '—')}</div>
                            </div>

                            <div class="col-md-4">
                                <div class="small fw-semibold">Personas</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_personas || '—')}</div>
                            </div>

                            <div class="col-md-4">
                                <div class="small fw-semibold">Entorno</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_entorno || '—')}</div>
                            </div>

                            <div class="col-md-4">
                                <div class="small fw-semibold">Medición</div>
                                <div class="border rounded p-2">${escapeHtml(item.fish_medicion || '—')}</div>
                            </div>
                        </div>
                    </div>
                `;
                        }

                        return `
                <div class="detail-card mt-3">
                    <div class="detail-section-title">Análisis de Causa Raíz</div>
                    <div class="text-muted small">Sin análisis registrado.</div>
                </div>
            `;
                    }

                    listMult.innerHTML = `
            <div class="accordion" id="accordion-respuestas-sponsor">
                ${sponsorItems.map((item, idx) => {
                        const collapseId = `collapse-sponsor-${reclamoId}-${idx}`;
                        const headingId = `heading-sponsor-${reclamoId}-${idx}`;

                        const nombre = item.nombre || item.username || `Sponsor ${idx + 1}`;
                        const estado = item.estado || '';

                        const causas = item.causas || [];
                        const control = item.control || [];
                        const correctivaItems = item.correctiva_items || [];

                        const accionesSeguimiento = [
                            ...(Array.isArray(control) ? control : []),
                            ...(Array.isArray(correctivaItems) ? correctivaItems : [])
                        ];

                        const abierto = idx === 0;

                        return `
                        <div class="accordion-item border rounded-4 overflow-hidden mb-3 shadow-sm">
                            <h2 class="accordion-header" id="${headingId}">
                                <button class="accordion-button ${abierto ? '' : 'collapsed'}"
                                        type="button"
                                        data-bs-toggle="collapse"
                                        data-bs-target="#${collapseId}"
                                        aria-expanded="${abierto ? 'true' : 'false'}"
                                        aria-controls="${collapseId}">
                                    <div class="d-flex align-items-center gap-2 flex-wrap w-100">
                                        <strong>${escapeHtml(nombre)}</strong>

                                        <span class="badge bg-primary-subtle text-dark">
                                            Sponsor
                                        </span>

                                        <span class="badge bg-light text-muted">
                                            Respuesta oficial
                                        </span>

                                        ${estado ? `
                                            <span class="badge bg-success-subtle text-dark">
                                                ${escapeHtml(estado)}
                                            </span>
                                        ` : ''}
                                    </div>
                                </button>
                            </h2>

                            <div id="${collapseId}"
                                 class="accordion-collapse collapse ${abierto ? 'show' : ''}"
                                 aria-labelledby="${headingId}"
                                 data-bs-parent="#accordion-respuestas-sponsor">
                                <div class="accordion-body">

                                    <div class="row g-3">
                                        <div class="col-12 col-lg-4">
                                            <div class="border rounded-4 p-3 h-100 bg-white shadow-sm det-rt-card">
                                                <div class="d-flex align-items-center justify-content-between mb-2">
                                                    <span class="badge rounded-pill text-bg-primary">
                                                        <i class="bi bi-exclamation-circle me-1"></i>Causa
                                                    </span>
                                                </div>

                                                <div class="border rounded-3 p-2 det-rt-body det-bg-gray ws-pre-wrap">
                                                    ${renderListaAcciones(causas, item.respuesta_causa || item.causa || '')}
                                                </div>

                                                <div class="small text-muted mt-2">
                                                    <i class="bi bi-info-circle me-1"></i>
                                                    Descripción de la causa raíz identificada.
                                                </div>
                                            </div>
                                        </div>

                                        <div class="col-12 col-lg-4">
                                            <div class="border rounded-4 p-3 h-100 bg-white shadow-sm det-rt-card">
                                                <div class="d-flex align-items-center justify-content-between mb-2">
                                                    <span class="badge rounded-pill text-bg-warning">
                                                        <i class="bi bi-shield-check me-1"></i>Acción de Control
                                                    </span>
                                                </div>

                                                <div class="border rounded-3 p-2 det-rt-body det-bg-warn ws-pre-wrap">
                                                    ${renderListaAcciones(control, item.respuesta_preventiva || item.preventiva || '')}
                                                </div>

                                                <div class="small text-muted mt-2">
                                                    <i class="bi bi-lightbulb me-1"></i>
                                                    Control aplicado para evitar recurrencia inmediata.
                                                </div>
                                            </div>
                                        </div>

                                        <div class="col-12 col-lg-4">
                                            <div class="border rounded-4 p-3 h-100 bg-white shadow-sm det-rt-card">
                                                <div class="d-flex align-items-center justify-content-between mb-2">
                                                    <span class="badge rounded-pill text-bg-success">
                                                        <i class="bi bi-check2-circle me-1"></i>Acción Correctiva
                                                    </span>
                                                </div>

                                                <div class="border rounded-3 p-2 det-rt-body det-bg-ok ws-pre-wrap">
                                                    ${renderListaAcciones(correctivaItems, item.respuesta_correctiva || item.correctiva || '')}
                                                </div>

                                                <div class="small text-muted mt-2">
                                                    <i class="bi bi-flag me-1"></i>
                                                    Acción definitiva para eliminar la causa.
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="detail-card mt-3">
                                        <div class="d-flex justify-content-between align-items-center mb-2">
                                            <div class="detail-section-title mb-0">Seguimiento de acciones</div>
                                            <div class="small-muted">
                                                <i class="bi bi-check2-square me-1"></i>
                                                Cumplimiento y evidencia por acción
                                            </div>
                                        </div>

                                        ${renderSeguimientoAccionesReadonlyHtml(accionesSeguimiento)}
                                    </div>

                                    ${renderAnalisisSponsor(item)}

                                </div>
                            </div>
                        </div>
                    `;
                    }).join('')}
            </div>
        `;

                    // Limpiamos la vista vieja inferior para no duplicar/confundir.
                    document.getElementById('det-causa').innerHTML = '';
                    document.getElementById('det-preventiva').innerHTML = '';
                    document.getElementById('det-correctiva').innerHTML = '';
                    limpiarSeguimientoAcciones();

                    if (window.renderAnalisisDetalle) {
                        window.renderAnalisisDetalle({ metodo_analisis: "" });
                    }

                } catch (err) {
                    console.error('Error cargando respuestas del creador:', err);

                    filaUnica?.classList.remove('d-none');
                    contMult?.classList.add('d-none');

                    if (listMult) listMult.innerHTML = '';

                    document.getElementById('det-causa').innerHTML =
                        '<span class="text-muted">Error al cargar respuesta técnica.</span>';
                    document.getElementById('det-preventiva').innerHTML =
                        '<span class="text-muted">—</span>';
                    document.getElementById('det-correctiva').innerHTML =
                        '<span class="text-muted">—</span>';

                    limpiarSeguimientoAcciones();
                }

                return;
            }


        });
    });

    document.querySelectorAll('.js-aprobar-imputacion').forEach(btn => {
        btn.addEventListener('click', () => {
            const tr = btn.closest('tr');
            if (!tr) return;

            const impId = tr.dataset.imputacionId || '';
            const esEquipo = (tr.dataset.soyEquipo === '1');

            if (esEquipo && !impId) {
                alert('Error: esta OM no tiene imputación_id en la fila (data-imputacion-id). No puedo guardar la respuesta.');
                return;
            }

            document.getElementById('aprob-imp-id').value = impId;
            document.getElementById('aprob-reclamo-codigo').textContent = tr.dataset.codigo || '';
            document.getElementById('aprob-imputado-nombre').textContent = tr.dataset.imputado || '';
            document.getElementById('aprob-observacion').textContent = tr.dataset.observacion || '';
            const mot = document.getElementById('aprob-motivo-rechazo');
            if (mot) mot.value = '';
        });
    });

    document.getElementById('btnAprobarImp')?.addEventListener('click', async () => {
        const impId = document.getElementById('aprob-imp-id').value;
        try {
            const r = await withBusy(fetch(`/reclamos/imputacion/${impId}/aprobar`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ accion: 'aprobar' })
            }), 'Aprobando imputación…');

            if (!r.ok) throw new Error('HTTP ' + r.status);
            showToast?.('Imputación aprobada');
            location.reload();
        } catch (err) {
            showToast?.('Error: ' + err.message);
        }
    });

    document.getElementById('btnRechazarImp')?.addEventListener('click', async () => {
        const impId = document.getElementById('aprob-imp-id').value;
        const motivoEl = document.getElementById('aprob-motivo-rechazo');
        const motivo = motivoEl ? motivoEl.value.trim() : '';

        if (!motivo) {
            alert('Debe indicar motivo de rechazo');
            return;
        }

        try {
            const r = await withBusy(
                fetch(`/reclamos/imputacion/${impId}/aprobar`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ accion: 'rechazar', motivo })
                }),
                'Rechazando imputación…'
            );

            if (!r.ok) throw new Error('HTTP ' + r.status);
            showToast?.('Imputación rechazazada');
            location.reload();
        } catch (err) {
            showToast?.('Error: ' + err.message);
        }
    });

    document.getElementById('btnRechazarResp')?.addEventListener('click', async () => {
        const impId = document.getElementById('val-imp-id').value;
        const motivo = document.getElementById('val-motivo-rechazo').value.trim();

        if (!motivo) {
            alert('Debe indicar motivo de rechazo');
            return;
        }

        try {
            const r = await withBusy(
                fetch(`/reclamos/imputacion/${impId}/validar_respuesta`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({ accion: 'rechazar', motivo })
                }),
                'Rechazando respuesta…'
            );

            if (!r.ok) throw new Error('HTTP ' + r.status);
            showToast?.('Respuesta rechazada. Se notificará al imputado');
            location.reload();
        } catch (err) {
            showToast?.('Error: ' + err.message);
        }
    });
})();

document.addEventListener('click', async (ev) => {
    const btnAnalisis = ev.target.closest('.js-ver-analisis-imputado');
    if (btnAnalisis) {
        document.getElementById('ana-imputado').textContent = btnAnalisis.dataset.imputado || '';
        document.getElementById('ana-metodo').textContent = btnAnalisis.dataset.metodo || '';

        const metodo = (btnAnalisis.dataset.metodo || 'FISHBONE').toUpperCase();

        document.getElementById('ana-vista-fish').classList.toggle('d-none', metodo !== 'FISHBONE');
        document.getElementById('ana-vista-why').classList.toggle('d-none', metodo !== '5WHYS');

        document.getElementById('ana-why1').textContent = btnAnalisis.dataset.why1 || '';
        document.getElementById('ana-why2').textContent = btnAnalisis.dataset.why2 || '';
        document.getElementById('ana-why3').textContent = btnAnalisis.dataset.why3 || '';
        document.getElementById('ana-why4').textContent = btnAnalisis.dataset.why4 || '';
        document.getElementById('ana-why5').textContent = btnAnalisis.dataset.why5 || '';

        document.getElementById('ana-fish-metodo').textContent = btnAnalisis.dataset.fishMetodo || '';
        document.getElementById('ana-fish-maquinas').textContent = btnAnalisis.dataset.fishMaquinas || '';
        document.getElementById('ana-fish-materiales').textContent = btnAnalisis.dataset.fishMateriales || '';
        document.getElementById('ana-fish-personas').textContent = btnAnalisis.dataset.fishPersonas || '';
        document.getElementById('ana-fish-entorno').textContent = btnAnalisis.dataset.fishEntorno || '';
        document.getElementById('ana-fish-medicion').textContent = btnAnalisis.dataset.fishMedicion || '';

        window.renderAnalisisDetalle({
            metodo_analisis: metodo,
            why1: btnAnalisis.dataset.why1 || "",
            why2: btnAnalisis.dataset.why2 || "",
            why3: btnAnalisis.dataset.why3 || "",
            why4: btnAnalisis.dataset.why4 || "",
            why5: btnAnalisis.dataset.why5 || "",
            fish_metodo: btnAnalisis.dataset.fishMetodo || "",
            fish_maquinas: btnAnalisis.dataset.fishMaquinas || "",
            fish_materiales: btnAnalisis.dataset.fishMateriales || "",
            fish_personas: btnAnalisis.dataset.fishPersonas || "",
            fish_entorno: btnAnalisis.dataset.fishEntorno || "",
            fish_medicion: btnAnalisis.dataset.fishMedicion || ""
        });

        bootstrap.Modal.getOrCreateInstance(document.getElementById('modalAnalisisImputado')).show();
        return;
    }
    const btnGuardarObs = ev.target.closest('.js-guardar-observacion');
    const btnGuardarObsSponsor = ev.target.closest('.js-guardar-observacion-sponsor');
    if (btnGuardarObsSponsor) {
        const accionId = btnGuardarObsSponsor.dataset.accionId;
        if (!accionId) return;

        const textarea = document.querySelector(`.js-observacion-accion-sponsor[data-accion-id="${accionId}"]`);
        const observacion = (textarea?.value || '').trim();

        try {
            bloquearBtn(btnGuardarObsSponsor, 'Guardando...');

            const resp = await fetch(`/reclamos/imputado-acciones/${accionId}/observacion`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ observacion })
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Observación guardada');
            await window.recargarDetalleSponsorActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo guardar la observación del sponsor.');
        } finally {
            desbloquearBtn(btnGuardarObsSponsor);
        }

        return;
    }

    const btnEliminarEvSponsor = ev.target.closest('.js-eliminar-evidencia-sponsor');
    if (btnEliminarEvSponsor) {
        const evidenciaId = btnEliminarEvSponsor.dataset.evidenciaId;
        if (!evidenciaId) return;

        if (!confirm('¿Deseas eliminar esta evidencia?')) return;

        try {
            bloquearBtn(btnEliminarEvSponsor, '...');

            const resp = await fetch(`/reclamos/imputado-acciones/evidencias/${evidenciaId}/eliminar`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Evidencia eliminada');
            await window.recargarDetalleSponsorActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo eliminar la evidencia del sponsor.');
        } finally {
            desbloquearBtn(btnEliminarEvSponsor);
        }

        return;
    }

    const btnCumplirSponsor = ev.target.closest('.js-cumplir-accion-sponsor');
    if (btnCumplirSponsor) {
        const accionId = btnCumplirSponsor.dataset.accionId;
        if (!accionId) return;

        try {
            bloquearBtn(btnCumplirSponsor, 'Guardando...');

            const resp = await fetch(`/reclamos/imputado-acciones/${accionId}/cumplir`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    cumplido: true,
                    fecha_cumplimiento: new Date().toISOString().slice(0, 10)
                })
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Acción marcada como cumplida');
            await window.recargarDetalleSponsorActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo actualizar el cumplimiento del sponsor.');
        } finally {
            desbloquearBtn(btnCumplirSponsor);
        }

        return;
    }


    if (btnGuardarObs) {
        const accionId = btnGuardarObs.dataset.accionId;
        if (!accionId) return;

        const textarea = document.querySelector(`.js-observacion-accion[data-accion-id="${accionId}"]`);
        const observacion = (textarea?.value || '').trim();

        try {
            bloquearBtn(btnGuardarObs, 'Guardando...');

            const resp = await fetch(`/reclamos/equipo-acciones/${accionId}/observacion`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ observacion })
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Observación guardada');
            await window.recargarDetalleEquipoActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo guardar la observación.');
        } finally {
            desbloquearBtn(btnGuardarObs);
        }

        return;
    }
    const btnEliminarEv = ev.target.closest('.js-eliminar-evidencia');
    if (btnEliminarEv) {
        const evidenciaId = btnEliminarEv.dataset.evidenciaId;
        if (!evidenciaId) return;

        const ok = confirm('¿Deseas eliminar esta evidencia?');
        if (!ok) return;

        try {
            bloquearBtn(btnEliminarEv, '...');

            const resp = await fetch(`/reclamos/equipo-acciones/evidencias/${evidenciaId}/eliminar`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken

                }
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Evidencia eliminada');
            await window.recargarDetalleEquipoActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo eliminar la evidencia.');
        } finally {
            desbloquearBtn(btnEliminarEv);
        }

        return;
    }
    const btnCumplir = ev.target.closest('.js-cumplir-accion');
    if (btnCumplir) {
        const accionId = btnCumplir.dataset.accionId;
        if (!accionId) return;

        try {
            bloquearBtn(btnCumplir, 'Guardando...');

            const resp = await fetch(`/reclamos/equipo-acciones/${accionId}/cumplir`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    cumplido: true,
                    fecha_cumplimiento: new Date().toISOString().slice(0, 10)
                })
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            showToast('Acción marcada como cumplida');

            try {
                //await recargarDetalleEquipoActual();
                await window.recargarDetalleEquipoActual();
            } catch (errRecarga) {
                console.error('Error recargando detalle luego de marcar cumplido:', errRecarga);
                showToast('Se guardó el cumplimiento, pero no se pudo refrescar el detalle.');
            }

        } catch (err) {
            console.error(err);
            alert('No se pudo actualizar el cumplimiento.');
        } finally {
            desbloquearBtn(btnCumplir);
        }
    }
});

document.addEventListener('change', async (ev) => {
    const inputSponsor = ev.target.closest('.js-evidencia-accion-sponsor');
    if (inputSponsor && inputSponsor.files && inputSponsor.files.length) {
        const accionId = inputSponsor.dataset.accionId;
        if (!accionId) return;

        try {
            const form = new FormData();
            form.append('file', inputSponsor.files[0]);

            const resp = await fetch(`/reclamos/imputado-acciones/${accionId}/evidencia`, {
                method: 'POST',
                body: form,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            });

            const data = await resp.json().catch(() => ({}));

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
            }

            inputSponsor.value = '';
            showToast('Evidencia subida correctamente');
            await window.recargarDetalleSponsorActual();

        } catch (err) {
            console.error(err);
            alert('No se pudo subir la evidencia del sponsor.');
        }

        return;
    }

    const input = ev.target.closest('.js-evidencia-accion');
    if (!input || !input.files || !input.files.length) return;

    const accionId = input.dataset.accionId;
    if (!accionId) return;

    try {
        const form = new FormData();
        form.append('file', input.files[0]);

        const resp = await fetch(`/reclamos/equipo-acciones/${accionId}/evidencia`, {
            method: 'POST',
            body: form,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        });

        const data = await resp.json().catch(() => ({}));

        if (!resp.ok) {
            throw new Error(data.error || data.msg || `HTTP ${resp.status}`);
        }

        if (data.ok !== true) {
            throw new Error(data.error || data.msg || 'La evidencia no fue aceptada por el servidor.');
        }

        input.value = '';
        showToast('Evidencia subida correctamente');

        try {
            await window.recargarDetalleEquipoActual();
        } catch (errRecarga) {
            console.error('Error recargando detalle luego de subir evidencia:', errRecarga);
            showToast('La evidencia se subió, pero no se pudo refrescar el detalle.');
        }

    } catch (err) {
        console.error(err);
        alert('No se pudo subir la evidencia.');
    }
});







// Modal Validar Respuesta (Jefe)
document.querySelectorAll('.js-validar-respuesta').forEach(btn => {
    btn.addEventListener('click', () => {
        const tr = btn.closest('tr'); if (!tr) return;
        const impId = tr.dataset.imputacionId || '';
        document.getElementById('val-imp-id').value = impId;
        document.getElementById('val-reclamo-codigo').textContent = tr.dataset.codigo || '';
        document.getElementById('val-observacion').textContent = tr.dataset.observacion || '';
        document.getElementById('val-causa').textContent = tr.dataset.causa || '';
        document.getElementById('val-preventiva').textContent = tr.dataset.preventiva || '';
        document.getElementById('val-correctiva').textContent = tr.dataset.correctiva || '';
        document.getElementById('val-motivo-rechazo').value = '';
    });
});

document.getElementById('btnAprobarResp')?.addEventListener('click', async () => {
    const impId = document.getElementById('val-imp-id').value;
    try {
        const r = await withBusy(
            fetch(`/reclamos/imputacion/${impId}/validar_respuesta`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ accion: 'aprobar' })
            }),
            'Aprobando respuesta…'
        );
        if (!r.ok) throw new Error('HTTP ' + r.status);
        showToast?.('Respuesta aprobada');
        location.reload();
    } catch (err) {
        showToast?.('Error: ' + err.message);
    }
});

document.getElementById('btnRechazarResp')?.addEventListener('click', async () => {
    const impId = document.getElementById('val-imp-id').value;
    const motivo = document.getElementById('val-motivo-rechazo').value.trim();
    if (!motivo) {
        alert('Debe indicar motivo de rechazo');
        return;
    }
    const body = { accion: 'rechazar', motivo };
    try {
        const r = await withBusy(
            fetch(`/reclamos/imputacion/${impId}/validar_respuesta`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(body)
            }),
            'Rechazando respuesta…'
        );
        if (!r.ok) throw new Error('HTTP ' + r.status);
        showToast?.('Respuesta rechazada. Se notificará al imputado');
        location.reload();
    } catch (err) {
        showToast?.('Error: ' + err.message);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const formResponder = document.getElementById('formResponderMedidas');
    if (!formResponder) return;

    // evita doble binding
    if (formResponder.dataset.bound === '1') return;
    formResponder.dataset.bound = '1';

    const modalEl = document.getElementById('modalResponderMedidas');

    function normalizeDateInput(val) {
        val = (val || '').trim();
        if (!val) return '';

        if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return val;

        const m = val.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
        if (m) {
            const dd = String(m[1]).padStart(2, '0');
            const mm = String(m[2]).padStart(2, '0');
            const yy = m[3];
            return `${yy}-${mm}-${dd}`;
        }

        const d = new Date(val);
        if (!isNaN(d.getTime())) {
            const yy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            return `${yy}-${mm}-${dd}`;
        }

        return '';
    }

    const metodoInput = document.getElementById('resp-metodo');
    const bloque5Whys = document.getElementById('resp-bloque-5whys');
    const fishboneHelp = document.getElementById('fishbone-help');
    const metodoBtns = document.querySelectorAll('.js-metodo-btn');

    function setMetodo(metodo) {
        const m = (metodo || 'FISHBONE').toUpperCase();
        if (metodoInput) metodoInput.value = m;

        metodoBtns.forEach(btn => {
            const isActive = (btn.dataset.metodo || '').toUpperCase() === m;
            btn.classList.toggle('active', isActive);
        });

        if (bloque5Whys) bloque5Whys.classList.toggle('d-none', m !== '5WHYS');
        if (fishboneHelp) fishboneHelp.classList.toggle('d-none', m !== 'FISHBONE');
    }

    metodoBtns.forEach(btn => btn.addEventListener('click', () => setMetodo(btn.dataset.metodo)));
    window._setMetodoResponder = setMetodo;

    const btnAddCausa = document.getElementById('btn-add-causa');
    const btnAddControl = document.getElementById('btn-add-control');
    const btnAddCorrectiva = document.getElementById('btn-add-correctiva');

    btnAddCausa?.addEventListener('click', () => agregarAccion('causa'));
    btnAddControl?.addEventListener('click', () => agregarAccion('control'));
    btnAddCorrectiva?.addEventListener('click', () => agregarAccion('correctiva'));

    window.agregarAccion = function (tipo, data = {}) {
        const containerId = (
            tipo === 'causa'
                ? 'resp-lista-causas'
                : tipo === 'control'
                    ? 'resp-lista-control'
                    : 'resp-lista-correctiva'
        );

        const container = document.getElementById(containerId);
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'accion-row accion-card';

        row.innerHTML = `
        <div class="accion-card-top">
            <textarea class="form-control form-control-sm accion-text"
                rows="3"
                placeholder="Descripción">${data.descripcion || ''}</textarea>
        </div>

        <div class="accion-card-bottom">
            <div class="accion-fecha-wrap">
                <label class="form-label small text-muted mb-1">Fecha compromiso</label>
                <input type="date"
                    class="form-control form-control-sm accion-fecha"
                    value="${normalizeDateInput(data.fecha_compromiso || '')}">
            </div>

            <div class="accion-btn-wrap">
                <label class="form-label small text-muted mb-1 d-block">&nbsp;</label>
                <button type="button" class="btn btn-sm btn-outline-danger accion-remove">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
        </div>
    `;

        row.querySelector('.accion-remove')?.addEventListener('click', () => row.remove());
        container.appendChild(row);
    };

    function recogerAcciones(tipo) {
        const containerId = (
            tipo === 'causa'
                ? 'resp-lista-causas'
                : tipo === 'control'
                    ? 'resp-lista-control'
                    : 'resp-lista-correctiva'
        );

        const container = document.getElementById(containerId);
        if (!container) return [];

        const items = [];

        container.querySelectorAll('.accion-row').forEach(row => {
            const descripcion = (row.querySelector('.accion-text')?.value || '').trim();
            const fecha = (row.querySelector('.accion-fecha')?.value || '').trim();

            if (descripcion || fecha) {
                items.push({
                    descripcion: descripcion,
                    fecha_compromiso: fecha
                });
            }
        });

        return items;
    }


    // abrir modal
    document.addEventListener('click', async function (ev) {
        const btn = ev.target.closest('.js-responder-medidas');
        if (!btn) return;

        const tr = btn.closest('tr');
        if (!tr) return;

        const estadoGlobal = (
            tr.dataset.estadoGlobal ||
            tr.dataset.estado ||
            tr.dataset.estadoImputacion ||
            ''
        ).trim().toLowerCase();

        const esAdmin = String(tr.dataset.esAdmin || '0') === '1';

        if (!esAdmin && (estadoGlobal === 'cerrado' || estadoGlobal.includes('cerrad'))) {
            alert('Esta OM ya está cerrada. No se puede responder ni modificar la respuesta.');
            return;
        }

        const impId = (tr.dataset.imputacionId || '').trim();
        const reclamoId = (tr.dataset.reclamoId || '').trim();
        const esEquipo = (tr.dataset.soyEquipo === '1');

        if (esEquipo && (!impId || impId.toLowerCase() === 'none')) {
            alert('Error: esta OM no tiene imputación_id válido.');
            return;
        }


        formResponder.dataset.modo = esEquipo ? 'equipo' : 'responsable';
        const btnIA = document.getElementById('btnMejorarIA');
        if (btnIA) {
            btnIA.classList.remove('d-none');
            const badge = btnIA.querySelector('#ia-count-badge');
            btnIA.innerHTML = esEquipo
                ? `<i class="bi bi-stars me-1"></i>Sugerir respuesta`
                : `<i class="bi bi-stars me-1"></i>Mejorar con IA`;
            if (badge) {
                btnIA.appendChild(badge);
            }
        }

        document.getElementById('resp-imp-id').value = impId;
        window.actualizarEstadoBotonIA?.();
        document.getElementById('resp-reclamo-codigo').textContent = tr.dataset.codigo || '';

        // observación con fallback
        const obs =
            (tr.dataset.observacion || '').trim() ||
            (tr.querySelector('td[data-th="Observación"] .small-muted')?.textContent || '').trim() ||
            (tr.querySelector('td[data-th="Motivo / Observación"] .small-muted')?.textContent || '').trim() ||
            '';

        document.getElementById('resp-observacion').textContent = obs;

        const metodoFila = (tr.dataset.metodoAnalisis || 'FISHBONE').toUpperCase();
        setMetodo(metodoFila);

        const w1 = document.getElementById('resp-why1');
        if (w1) {
            w1.value = tr.dataset.why1 || '';
            document.getElementById('resp-why2').value = tr.dataset.why2 || '';
            document.getElementById('resp-why3').value = tr.dataset.why3 || '';
            document.getElementById('resp-why4').value = tr.dataset.why4 || '';
            document.getElementById('resp-why5').value = tr.dataset.why5 || '';
        }

        const fm = document.getElementById('resp-fish-metodo');
        if (fm) {
            fm.value = tr.dataset.fishMetodo || '';
            document.getElementById('resp-fish-maquinas').value = tr.dataset.fishMaquinas || '';
            document.getElementById('resp-fish-materiales').value = tr.dataset.fishMateriales || '';
            document.getElementById('resp-fish-personas').value = tr.dataset.fishPersonas || '';
            document.getElementById('resp-fish-entorno').value = tr.dataset.fishEntorno || '';
            document.getElementById('resp-fish-medicion').value = tr.dataset.fishMedicion || '';
        }

        const listaCausas = document.getElementById('resp-lista-causas');
        const listaControl = document.getElementById('resp-lista-control');
        const listaCorrectiva = document.getElementById('resp-lista-correctiva');

        if (listaCausas) listaCausas.innerHTML = '';
        if (listaControl) listaControl.innerHTML = '';
        if (listaCorrectiva) listaCorrectiva.innerHTML = '';

        function pintarAcciones(tipo, items) {
            if (!Array.isArray(items) || !items.length) return;

            items.forEach(item => {
                agregarAccion(tipo, {
                    descripcion: item.descripcion || '',
                    fecha_compromiso: item.fecha_compromiso || ''
                });
            });
        }

        try {
            if (esEquipo && impId) {
                const miembroId = tr.dataset.miembroId || tr.dataset.usuarioId || '';
                if (miembroId) {
                    const r = await fetch(
                        `/reclamos/${reclamoId}/equipo-respuestas/aporte?imputacion_id=${encodeURIComponent(impId)}&miembro_id=${encodeURIComponent(miembroId)}`,
                        { headers: { 'X-Requested-With': 'XMLHttpRequest' } }
                    );

                    const data = await r.json();
                    const item = data?.item || {};

                    pintarAcciones('causa', item.causas || []);
                    pintarAcciones('control', item.control || []);
                    pintarAcciones('correctiva', item.correctiva_items || []);
                    return;
                }
            }

            const causas = JSON.parse(tr.dataset.causasDetalle || '[]');
            const control = JSON.parse(tr.dataset.controlDetalle || '[]');
            const correctiva = JSON.parse(tr.dataset.correctivaDetalle || '[]');

            pintarAcciones('causa', causas);
            pintarAcciones('control', control);
            pintarAcciones('correctiva', correctiva);

        } catch (e) {
            console.warn('No se pudieron precargar acciones:', e);
        }
    });


    // submit
    formResponder.addEventListener('submit', async (ev) => {
        ev.preventDefault();

        const overlay = document.querySelector('#modalResponderMedidas #resp-loading');
        const msgEl = document.getElementById('resp-loading-msg');
        const btn = document.getElementById('btnEnviarRespuesta');

        overlay?.classList.remove('d-none');
        if (msgEl) msgEl.textContent = 'Guardando respuesta…';
        const unlock = lockButton(btn, 'Guardando…');

        try {
            const impId = (document.getElementById('resp-imp-id').value || '').trim();
            const modo = (formResponder.dataset.modo || 'responsable').toLowerCase();

            if (!impId) {
                alert('No se encontró imputacion_id.');
                return;
            }

            const url = (modo === 'equipo')
                ? `/reclamos/imputacion/${impId}/responder_equipo`
                : `/reclamos/imputacion/${impId}/responder`;

            const payload = {
                metodo_analisis: (document.getElementById('resp-metodo')?.value || 'FISHBONE'),
                causas: recogerAcciones('causa'),
                control: recogerAcciones('control'),
                correctiva: recogerAcciones('correctiva'),
                why1: (document.getElementById('resp-why1')?.value || '').trim(),
                why2: (document.getElementById('resp-why2')?.value || '').trim(),
                why3: (document.getElementById('resp-why3')?.value || '').trim(),
                why4: (document.getElementById('resp-why4')?.value || '').trim(),
                why5: (document.getElementById('resp-why5')?.value || '').trim(),
                fish_metodo: (document.getElementById('resp-fish-metodo')?.value || '').trim(),
                fish_maquinas: (document.getElementById('resp-fish-maquinas')?.value || '').trim(),
                fish_materiales: (document.getElementById('resp-fish-materiales')?.value || '').trim(),
                fish_personas: (document.getElementById('resp-fish-personas')?.value || '').trim(),
                fish_entorno: (document.getElementById('resp-fish-entorno')?.value || '').trim(),
                fish_medicion: (document.getElementById('resp-fish-medicion')?.value || '').trim(),
            };

            console.log('PAYLOAD RESPUESTA EQUIPO:', payload);

            if (!payload.causas.length || !payload.control.length || !payload.correctiva.length) {
                alert("Debe ingresar al menos una causa, una acción de control y una correctiva");
                return;
            }


            const csrfToken =
                document.querySelector('input[name="csrf_token"]')?.value ||
                document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                '';

            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            const ct = resp.headers.get('content-type') || '';
            const data = ct.includes('application/json') ? await resp.json() : {};

            if (!resp.ok || data.ok !== true) {
                alert((data && (data.error || data.msg)) || `No se pudo guardar (HTTP ${resp.status})`);
                return;
            }

            showToast?.('Respuesta guardada');
            bootstrap.Modal.getInstance(modalEl)?.hide();
            location.reload();

        } catch (err) {
            console.error(err);
            alert('Error al guardar la respuesta.');
        } finally {
            overlay?.classList.add('d-none');
            unlock();
        }
    });
});

(function () {
    const input = document.getElementById('recl-cliente-nombre');
    const hiddenId = document.getElementById('recl-cliente-id');
    const dl = document.getElementById('recl-dl-clientes');
    if (!input || !dl || !hiddenId) return;

    let timer = null;

    function cargarClientes(q) {
        const apiClientesUrl = getMetaUrl('api-clientes-url');
        if (!apiClientesUrl) return;
        const url = new URL(apiClientesUrl, window.location.origin);
        if (q) url.searchParams.set('q', q);
        fetch(url)
            .then(r => r.json())
            .then(data => {
                dl.innerHTML = '';
                (data.items || []).forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.nombre;
                    opt.dataset.id = c.id;
                    opt.label = c.identificacion ? `${c.nombre} (${c.identificacion})` : c.nombre;
                    dl.appendChild(opt);
                });
                syncClienteHidden();
            })
            .catch(console.error);
    }

    function syncClienteHidden() {
        const val = (input.value || '').trim().toLowerCase();
        hiddenId.value = '';
        if (!val) return;
        const match = Array.from(dl.options)
            .find(o => (o.value || '').trim().toLowerCase() === val);
        if (match) hiddenId.value = match.dataset.id || '';
    }

    input.addEventListener('input', function () {
        hiddenId.value = '';
        const q = input.value.trim();
        if (timer) clearTimeout(timer);
        if (q.length < 2) { dl.innerHTML = ''; return; }
        timer = setTimeout(() => cargarClientes(q), 250);
        syncClienteHidden();
    });

    input.addEventListener('change', syncClienteHidden);
    input.addEventListener('blur', syncClienteHidden);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') syncClienteHidden(); });
})();

(function () {
    const tipoSel = document.getElementById('recl-tipo-reclamo');
    if (!tipoSel) return;

    const sections = {
        proceso: document.querySelectorAll('.field-proceso'),
        fechaPedido: document.querySelectorAll('.field-fecha-pedido'),
        fechaOfrec: document.querySelectorAll('.field-fecha-ofrec'),
        fechaEntrega: document.querySelectorAll('.field-fecha-entrega'),
        material: document.querySelectorAll('.field-material'),

        colaborador: document.querySelectorAll('.field-colaborador'),
        facturaGuia: document.querySelectorAll('.field-factura-guia'),
        observacion: document.querySelectorAll('.field-observacion'),
    };

    function setVisible(nodeList, show) {
        nodeList.forEach(el => {
            if (!el) return;
            el.classList.toggle('d-none', !show);
        });
    }

    function updateCampos() {
        const opt = tipoSel.options[tipoSel.selectedIndex];
        if (!opt) return;

        const flags = {
            proceso: opt.dataset.usaProceso === '1',
            fechaPedido: opt.dataset.usaFechaPedido === '1',
            fechaOfrec: opt.dataset.usaFechaOfrec === '1',
            fechaEntrega: opt.dataset.usaFechaEntrega === '1',
            material: opt.dataset.usaMaterial === '1',
            colaborador: opt.dataset.usaColaborador === '1',
            facturaGuia: opt.dataset.usaFacturaGuia === '1',
            observacion: opt.dataset.usaObservacion === '1',
        };

        for (const k in sections) {
            setVisible(sections[k], !!flags[k]);
        }
    }

    tipoSel.addEventListener('change', updateCampos);
    updateCampos();
})();

document.addEventListener('DOMContentLoaded', function () {
    const selRegion = document.getElementById('recl-region');
    const selProv = document.getElementById('recl-provincia');
    const selCanton = document.getElementById('recl-canton');

    if (!selRegion || !selProv || !selCanton) return;

    function resetSelect(select, placeholder) {
        select.innerHTML = '';
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = placeholder;
        select.appendChild(opt);
    }

    function fillSelect(select, items, placeholder) {
        resetSelect(select, placeholder);
        items.forEach(it => {
            const o = document.createElement('option');
            o.value = it.id;
            o.textContent = it.nombre;
            select.appendChild(o);
        });
    }
    function recogerAcciones(tipo) {
        const containerId = (
            tipo === 'causa'
                ? 'resp-lista-causas'
                : tipo === 'control'
                    ? 'resp-lista-control'
                    : 'resp-lista-correctiva'
        );

        const container = document.getElementById(containerId);
        if (!container) return [];

        const items = [];

        container.querySelectorAll('.accion-row').forEach(row => {
            const descripcion = (row.querySelector('.accion-text')?.value || '').trim();
            const fecha = (row.querySelector('.accion-fecha')?.value || '').trim();

            if (descripcion || fecha) {
                items.push({
                    descripcion: descripcion,
                    fecha_compromiso: fecha
                });
            }
        });

        return items;
    }


    selRegion.addEventListener('change', async function () {
        const rid = this.value;
        resetSelect(selProv, '— Provincia —');
        resetSelect(selCanton, '— Cantón / Ciudad —');
        if (!rid) return;

        try {
            const apiProvinciasUrl = getMetaUrl('api-provincias-url');
            if (!apiProvinciasUrl) return;
            const url = apiProvinciasUrl + '?region_id=' + encodeURIComponent(rid);
            const resp = await fetch(url);
            const data = await resp.json();
            fillSelect(selProv, data, '— Provincia —');
        } catch (err) {
            console.error('Error cargando provincias', err);
        }
    });

    selProv.addEventListener('change', async function () {
        const pid = this.value;
        resetSelect(selCanton, '— Cantón / Ciudad —');
        if (!pid) return;

        try {
            const apiCantonesUrl = getMetaUrl('api-cantones-url');
            if (!apiCantonesUrl) return;
            const url = apiCantonesUrl + '?provincia_id=' + encodeURIComponent(pid);
            const resp = await fetch(url);
            const data = await resp.json();
            fillSelect(selCanton, data, '— Cantón / Ciudad —');
        } catch (err) {
            console.error('Error cargando cantones', err);
        }
    });
});

(function () {
    const input = document.getElementById('recl-imputado-search');
    const dl = document.getElementById('recl-dl-usuarios');
    const chips = document.getElementById('recl-imputados-chips');
    const info = document.getElementById('recl-imputado-info');
    const form = document.getElementById('formNuevoReclamo');
    if (!input || !dl || !chips || !form) return;

    const selected = new Map();

    function updateInfo(label, depto, jefe) {
        if (!info) return;
        if (!label) {
            info.textContent = '';
            return;
        }
        let txt = `Último imputado: ${label}`;
        if (depto) txt += ` • Depto: ${depto}`;
        if (jefe) txt += ` • Jefe: ${jefe}`;
        info.textContent = txt;
    }

    /**
     * locked = true  => chip SIN botón de cerrar (no se puede quitar)
     */
    function addUser(id, label, depto, jefe, locked = false) {
        if (!id) return;

        // si ya está seleccionado y es el mismo, no duplicar
        if (selected.has(id)) return;
        selected.set(id, label);

        const chip = document.createElement('span');
        chip.className = 'badge bg-primary me-1 mb-1 d-inline-flex align-items-center';
        chip.dataset.id = id;
        if (locked) chip.dataset.locked = '1';

        chip.title = [
            depto ? `Departamento: ${depto}` : '',
            jefe ? `Jefe: ${jefe}` : ''
        ].filter(Boolean).join(' | ');

        chip.innerHTML = `
  <div class="d-flex flex-column">
    <span>${label}</span>
    <small class="ms-1">
      ${depto ? depto : ''}${jefe ? ' · Jefe: ' + jefe : ''}
    </small>
  </div>
  ${locked ? '' : '<button type="button" class="btn-close btn-close-white btn-sm ms-2" aria-label="Quitar"></button>'}
`;
        chips.appendChild(chip);

        // hidden para enviar al backend
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'imputados[]';
        hidden.value = id;
        hidden.dataset.id = id;
        form.appendChild(hidden);

        updateInfo(label, depto, jefe);
    }

    // 🔒 Permitir que otros scripts agreguen un sponsor automáticamente y lo bloqueen
    // Quita sponsors automáticos asociados a un proceso (por su "cedula key")
    window._omRemoveAutoSponsorByKey = function (key) {
        if (!key) return;

        // recorrer chips automáticos y quitar los que tengan esta key
        chips.querySelectorAll('.badge[data-auto="1"]').forEach(chip => {
            const keys = (chip.dataset.autoKeys || '').split('|').filter(Boolean);
            const newKeys = keys.filter(k => k !== key);

            // actualizar keys
            chip.dataset.autoKeys = newKeys.join('|');

            // si ya no tiene keys auto, se elimina completo (chip + hidden + selected)
            if (newKeys.length === 0) {
                const id = chip.dataset.id;
                selected.delete(id);
                chip.remove();
                form.querySelectorAll(
                    'input[type="hidden"][name="imputados[]"][data-id="' + id + '"]'
                ).forEach(el => el.remove());
            }
        });
    };

    // Agrega sponsor automático (sin borrar los manuales, sin bloquear input)
    window.agregarImputadoDesdeProceso = function (user, key) {
        if (!user) return;

        const id = String(user.id || '').trim();
        const nombre = user.nombre || user.username || '';
        const depto = user.departamento || '';
        const jefe = user.jefe || '';

        if (!id) return;

        // Si ya existe chip de ese usuario, solo agregamos la key a sus autoKeys
        const existing = chips.querySelector('.badge[data-id="' + id + '"]');
        if (existing) {
            const keys = (existing.dataset.autoKeys || '').split('|').filter(Boolean);
            if (key && !keys.includes(key)) keys.push(key);
            existing.dataset.auto = '1';
            existing.dataset.autoKeys = keys.join('|');
            return;
        }

        // Si no existe, lo creamos como AUTO (sin botón de quitar)
        addUser(id, nombre, depto, jefe, true);

        const chip = chips.querySelector('.badge[data-id="' + id + '"]');
        if (chip) {
            chip.dataset.auto = '1';
            chip.dataset.autoKeys = key ? String(key) : '';
        }

        // OJO: ya NO bloqueamos el input, así pueden agregar sponsors manuales también
        input.readOnly = false;
        input.classList.remove('bg-light');
    };

    // Eliminar chips SOLO si NO están bloqueados
    chips.addEventListener('click', function (e) {
        if (!e.target.classList.contains('btn-close')) return;
        const chip = e.target.closest('.badge[data-id]');
        if (!chip) return;

        // si es chip bloqueado (auto por proceso), no hacemos nada
        if (chip.dataset.locked === '1') return;

        const id = chip.dataset.id;
        selected.delete(id);
        chip.remove();

        form.querySelectorAll(
            'input[type="hidden"][name="imputados[]"][data-id="' + id + '"]'
        ).forEach(el => el.remove());

        if (!chips.querySelector('.badge[data-id]')) {
            updateInfo('', '', '');
        }
    });

    // Selección manual de sponsor (solo se usará mientras el input NO esté readOnly)
    function handleSelect() {
        if (input.readOnly || input.disabled) return; // por seguridad

        const text = input.value.trim();
        if (!text) return;

        const opt = Array.from(dl.options).find(o => o.value === text);
        if (!opt) return;

        const id = opt.dataset.id;
        const label = opt.value;
        const depto = opt.dataset.depto || '';
        const jefe = opt.dataset.jefe || '';
        if (!id) return;

        addUser(id, label, depto, jefe, false);
        input.value = '';
    }

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSelect();
        }
    });

    input.addEventListener('change', handleSelect);
})();

// Ventanita de procesando
const Busy = (() => {
    let modal, el, msgEl;
    function ensure() {
        el = el || document.getElementById('busyModal');
        if (!el) return null;
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
        hide() { try { modal?.hide(); } catch (e) { } }
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
    return () => { btn.disabled = false; btn.innerHTML = html; };
}

(function () {
    const form = document.getElementById('formNuevoMaterial');
    const modalEl = document.getElementById('modalNuevoMaterial');
    const selMat = document.getElementById('recl-material');
    if (!form || !modalEl || !selMat) return;

    form.addEventListener('submit', async function (ev) {
        ev.preventDefault();

        const fd = new FormData(form);
        const nombre = (fd.get('nombre') || '').trim();
        if (!nombre) {
            alert('El nombre del material es obligatorio');
            return;
        }

        try {
            const apiMaterialesNuevoUrl = getMetaUrl('api-materiales-nuevo-url');
            if (!apiMaterialesNuevoUrl) {
                alert('No se encontró la URL para crear material');
                return;
            }

            const resp = await fetch(apiMaterialesNuevoUrl, {
                method: 'POST',
                body: fd
            });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                alert(data.msg || 'Error al crear material');
                return;
            }

            const opt = document.createElement('option');
            opt.value = data.item.id;
            opt.textContent = data.item.nombre;
            selMat.appendChild(opt);
            selMat.value = data.item.id;

            form.reset();
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) bsModal.hide();
            if (typeof showToast === 'function') {
                showToast('Material creado correctamente');
            }
        } catch (err) {
            console.error(err);
            alert('Error al crear material');
        }
    });
})();

let currentReclamoId = null;

function cargarAdjuntosDetalle() {
    const hiddenId = document.getElementById('det-reclamo-id');
    if (!hiddenId) return;

    currentReclamoId = hiddenId.value;
    if (!currentReclamoId) return;

    const tbody = document.getElementById('det-adjuntos-body');
    if (!tbody) return;

    tbody.innerHTML = `
        <tr>
          <td colspan="5" class="text-muted small">Cargando adjuntos...</td>
        </tr>
    `;

    fetch(`/reclamos/api/${currentReclamoId}/adjuntos`)
        .then(r => r.json())
        .then(data => {
            tbody.innerHTML = '';
            const items = data.items || [];

            if (!items.length) {
                tbody.innerHTML = `
                <tr>
                  <td colspan="5" class="text-muted small">Sin adjuntos.</td>
                </tr>
              `;
                return;
            }

            items.forEach(it => {
                const tr = document.createElement('tr');
                const sizeKb = it.size_bytes
                    ? (it.size_bytes / 1024).toFixed(1) + ' KB'
                    : '';

                tr.innerHTML = `
                <td>
                  <a href="/reclamos/adjunto/${it.id}/download">
                    ${it.original_name}
                  </a>
                </td>
                <td>${sizeKb}</td>
                <td>${it.created_at || ''}</td>
                <td>${it.creado_por || ''}</td>
                <td class="text-end">
                  <button type="button"
                          class="btn btn-sm btn-link text-danger p-0"
                          data-adj-id="${it.id}">
                    <i class="bi bi-trash"></i>
                  </button>
                </td>
              `;
                tbody.appendChild(tr);
            });
        })
        .catch(err => {
            console.error(err);
            tbody.innerHTML = `
            <tr>
              <td colspan="5" class="text-danger small">
                Error al cargar adjuntos.
              </td>
            </tr>
          `;
        });
}

document.addEventListener('click', async function (ev) {
    const btn = ev.target.closest('#btn-det-subir-adjuntos');
    if (!btn) return;

    ev.preventDefault();

    const hiddenId = document.getElementById('det-reclamo-id');
    const input = document.getElementById('det-adjuntos-input');

    if (!hiddenId || !input) return;

    const reclamoId = hiddenId.value;
    if (!reclamoId) {
        alert('No se pudo determinar el ID de la OM.');
        return;
    }

    if (!input.files.length) {
        alert('Seleccione al menos un archivo.');
        return;
    }

    const formData = new FormData();
    for (const file of input.files) {
        formData.append('adjuntos', file);
    }

    try {
        const resp = await withBusy(
            fetch(`/reclamos/${reclamoId}/adjuntos`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            }),
            'Subiendo adjuntos…'
        );

        const data = await resp.json();

        if (!resp.ok || !data.ok) {
            alert(data.msg || 'Error al subir adjuntos.');
            return;
        }

        input.value = '';
        cargarAdjuntosDetalle();
        if (typeof showToast === 'function') {
            showToast('Adjuntos subidos correctamente');
        }
    } catch (err) {
        console.error(err);
        alert('Error al subir adjuntos.');
    }
});

document.addEventListener('click', async function (ev) {
    const btn = ev.target.closest('button[data-adj-id]');
    if (!btn) return;

    const adjId = btn.getAttribute('data-adj-id');
    if (!adjId) return;

    if (!confirm('¿Desea eliminar este adjunto?')) return;

    try {
        const resp = await withBusy(
            fetch(`/reclamos/adjunto/${adjId}/delete`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            }),
            'Eliminando adjunto…'
        );
        const data = await resp.json();

        if (!resp.ok || !data.ok) {
            alert(data.msg || 'No se pudo eliminar el archivo.');
            return;
        }
        cargarAdjuntosDetalle();
        showToast?.('Adjunto eliminado');
    } catch (err) {
        console.error(err);
        alert('Error al eliminar el archivo.');
    }
});

(function () {
    const input = document.getElementById('recl-persona-nombre');
    const hidden = document.getElementById('recl-persona-id');
    const dl = document.getElementById('recl-dl-persona');
    const info = document.getElementById('recl-persona-info');

    if (!input || !hidden || !dl) return;

    function syncPersona() {
        const val = (input.value || '').trim().toLowerCase();
        hidden.value = '';
        if (info) info.textContent = '';

        if (!val) return;

        const opt = Array.from(dl.options).find(o =>
            (o.value || '').trim().toLowerCase() === val
        );
        if (!opt) return;

        hidden.value = opt.dataset.id || '';

        const depto = opt.dataset.depto || '';
        const jefe = opt.dataset.jefe || '';
        let txt = opt.value;
        if (depto) txt += ` • Depto: ${depto}`;
        if (jefe) txt += ` • Jefe: ${jefe}`;
        if (info) info.textContent = txt;
    }

    input.addEventListener('input', () => {
        hidden.value = '';
        if (info) info.textContent = '';
    });

    input.addEventListener('change', syncPersona);
    input.addEventListener('blur', syncPersona);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            syncPersona();
        }
    });
})();

(function () {
    const modalEl = document.getElementById('modalEquipoRespuestas');
    if (!modalEl) return;

    const reclamoIdInput = document.getElementById('eq-reclamo-id');
    const imputacionIdInput = document.getElementById('eq-imputacion-id');
    const tituloCodigoEl = document.getElementById('eq-titulo-codigo');
    const usuarioSelect = document.getElementById('eq-usuario-id');
    const tablaEquipo = document.getElementById('tabla-equipo-respuestas');
    const tbodyEquipo = document.getElementById('equipo-respuestas-body');

    function setTablaMensaje(msg) {
        if (!tbodyEquipo) return;
        tbodyEquipo.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center small text-muted py-3">${msg}</td>
                </tr>`;
    }

    // =========================
    // Cargar equipo desde backend
    // =========================
    function cargarEquipoRespuestas(reclamoId) {
        if (!tbodyEquipo) return;

        const impId = (imputacionIdInput?.value || '').trim();
        const url = impId
            ? `/reclamos/${reclamoId}/equipo-respuestas/json?imputacion_id=${encodeURIComponent(impId)}`
            : `/reclamos/${reclamoId}/equipo-respuestas/json`;

        fetch(url, {
            method: "GET",
            headers: {
                "Accept": "application/json",
                'X-CSRFToken': csrfToken,
                "X-Requested-With": "XMLHttpRequest"
            },
            credentials: "same-origin"
        })
            .then(r => {
                if (!r.ok) throw new Error('Error al cargar el equipo (HTTP ' + r.status + ')');
                return r.json();
            })
            .then(data => {
                const items = Array.isArray(data) ? data : (data && data.items ? data.items : []);
                tbodyEquipo.innerHTML = '';

                if (!items.length) {
                    setTablaMensaje('Aún no has agregado miembros al equipo para este reclamo.');
                    return;
                }

                items.forEach(mi => {
                    const tr = document.createElement('tr');

                    const tdUsuario = document.createElement('td');
                    tdUsuario.textContent = mi.nombre || '(Sin nombre)';

                    const tdRolArea = document.createElement('td');
                    const rol = mi.rol || '';
                    const dep = mi.departamento || '';
                    tdRolArea.textContent = (rol && dep) ? `${rol} / ${dep}` : (rol || dep || '');

                    const tdPuede = document.createElement('td');
                    tdPuede.textContent = mi.puede_responder ? 'Sí' : 'No';

                    const tdAcciones = document.createElement('td');
                    tdAcciones.className = 'text-end';

                    const disabled = (mi.tiene_respuesta === 0 || mi.tiene_respuesta === false) ? 'disabled' : '';

                    tdAcciones.innerHTML = `
                            <button type="button"
                                    class="btn btn-sm btn-outline-secondary me-1 js-eq-ver-aporte"
                                    data-equipo-id="${mi.id ?? mi.equipo_id ?? ''}"
                                    data-usuario-id="${mi.usuario_id ?? mi.miembro_id ?? ''}"
                                    data-miembro-nombre="${(mi.nombre || '').replace(/"/g, '&quot;')}"
                                    ${disabled}
                                    title="Ver aporte">
                                <i class="bi bi-eye"></i>
                            </button>

                            <button type="button"
                                    class="btn btn-sm btn-outline-danger js-eq-eliminar"
                                    data-equipo-id="${mi.id ?? mi.equipo_id ?? ''}">
                                Quitar
                            </button>
                        `;

                    tr.appendChild(tdUsuario);
                    tr.appendChild(tdRolArea);
                    tr.appendChild(tdPuede);
                    tr.appendChild(tdAcciones);
                    tbodyEquipo.appendChild(tr);
                });
            })
            .catch(err => {
                console.error('Error cargando equipo:', err);
                setTablaMensaje('Error al cargar el equipo.');
            });
    }

    // =========================
    // Abrir modal desde tabla sponsor
    // =========================
    document.addEventListener('click', function (ev) {
        const btn = ev.target.closest('.js-equipo-respuestas');
        if (!btn) return;

        const tr = btn.closest('tr');
        if (!tr) return;

        const estadoGlobal = (
            tr.dataset.estadoGlobal ||
            tr.dataset.estado ||
            tr.dataset.estadoImputacion ||
            ''
        ).trim().toLowerCase();

        const esAdmin = String(tr.dataset.esAdmin || '0') === '1';

        if (!esAdmin && (estadoGlobal === 'cerrado' || estadoGlobal.includes('cerrad'))) {
            alert('Esta OM ya está cerrada. No se puede gestionar el equipo de respuestas.');
            return;
        }

        const reclamoId = tr.dataset.reclamoId;
        const imputacionId = tr.dataset.imputacionId;
        const codigo = tr.dataset.codigo || '';

        reclamoIdInput.value = reclamoId || '';
        imputacionIdInput.value = imputacionId || '';
        tituloCodigoEl.textContent = codigo;

        if (usuarioSelect) usuarioSelect.value = '';

        if (reclamoId) {
            cargarEquipoRespuestas(reclamoId);
        } else {
            setTablaMensaje('No se pudo identificar el reclamo.');
        }
    });

    // =========================
    // Agregar miembro
    // =========================
    const btnAgregarEquipo = document.getElementById('btn-eq-agregar');

    btnAgregarEquipo?.addEventListener('click', () => {
        if (btnAgregarEquipo.disabled) return;

        const reclamoId = document.getElementById('eq-reclamo-id')?.value;
        const imputacionId = document.getElementById('eq-imputacion-id')?.value;
        const usuarioId = document.getElementById('eq-usuario-id')?.value;

        if (!reclamoId || !imputacionId || !usuarioId) {
            alert('Seleccione un usuario válido.');
            return;
        }

        bloquearBtn(btnAgregarEquipo, 'Agregando...');

        fetch(`/reclamos/${reclamoId}/equipo-respuestas/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                imputacion_id: imputacionId,
                usuario_id: usuarioId
            })
        })
            .then(r => r.json())
            .then(resp => {
                if (!resp.ok) {
                    throw new Error(resp.msg || 'Error al agregar miembro');
                }

                document.getElementById('eq-usuario-id').value = '';
                cargarEquipoRespuestas(reclamoId);
            })
            .catch(err => {
                console.error(err);
                alert(err.message || 'No se pudo agregar el miembro.');
            })
            .finally(() => {
                desbloquearBtn(btnAgregarEquipo);
            });
    });

    // =========================
    // Ver aporte / eliminar miembro
    // =========================
    if (tablaEquipo) {
        tablaEquipo.addEventListener('click', async function (ev) {

            // -------- VER APORTE ----------
            const btnVer = ev.target.closest('.js-eq-ver-aporte');
            if (btnVer) {
                const miembroId = btnVer.dataset.usuarioId;
                const miembroNombre = btnVer.dataset.miembroNombre || '';
                const reclamoId = reclamoIdInput.value;
                const imputacionId = imputacionIdInput.value;

                if (!reclamoId || !imputacionId || !miembroId) {
                    alert('No se pudo determinar reclamo_id / imputacion_id / miembro_id.');
                    return;
                }

                const url = `/reclamos/${reclamoId}/equipo-respuestas/aporte?imputacion_id=${encodeURIComponent(imputacionId)}&miembro_id=${encodeURIComponent(miembroId)}`;

                try {
                    const resp = await fetch(url, {
                        method: "GET",
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            'X-CSRFToken': csrfToken,
                            "Accept": "application/json"
                        },
                        credentials: "same-origin"
                    });

                    if (!resp.ok) {
                        const t = await resp.text();
                        console.error("Aporte error:", resp.status, t);
                        alert("Error al cargar el aporte.");
                        return;
                    }

                    const data = await resp.json().catch(() => ({}));

                    if (!data.ok) {
                        alert(data.error || 'No se pudo cargar el aporte.');
                        return;
                    }

                    if (!data.item) {
                        alert('Este miembro aún no ha registrado un aporte.');
                        return;
                    }

                    const it = data.item;
                    const modalAporte = document.getElementById('modalAporteEquipo');

                    if (modalAporte) {
                        modalAporte.dataset.reclamoId = String(reclamoId || '');
                        modalAporte.dataset.imputacionId = String(imputacionId || '');
                        modalAporte.dataset.miembroId = String(miembroId || '');
                        modalAporte.dataset.miembroNombre = String(miembroNombre || '');
                        window.__ap_last_item = it;
                    }

                    apPintarAporteEquipo(it);

                    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalAporteEquipo')).show();

                } catch (err) {
                    console.error(err);
                    alert('Error al cargar el aporte.');
                }
                return;
            }

            // -------- ELIMINAR MIEMBRO ----------
            const btnDel = ev.target.closest('.js-eq-eliminar');
            if (!btnDel) return;

            const equipoId = btnDel.dataset.equipoId;
            const reclamoId = reclamoIdInput.value;

            if (!equipoId || !reclamoId) return;

            if (!confirm('¿Quitar a este miembro del equipo para este reclamo?')) return;

            fetch(`/reclamos/${reclamoId}/equipo-respuestas/${equipoId}/eliminar`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json'
                },
                credentials: 'same-origin'
            })
                .then(async (r) => {
                    const ct = r.headers.get('content-type') || '';
                    const data = ct.includes('application/json') ? await r.json() : {};

                    if (!r.ok || (data && data.ok === false) || (data && data.error)) {
                        alert((data && (data.error || data.msg)) || 'No se pudo eliminar el miembro.');
                        return;
                    }

                    cargarEquipoRespuestas(reclamoId);
                })
                .catch(err => {
                    console.error(err);
                    alert('No se pudo eliminar el miembro. Intenta nuevamente.');
                });
        });
    }

})();

// =========================
// Helpers visuales modal aporte
// =========================
function apFmtDMY(s) {
    if (!s) return '';
    const t = String(s).trim();
    if (t.length >= 10 && t[4] === '-' && t[7] === '-') {
        const y = t.slice(0, 4), m = t.slice(5, 7), d = t.slice(8, 10);
        return `${d}/${m}/${y}`;
    }
    return t;
}

function apEscapeHtml(str) {
    return String(str || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", "&#039;");
}

function apBuildEvidenciaDownloadUrl(ev) {
    if (!ev) return '#';
    if (ev.download_url) return ev.download_url;
    if (ev.id) return `/reclamos/equipo-acciones/evidencias/${encodeURIComponent(ev.id)}/download`;
    return '#';
}

function apRenderDetalleLista(elId, lista) {
    const el = document.getElementById(elId);
    if (!el) return;

    if (!Array.isArray(lista) || !lista.length) {
        el.innerHTML = '<span class="text-muted">—</span>';
        return;
    }

    el.innerHTML = lista.map(x => {
        const desc = apEscapeHtml(x.descripcion || '');
        const fecha = x.fecha_compromiso ? ` <span class="text-muted">(${apFmtDMY(x.fecha_compromiso)})</span>` : '';
        return `<div class="mb-1">• ${desc}${fecha}</div>`;
    }).join('');
}

function apRenderEvidenciasHtml(evidencias) {
    if (!Array.isArray(evidencias) || !evidencias.length) {
        return `<div class="small text-muted mt-2">Sin evidencias.</div>`;
    }

    return `
            <ul class="det-seg-evid-list small mb-0">
                ${evidencias.map(ev => `
                    <li class="d-flex align-items-center gap-2 flex-wrap">
                        <a href="${apBuildEvidenciaDownloadUrl(ev)}"
                           class="link-primary text-decoration-none"
                           target="_blank"
                           rel="noopener">
                            <i class="bi bi-paperclip me-1"></i>${apEscapeHtml(ev.original_name || ev.filename || 'Archivo')}
                        </a>
                        ${ev.created_at ? `<span class="text-muted">(${apEscapeHtml(ev.created_at)})</span>` : ''}
                    </li>
                `).join('')}
            </ul>
        `;
}

function apBadgeTipoAccion(tipo) {
    const t = String(tipo || '').toUpperCase();
    if (t === 'CORRECTIVA') {
        return `<span class="det-badge-soft det-badge-correctiva">Correctiva</span>`;
    }
    return `<span class="det-badge-soft det-badge-control">Control</span>`;
}

function apBadgeEstadoAccion(cumplido) {
    return Number(cumplido || 0) === 1
        ? `<span class="det-badge-soft det-badge-cumplido">Cumplido</span>`
        : `<span class="det-badge-soft det-badge-pendiente">Pendiente</span>`;
}

function apRenderSeguimientoAcciones(items) {
    const wrap = document.getElementById('ap-seguimiento-acciones-list');
    if (!wrap) return;

    if (!Array.isArray(items) || !items.length) {
        wrap.innerHTML = `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
        return;
    }

    wrap.innerHTML = items.map(x => {
        const tipo = String(x.tipo || '').toUpperCase();
        const soloSeguimiento = (tipo === 'CONTROL' || tipo === 'CORRECTIVA');
        if (!soloSeguimiento) return '';

        const requiereEvidencia = Number(x.requiere_evidencia || 0) === 1;
        const observacion = x.observacion_cumplimiento || '';

        return `
                <div class="det-seg-card mb-2">
                    <div class="det-seg-top">
                        <div class="flex-grow-1">
                            <div class="mb-1">${apBadgeTipoAccion(tipo)}</div>

                            <div class="det-seg-desc">${apEscapeHtml(x.descripcion || '')}</div>

                            <div class="det-seg-meta mt-1">
                                Fecha compromiso: ${x.fecha_compromiso ? apFmtDMY(x.fecha_compromiso) : '—'}
                            </div>

                            <div class="det-seg-meta">
                                Fecha cumplimiento: ${x.fecha_cumplimiento ? apFmtDMY(x.fecha_cumplimiento) : '—'}
                            </div>

                            <div class="mt-2">
                                ${apBadgeEstadoAccion(x.cumplido)}
                                ${requiereEvidencia ? `<span class="badge bg-light text-dark border ms-2">Requiere evidencia</span>` : ''}
                            </div>

                            <div class="mt-2">
                                <div class="small fw-semibold">Observación</div>
                                <div class="small text-muted ws-pre-wrap">${apEscapeHtml(observacion || '—')}</div>
                            </div>

                            <div class="mt-3">
                                ${apRenderEvidenciasHtml(x.evidencias || [])}
                            </div>
                        </div>
                    </div>
                </div>
            `;
    }).filter(Boolean).join('') || `<div class="text-muted small">Sin acciones de seguimiento.</div>`;
}

function apPintarMetodologia(it) {
    const metodo = String(it?.metodo_analisis || 'FISHBONE').toUpperCase();

    document.getElementById('ap-metodo-badge-fish')?.classList.toggle('text-bg-primary', metodo === 'FISHBONE');
    document.getElementById('ap-metodo-badge-fish')?.classList.toggle('text-bg-light', metodo !== 'FISHBONE');
    document.getElementById('ap-metodo-badge-why')?.classList.toggle('text-bg-primary', metodo === '5WHYS');
    document.getElementById('ap-metodo-badge-why')?.classList.toggle('text-bg-light', metodo !== '5WHYS');

    document.getElementById('ap-fish-wrap')?.classList.toggle('d-none', metodo !== 'FISHBONE');
    document.getElementById('ap-why-wrap')?.classList.toggle('d-none', metodo !== '5WHYS');

    const setVal = (id, v) => {
        const el = document.getElementById(id);
        if (el) el.value = v || '';
    };

    setVal('ap-why1', it?.why1);
    setVal('ap-why2', it?.why2);
    setVal('ap-why3', it?.why3);
    setVal('ap-why4', it?.why4);
    setVal('ap-why5', it?.why5);

    setVal('ap-fish-metodo', it?.fish_metodo);
    setVal('ap-fish-maquinas', it?.fish_maquinas);
    setVal('ap-fish-materiales', it?.fish_materiales);
    setVal('ap-fish-personas', it?.fish_personas);
    setVal('ap-fish-entorno', it?.fish_entorno);
    setVal('ap-fish-medicion', it?.fish_medicion);
}

function apPintarAporteEquipo(it) {
    document.getElementById('ap-miembro').textContent = it?.miembro_nombre || it?.miembro_username || '';

    apPintarMetodologia(it);

    apRenderDetalleLista('ap-causa', it?.causas || []);
    apRenderDetalleLista('ap-prev', it?.control || []);
    apRenderDetalleLista('ap-corr', it?.correctiva_items || []);

    const accionesSeguimiento = [
        ...(Array.isArray(it?.control) ? it.control : []),
        ...(Array.isArray(it?.correctiva_items) ? it.correctiva_items : [])
    ];
    apRenderSeguimientoAcciones(accionesSeguimiento);
}


window.cargarAccionesEnModal = function (it) {
    const listaCausas = document.getElementById('resp-lista-causas');
    const listaControl = document.getElementById('resp-lista-control');
    const listaCorrectiva = document.getElementById('resp-lista-correctiva');

    if (listaCausas) listaCausas.innerHTML = '';
    if (listaControl) listaControl.innerHTML = '';
    if (listaCorrectiva) listaCorrectiva.innerHTML = '';

    function pintar(tipo, items) {
        if (!Array.isArray(items) || !items.length) return;

        items.forEach(item => {
            if (typeof agregarAccion === 'function') {
                agregarAccion(tipo, {
                    descripcion: item.descripcion || '',
                    fecha_compromiso: item.fecha_compromiso || ''
                });
            }
        });
    }

    pintar('causa', it?.causas || []);
    pintar('control', it?.control || []);
    pintar('correctiva', it?.correctiva_items || []);

    if (listaCausas && !listaCausas.children.length && typeof agregarAccion === 'function') {
        agregarAccion('causa');
    }
    if (listaControl && !listaControl.children.length && typeof agregarAccion === 'function') {
        agregarAccion('control');
    }
    if (listaCorrectiva && !listaCorrectiva.children.length && typeof agregarAccion === 'function') {
        agregarAccion('correctiva');
    }
};

// =========================
// Aprobar / rechazar aporte y copiar a respuesta final
// =========================
(function () {
    const btnAprobar = document.getElementById('btn-ap-aprobar');
    const btnRechazar = document.getElementById('btn-ap-rechazar');
    const modalAporte = document.getElementById('modalAporteEquipo');

    if (!btnAprobar || !btnRechazar || !modalAporte) return;

    function setMetodoEnResponder(metodo) {
        const m = (metodo || 'FISHBONE').toUpperCase();
        const btn = document.querySelector(`#modalResponderMedidas .js-metodo-btn[data-metodo="${m}"]`);
        if (btn) btn.click();
        const hidden = document.getElementById('resp-metodo');
        if (hidden) hidden.value = m || 'FISHBONE';
    }

    function copiarAResponderMedidas(it) {
        setMetodoEnResponder(it.metodo_analisis || 'FISHBONE');

        const setVal = (id, v) => {
            const el = document.getElementById(id);
            if (el) el.value = v || '';
        };

        if (typeof cargarAccionesEnModal === 'function') {
            cargarAccionesEnModal(it);
        }

        setVal('resp-why1', it.why1);
        setVal('resp-why2', it.why2);
        setVal('resp-why3', it.why3);
        setVal('resp-why4', it.why4);
        setVal('resp-why5', it.why5);

        setVal('resp-fish-metodo', it.fish_metodo);
        setVal('resp-fish-maquinas', it.fish_maquinas);
        setVal('resp-fish-materiales', it.fish_materiales);
        setVal('resp-fish-personas', it.fish_personas);
        setVal('resp-fish-entorno', it.fish_entorno);
        setVal('resp-fish-medicion', it.fish_medicion);
    }

    btnAprobar.addEventListener('click', async () => {
        const it = window.__ap_last_item || null;
        const reclamoId = modalAporte.dataset.reclamoId || '';
        const imputacionId = modalAporte.dataset.imputacionId || '';
        const miembroId = modalAporte.dataset.miembroId || '';
        const miembroNombre = modalAporte.dataset.miembroNombre || 'el miembro';

        if (!it || !reclamoId || !imputacionId || !miembroId) {
            alert('No se pudo determinar la información del aporte.');
            return;
        }

        const ok = confirm(
            `Se enviará este aporte como base para la respuesta final del sponsor.\n\n` +
            `¿Deseas aprobar la respuesta de ${miembroNombre} y copiarla a "Responder medidas"?`
        );
        if (!ok) return;
        document.getElementById('resp-reclamo-codigo').textContent =
            modalAporte.dataset.reclamoId || '';

        document.getElementById('resp-observacion').textContent =
            `Base tomada del aporte aprobado de ${miembroNombre}. Puedes ajustarla antes de enviar la respuesta final.`;

        const formResponder = document.getElementById('formResponderMedidas');
        if (formResponder) {
            formResponder.dataset.modo = 'responsable';
        }
        copiarAResponderMedidas(it);
        document.getElementById('resp-imp-id').value = imputacionId;

        try {
            await fetch(`/reclamos/${encodeURIComponent(reclamoId)}/equipo-respuestas/aprobar`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    imputacion_id: imputacionId,
                    miembro_id: miembroId
                })
            });
        } catch (e) {
            console.warn('No se pudo registrar aprobación en backend:', e);
        }

        const instAporte = bootstrap.Modal.getInstance(modalAporte);
        if (instAporte) instAporte.hide();

        const modalEquipo = document.getElementById('modalEquipoRespuestas');
        const instEquipo = modalEquipo ? bootstrap.Modal.getInstance(modalEquipo) : null;
        if (instEquipo) instEquipo.hide();

        setTimeout(() => {
            document.body.classList.remove('modal-open');
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalResponderMedidas')).show();
        }, 250);
    });

    btnRechazar.addEventListener('click', async () => {
        const reclamoId = modalAporte.dataset.reclamoId || '';
        const imputacionId = modalAporte.dataset.imputacionId || '';
        const miembroId = modalAporte.dataset.miembroId || '';
        const miembroNombre = modalAporte.dataset.miembroNombre || 'el miembro';

        if (!reclamoId || !imputacionId || !miembroId) {
            alert('No se pudo determinar reclamo / imputación / miembro.');
            return;
        }

        const motivo = prompt(
            `Vas a rechazar la respuesta de ${miembroNombre}.\n` +
            `Escribe el motivo o correcciones solicitadas (se enviará por correo):`
        );
        if (motivo === null) return;
        if (!motivo.trim()) {
            alert('Debes escribir un motivo para el rechazo.');
            return;
        }

        const ok = confirm(
            `Se enviará un correo a ${miembroNombre} solicitando corrección.\n\n¿Confirmas el rechazo?`
        );
        if (!ok) return;

        const resp = await fetch(`/reclamos/${encodeURIComponent(reclamoId)}/equipo-respuestas/rechazar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                imputacion_id: imputacionId,
                miembro_id: miembroId,
                motivo
            })
        });

        const ct = resp.headers.get('content-type') || '';
        const data = ct.includes('application/json') ? await resp.json() : {};

        if (!resp.ok || data.ok !== true) {
            alert((data && (data.error || data.msg)) || `No se pudo enviar (HTTP ${resp.status})`);
            return;
        }

        alert('Rechazo enviado por correo al miembro.');
        bootstrap.Modal.getInstance(modalAporte)?.hide();
    });
})();

document.addEventListener("DOMContentLoaded", function () {
    const fechaInput = document.getElementById("recl-fecha-om");
    if (!fechaInput) return;

    // Fecha de hoy en formato YYYY-MM-DD
    const hoy = new Date();
    const yyyy = hoy.getFullYear();
    const mm = String(hoy.getMonth() + 1).padStart(2, '0');
    const dd = String(hoy.getDate()).padStart(2, '0');
    const hoyStr = `${yyyy}-${mm}-${dd}`;

    // Setear valor por defecto
    fechaInput.value = hoyStr;

    // Bloquear fechas pasadas
    fechaInput.min = hoyStr;
});

(function () {

    const tipoSel = document.getElementById('recl-tipo-reclamo');
    const subSel = document.getElementById('recl-subtipo');
    const subOtro = document.getElementById('recl-subtipo-otro');

    if (!tipoSel || !subSel || !subOtro) return;

    function resetSubtipo() {
        subSel.innerHTML = '<option value="">— Seleccione —</option>';
        subSel.disabled = true;
        subSel.removeAttribute('name');

        subOtro.value = '';
        subOtro.classList.add('d-none');
        subOtro.removeAttribute('name');
    }

    async function cargarSubtipos(tipoId) {
        resetSubtipo();
        if (!tipoId) return;

        subSel.innerHTML = '<option value="">Cargando…</option>';

        try {
            const resp = await fetch(`/reclamos/api/subtipos?tipo_id=${tipoId}`);
            const data = await resp.json();

            subSel.innerHTML = '<option value="">— Seleccione —</option>';

            if (!Array.isArray(data) || data.length === 0) {
                // No hay submotivos → texto libre
                subOtro.classList.remove('d-none');
                subOtro.setAttribute('name', 'antecedente');
                return;
            }

            data.forEach(it => {
                const opt = document.createElement('option');
                opt.value = it.id;          // enviamos ID
                opt.textContent = it.valor; // mostramos texto
                subSel.appendChild(opt);
            });

            const optOtro = document.createElement('option');
            optOtro.value = '__OTRO__';
            optOtro.textContent = 'Otro (especificar)';
            subSel.appendChild(optOtro);

            subSel.disabled = false;
            subSel.setAttribute('name', 'antecedente');

        } catch (e) {
            console.error(e);
            subOtro.classList.remove('d-none');
            subOtro.setAttribute('name', 'antecedente');
        }
    }

    // Cambio de TIPO
    tipoSel.addEventListener('change', () => {
        const opt = tipoSel.options[tipoSel.selectedIndex];
        const tipoId = opt?.dataset?.id || '';
        cargarSubtipos(tipoId);
    });

    // Cambio de SUBTIPO
    subSel.addEventListener('change', () => {
        if (subSel.value === '__OTRO__') {
            subSel.removeAttribute('name');
            subOtro.classList.remove('d-none');
            subOtro.setAttribute('name', 'antecedente');
            subOtro.focus();
        } else {
            subOtro.classList.add('d-none');
            subOtro.removeAttribute('name');
            subSel.setAttribute('name', 'antecedente');
        }
    });

    resetSubtipo();

})();

document.addEventListener('click', async function (e) {
    const btn = e.target.closest('.js-eliminar-om');
    if (!btn) return;

    const tr = btn.closest('tr');

    const reclamoId =
        btn.dataset.reclamoId ||
        tr?.dataset?.reclamoId ||
        '';

    const codigo =
        btn.dataset.codigo ||
        tr?.dataset?.codigo ||
        '';

    if (!reclamoId || reclamoId === 'undefined' || reclamoId === 'None') {
        alert('No se pudo determinar el ID de la OM.');
        console.error('Eliminar OM sin reclamoId', { btn, tr });
        return;
    }

    if (!confirm(`¿Seguro que deseas eliminar la OM ${codigo || reclamoId}?\nEsta acción no se puede deshacer.`)) {
        return;
    }

    try {
        const resp = await fetch(`/reclamos/${encodeURIComponent(reclamoId)}/eliminar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            credentials: 'same-origin'
        });

        const ct = resp.headers.get('content-type') || '';
        const data = ct.includes('application/json')
            ? await resp.json()
            : { ok: false, msg: await resp.text() };

        if (!resp.ok || data.ok !== true) {
            alert(data.msg || `Error al eliminar la OM. HTTP ${resp.status}`);
            return;
        }

        const row = btn.closest('tr');
        if (row) row.remove();

        alert(data.msg || 'OM eliminada correctamente.');

    } catch (err) {
        console.error(err);
        alert('Error inesperado al eliminar la OM.');
    }
});

document.addEventListener("DOMContentLoaded", function () {

    // 🔹 1. Activar tab según querystring
    const urlParams = new URLSearchParams(window.location.search);
    const activeTab = urlParams.get("tab");

    if (activeTab) {
        const triggerEl = document.querySelector(`[data-tab-id="${activeTab}"]`);
        if (triggerEl) {
            new bootstrap.Tab(triggerEl).show();
        }
    }

    // 🔹 2. Guardar tab activo cuando se cambia
    document.querySelectorAll('[data-bs-toggle="pill"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', function (event) {
            const tabId = event.target.getAttribute("data-tab-id");
            document.getElementById("activeTabInput").value = tabId;
        });
    });

});

(function () {
    const table = document.querySelector('.recl-table'); // tu clase actual
    if (!table) return;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;

    const getDataRows = () =>
        Array.from(tbody.querySelectorAll('tr'))
            .filter(tr => tr.querySelector('td') && !tr.querySelector('td[colspan]')); // ignora “no hay datos”

    let rows = getDataRows();
    let sortState = { index: -1, dir: 'asc' };

    const parseEsNumber = (s) => {
        if (!s) return 0;
        const n = s.replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '');
        const v = parseFloat(n);
        return isNaN(v) ? 0 : v;
    };

    const parseDate = (txt) => {
        if (!txt) return 0;
        txt = txt.trim();
        // soporta dd/mm/yyyy o yyyy-mm-dd o cualquier Date.parse
        let t = Date.parse(txt.replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$3-$2-$1'));
        if (isNaN(t)) t = Date.parse(txt);
        return isNaN(t) ? 0 : t;
    };

    const cellVal = (tr, idx, type) => {
        const td = tr.children[idx];
        const txt = (td?.textContent || '').trim();
        if (type === 'num') return parseEsNumber(txt);
        if (type === 'date') return parseDate(txt);
        return txt.toLocaleLowerCase();
    };

    const clearSortClasses = () => {
        thead.querySelectorAll('th').forEach(th => th.classList.remove('sorted-asc', 'sorted-desc'));
        thead.querySelectorAll('.th-sortable i').forEach(i => {
            i.classList.remove('bi-chevron-up', 'bi-chevron-down');
            i.classList.add('bi-arrow-down-up');
        });
    };

    const setIcon = (th, dir) => {
        const i = th.querySelector('.th-sortable i');
        if (!i) return;
        i.classList.remove('bi-arrow-down-up', 'bi-chevron-up', 'bi-chevron-down');
        i.classList.add(dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down');
    };

    const applySort = (th, idx, type) => {
        const same = idx === sortState.index;
        sortState.dir = same ? (sortState.dir === 'asc' ? 'desc' : 'asc') : 'asc';
        sortState.index = idx;

        rows = getDataRows(); // por si cambió el DOM
        rows.sort((a, b) => {
            const va = cellVal(a, idx, type);
            const vb = cellVal(b, idx, type);
            let c = 0;
            if (va > vb) c = 1; else if (va < vb) c = -1;
            return sortState.dir === 'asc' ? c : -c;
        });

        const frag = document.createDocumentFragment();
        rows.forEach(r => frag.appendChild(r));
        tbody.appendChild(frag);

        clearSortClasses();
        th.classList.add(sortState.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
        setIcon(th, sortState.dir);
    };

    thead.querySelectorAll('th[data-sort]').forEach(th => {
        const type = (th.getAttribute('data-sort') || 'text').toLowerCase();
        const clickable = th.querySelector('.th-sortable') || th;
        clickable.setAttribute('role', 'button');
        clickable.setAttribute('tabindex', '0');

        clickable.addEventListener('click', () => {
            const idx = Array.from(th.parentElement.children).indexOf(th);
            applySort(th, idx, type);
        });

        clickable.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); clickable.click(); }
        });
    });

    clearSortClasses();
})();

function fmtDateTimeES(s) {
    if (!s) return '';

    // Normaliza: "YYYY-MM-DDTHH:MM:SS" -> "YYYY-MM-DD HH:MM:SS"
    s = String(s).trim().replace('T', ' ');

    // Toma solo los 19 chars: YYYY-MM-DD HH:MM:SS
    // (si viene con milisegundos o zona horaria, lo recorta)
    if (s.length >= 19) s = s.slice(0, 19);

    // Caso solo fecha
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) s = s + ' 00:00:00';

    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/);
    if (!m) return s; // fallback: no rompas si llega raro

    const [, y, mo, d, hh, mm, ss] = m;
    return `${d}/${mo}/${y} ${hh}:${mm}:${ss}`;
}

document.addEventListener('DOMContentLoaded', function () {
    const btnMejorarIA = document.getElementById('btnMejorarIA');
    const modalEl = document.getElementById('modalResponderMedidas');

    if (!btnMejorarIA || !modalEl) return;

    const IA_MAX_USOS = 2;

    function getIaStorageKey() {
        const impId = (document.getElementById('resp-imp-id')?.value || '').trim() || 'sin_om';
        return `om_ia_usos_${impId}`;
    }

    function getIaUsos() {
        return parseInt(localStorage.getItem(getIaStorageKey()) || '0', 10);
    }

    function setIaUsos(n) {
        localStorage.setItem(getIaStorageKey(), String(n));
    }

    window.actualizarEstadoBotonIA = function () {
        const usados = getIaUsos();
        const badge = document.getElementById('ia-count-badge');

        if (badge) {
            badge.textContent = `${usados}/${IA_MAX_USOS}`;
        }

        btnMejorarIA.disabled = usados >= IA_MAX_USOS;
        btnMejorarIA.classList.toggle('disabled', usados >= IA_MAX_USOS);
        btnMejorarIA.title = usados >= IA_MAX_USOS
            ? 'Límite alcanzado: máximo 2 mejoras con IA para esta OM.'
            : 'Puedes usar la mejora con IA hasta 2 veces para esta OM.';
    };

    function getCsrfTokenIA() {
        return (
            document.querySelector('input[name="csrf_token"]')?.value ||
            document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
            ''
        );
    }

    function getPayloadMejorarIA() {
        return {
            observacion: (document.getElementById('resp-observacion')?.textContent || '').trim(),
            metodo_analisis: (document.getElementById('resp-metodo')?.value || 'FISHBONE').trim(),

            causas: (typeof recogerAcciones === 'function') ? recogerAcciones('causa') : [],
            control: (typeof recogerAcciones === 'function') ? recogerAcciones('control') : [],
            correctiva: (typeof recogerAcciones === 'function') ? recogerAcciones('correctiva') : [],

            why1: (document.getElementById('resp-why1')?.value || '').trim(),
            why2: (document.getElementById('resp-why2')?.value || '').trim(),
            why3: (document.getElementById('resp-why3')?.value || '').trim(),
            why4: (document.getElementById('resp-why4')?.value || '').trim(),
            why5: (document.getElementById('resp-why5')?.value || '').trim(),

            fish_metodo: (document.getElementById('resp-fish-metodo')?.value || '').trim(),
            fish_maquinas: (document.getElementById('resp-fish-maquinas')?.value || '').trim(),
            fish_materiales: (document.getElementById('resp-fish-materiales')?.value || '').trim(),
            fish_personas: (document.getElementById('resp-fish-personas')?.value || '').trim(),
            fish_entorno: (document.getElementById('resp-fish-entorno')?.value || '').trim(),
            fish_medicion: (document.getElementById('resp-fish-medicion')?.value || '').trim()
        };
    }

    function aplicarMejoraIA(data) {
        const setVal = (id, valor) => {
            const el = document.getElementById(id);
            if (el) el.value = valor || '';
        };

        const metodo = (document.getElementById('resp-metodo')?.value || 'FISHBONE').toUpperCase();

        if (metodo === '5WHYS') {
            setVal('resp-why1', data.why1 || '');
            setVal('resp-why2', data.why2 || '');
            setVal('resp-why3', data.why3 || '');
            setVal('resp-why4', data.why4 || '');
            setVal('resp-why5', data.why5 || '');
        } else {
            setVal('resp-fish-metodo', data.fish_metodo || '');
            setVal('resp-fish-maquinas', data.fish_maquinas || '');
            setVal('resp-fish-materiales', data.fish_materiales || '');
            setVal('resp-fish-personas', data.fish_personas || '');
            setVal('resp-fish-entorno', data.fish_entorno || '');
            setVal('resp-fish-medicion', data.fish_medicion || '');
        }

        if (typeof window.cargarAccionesEnModal === 'function') {
            window.cargarAccionesEnModal({
                causas: data.causas || [],
                control: data.control || [],
                correctiva_items: data.correctiva || []
            });
        }
    }

    function textoConContenido(v) {
        return String(v || '').trim().length >= 12;
    }

    function listaConContenido(arr) {
        return Array.isArray(arr) && arr.some(x => textoConContenido(x.descripcion));
    }

    btnMejorarIA.addEventListener('click', async function () {
        const overlay = document.querySelector('#modalResponderMedidas #resp-loading');
        const msgEl = document.getElementById('resp-loading-msg');

        if (getIaUsos() >= IA_MAX_USOS) {
            showToast?.('La mejora con IA solo puede ejecutarse 2 veces por esta OM.');
            window.actualizarEstadoBotonIA?.();
            return;
        }

        try {
            bloquearBtn(btnMejorarIA, 'Mejorando...');
            overlay?.classList.remove('d-none');

            if (msgEl) {
                msgEl.textContent = 'Mejorando texto con IA…';
            }

            const payload = getPayloadMejorarIA();

            const tieneAnalisis5Whys =
                textoConContenido(payload.why1) ||
                textoConContenido(payload.why2) ||
                textoConContenido(payload.why3) ||
                textoConContenido(payload.why4) ||
                textoConContenido(payload.why5);

            const tieneAnalisisFishbone =
                textoConContenido(payload.fish_metodo) ||
                textoConContenido(payload.fish_maquinas) ||
                textoConContenido(payload.fish_materiales) ||
                textoConContenido(payload.fish_personas) ||
                textoConContenido(payload.fish_entorno) ||
                textoConContenido(payload.fish_medicion);

            const tieneCausas = listaConContenido(payload.causas);
            const tieneControl = listaConContenido(payload.control);
            const tieneCorrectiva = listaConContenido(payload.correctiva);

            const formEl = document.getElementById('formResponderMedidas');
            const modo = ((formEl?.dataset?.modo) || 'responsable').toLowerCase();

            if (
                modo !== 'equipo' &&
                !(tieneAnalisis5Whys || tieneAnalisisFishbone || tieneCausas || tieneControl || tieneCorrectiva)
            ) {
                showToast?.('Para usar IA, completa el análisis, causas o acciones con al menos 12 caracteres en cada campo.');
                return;
            }

            const csrfToken = getCsrfTokenIA();

            const resp = await fetch('/reclamos/ia/mejorar_respuesta', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            const ct = resp.headers.get('content-type') || '';
            const data = ct.includes('application/json') ? await resp.json() : {};

            if (!resp.ok || data.ok !== true) {
                throw new Error(data.msg || data.error || `HTTP ${resp.status}`);
            }

            aplicarMejoraIA(data);

            const usadosActuales = getIaUsos() + 1;
            setIaUsos(usadosActuales);
            window.actualizarEstadoBotonIA?.();

            if (usadosActuales >= IA_MAX_USOS) {
                showToast?.('Has alcanzado el máximo de 2 mejoras con IA para esta OM.');
            } else {
                showToast?.(`Texto mejorado con IA (${usadosActuales}/${IA_MAX_USOS})`);
            }

        } catch (err) {
            console.error('Error IA:', err);
            alert(err.message || 'No se pudo mejorar el texto con IA.');
        } finally {
            overlay?.classList.add('d-none');
            desbloquearBtn(btnMejorarIA);
            window.actualizarEstadoBotonIA?.();
        }
    });

    window.actualizarEstadoBotonIA?.();
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tab-pane').forEach(pane => {
        const table = pane.querySelector('table.recl-table');
        const pager = pane.querySelector('.recl-pagination');
        if (!table || !pager) return;

        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr')).filter(tr => {
            return tr.querySelectorAll('td').length > 1 && !tr.querySelector('td[colspan]');
        });

        const sizeSelect = pager.querySelector('.js-page-size');
        const btnPrev = pager.querySelector('.js-page-prev');
        const btnNext = pager.querySelector('.js-page-next');
        const info = pager.querySelector('.js-page-info');

        let currentPage = 1;

        function renderPage() {
            const pageSize = Number(sizeSelect.value || 10);
            const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;

            rows.forEach((tr, idx) => {
                const visible = idx >= start && idx < end;
                tr.classList.toggle('d-none', !visible);
            });

            info.textContent = `Página ${currentPage} de ${totalPages}`;
            btnPrev.disabled = currentPage <= 1;
            btnNext.disabled = currentPage >= totalPages;

            pager.classList.toggle('d-none', rows.length === 0);
        }

        sizeSelect.addEventListener('change', () => {
            currentPage = 1;
            renderPage();
        });

        btnPrev.addEventListener('click', () => {
            currentPage--;
            renderPage();
        });

        btnNext.addEventListener('click', () => {
            currentPage++;
            renderPage();
        });

        renderPage();
    });
});


document.addEventListener("DOMContentLoaded", () => {

    // ── Panel flotante Asistente OM (no usa Bootstrap Modal) ─
    const _panel = document.getElementById("omChatPanel");

    function _abrirPanel() {
        if (_panel) _panel.classList.add("omc-visible");
    }

    function _cerrarPanel() {
        if (_panel) _panel.classList.remove("omc-visible");
    }

    document.querySelectorAll(".js-open-om-chat").forEach(b => {
        b.addEventListener("click", _abrirPanel);
    });

    document.getElementById("omChatClose")?.addEventListener("click", _cerrarPanel);

    // ── Chat ──────────────────────────────────────────────────
    const input = document.getElementById("om-chat-input");
    const btn = document.getElementById("om-chat-send");
    const box = document.getElementById("om-chat-messages");

    if (!input || !btn || !box) return;

    function addMsg(content, who, isHtml = false) {
        const div = document.createElement("div");
        div.className = `om-chat-bubble ${who}`;

        if (isHtml) {
            div.innerHTML = content;
        } else {
            div.textContent = content;
        }

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    }

    function renderBotAnswer(text) {
        const raw = String(text || "").trim();

        const clean = raw
            .replace(/^Estos son los principales resultados:\s*/i, "")
            .trim();

        const rows = clean
            .split(/(?=Usuario:\s*)/i)
            .map(x => x.trim())
            .filter(Boolean);

        if (rows.length > 1) {
            return `
      <div class="om-answer-title">
        <i class="bi bi-bar-chart-line"></i>
        Principales resultados
      </div>

      <div class="om-result-list">
        ${rows.map((row, index) => {
                const usuario = getPart(row, "Usuario");
                const nombre = getPart(row, "Nombre");
                const asignadas = getPart(row, "Om asignadas");

                return `
            <div class="om-result-card">
              <div class="om-result-rank">${index + 1}</div>
              <div class="om-result-main">
                <div class="om-result-name">${escapeHtml(nombre || usuario || "Sin nombre")}</div>
                <div class="om-result-user">@${escapeHtml(usuario || "—")}</div>
              </div>
              <div class="om-result-count">
                <strong>${escapeHtml(asignadas || "0")}</strong>
                <span>OM</span>
              </div>
            </div>
          `;
            }).join("")}
      </div>
    `;
        }

        return `
    <div class="om-answer-title">
      <i class="bi bi-info-circle"></i>
      Resultado
    </div>
    <div class="om-answer-text">${escapeHtml(clean)}</div>
  `;
    }

    function getPart(row, label) {
        const regex = new RegExp(`${label}:\\s*([^|]+)`, "i");
        const match = row.match(regex);
        return match ? match[1].trim() : "";
    }

    function escapeHtml(str) {
        return String(str || "").replace(/[&<>"']/g, m => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        }[m]));
    }





    function renderOmActionsCard(rows) {
        const first = rows[0] || {};

        return `
        <div class="om-answer-title">
            <i class="bi bi-check2-square"></i>
            Acciones de la OM
        </div>

        <div class="om-om-card">
            <div class="om-om-header">
                <div>
                    <div class="om-om-code">${escapeHtml(first.codigo_om || "—")}</div>
                    <div class="om-om-subtitle">${escapeHtml(first.cliente || "Sin cliente")}</div>
                </div>
            </div>

            <div class="om-result-list">
                ${rows.map(row => `
                    <div class="om-action-card">
                        <div class="om-action-top">
                            <span class="om-action-type ${String(row.tipo_accion || "").toLowerCase()}">
                                ${escapeHtml(row.tipo_accion || "Acción")}
                            </span>

                            <span class="om-action-status ${Number(row.cumplido || 0) === 1 ? "done" : "pending"}">
                                ${Number(row.cumplido || 0) === 1 ? "Cumplida" : "Pendiente"}
                            </span>
                        </div>

                        <div class="om-action-desc">
                            ${escapeHtml(row.descripcion_accion || "—")}
                        </div>

                        <div class="om-action-meta">
                            <div><strong>Fecha compromiso:</strong> ${escapeHtml(formatDateChat(row.fecha_compromiso) || "—")}</div>
                            <div><strong>Fecha cumplimiento:</strong> ${escapeHtml(formatDateChat(row.fecha_cumplimiento) || "—")}</div>
                            <div><strong>Estado:</strong> ${escapeHtml(row.estado_cumplimiento_accion || "—")}</div>
                            <div><strong>Evidencia:</strong> ${Number(row.tiene_evidencia || 0) === 1 ? "Sí" : "No"}</div>
                        </div>
                    </div>
                `).join("")}
            </div>
        </div>
    `;
    }
    function renderBotResponse(data) {
        if (!data.rows || !data.rows.length) {
            return renderBotAnswer(data.respuesta || "No encontré resultados.");
        }

        const first = data.rows[0] || {};

        // Si viene una OM específica, pinta tarjeta ejecutiva
        if (first.tipo_accion || data.source === "predefinido_acciones_om") {
            return renderOmActionsCard(data.rows);
        }
if (first.codigo_om && first.estado_global) {
    if (data.rows.length > 1) {
        return renderOmDetailList(data.rows);
    }

    return renderOmDetailCard(first);
}

        // Si es resultado genérico, mantiene formato lista
        return `
        <div class="om-answer-title">
            <i class="bi bi-list-check"></i> Resultados encontrados
        </div>

        <div class="om-result-list">
            ${data.rows.slice(0, 10).map(row => `
                <div class="om-detail-card">
                    ${Object.entries(row).map(([key, value]) => {
            if (key.endsWith("_id") || key === "id") return "";

            return `
                            <div class="om-row-field">
                                <strong>${formatLabel(key)}:</strong>
                                <span>${escapeHtml(value ?? "—")}</span>
                            </div>
                        `;
        }).join("")}
                </div>
            `).join("")}
        </div>
    `;
    }


    function renderOmDetailCard(row) {
        const estado = String(row.estado_global || "").toLowerCase();
        const estadoClass = estado.includes("abierto") ? "is-open" : "is-closed";

        const sponsorOk = !!String(row.sponsor_nombre || "").trim();
        const equipoOk = !!String(row.miembros_equipo || "").trim();
        const respEquipoOk = !!String(row.fecha_primera_respuesta_equipo || "").trim();
        const respSponsorOk = !!String(row.fecha_respuesta_imputado || "").trim();
        const aprobadoOk = !!String(row.fecha_aprobacion_respuesta || "").trim();

        return `
        <div class="om-answer-title">
            <i class="bi bi-activity"></i>
            Estado de la OM
        </div>

        <div class="om-om-card">
            <div class="om-om-header">
                <div>
                    <div class="om-om-code">${escapeHtml(row.codigo_om || "—")}</div>
                    <div class="om-om-subtitle">${escapeHtml(row.cliente || "Sin cliente")}</div>
                </div>

                <span class="om-status-pill ${estadoClass}">
                    ${escapeHtml(row.estado_global || "—")}
                </span>
            </div>

            <div class="om-om-meta">
                <div>
                    <span>Proceso</span>
                    <strong>${escapeHtml(row.proceso || "—")}</strong>
                </div>
                <div>
                    <span>Tipo reclamo</span>
                    <strong>${escapeHtml(row.tipo_reclamo || "—")}</strong>
                </div>
                <div>
                    <span>Días sin respuesta sponsor</span>
                    <strong>${escapeHtml(row.dias_sin_respuesta_sponsor ?? "—")}</strong>
                </div>
            </div>

            <div class="om-om-owner">
                <i class="bi bi-person-badge"></i>
                <div>
                    <span>Responsable actual</span>
                    <strong>${escapeHtml(row.sponsor_nombre || "—")}</strong>
                </div>
            </div>

            <div class="om-timeline-title">Línea de tiempo</div>

            <div class="om-mini-timeline">
                ${timelineStep("Creada", true)}
                ${timelineStep("Sponsor", sponsorOk)}
                ${timelineStep("Equipo", equipoOk)}
                ${timelineStep("Resp. equipo", respEquipoOk)}
                ${timelineStep("Resp. sponsor", respSponsorOk)}
                ${timelineStep("Aprobación", aprobadoOk)}
            </div>

            <div class="om-om-dates">
                <div><strong>Fecha OM:</strong> ${escapeHtml(formatDateChat(row.fecha_reclamo) || "—")}</div>
                <div><strong>Fecha respuesta sponsor:</strong> ${escapeHtml(formatDateChat(row.fecha_respuesta_imputado) || "—")}</div>
                <div><strong>Fecha aprobación:</strong> ${escapeHtml(formatDateChat(row.fecha_aprobacion_respuesta) || "—")}</div>
            </div>
        </div>
    `;
    }

    function renderOmDetailList(rows) {
    const total = Array.isArray(rows) ? rows.length : 0;

    return `
        <div class="om-answer-title">
            <i class="bi bi-list-check"></i>
            Detalle de OMs encontradas
        </div>

        <div class="small text-muted mb-2">
            Se encontraron ${total} OM.
        </div>

        <div class="om-result-list">
            ${rows.map(row => renderOmDetailCard(row)).join("")}
        </div>
    `;
}

    function timelineStep(label, done) {
        return `
        <div class="om-timeline-step ${done ? "done" : "pending"}">
            <span>${done ? "✓" : "○"}</span>
            ${escapeHtml(label)}
        </div>
    `;
    }

    function formatDateChat(value) {
        if (!value) return "";
        const s = String(value).trim();

        if (s.length >= 10 && s[4] === "-" && s[7] === "-") {
            const y = s.slice(0, 4);
            const m = s.slice(5, 7);
            const d = s.slice(8, 10);
            return `${d}/${m}/${y}`;
        }

        return s;
    }


    function formatLabel(key) {
        const labels = {
            codigo_om: "Código OM",
            fecha_reclamo: "Fecha OM",
            fecha_creacion: "Fecha creación",
            cliente: "Cliente",
            cliente_nombre: "Cliente",
            proceso: "Proceso",
            proceso_text: "Proceso",
            sponsor_nombre: "Sponsor",
            imputado_nombre: "Sponsor",
            tipo_reclamo: "Tipo reclamo",
            tipo_om: "Tipo OM",
            estado_global: "Estado",
            total_om: "Total OM"
        };

        return labels[key] || key.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
    }

    async function sendQuestion() {
        const pregunta = input.value.trim();
        if (!pregunta) return;

        addMsg(pregunta, "user");

        input.value = "";
        btn.disabled = true;
        btn.textContent = "Consultando...";

        try {
            const resp = await fetch("/api/om-chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || ""
                },
                body: JSON.stringify({ pregunta })
            });

            const data = await resp.json();

            if (!data.ok) {
                addMsg(data.error || "No se pudo procesar la pregunta.", "bot");
            } else {
                const html = renderBotResponse(data);
                addMsg(html, "bot", true);
            }

        } catch (err) {
            addMsg("Error consultando el asistente OM.", "bot");
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send me-1"></i>Preguntar';
            input.focus();
        }
    }

    btn.addEventListener("click", sendQuestion);

    input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
            ev.preventDefault();
            sendQuestion();
        }
    });

    // ── Botón "Nueva conversación" ──────────────────────────────
    document.getElementById("om-chat-reset")?.addEventListener("click", async () => {
        try {
            await fetch("/api/om-chat/reset", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || ""
                }
            });
        } catch (_) { /* silencioso */ }

        box.innerHTML = `
            <div class="om-chat-bubble bot">
                Conversación reiniciada. Puedes hacer una nueva pregunta 👋
            </div>`;
    });

    // ── Parsear **negrita** de respuestas OpenAI ────────────────
    function parsearNegritas(text) {
        return text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                   .replace(/\n/g, "<br>");
    }


    document.addEventListener('click', async function (ev) {
        const btn = ev.target.closest('.js-subir-carta-cliente');
        if (!btn) return;

        const reclamoId = btn.dataset.reclamoId || '';
        const codigo = btn.dataset.codigo || '';

        if (!reclamoId) {
            alert('No se pudo determinar la OM.');
            return;
        }

        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx';

        input.addEventListener('change', async function () {
            if (!input.files || !input.files.length) return;

            const ok = confirm(`¿Deseas subir la carta final para la OM ${codigo || reclamoId}?`);
            if (!ok) return;

            const formData = new FormData();
            formData.append('carta_cliente', input.files[0]);

            try {
                bloquearBtn(btn, 'Subiendo...');

                const resp = await fetch(`/reclamos/${encodeURIComponent(reclamoId)}/carta-cliente`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin',
                    body: formData
                });

                const ct = resp.headers.get('content-type') || '';
                const data = ct.includes('application/json') ? await resp.json() : {};

                if (!resp.ok || data.ok !== true) {
                    alert(data.msg || data.error || `No se pudo subir la carta. HTTP ${resp.status}`);
                    return;
                }

                alert(data.msg || 'Carta cargada correctamente.');
                location.reload();

            } catch (err) {
                console.error(err);
                alert('Error inesperado al subir la carta.');
            } finally {
                desbloquearBtn(btn);
            }
        });

        input.click();
    });


    // ── Generar carta PDF para el cliente ──────────────────────────────────
    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.js-generar-carta-pdf');
        if (!btn) return;

        const reclamoId = btn.dataset.reclamoId;
        const codigo    = btn.dataset.codigo || reclamoId;

        if (!confirm(`¿Generar carta PDF para el cliente de la OM ${codigo}?\n\nEsto puede tardar unos segundos mientras se procesa el análisis.`)) return;

        const iconOrig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

        try {
            const resp = await fetch(`/reclamos/${encodeURIComponent(reclamoId)}/generar-carta-pdf`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                },
            });

            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data.msg || `Error ${resp.status}`);
            }

            // Descargar el PDF directamente en el browser
            const blob  = await resp.blob();
            const url   = URL.createObjectURL(blob);
            const a     = document.createElement('a');
            const cd    = resp.headers.get('Content-Disposition') || '';
            const match = cd.match(/filename="?([^";\n]+)"?/);
            a.download  = match ? match[1] : `Carta_Cliente_${codigo}.pdf`;
            a.href      = url;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            // Toast éxito
            if (typeof showToast === 'function') {
                showToast(`Carta PDF generada correctamente para ${codigo}.`);
            }
        } catch (err) {
            alert(`Error al generar la carta: ${err.message}`);
        } finally {
            btn.disabled = false;
            btn.innerHTML = iconOrig;
        }
    });

});

// =========================================================
// VALIDAR RESPUESTA — CREADOR DE LA OM
// =========================================================
(function () {
    'use strict';

    const modalEl  = document.getElementById('modalValidarCreador');
    if (!modalEl) return;

    const modal       = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    const elId        = document.getElementById('vc-reclamo-id');
    const elAccion    = document.getElementById('vc-accion');
    const elCodigo    = document.getElementById('vc-codigo');
    const elTexto     = document.getElementById('vc-texto-accion');
    const elMotivoW   = document.getElementById('vc-motivo-wrap');
    const elMotivo    = document.getElementById('vc-motivo');
    const elAceptInfo = document.getElementById('vc-aceptar-info');
    const btnConf     = document.getElementById('btn-vc-confirmar');

    // Abrir modal al hacer clic en los botones js-validar-creador
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.js-validar-creador');
        if (!btn) return;

        const accion   = btn.dataset.accion;   // 'aceptar' | 'rechazar'
        const reclamoId = btn.dataset.reclamoId;
        const codigo   = btn.dataset.codigo || '';

        elId.value     = reclamoId;
        elAccion.value = accion;
        elCodigo.textContent = codigo;

        if (accion === 'aceptar') {
            elTexto.textContent  = '¿Confirmas que la respuesta técnica es satisfactoria?';
            elMotivoW.classList.add('d-none');
            elAceptInfo.classList.remove('d-none');
            btnConf.className    = 'btn btn-success';
            btnConf.textContent  = 'Aceptar respuesta';
        } else {
            elTexto.textContent  = 'Indica el motivo del rechazo. La OM volverá a estado Abierto.';
            elMotivoW.classList.remove('d-none');
            elAceptInfo.classList.add('d-none');
            elMotivo.value       = '';
            btnConf.className    = 'btn btn-danger';
            btnConf.textContent  = 'Rechazar respuesta';
        }

        modal.show();
    });

    // Confirmar acción
    btnConf?.addEventListener('click', async function () {
        const reclamoId = elId.value;
        const accion    = elAccion.value;
        const motivo    = (elMotivo.value || '').trim();

        if (accion === 'rechazar' && !motivo) {
            elMotivo.classList.add('is-invalid');
            elMotivo.focus();
            return;
        }
        elMotivo.classList.remove('is-invalid');

        btnConf.disabled = true;
        const textoOrig  = btnConf.textContent;
        btnConf.textContent = 'Procesando…';

        try {
            const resp = await fetch(`/reclamos/${reclamoId}/validar-creador`, {
                method : 'POST',
                headers: {
                    'Content-Type' : 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken'  : document.querySelector('meta[name="csrf-token"]')
                                        ?.getAttribute('content') || ''
                },
                body: JSON.stringify({ accion, motivo })
            });

            const data = await resp.json();

            modal.hide();

            if (data.ok) {
                showToast?.(data.msg || 'Operación realizada.', 'success');
                setTimeout(() => location.reload(), 1200);
            } else {
                showToast?.(data.msg || 'Error al procesar.', 'danger');
            }
        } catch (err) {
            showToast?.('Error de conexión.', 'danger');
        } finally {
            btnConf.disabled    = false;
            btnConf.textContent = textoOrig;
        }
    });

    // Limpiar validación al escribir
    elMotivo?.addEventListener('input', function () {
        elMotivo.classList.remove('is-invalid');
    });
}());

// ── Analizar descripción de OM con IA ───────────────────────────────────────
(function () {
    const btn      = document.getElementById('btn-analizar-desc');
    const textarea = document.getElementById('om-observacion');
    const panel    = document.getElementById('om-ia-feedback');
    if (!btn || !textarea || !panel) return;

    const ICONOS = { ok: '✅', warn: '⚠️', fail: '❌' };
    const CLASES = { ok: 'ia-ic-ok', warn: 'ia-ic-warn', fail: 'ia-ic-fail' };

    function setPanelMsg(msg, cssClass) {
        panel.className = 'om-ia-feedback';
        var sp = document.createElement('span');
        sp.className = cssClass || '';
        sp.textContent = msg;
        panel.innerHTML = '';
        panel.appendChild(sp);
    }

    btn.addEventListener('click', function () {
        const texto = (textarea.value || '').trim();
        if (texto.length < 15) {
            setPanelMsg('Escribe una descripción más detallada antes de analizar.', 'ia-msg-error');
            return;
        }

        // Tomar motivo y submotivo del formulario actual
        const form      = btn.closest('form') || document.querySelector('form');
        const motivo    = (form && form.querySelector('[name="tipo_reclamo"]') ? form.querySelector('[name="tipo_reclamo"]').value : '').trim();
        const submotivo = (form && form.querySelector('[name="subtipo"]')      ? form.querySelector('[name="subtipo"]').value      : '').trim();

        btn.disabled = true;
        const textoOrig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Analizando…';

        panel.className = 'om-ia-feedback';
        var loadEl = document.createElement('span');
        loadEl.className = 'ia-msg-info';
        var icon = document.createElement('i');
        icon.className = 'bi bi-stars';
        loadEl.appendChild(icon);
        loadEl.appendChild(document.createTextNode(' Analizando con IA…'));
        panel.innerHTML = '';
        panel.appendChild(loadEl);

        fetch('/api/om/analizar-descripcion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: JSON.stringify({ texto: texto, motivo: motivo, submotivo: submotivo }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.ok) {
                setPanelMsg(data.error || 'Error al analizar.', 'ia-msg-error');
                return;
            }
            const puntaje   = data.puntaje || 0;
            const criterios = data.criterios || [];
            const sug       = data.sugerencia || '';

            panel.className = 'om-ia-feedback';
            panel.innerHTML = '';

            // Score bar
            var scoreBar = document.createElement('div');
            scoreBar.className = 'ia-score-bar';
            var scoreNum = document.createElement('div');
            scoreNum.className = 'ia-score-num';
            scoreNum.textContent = puntaje + '/8';
            var scoreLabel = document.createElement('div');
            scoreLabel.className = 'ia-score-label';
            scoreLabel.textContent = 'criterios cumplidos';
            var scoreSub = document.createElement('div');
            scoreSub.className = puntaje >= 7 ? 'ia-ic-ok' : (puntaje >= 5 ? 'ia-ic-warn' : 'ia-ic-fail');
            scoreSub.textContent = puntaje >= 7 ? '✅ Descripción lista' : (puntaje >= 5 ? '⚠️ Puede mejorar' : '❌ Necesita mejoras');
            scoreLabel.appendChild(document.createElement('br'));
            scoreLabel.appendChild(scoreSub);
            scoreBar.appendChild(scoreNum);
            scoreBar.appendChild(scoreLabel);
            panel.appendChild(scoreBar);

            // Criterios
            var lista = document.createElement('div');
            lista.className = 'ia-criterios';
            criterios.forEach(function (c) {
                var row = document.createElement('div');
                row.className = 'ia-criterio';
                var ic = document.createElement('span');
                ic.className = 'ia-ic ' + (CLASES[c.estado] || '');
                ic.textContent = ICONOS[c.estado] || '•';
                var txt = document.createElement('span');
                var strong = document.createElement('strong');
                strong.textContent = c.texto;
                txt.appendChild(strong);
                if (c.nota) {
                    txt.appendChild(document.createTextNode(' — '));
                    var em = document.createElement('em');
                    em.textContent = c.nota;
                    txt.appendChild(em);
                }
                row.appendChild(ic);
                row.appendChild(txt);
                lista.appendChild(row);
            });
            panel.appendChild(lista);

            // Sugerencia
            if (sug) {
                var sugDiv = document.createElement('div');
                sugDiv.className = 'ia-sugerencia';
                var sugIcon = document.createElement('i');
                sugIcon.className = 'bi bi-lightbulb';
                sugDiv.appendChild(sugIcon);
                sugDiv.appendChild(document.createTextNode(' ' + sug));
                panel.appendChild(sugDiv);
            }

            // Botón "Mejorar con IA"
            var mejoraBtnWrap = document.createElement('div');
            mejoraBtnWrap.className = 'ia-mejora-btn-wrap';
            var btnMejorar = document.createElement('button');
            btnMejorar.type = 'button';
            btnMejorar.className = 'btn-om-ia-analizar';
            var icoMejorar = document.createElement('i');
            icoMejorar.className = 'bi bi-magic';
            btnMejorar.appendChild(icoMejorar);
            btnMejorar.appendChild(document.createTextNode(' Mejorar con IA'));
            mejoraBtnWrap.appendChild(btnMejorar);
            panel.appendChild(mejoraBtnWrap);

            // Panel de sugerencia de mejora (oculto al inicio)
            var mejoraPanel = document.createElement('div');
            mejoraPanel.className = 'om-ia-mejora d-none';
            panel.appendChild(mejoraPanel);

            btnMejorar.addEventListener('click', function () {
                var textoActual = (textarea.value || '').trim();
                if (!textoActual) { return; }

                var form2      = btn.closest('form') || document.querySelector('form');
                var motivo2    = (form2 && form2.querySelector('[name="tipo_reclamo"]') ? form2.querySelector('[name="tipo_reclamo"]').value : '').trim();
                var submotivo2 = (form2 && form2.querySelector('[name="subtipo"]')      ? form2.querySelector('[name="subtipo"]').value      : '').trim();

                btnMejorar.disabled = true;
                btnMejorar.innerHTML = '';
                btnMejorar.appendChild(document.createTextNode('Mejorando…'));

                mejoraPanel.className = 'om-ia-mejora';
                mejoraPanel.innerHTML = '';
                var loadMej = document.createElement('span');
                loadMej.className = 'ia-msg-info';
                loadMej.textContent = '✨ Generando versión mejorada…';
                mejoraPanel.appendChild(loadMej);

                fetch('/api/om/mejorar-descripcion', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({ texto: textoActual, motivo: motivo2, submotivo: submotivo2 }),
                })
                .then(function (r) { return r.json(); })
                .then(function (mdata) {
                    mejoraPanel.innerHTML = '';
                    if (!mdata.ok) {
                        var errEl = document.createElement('span');
                        errEl.className = 'ia-msg-error';
                        errEl.textContent = mdata.error || 'Error al mejorar.';
                        mejoraPanel.appendChild(errEl);
                        return;
                    }
                    var descMejorada = mdata.descripcion_mejorada || '';
                    var cambios      = mdata.cambios || [];

                    // Label
                    var lbl = document.createElement('div');
                    lbl.className = 'ia-mejora-label';
                    var lIcon = document.createElement('i');
                    lIcon.className = 'bi bi-stars';
                    lbl.appendChild(lIcon);
                    lbl.appendChild(document.createTextNode(' Versión mejorada'));
                    mejoraPanel.appendChild(lbl);

                    // Texto mejorado
                    var txEl = document.createElement('div');
                    txEl.className = 'ia-mejora-texto';
                    txEl.textContent = descMejorada;
                    mejoraPanel.appendChild(txEl);

                    // Lista de cambios
                    if (cambios.length) {
                        var camDiv = document.createElement('div');
                        camDiv.className = 'ia-cambios';
                        cambios.forEach(function (c) {
                            var ci = document.createElement('div');
                            ci.className = 'ia-cambio-item';
                            ci.textContent = '• ' + c;
                            camDiv.appendChild(ci);
                        });
                        mejoraPanel.appendChild(camDiv);
                    }

                    // Botones aceptar / descartar
                    var mbtns = document.createElement('div');
                    mbtns.className = 'ia-mejora-btns';

                    var btnUsar = document.createElement('button');
                    btnUsar.type = 'button';
                    btnUsar.className = 'btn-om-ia-usar btn-om-ia-usar-si';
                    btnUsar.textContent = '✅ Usar esta descripción';
                    btnUsar.addEventListener('click', function () {
                        textarea.value = descMejorada;
                        mejoraPanel.className = 'om-ia-mejora d-none';
                        panel.classList.add('d-none');
                    });

                    var btnDesc = document.createElement('button');
                    btnDesc.type = 'button';
                    btnDesc.className = 'btn-om-ia-usar btn-om-ia-usar-no';
                    btnDesc.textContent = '✖ Descartar';
                    btnDesc.addEventListener('click', function () {
                        mejoraPanel.className = 'om-ia-mejora d-none';
                    });

                    mbtns.appendChild(btnUsar);
                    mbtns.appendChild(btnDesc);
                    mejoraPanel.appendChild(mbtns);
                })
                .catch(function () {
                    mejoraPanel.innerHTML = '';
                    var errEl2 = document.createElement('span');
                    errEl2.className = 'ia-msg-error';
                    errEl2.textContent = 'Error de conexión al mejorar.';
                    mejoraPanel.appendChild(errEl2);
                })
                .finally(function () {
                    btnMejorar.disabled = false;
                    btnMejorar.innerHTML = '';
                    var icoM2 = document.createElement('i');
                    icoM2.className = 'bi bi-magic';
                    btnMejorar.appendChild(icoM2);
                    btnMejorar.appendChild(document.createTextNode(' Mejorar con IA'));
                });
            });
        })
        .catch(function () {
            setPanelMsg('Error de conexión. Intenta de nuevo.', 'ia-msg-error');
        })
        .finally(function () {
            btn.disabled = false;
            btn.innerHTML = textoOrig;
        });
    });

    // Ocultar panel si el usuario edita el texto
    textarea.addEventListener('input', function () {
        panel.classList.add('d-none');
    });
}());