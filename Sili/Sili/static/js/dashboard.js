(function () {
  const chartDataEl = document.getElementById("chart-data");
  if (!chartDataEl) return;

  let CHART = null;
  try {
    CHART = JSON.parse(chartDataEl.textContent || "null");
  } catch (err) {
    console.error("No se pudo parsear chart-data:", err);
    return;
  }

  if (!CHART) return;
  if (typeof Chart === "undefined") {
    console.error("Chart.js no está cargado.");
    return;
  }

  const cssVar = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "";

  const rgba = (hex, alpha) => {
    if (!hex || hex.length < 7) return `rgba(0,0,0,${alpha})`;

    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);

    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "top" },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: { grid: { display: false } },
      y: { beginAtZero: true, grid: { drawBorder: false } },
    },
  };

  let statusChart = null;
  let asignacionChart = null;
  let overUserChart = null;
  let overDeptChart = null;
  let timelineChart = null;
  let horasDiaChart = null;
  let horasUsuarioChart = null;
  let horasDeptoChart = null;
  let cumplimientoChart = null;

  const ctxStatus = document.getElementById("chartStatus");
  if (ctxStatus && CHART.status) {
    statusChart = new Chart(ctxStatus, {
      type: "bar",
      data: {
        labels: CHART.status.labels,
        datasets: [
          {
            label: "Tareas",
            data: CHART.status.data,
            backgroundColor: rgba("#3b82f6", 0.6),
            borderColor: "#2563EB",
            borderWidth: 1,
          },
        ],
      },
      options: baseOptions,
    });
  }

  // ── Asignación de tareas (donut) ──────────────────────────────
  const ctxAsignacion = document.getElementById("chartAsignacion");
  if (ctxAsignacion && CHART.asignacion && CHART.asignacion.labels.length) {
    asignacionChart = new Chart(ctxAsignacion, {
      type: "doughnut",
      data: {
        labels: CHART.asignacion.labels,
        datasets: [{
          data: CHART.asignacion.data,
          backgroundColor: CHART.asignacion.colors,
          borderColor: "#ffffff",
          borderWidth: 2,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, padding: 8, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (c) => {
                const total = c.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total > 0 ? ((c.parsed / total) * 100).toFixed(1) : 0;
                return ` ${c.label}: ${c.parsed} (${pct}%)`;
              },
            },
          },
        },
      },
    });
  } else if (ctxAsignacion) {
    ctxAsignacion.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin tareas para mostrar</div>';
  }

  const ctxOverUser = document.getElementById("chartOverUser");
  if (ctxOverUser && CHART.overdue_user) {
    overUserChart = new Chart(ctxOverUser, {
      type: "bar",
      data: {
        labels: CHART.overdue_user.labels,
        datasets: [
          {
            label: "Atrasadas",
            data: CHART.overdue_user.data,
            backgroundColor: rgba("#ef4444", 0.6),
            borderColor: "#DC2626",
            borderWidth: 1,
          },
        ],
      },
      options: { ...baseOptions, indexAxis: "y" },
    });
  }

  const ctxOverDept = document.getElementById("chartOverDept");
  if (ctxOverDept && CHART.overdue_depto) {
    overDeptChart = new Chart(ctxOverDept, {
      type: "bar",
      data: {
        labels: CHART.overdue_depto.labels,
        datasets: [
          {
            label: "Atrasadas",
            data: CHART.overdue_depto.data,
            backgroundColor: rgba("#f97316", 0.6),
            borderColor: "#EA580C",
            borderWidth: 1,
          },
        ],
      },
      options: { ...baseOptions, indexAxis: "y" },
    });
  }

  const ctxTimeline = document.getElementById("chartTimeline");
  if (ctxTimeline && CHART.timeline) {
    timelineChart = new Chart(ctxTimeline, {
      type: "line",
      data: {
        labels: CHART.timeline.labels,
        datasets: [
          {
            label: "Tareas por fecha compromiso",
            data: CHART.timeline.data,
            borderColor: "#22C55E",
            backgroundColor: rgba("#22C55E", 0.15),
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointRadius: 0,
          },
        ],
      },
      options: baseOptions,
    });
  }

  // ── Horas por usuario (barras horizontales) ─────────────────
  const ctxHorasUsuario = document.getElementById("chartHorasUsuario");
  if (ctxHorasUsuario && CHART.horas_usuario && CHART.horas_usuario.labels.length) {
    const maxH = Math.max(...CHART.horas_usuario.data, 1);
    horasUsuarioChart = new Chart(ctxHorasUsuario, {
      type: "bar",
      data: {
        labels: CHART.horas_usuario.labels,
        datasets: [{
          label: "Horas",
          data: CHART.horas_usuario.data,
          backgroundColor: CHART.horas_usuario.data.map((v) => {
            const pct = v / maxH;
            if (pct > 0.66) return rgba("#6366f1", 0.80);
            if (pct > 0.33) return rgba("#3b82f6", 0.75);
            return rgba("#10b981", 0.70);
          }),
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (c) => ` ${c.parsed.x.toFixed(1)} h` },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { drawBorder: false },
            ticks: { callback: (v) => v + "h" },
          },
          y: { grid: { display: false } },
        },
      },
    });
  } else if (ctxHorasUsuario) {
    ctxHorasUsuario.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin horas registradas</div>';
  }

  // ── Horas por departamento (donut) ───────────────────────────
  const ctxHorasDepto = document.getElementById("chartHorasDepto");
  if (ctxHorasDepto && CHART.horas_depto && CHART.horas_depto.labels.length) {
    horasDeptoChart = new Chart(ctxHorasDepto, {
      type: "doughnut",
      data: {
        labels: CHART.horas_depto.labels,
        datasets: [{
          data: CHART.horas_depto.data,
          backgroundColor: CHART.horas_depto.colors,
          borderColor: "#ffffff",
          borderWidth: 2,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, padding: 8, font: { size: 11 } },
          },
          tooltip: {
            callbacks: {
              label: (c) => {
                const total = c.dataset.data.reduce((a, b) => a + b, 0);
                const pct = total > 0 ? ((c.parsed / total) * 100).toFixed(1) : 0;
                return ` ${c.label}: ${c.parsed.toFixed(1)}h (${pct}%)`;
              },
            },
          },
        },
      },
    });
  } else if (ctxHorasDepto) {
    ctxHorasDepto.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin horas por departamento</div>';
  }

  // ── Tickets por día ─────────────────────────────────────────
  const ctxHorasDia = document.getElementById("chartHorasDia");
  if (ctxHorasDia && CHART.tickets_dia && CHART.tickets_dia.labels.length) {
    horasDiaChart = new Chart(ctxHorasDia, {
      type: "line",
      data: {
        labels: CHART.tickets_dia.labels,
        datasets: [{
          label: "Tickets",
          data: CHART.tickets_dia.data,
          borderColor: "#6366f1",
          backgroundColor: rgba("#6366f1", 0.12),
          borderWidth: 2,
          tension: 0.4,
          fill: true,
          pointRadius: 3,
          pointHoverRadius: 5,
        }],
      },
      options: {
        ...baseOptions,
        plugins: {
          ...baseOptions.plugins,
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.parsed.y} ticket(s)`,
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  } else if (ctxHorasDia) {
    ctxHorasDia.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin tickets registrados aún</div>';
  }

  // ── Evolución de tareas: abiertas vs cerradas (línea) ────────
  const ctxCumplimiento = document.getElementById("chartCumplimiento");
  if (ctxCumplimiento && CHART.cumplimiento && CHART.cumplimiento.labels.length) {
    cumplimientoChart = new Chart(ctxCumplimiento, {
      type: "line",
      data: {
        labels: CHART.cumplimiento.labels,
        datasets: [
          {
            label: "Abiertas",
            data: CHART.cumplimiento.abiertas,
            borderColor: "#f59e0b",
            backgroundColor: rgba("#f59e0b", 0.15),
            tension: 0.35,
            fill: false,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: "#f59e0b",
          },
          {
            label: "Cerradas",
            data: CHART.cumplimiento.cerradas,
            borderColor: "#10b981",
            backgroundColor: rgba("#10b981", 0.15),
            tension: 0.35,
            fill: false,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: "#10b981",
          },
        ],
      },
      options: {
        ...baseOptions,
        plugins: {
          ...baseOptions.plugins,
          legend: { position: "bottom", labels: { boxWidth: 12, padding: 8 } },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  } else if (ctxCumplimiento) {
    ctxCumplimiento.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin tareas registradas</div>';
  }

  const applyTheme = () => {
    const ink = cssVar("--ink") || "#111827";
    const line = cssVar("--line") || "#E5E7EB";
    const muted = cssVar("--muted") || "#6B7280";

    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;

    [statusChart, overUserChart, overDeptChart, timelineChart,
     horasUsuarioChart, horasDeptoChart,
     horasDiaChart, cumplimientoChart].forEach((ch) => {
      if (!ch) return;

      if (ch.options.scales?.x?.ticks) ch.options.scales.x.ticks.color = muted;
      if (ch.options.scales?.y?.ticks) ch.options.scales.y.ticks.color = muted;
      if (ch.options.scales?.x?.grid) ch.options.scales.x.grid.color = line;
      if (ch.options.scales?.y?.grid) ch.options.scales.y.grid.color = line;

      ch.update();
    });
  };

  applyTheme();

  const toCSV = (labels, ds) => {
    const head = ["Etiqueta", ds.label].join(",");
    const rows = labels.map((lab, i) => `${lab},${ds.data[i] ?? ""}`);
    return [head, ...rows].join("\n");
  };

  const charts = {
    chartStatus:        statusChart,
    chartOverUser:      overUserChart,
    chartOverDept:      overDeptChart,
    chartTimeline:      timelineChart,
    chartHorasUsuario:  horasUsuarioChart,
    chartHorasDepto:    horasDeptoChart,
    chartHorasDia:      horasDiaChart,
    chartCumplimiento:  cumplimientoChart,
  };

  document.querySelectorAll(".chart-toolbar").forEach((tb) => {
    const id = tb.dataset.for;
    const ch = charts[id];
    const canvas = document.getElementById(id);

    if (!ch || !canvas) {
      const section = tb.closest(".section");
      const box = section ? section.querySelector(".chart-box") : null;
      if (box) box.innerHTML = '<div class="empty-state">Sin datos para mostrar</div>';
      return;
    }

    const btnFull = tb.querySelector(".ct-full");
    const btnPng = tb.querySelector(".ct-png");
    const btnCsv = tb.querySelector(".ct-csv");

    if (btnFull) {
      btnFull.addEventListener("click", () => {
        const card = canvas.closest(".section");
        if (card?.requestFullscreen) {
          card.requestFullscreen();
        }
      });
    }

    if (btnPng) {
      btnPng.addEventListener("click", () => {
        const a = document.createElement("a");
        a.href = canvas.toDataURL("image/png");
        a.download = `${id}.png`;
        a.click();
      });
    }

    if (btnCsv) {
      btnCsv.addEventListener("click", () => {
        let csv;
        if (ch.data.datasets.length > 1) {
          // Multi-dataset (e.g. cumplimiento)
          const head = ["Mes", ...ch.data.datasets.map((d) => d.label)].join(",");
          const rows = ch.data.labels.map((lab, i) =>
            [lab, ...ch.data.datasets.map((d) => d.data[i] ?? "")].join(",")
          );
          csv = [head, ...rows].join("\n");
        } else {
          csv = toCSV(ch.data.labels, ch.data.datasets[0]);
        }
        const blob = new Blob([csv], { type: "text/csv" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${id}.csv`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 500);
      });
    }
  });
})();

