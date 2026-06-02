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
  let overUserChart = null;
  let overDeptChart = null;
  let timelineChart = null;
  let horasDiaChart = null;
  let horasUsuarioChart = null;
  let horasDeptoChart = null;
  let deptoMesChart = null;
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

  // ── Horas de atención por día ────────────────────────────────
  const ctxHorasDia = document.getElementById("chartHorasDia");
  if (ctxHorasDia && CHART.horas_dia && CHART.horas_dia.labels.length) {
    horasDiaChart = new Chart(ctxHorasDia, {
      type: "line",
      data: {
        labels: CHART.horas_dia.labels,
        datasets: [{
          label: "Horas de atención",
          data: CHART.horas_dia.data,
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
              label: (ctx) => ` ${ctx.parsed.y.toFixed(1)} h`,
            },
          },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: (v) => v + "h" } },
        },
      },
    });
  } else if (ctxHorasDia) {
    ctxHorasDia.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin datos de horas aún</div>';
  }

  // ── Tareas por departamento por mes (stacked bar) ────────────
  const ctxDeptoMes = document.getElementById("chartDeptoMes");
  if (ctxDeptoMes && CHART.depto_mes && CHART.depto_mes.datasets.length) {
    deptoMesChart = new Chart(ctxDeptoMes, {
      type: "bar",
      data: {
        labels: CHART.depto_mes.labels,
        datasets: CHART.depto_mes.datasets.map((ds) => ({
          label: ds.label,
          data: ds.data,
          backgroundColor: rgba(ds.color, 0.75),
          borderColor: ds.color,
          borderWidth: 1,
          borderRadius: 3,
        })),
      },
      options: {
        ...baseOptions,
        plugins: {
          ...baseOptions.plugins,
          legend: { position: "bottom", labels: { boxWidth: 12, padding: 10 } },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: { stacked: true, beginAtZero: true },
        },
      },
    });
  } else if (ctxDeptoMes) {
    ctxDeptoMes.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin datos por departamento</div>';
  }

  // ── Cumplimiento mensual (grouped bar) ───────────────────────
  const ctxCumplimiento = document.getElementById("chartCumplimiento");
  if (ctxCumplimiento && CHART.cumplimiento && CHART.cumplimiento.labels.length) {
    cumplimientoChart = new Chart(ctxCumplimiento, {
      type: "bar",
      data: {
        labels: CHART.cumplimiento.labels,
        datasets: [
          {
            label: "A tiempo",
            data: CHART.cumplimiento.a_tiempo,
            backgroundColor: rgba("#10b981", 0.7),
            borderColor: "#10b981",
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "Tardías",
            data: CHART.cumplimiento.atrasadas,
            backgroundColor: rgba("#ef4444", 0.7),
            borderColor: "#ef4444",
            borderWidth: 1,
            borderRadius: 4,
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
          y: { beginAtZero: true },
        },
      },
    });
  } else if (ctxCumplimiento) {
    ctxCumplimiento.closest(".chart-box").innerHTML =
      '<div class="empty-state">Sin cierres registrados</div>';
  }

  const applyTheme = () => {
    const ink = cssVar("--ink") || "#111827";
    const line = cssVar("--line") || "#E5E7EB";
    const muted = cssVar("--muted") || "#6B7280";

    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;

    [statusChart, overUserChart, overDeptChart, timelineChart,
     horasUsuarioChart, horasDeptoChart,
     horasDiaChart, deptoMesChart, cumplimientoChart].forEach((ch) => {
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
    chartDeptoMes:      deptoMesChart,
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
          // Multi-dataset (e.g. depto_mes, cumplimiento)
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

document.addEventListener("DOMContentLoaded", () => {
  const btnFiltrar = document.getElementById("btnFiltrarTareas");
  const btnReset = document.getElementById("btnResetTareas");

  if (btnFiltrar) {
    btnFiltrar.addEventListener("click", () => {
      const params = new URLSearchParams(window.location.search);

      const desde = document.getElementById("fDesde")?.value || "";
      const hasta = document.getElementById("fHasta")?.value || "";
      const depto = document.getElementById("fDepto")?.value || "";

      if (desde) params.set("fecha_desde", desde);
      else params.delete("fecha_desde");

      if (hasta) params.set("fecha_hasta", hasta);
      else params.delete("fecha_hasta");

      if (depto) params.set("depto", depto);
      else params.delete("depto");

      window.location.search = params.toString();
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", () => {
      window.location.href = window.location.pathname;
    });
  }
});