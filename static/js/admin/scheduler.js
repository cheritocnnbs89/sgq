// static/js/admin/scheduler.js
// Panel de administración de jobs del scheduler

(function () {
    const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || '';

    function apiCall(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF,
            },
            body: JSON.stringify(body),
        }).then(r => r.json());
    }

    function jobKey(tr) {
        return tr.dataset.jobKey;
    }

    // ── Toggle activo / inactivo ──────────────────────────
    document.querySelectorAll('.sch-toggle-activo').forEach(chk => {
        chk.addEventListener('change', function () {
            const tr = this.closest('tr');
            const key = jobKey(tr);
            const activo = this.checked;
            apiCall(`/admin/scheduler/${key}/toggle`, { activo })
                .then(data => {
                    if (!data.ok) {
                        this.checked = !activo;
                        alert('Error al cambiar estado: ' + (data.error || ''));
                    }
                })
                .catch(() => {
                    this.checked = !activo;
                    alert('Error de conexión');
                });
        });
    });

    // ── Botón lápiz: mostrar/ocultar edición inline ───────
    document.querySelectorAll('.sch-btn-edit').forEach(btn => {
        btn.addEventListener('click', function () {
            const tr = this.closest('tr');
            const key = jobKey(tr);
            const editDiv = document.getElementById('edit-' + key);
            if (editDiv) editDiv.classList.toggle('visible');
        });
    });

    // ── Cancelar edición ──────────────────────────────────
    document.querySelectorAll('.sch-btn-cancel-edit').forEach(btn => {
        btn.addEventListener('click', function () {
            this.closest('.sch-edit-inline').classList.remove('visible');
        });
    });

    // ── Guardar config (horario/intervalo) ────────────────
    document.querySelectorAll('.sch-btn-save-config').forEach(btn => {
        btn.addEventListener('click', function () {
            const tr = this.closest('tr');
            const key = jobKey(tr);
            const editDiv = this.closest('.sch-edit-inline');

            const inputIntervalo = editDiv.querySelector('.sch-input-intervalo');
            const inputHora = editDiv.querySelector('.sch-input-hora');

            const body = {
                intervalo_min: inputIntervalo ? (inputIntervalo.value || null) : null,
                hora_inicio: inputHora ? (inputHora.value || null) : null,
            };

            const orig = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            apiCall(`/admin/scheduler/${key}/config`, body)
                .then(data => {
                    btn.disabled = false;
                    btn.innerHTML = orig;
                    if (data.ok) {
                        editDiv.classList.remove('visible');
                        // Actualizar badge visual sin recargar
                        const badgeIntervalo = tr.querySelector('.sch-badge-intervalo');
                        const badgeHora = tr.querySelector('.sch-badge-hora');
                        if (badgeIntervalo && body.intervalo_min) {
                            badgeIntervalo.innerHTML =
                                `<i class="bi bi-arrow-repeat me-1"></i>cada ${body.intervalo_min} min`;
                        }
                        if (badgeHora && body.hora_inicio) {
                            badgeHora.innerHTML =
                                `<i class="bi bi-clock me-1"></i>${body.hora_inicio}`;
                        }
                    } else {
                        alert('Error: ' + (data.error || 'No se pudo guardar'));
                    }
                })
                .catch(() => {
                    btn.disabled = false;
                    btn.innerHTML = orig;
                    alert('Error de conexión');
                });
        });
    });

    // ── Ejecutar ahora ────────────────────────────────────
    const modalEl = document.getElementById('modalRunResult');
    const modalBody = document.getElementById('modalRunResultBody');
    const bsModal = modalEl ? new bootstrap.Modal(modalEl) : null;

    document.querySelectorAll('.sch-btn-run-now').forEach(btn => {
        btn.addEventListener('click', function () {
            const tr = this.closest('tr');
            const key = jobKey(tr);
            const orig = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            apiCall(`/admin/scheduler/${key}/run`, {})
                .then(data => {
                    btn.disabled = false;
                    btn.innerHTML = orig;
                    if (bsModal) {
                        modalBody.textContent = data.ok
                            ? ('OK — ' + (data.resultado || ''))
                            : ('Error: ' + (data.error || ''));
                        bsModal.show();
                    }
                    // Actualizar última ejecución visualmente
                    if (data.ok) {
                        const tdFecha = tr.querySelectorAll('td')[4];
                        if (tdFecha) {
                            const now = new Date();
                            const fmt = now.toLocaleDateString('es-EC') + ' ' +
                                now.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
                            tdFecha.innerHTML = `<span class="text-muted" style="font-size:.78rem">${fmt}</span>`;
                        }
                        const tdResult = tr.querySelectorAll('td')[5];
                        if (tdResult) {
                            const span = tdResult.querySelector('.sch-resultado');
                            if (span) span.textContent = data.resultado || 'OK';
                        }
                    }
                })
                .catch(() => {
                    btn.disabled = false;
                    btn.innerHTML = orig;
                    alert('Error de conexión');
                });
        });
    });
})();
