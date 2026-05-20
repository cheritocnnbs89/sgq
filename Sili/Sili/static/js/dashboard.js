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

  const applyTheme = () => {
    const ink = cssVar("--ink") || "#111827";
    const line = cssVar("--line") || "#E5E7EB";
    const muted = cssVar("--muted") || "#6B7280";

    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;

    [statusChart, overUserChart, overDeptChart, timelineChart].forEach((ch) => {
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
    chartStatus: statusChart,
    chartOverUser: overUserChart,
    chartOverDept: overDeptChart,
    chartTimeline: timelineChart,
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
        const csv = toCSV(ch.data.labels, ch.data.datasets[0]);
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