// ── Modal detalle completo — historial + agregar acción (mismo que /tareas) ──
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
  const respSelect = document.getElementById('tdDetRespSelect');

  const editBtn    = document.getElementById('tdDetBtnEditar');
  const editPanel  = document.getElementById('tdDetEditPanel');
  const editForm   = document.getElementById('tdDetEditForm');
  const editError  = document.getElementById('tdDetEditError');
  const editSuccess = document.getElementById('tdDetEditSuccess');

  let lastTarea = null;
  let lastEstados = [];
  let lastIsAdmin = false;
  let lastSolicitantes = [];

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
          Responsable: <strong class="text-body">${esc(t.responsable_nombre||t.responsable_username||'-')}</strong>
          &nbsp;·&nbsp; Creada por: <strong class="text-body">${esc(t.creador_nombre||t.creador_username||'-')}</strong>
        </div>
        ${estadoBadge(t.estado)}
      </div>
      ${t.descripcion ? `<div class="td-modal-desc mb-3">${esc(t.descripcion)}</div>` : ''}
      <div class="td-detalle-fechas">
        ${[['Creación',t.fecha_creacion],['Inicio',t.fecha_inicio],['Compromiso',t.fecha_compromiso],['Fin Planif.',t.fecha_fin],
           ...(t.fecha_cierre_real ? [['Cierre Real',t.fecha_cierre_real]] : [])]
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

  function toDtLocal(v) {
    if (!v) return '';
    return String(v).slice(0, 16).replace(' ', 'T');
  }

  function closeEditMode() {
    editPanel.classList.add('d-none');
    infoDiv.classList.remove('d-none');
  }

  function openEditMode() {
    if (!lastTarea) return;
    const t = lastTarea;
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val ?? ''; };

    set('tdDetFTitulo', t.titulo);
    set('tdDetFDesc', t.descripcion);
    set('tdDetFAvance', t.porcentaje_avance ?? 0);
    set('tdDetFFechaInicio', toDtLocal(t.fecha_inicio));
    set('tdDetFFechaCompromiso', toDtLocal(t.fecha_compromiso));
    set('tdDetFFechaFin', toDtLocal(t.fecha_fin));
    set('tdDetFFechaReal', toDtLocal(t.fecha_cierre_real));

    const fEstado = document.getElementById('tdDetFEstado');
    if (fEstado) {
      fEstado.innerHTML = '';
      lastEstados.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s;
        if (s === t.estado) opt.selected = true;
        fEstado.appendChild(opt);
      });
    }

    const solWrap = document.getElementById('tdDetSolicitanteWrap');
    const fSolicitante = document.getElementById('tdDetFSolicitante');
    if (solWrap && fSolicitante) {
      if (lastIsAdmin) {
        fSolicitante.innerHTML = '';
        lastSolicitantes.forEach(sol => {
          const opt = document.createElement('option');
          opt.value = sol.id; opt.textContent = sol.label;
          if (String(sol.id) === String(t.solicitante_id)) opt.selected = true;
          fSolicitante.appendChild(opt);
        });
        solWrap.classList.remove('d-none');
      } else {
        solWrap.classList.add('d-none');
      }
    }

    document.getElementById('tdDetEditCsrf').value =
      document.getElementById('td-csrf-token')?.dataset.token || '';
    editError.classList.add('d-none');
    editSuccess.classList.add('d-none');

    infoDiv.classList.add('d-none');
    editPanel.classList.remove('d-none');
  }

  editBtn?.addEventListener('click', openEditMode);
  document.getElementById('tdDetBtnCancelarEdit')?.addEventListener('click', closeEditMode);

  editForm?.addEventListener('submit', function(e) {
    e.preventDefault();
    if (!currentTaskId) return;
    const btn = document.getElementById('tdDetBtnGuardarEdit');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Guardando...'; }
    editError.classList.add('d-none');
    editSuccess.classList.add('d-none');

    fetch(`/tareas/${currentTaskId}/editar-ajax`, { method: 'POST', body: new FormData(editForm) })
      .then(r => r.json())
      .then(data => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Guardar cambios'; }
        if (data.ok) {
          editSuccess.textContent = data.message || 'Guardado correctamente.';
          editSuccess.classList.remove('d-none');
          setTimeout(() => { closeEditMode(); openModal(currentTaskId); }, 900);
        } else {
          editError.textContent = data.message || 'Error al guardar.';
          editError.classList.remove('d-none');
        }
      })
      .catch(() => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Guardar cambios'; }
        editError.textContent = 'Error de red al guardar.';
        editError.classList.remove('d-none');
      });
  });

  function openModal(taskId) {
    currentTaskId = taskId;
    loading.classList.remove('d-none');
    content.classList.add('d-none');
    formMsg.classList.add('d-none');
    closeEditMode();
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
        lastTarea = t;
        lastEstados = data.estados || [];
        lastIsAdmin = !!data.is_admin;
        lastSolicitantes = data.solicitantes || [];
        document.getElementById('tdDetCodigo').textContent = String(t.id||'').padStart(8,'0');
        document.getElementById('tdDetTitulo').textContent = t.titulo||'';
        renderInfo(t);
        renderHistorial(data.acciones);
        populateResp(data.responsables);

        if (editBtn) editBtn.classList.toggle('d-none', !data.editable);

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
    const obsHidden = document.getElementById('tdDetObservacion');
    if (obsHidden) obsHidden.value = detalles;

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

  // ── Mejorar texto con IA ─────────────────────────────
  document.getElementById('tdDetBtnMejorarIA')?.addEventListener('click', async function () {
    const textarea = document.getElementById('tdDetDetalles');
    const panel    = document.getElementById('tdDetIaMejoraPanel');
    const btn      = this;
    if (!textarea || !panel) return;

    const texto = textarea.value.trim();
    if (!texto) {
      alert('Escribe el detalle de actividad antes de mejorar.');
      return;
    }

    btn.disabled = true;
    const spinEl = document.createElement('span');
    spinEl.className = 'spinner-border spinner-border-sm me-1';
    btn.textContent = 'Mejorando…';
    btn.prepend(spinEl);

    panel.classList.remove('d-none');
    panel.textContent = '';

    const csrf = document.querySelector('meta[name="csrf-token"]')?.content
              || document.querySelector('input[name="csrf_token"]')?.value || '';

    try {
      const resp = await fetch('/api/tareas/mejorar-comentario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ texto }),
      });
      const data = await resp.json();

      panel.textContent = '';

      if (!data.ok) {
        const errEl = document.createElement('span');
        errEl.className = 'text-danger';
        errEl.textContent = data.error || 'Error al mejorar.';
        panel.appendChild(errEl);
        return;
      }

      const lbl = document.createElement('div');
      lbl.className = 'mb-1 fw-semibold td-fecha-val';
      const icoLbl = document.createElement('i');
      icoLbl.className = 'bi bi-stars text-warning me-1';
      lbl.appendChild(icoLbl);
      lbl.appendChild(document.createTextNode('Texto mejorado:'));
      panel.appendChild(lbl);

      const txt = document.createElement('div');
      txt.className = 'mb-2 td-fecha-val td-det-pretext';
      txt.textContent = data.texto_mejorado;
      panel.appendChild(txt);

      const btnUsar = document.createElement('button');
      btnUsar.type = 'button';
      btnUsar.className = 'btn btn-sm btn-outline-primary';
      const icoUsar = document.createElement('i');
      icoUsar.className = 'bi bi-clipboard-check me-1';
      btnUsar.appendChild(icoUsar);
      btnUsar.appendChild(document.createTextNode('Usar este texto'));
      btnUsar.addEventListener('click', () => {
        textarea.value = data.texto_mejorado;
        panel.classList.add('d-none');
        panel.textContent = '';
      });
      panel.appendChild(btnUsar);

    } catch (e) {
      panel.textContent = '';
      const errEl = document.createElement('span');
      errEl.className = 'text-danger';
      errEl.textContent = 'Error de conexión al mejorar.';
      panel.appendChild(errEl);
    } finally {
      btn.disabled = false;
      btn.textContent = '';
      const icoBtn = document.createElement('i');
      icoBtn.className = 'bi bi-stars me-1';
      btn.appendChild(icoBtn);
      btn.appendChild(document.createTextNode('Mejorar texto'));
    }
  });

  document.getElementById('tdDetBtnCerrar')?.addEventListener('click', () => {
    if (!currentTaskId) return;

    const textoDetalle = document.getElementById('tdDetDetalles')?.value.trim() || '';
    if (!textoDetalle) {
      const msg = document.getElementById('tdDetFormMsg');
      if (msg) {
        msg.className = 'alert alert-warning mt-2 py-2';
        msg.textContent = 'Escribe el detalle de la atención antes de cerrar la tarea.';
        msg.classList.remove('d-none');
      }
      return;
    }

    if (!confirm('¿Confirmas que deseas cerrar esta tarea? Esta acción actualizará el estado a Terminado.')) return;

    const btn = document.getElementById('tdDetBtnCerrar');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Cerrando...'; }

    const csrfToken = document.getElementById('td-csrf-token')?.dataset.token || '';
    const fd = new FormData();
    fd.append('csrf_token', csrfToken);
    fd.append('estado_accion', 'Finalizado');
    fd.append('detalles', textoDetalle);
    fd.append('observacion', textoDetalle);
    fd.append('cerrar_tarea', '1');

    fetch(`/tareas/${currentTaskId}/accion-ajax`, { method: 'POST', body: fd })
      .then(r => r.json())
      .then(data => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-flag-fill me-1"></i>Cerrar tarea'; }
        formMsg.className = `alert alert-${data.ok ? 'success' : 'danger'} mt-2 py-2`;
        formMsg.textContent = data.message || (data.ok ? 'Tarea cerrada correctamente.' : 'Error al cerrar.');
        formMsg.classList.remove('d-none');
        if (data.ok) {
          setTimeout(() => { closeModal(); window.location.reload(); }, 1500);
        }
      })
      .catch(() => {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-flag-fill me-1"></i>Cerrar tarea'; }
        formMsg.className = 'alert alert-danger mt-2 py-2';
        formMsg.textContent = 'Error de red al cerrar tarea.';
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