(function () {
  const chartDataNode = document.getElementById("reclamos-chart-data");
  if (!chartDataNode) return;

  let CHART = null;
  try {
    CHART = JSON.parse(chartDataNode.textContent || "null");
  } catch (err) {
    console.error("No se pudo parsear CHART:", err);
    return;
  }

  console.log("CHART reclamos:", CHART);
  console.log("CHART.vencidas:", CHART?.vencidas);
  console.log("CHART.vencidas_equipo:", CHART?.vencidas_equipo);

  const KPI_ABIERTAS = Number(chartDataNode.dataset.abiertas || 0);
  const KPI_CERRADAS = Number(chartDataNode.dataset.cerradas || 0);

  const centerTextPlugin = {
    id: "centerTextPlugin",
    afterDraw(chart, args, pluginOptions) {
      const { ctx, chartArea } = chart;
      if (!chartArea) return;

      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data || !meta.data.length) return;

      const x = meta.data[0].x;
      const y = meta.data[0].y;

      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      ctx.fillStyle = pluginOptions.color || "#111827";
      ctx.font = "700 24px sans-serif";
      ctx.fillText(pluginOptions.value || "", x, y - 8);

      ctx.fillStyle = pluginOptions.subColor || "#6B7280";
      ctx.font = "12px sans-serif";
      ctx.fillText(pluginOptions.label || "", x, y + 14);

      ctx.restore();
    }
  };

  const barValueLabelsPlugin = {
    id: "barValueLabelsPlugin",
    afterDatasetsDraw(chart, args, pluginOptions) {
      if (!pluginOptions || !pluginOptions.enabled) return;

      const { ctx } = chart;
      const datasetIndex = pluginOptions.datasetIndex ?? 0;
      const meta = chart.getDatasetMeta(datasetIndex);
      const dataset = chart.data.datasets[datasetIndex];

      if (!meta || !dataset) return;

      ctx.save();
      ctx.fillStyle = pluginOptions.color || (cssVar("--ink") || "#111827");
      ctx.font = pluginOptions.font || "600 12px sans-serif";
      ctx.textAlign = pluginOptions.textAlign || "left";
      ctx.textBaseline = "middle";

      meta.data.forEach((bar, index) => {
        const rawValue = Array.isArray(dataset.data) ? dataset.data[index] : null;
        const labelText = typeof pluginOptions.formatter === "function"
          ? pluginOptions.formatter(rawValue, index, chart)
          : String(rawValue ?? "");

        if (!labelText) return;

        const offsetX = pluginOptions.offsetX ?? 6;
        const offsetY = pluginOptions.offsetY ?? 0;

        ctx.fillText(labelText, bar.x + offsetX, bar.y + offsetY);
      });

      ctx.restore();
    }
  };

  Chart.register(centerTextPlugin);
  Chart.register(barValueLabelsPlugin);

  function emptyChart(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const box = canvas.closest(".chart-box");
    if (!box) return;

    box.innerHTML = `<div class="empty-state">${message}</div>`;
  }

  function buildCharts() {
    if (!CHART) return;

    // ====== ESTADOS ======
    if (CHART.estados?.labels?.length) {
      const el = document.getElementById("chartEstados");
      if (el) {
        const ctx = el.getContext("2d");
        const base = cssVar("--primary") || "#3b82f6";
        const grad = makeBarGradient(ctx, base);

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.estados.labels,
            datasets: [
              {
                label: "OM",
                data: CHART.estados.total,
                backgroundColor: grad,
                borderColor: rgbaHex(base, 1),
                borderWidth: 1.2
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
          }
        });
      }
    }

    // ====== MESES ======
    if (CHART.meses?.labels?.length) {
      const el = document.getElementById("chartMeses");
      if (el) {
        const ctx = el.getContext("2d");
        const base = "#22c55e";
        const grad = makeLineGradient(ctx, base);

        new Chart(ctx, {
          type: "line",
          data: {
            labels: CHART.meses.labels,
            datasets: [
              {
                label: "OM creadas",
                data: CHART.meses.total,
                borderColor: rgbaHex(base, 1),
                backgroundColor: grad,
                tension: 0.35,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            scales: { y: { beginAtZero: true } }
          }
        });
      }
    }

    // ====== IMPUTADOS ======
    if (CHART.imputados?.labels?.length) {
      const el = document.getElementById("chartImputados");
      if (el) {
        const ctx = el.getContext("2d");
        const baseA = "#3b82f6";
        const baseC = "#10b981";
        const gradA = makeBarGradient(ctx, baseA);
        const gradC = makeBarGradient(ctx, baseC);

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.imputados.labels,
            datasets: [
              {
                label: "Abiertas",
                data: CHART.imputados.abiertas,
                backgroundColor: gradA,
                borderColor: rgbaHex(baseA, 1),
                borderWidth: 1.2
              },
              {
                label: "Cerradas",
                data: CHART.imputados.cerradas,
                backgroundColor: gradC,
                borderColor: rgbaHex(baseC, 1),
                borderWidth: 1.2
              }
            ]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { beginAtZero: true } }
          }
        });
      }
    }

    // ====== PROCESOS (CREADAS) ======
    if (CHART.procesos?.labels?.length) {
      const el = document.getElementById("chartProcesos");
      if (el) {
        const ctx = el.getContext("2d");
        const baseA = "#6366f1";
        const baseC = "#10b981";
        const gradA = makeBarGradient(ctx, baseA);
        const gradC = makeBarGradient(ctx, baseC);

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.procesos.labels,
            datasets: [
              {
                label: "Abiertas",
                data: CHART.procesos.abiertas,
                backgroundColor: gradA,
                borderColor: rgbaHex(baseA, 1),
                borderWidth: 1.2
              },
              {
                label: "Cerradas",
                data: CHART.procesos.cerradas,
                backgroundColor: gradC,
                borderColor: rgbaHex(baseC, 1),
                borderWidth: 1.2
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
          }
        });
      }
    } else {
      console.warn("Sin datos para procesos", CHART.procesos);
    }

    // ====== TIPOS ======
    if (CHART.tipos?.labels?.length) {
      const el = document.getElementById("chartTipos");
      if (el) {
        const ctx = el.getContext("2d");

        const totalPorTipo = CHART.tipos.labels.map((_, i) =>
          Number(CHART.tipos.abiertas[i] || 0) + Number(CHART.tipos.cerradas[i] || 0)
        );

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.tipos.labels,
            datasets: [
              {
                label: "Abiertas",
                data: CHART.tipos.abiertas,
                backgroundColor: "#3b82f6",
                borderColor: "#2563eb",
                borderWidth: 1.2,
                borderRadius: 6,
                borderSkipped: false
              },
              {
                label: "Cerradas",
                data: CHART.tipos.cerradas,
                backgroundColor: "#10b981",
                borderColor: "#059669",
                borderWidth: 1.2,
                borderRadius: 6,
                borderSkipped: false
              }
            ]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            layout: {
              padding: { right: 30 }
            },
            scales: {
              x: {
                stacked: true,
                beginAtZero: true,
                ticks: { precision: 0 },
                title: {
                  display: true,
                  text: "Cantidad de OM"
                }
              },
              y: {
                stacked: true,
                ticks: {
                  color: cssVar("--ink") || "#111827",
                  callback: function (value) {
                    const label = this.getLabelForValue(value) || "";
                    return label.length > 28 ? label.slice(0, 28) + "…" : label;
                  }
                }
              }
            },
            plugins: {
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827",
                  usePointStyle: true,
                  pointStyle: "rectRounded"
                }
              },
              tooltip: {
                callbacks: {
                  title: function (context) {
                    return context[0]?.label || "";
                  },
                  label: function (context) {
                    const i = context.dataIndex;
                    const abiertas = Number(CHART.tipos.abiertas[i] || 0);
                    const cerradas = Number(CHART.tipos.cerradas[i] || 0);

                    if (context.dataset.label === "Abiertas") {
                      return `Abiertas: ${abiertas}`;
                    }
                    if (context.dataset.label === "Cerradas") {
                      return `Cerradas: ${cerradas}`;
                    }
                    return `${context.dataset.label}: ${context.raw}`;
                  },
                  footer: function (items) {
                    const i = items[0]?.dataIndex ?? 0;
                    return `Total: ${totalPorTipo[i]}`;
                  }
                }
              },
              barValueLabelsPlugin: {
                enabled: true,
                datasetIndex: 1,
                color: cssVar("--ink") || "#111827",
                font: "600 12px sans-serif",
                formatter: function (value, index) {
                  return `${totalPorTipo[index]}`;
                }
              }
            }
          }
        });
      }
    }

    // ====== PROCESOS INVOLUCRADOS ======
    if (CHART.procesos_involucrados?.labels?.length) {
      const el = document.getElementById("chartProcesosInvolucrados");

      if (el) {
        const ctx = el.getContext("2d");

        const labels = CHART.procesos_involucrados.labels || [];
        const abiertas = CHART.procesos_involucrados.abiertas || [];
        const cerradas = CHART.procesos_involucrados.cerradas || [];
        const total = CHART.procesos_involucrados.total || labels.map((_, i) =>
          Number(abiertas[i] || 0) + Number(cerradas[i] || 0)
        );

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: labels,
            datasets: [
              {
                label: "Abiertas",
                data: abiertas,
                backgroundColor: "#f59e0b",
                borderColor: "#d97706",
                borderWidth: 1.2,
                borderRadius: 6,
                borderSkipped: false
              },
              {
                label: "Cerradas",
                data: cerradas,
                backgroundColor: "#10b981",
                borderColor: "#059669",
                borderWidth: 1.2,
                borderRadius: 6,
                borderSkipped: false
              }
            ]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            layout: {
              padding: { right: 42 }
            },
            animation: {
              onComplete() {
                const { ctx } = this;

                ctx.save();
                ctx.fillStyle = cssVar("--ink") || "#111827";
                ctx.font = "600 12px sans-serif";
                ctx.textAlign = "left";
                ctx.textBaseline = "middle";

                const metaAbiertas = this.getDatasetMeta(0);
                const metaCerradas = this.getDatasetMeta(1);

                labels.forEach((_, i) => {
                  const barA = metaAbiertas.data[i];
                  const barC = metaCerradas.data[i];

                  if (!barA && !barC) return;

                  const xA = barA ? barA.x : 0;
                  const xC = barC ? barC.x : 0;
                  const y = barC ? barC.y : (barA ? barA.y : 0);

                  ctx.fillText(String(total[i] || 0), Math.max(xA, xC) + 8, y);
                });

                ctx.restore();
              }
            },
            scales: {
              x: {
                stacked: true,
                beginAtZero: true,
                ticks: { precision: 0 },
                title: {
                  display: true,
                  text: "Participaciones de procesos"
                }
              },
              y: {
                stacked: true,
                ticks: {
                  color: cssVar("--ink") || "#111827",
                  callback: function (value) {
                    const label = this.getLabelForValue(value) || "";
                    return label.length > 42 ? label.slice(0, 42) + "…" : label;
                  }
                }
              }
            },
            plugins: {
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827",
                  usePointStyle: true,
                  pointStyle: "rectRounded"
                }
              },
              tooltip: {
                callbacks: {
                  title: function (context) {
                    return context[0]?.label || "";
                  },
                  label: function (context) {
                    const i = context.dataIndex;
                    const abiertasVal = Number(abiertas[i] || 0);
                    const cerradasVal = Number(cerradas[i] || 0);

                    if (context.dataset.label === "Abiertas") {
                      return `Abiertas: ${abiertasVal}`;
                    }

                    if (context.dataset.label === "Cerradas") {
                      return `Cerradas: ${cerradasVal}`;
                    }

                    return `${context.dataset.label}: ${context.raw}`;
                  },
                  footer: function (items) {
                    const i = items[0]?.dataIndex ?? 0;
                    return `Total participaciones de procesos: ${total[i] || 0}`;
                  }
                }
              }
            }
          }
        });
      }
    } else {
      emptyChart("chartProcesosInvolucrados", "No hay procesos involucrados para mostrar");
    }
    // ====== LÍNEA DE TIEMPO / CUELLOS DE BOTELLA ======
if (CHART.linea_abiertas?.cuellos?.labels?.length) {
  const el = document.getElementById("chartCuellosBotella");

  if (el) {
    const ctx = el.getContext("2d");

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: CHART.linea_abiertas.cuellos.labels,
        datasets: [{
          label: "OM abiertas",
          data: CHART.linea_abiertas.cuellos.total,
          backgroundColor: "#f59e0b",
          borderColor: "#d97706",
          borderWidth: 1.2,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: { right: 36 }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
            title: {
              display: true,
              text: "Cantidad de OM abiertas"
            }
          },
          y: {
            ticks: {
              color: cssVar("--ink") || "#111827"
            }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: {
              color: cssVar("--ink") || "#111827"
            }
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                const i = context.dataIndex;
                const total = Number(CHART.linea_abiertas.cuellos.total[i] || 0);
                const prom = Number(CHART.linea_abiertas.cuellos.dias_promedio[i] || 0).toFixed(2);
                return [
                  `OM abiertas: ${total}`,
                  `Promedio en etapa: ${prom} días`
                ];
              }
            }
          },
          barValueLabelsPlugin: {
            enabled: true,
            datasetIndex: 0,
            color: cssVar("--ink") || "#111827",
            font: "600 12px sans-serif",
            formatter: (value) => `${value ?? 0}`
          }
        }
      }
    });
  }
} else {
  emptyChart("chartCuellosBotella", "No hay cuellos de botella para mostrar");
}

if (CHART.linea_abiertas?.aging_etapas?.labels?.length) {
  const el = document.getElementById("chartAgingEtapas");

  if (el) {
    const ctx = el.getContext("2d");

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: CHART.linea_abiertas.aging_etapas.labels,
        datasets: [{
          label: "Días promedio",
          data: CHART.linea_abiertas.aging_etapas.dias_promedio,
          backgroundColor: "#ef4444",
          borderColor: "#dc2626",
          borderWidth: 1.2,
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: { right: 44 }
        },
        scales: {
          x: {
            beginAtZero: true,
            title: {
              display: true,
              text: "Días promedio en etapa"
            }
          },
          y: {
            ticks: {
              color: cssVar("--ink") || "#111827",
              callback: function (value) {
                const label = this.getLabelForValue(value) || "";
                return label.length > 44 ? label.slice(0, 44) + "…" : label;
              }
            }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: {
              color: cssVar("--ink") || "#111827"
            }
          },
          tooltip: {
            callbacks: {
              title: function (context) {
                return context[0]?.label || "";
              },
              label: function (context) {
                const i = context.dataIndex;
                const dias = Number(CHART.linea_abiertas.aging_etapas.dias_promedio[i] || 0).toFixed(2);
                const total = Number(CHART.linea_abiertas.aging_etapas.total[i] || 0);
                return [
                  `Días promedio: ${dias}`,
                  `OM en esta etapa: ${total}`
                ];
              }
            }
          },
          barValueLabelsPlugin: {
            enabled: true,
            datasetIndex: 0,
            color: cssVar("--ink") || "#111827",
            font: "600 12px sans-serif",
            formatter: (value) => `${Number(value || 0).toFixed(1)} d`
          }
        }
      }
    });
  }
} else {
  emptyChart("chartAgingEtapas", "No hay aging por etapa para mostrar");
}

renderTimelineOmAbiertas();

    // ====== TIEMPO PROMEDIO DE RESPUESTA POR PROCESO ======
    if (CHART.tiempos?.labels?.length) {
      const el = document.getElementById("chartTiempos");
      if (el) {
        const ctx = el.getContext("2d");
        const META_DIAS = 5;

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.tiempos.labels,
            datasets: [
              {
                label: "Promedio días de respuesta",
                data: CHART.tiempos.promedio,
                backgroundColor: CHART.tiempos.promedio.map(v => v > 5 ? "#ef4444" : "#22c55e"),
                borderColor: CHART.tiempos.promedio.map(v => v > 5 ? "#dc2626" : "#16a34a"),
                borderWidth: 1.2,
                borderRadius: 6
              },
              {
                label: "Meta (5 días)",
                data: Array(CHART.tiempos.labels.length).fill(META_DIAS),
                type: "line",
                borderColor: "#ef4444",
                borderWidth: 2,
                borderDash: [6, 6],
                pointRadius: 0,
                fill: false
              }
            ]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                beginAtZero: true,
                title: {
                  display: true,
                  text: "Días promedio"
                }
              }
            },
            plugins: {
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827"
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    if (context.dataset.label === "Meta (5 días)") {
                      return "Meta objetivo: 5 días";
                    }

                    const i = context.dataIndex;
                    const dias = Number(CHART.tiempos.promedio[i] || 0).toFixed(2);
                    const total = Number(CHART.tiempos.total_om[i] || 0);

                    return ` ${dias} días promedio | ${total} OM`;
                  }
                }
              }
            }
          }
        });
      }
    }

    // ====== PROCESOS ABIERTAS PIE ======
    if (CHART.procesos?.labels?.length && CHART.procesos?.abiertas?.length) {
      const el = document.getElementById("chartProcesosAbiertasPie");
      if (el) {
        const ctx = el.getContext("2d");

        const labelsAbiertas = [];
        const dataAbiertas = [];

        CHART.procesos.labels.forEach((label, i) => {
          const val = Number(CHART.procesos.abiertas[i] || 0);
          if (val > 0) {
            labelsAbiertas.push(label);
            dataAbiertas.push(val);
          }
        });

        if (labelsAbiertas.length) {
          new Chart(ctx, {
            type: "doughnut",
            data: {
              labels: labelsAbiertas,
              datasets: [{
                label: "OM abiertas",
                data: dataAbiertas,
                backgroundColor: [
                  "#f59e0b", "#fbbf24", "#f97316", "#fb7185", "#a855f7",
                  "#6366f1", "#3b82f6", "#06b6d4", "#14b8a6", "#84cc16",
                  "#eab308", "#ef4444"
                ].slice(0, labelsAbiertas.length),
                borderColor: "#ffffff",
                borderWidth: 2,
                hoverOffset: 10
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: "42%",
              plugins: {
                centerTextPlugin: {
                  value: KPI_ABIERTAS,
                  label: "Abiertas",
                  color: "#f59e0b",
                  subColor: cssVar("--muted") || "#6B7280"
                },
                legend: {
                  position: "right",
                  labels: {
                    boxWidth: 14,
                    padding: 14,
                    color: cssVar("--ink") || "#111827",
                    font: { size: 11 }
                  }
                },
                tooltip: {
                  callbacks: {
                    label: function (context) {
                      const value = Number(context.raw || 0);
                      const total = context.dataset.data.reduce((a, b) => a + b, 0);
                      const pct = total ? ((value * 100) / total).toFixed(2) : "0.00";
                      return `${context.label}: ${value} abiertas (${pct}%)`;
                    }
                  }
                }
              }
            }
          });
        }
      }
    }

    // ====== PROCESOS CERRADAS PIE ======
    if (CHART.procesos?.labels?.length && CHART.procesos?.cerradas?.length) {
      const el = document.getElementById("chartProcesosCerradasPie");
      if (el) {
        const ctx = el.getContext("2d");

        const labelsCerradas = [];
        const dataCerradas = [];

        CHART.procesos.labels.forEach((label, i) => {
          const val = Number(CHART.procesos.cerradas[i] || 0);
          if (val > 0) {
            labelsCerradas.push(label);
            dataCerradas.push(val);
          }
        });

        if (labelsCerradas.length) {
          new Chart(ctx, {
            type: "doughnut",
            data: {
              labels: labelsCerradas,
              datasets: [{
                label: "OM cerradas",
                data: dataCerradas,
                backgroundColor: [
                  "#10b981", "#22c55e", "#14b8a6", "#06b6d4", "#3b82f6",
                  "#6366f1", "#8b5cf6", "#a855f7", "#84cc16", "#65a30d",
                  "#16a34a", "#0ea5e9"
                ].slice(0, labelsCerradas.length),
                borderColor: "#ffffff",
                borderWidth: 2,
                hoverOffset: 10
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              cutout: "42%",
              plugins: {
                centerTextPlugin: {
                  value: KPI_CERRADAS,
                  label: "Cerradas",
                  color: "#10b981",
                  subColor: cssVar("--muted") || "#6B7280"
                },
                legend: {
                  position: "right",
                  labels: {
                    boxWidth: 14,
                    padding: 14,
                    color: cssVar("--ink") || "#111827",
                    font: { size: 11 }
                  }
                },
                tooltip: {
                  callbacks: {
                    label: function (context) {
                      const value = Number(context.raw || 0);
                      const total = context.dataset.data.reduce((a, b) => a + b, 0);
                      const pct = total ? ((value * 100) / total).toFixed(2) : "0.00";
                      return `${context.label}: ${value} cerradas (${pct}%)`;
                    }
                  }
                }
              }
            }
          });
        }
      }
    }

    // ====== DÍAS ======
    if (CHART.dias?.labels?.length) {
      const el = document.getElementById("chartDias");
      if (el) {
        const ctx = el.getContext("2d");
        const base = "#0ea5e9";
        const grad = makeLineGradient(ctx, base);

        new Chart(ctx, {
          type: "line",
          data: {
            labels: CHART.dias.labels,
            datasets: [{
              label: "OM creadas por día",
              data: CHART.dias.total,
              borderColor: rgbaHex(base, 1),
              backgroundColor: grad,
              tension: 0.3,
              fill: true,
              pointRadius: 3,
              pointHoverRadius: 5
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
              mode: "index",
              intersect: false
            },
            scales: {
              x: {
                ticks: {
                  maxRotation: 45,
                  minRotation: 45
                }
              },
              y: {
                beginAtZero: true,
                title: {
                  display: true,
                  text: "Cantidad de OM"
                }
              }
            },
            plugins: {
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827"
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    return ` ${context.raw || 0} OM`;
                  }
                }
              }
            }
          }
        });
      }
    }

    // ====== TOP PROCESOS CON MÁS OM VENCIDAS ======
    if (CHART.vencidas?.labels?.length) {
      const el = document.getElementById("chartVencidas");
      if (el) {
        const ctx = el.getContext("2d");

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.vencidas.labels,
            datasets: [{
              label: "OM Sin Respuestas",
              data: CHART.vencidas.total,
              backgroundColor: "#ef4444",
              borderColor: "#dc2626",
              borderWidth: 1.2,
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                beginAtZero: true,
                title: {
                  display: true,
                  text: "Cantidad de Sin Respuestas"
                },
                ticks: { precision: 0 }
              },
              y: {
                ticks: {
                  color: cssVar("--ink") || "#111827"
                }
              }
            },
            plugins: {
              barValueLabelsPlugin: {
                enabled: true,
                datasetIndex: 0,
                color: cssVar("--ink") || "#111827",
                font: "600 12px sans-serif",
                formatter: (value) => `${value ?? 0}`
              },
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827"
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    const total = Number(context.raw || 0);
                    return ` Total OM vencidas: ${total}`;
                  }
                }
              }
            }
          }
        });
      }
    } else {
      emptyChart("chartVencidas", "No hay OM vencidas para mostrar");
    }

    // ====== TOP MIEMBROS DE EQUIPO CON MAYOR ATRASO EN RESPONDER ======
    if (CHART.vencidas_equipo?.labels?.length) {
      const el = document.getElementById("chartVencidasEquipo");
      if (el) {
        const ctx = el.getContext("2d");

        new Chart(ctx, {
          type: "bar",
          data: {
            labels: CHART.vencidas_equipo.labels,
            datasets: [{
              label: "Máximo de días sin responder",
              data: CHART.vencidas_equipo.atraso_maximo,
              backgroundColor: CHART.vencidas_equipo.atraso_maximo.map(v =>
                v > 30 ? "#b91c1c" : v > 15 ? "#ea580c" : "#dc2626"
              ),
              borderColor: CHART.vencidas_equipo.atraso_maximo.map(v =>
                v > 30 ? "#991b1b" : v > 15 ? "#c2410c" : "#b91c1c"
              ),
              borderWidth: 1.2,
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            animation: {
              onComplete() {
                const { ctx } = this;
                ctx.save();
                ctx.fillStyle = cssVar("--ink") || "#111827";
                ctx.font = "600 12px sans-serif";

                this.data.datasets.forEach((dataset, datasetIndex) => {
                  const meta = this.getDatasetMeta(datasetIndex);
                  meta.data.forEach((bar, index) => {
                    const dias = Number(CHART.vencidas_equipo.atraso_maximo[index] || 0).toFixed(0);
                    const total = Number(CHART.vencidas_equipo.total[index] || 0);
                    const txt = `${dias} d | ${total} OM`;

                    ctx.textAlign = "left";
                    ctx.textBaseline = "middle";
                    ctx.fillText(txt, bar.x + 6, bar.y);
                  });
                });

                ctx.restore();
              }
            },
            scales: {
              x: {
                beginAtZero: true,
                suggestedMax: Math.max(...CHART.vencidas_equipo.atraso_maximo, 5) + 4,
                title: {
                  display: true,
                  text: "Días máximos de atraso"
                },
                ticks: { precision: 0 }
              },
              y: {
                ticks: {
                  color: cssVar("--ink") || "#111827",
                  callback: function (value) {
                    const label = this.getLabelForValue(value) || "";
                    return label.length > 42 ? label.slice(0, 42) + "…" : label;
                  }
                }
              }
            },
            plugins: {
              legend: {
                position: "top",
                labels: {
                  color: cssVar("--ink") || "#111827"
                }
              },
              tooltip: {
                callbacks: {
                  title: function (context) {
                    const i = context[0].dataIndex;
                    return CHART.vencidas_equipo.miembro?.[i] || CHART.vencidas_equipo.labels[i] || "";
                  },
                  label: function (context) {
                    const i = context.dataIndex;
                    const sponsor = CHART.vencidas_equipo.sponsor[i] || "SIN SPONSOR";
                    const proceso = CHART.vencidas_equipo.proceso[i] || "SIN PROCESO";
                    const vencidas = Number(CHART.vencidas_equipo.total[i] || 0);
                    const prom = Number(CHART.vencidas_equipo.atraso_promedio[i] || 0).toFixed(2);
                    const max = Number(CHART.vencidas_equipo.atraso_maximo[i] || 0).toFixed(2);

                    return [
                      `Sponsor: ${sponsor}`,
                      `Proceso: ${proceso}`,
                      `Total OM vencidas: ${vencidas}`,
                      `Atraso promedio: ${prom} días`,
                      `Atraso máximo: ${max} días`
                    ];
                  }
                }
              }
            }
          }
        });
      }
    } else {
      emptyChart("chartVencidasEquipo", "No hay miembros con OM vencidas para mostrar");
    }
  }
function renderTimelineOmAbiertas() {
  const body = document.getElementById("timelineOmBody");
  if (!body) return;

  const items = CHART.linea_abiertas?.items || [];

  if (!items.length) {
    body.innerHTML = `
      <tr>
        <td colspan="8" class="text-muted small">No hay OM abiertas para mostrar.</td>
      </tr>
    `;
    return;
  }

  body.innerHTML = items.map(item => {
    const pasos = item.pasos || {};

    const timeline = [
      timelineStep("Creada", pasos.creada),
      timelineStep("Sponsor", pasos.sponsor),
      timelineStep("Equipo", pasos.equipo),
      timelineStep("Resp. equipo", pasos.respuesta_equipo),
      timelineStep("Resp. sponsor", pasos.respuesta_sponsor),
      timelineStep("Aprobación", pasos.aprobacion)
    ].join(`<span class="tl-sep">─</span>`);

    const cuelloClass = cuelloBadgeClass(item.cuello);
    const diasClass = Number(item.dias_en_etapa || 0) > 5 ? "text-danger fw-bold" : "text-muted";

    return `
      <tr>
        <td>
          <div class="fw-semibold">${escapeHtmlDash(item.codigo || "")}</div>
          <div class="small text-muted">${escapeHtmlDash(item.fecha_inicio || "")}</div>
        </td>

        <td>
          <div class="fw-semibold">${escapeHtmlDash(item.proceso || "SIN PROCESO")}</div>
          <div class="small text-muted">${escapeHtmlDash(item.cliente || "")}</div>
        </td>

        <td class="text-end">
          <span class="fw-semibold">${Number(item.dias_abierta || 0)}</span>
          <span class="small text-muted">d</span>
        </td>

        <td class="text-end">
          <span class="${diasClass}">${Number(item.dias_en_etapa || 0)} d</span>
        </td>

        <td>
          <div class="fw-semibold">${escapeHtmlDash(item.etapa_actual || "")}</div>
          <div class="small text-muted">${escapeHtmlDash(item.motivo || "")}</div>
        </td>

        <td>
          <span class="badge rounded-pill ${cuelloClass}">
            ${escapeHtmlDash(item.cuello || "")}
          </span>
        </td>

        <td>
          <div class="small">${escapeHtmlDash(item.responsable_actual || "")}</div>
        </td>

        <td>
          <div class="tl-wrap">${timeline}</div>
        </td>
      </tr>
    `;
  }).join("");
}

function timelineStep(label, done) {
  const cls = done ? "tl-step tl-ok" : "tl-step tl-pending";
  const icon = done ? "✓" : "○";

  return `
    <span class="${cls}" title="${escapeHtmlDash(label)}">
      <span class="tl-dot">${icon}</span>
      <span class="tl-label">${escapeHtmlDash(label)}</span>
    </span>
  `;
}

function cuelloBadgeClass(cuello) {
  const c = String(cuello || "").toLowerCase();

  if (c.includes("equipo")) return "text-bg-danger";
  if (c.includes("sponsor")) return "text-bg-warning";
  if (c.includes("aprobador") || c.includes("jefe")) return "text-bg-primary";
  if (c.includes("sin")) return "text-bg-secondary";

  return "text-bg-info";
}

function escapeHtmlDash(str) {
  return String(str || "").replace(/[&<>"']/g, m => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[m]));
}
  function rgbaHex(hex, a) {
    if (!hex) return `rgba(0,0,0,${a})`;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${a})`;
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function makeBarGradient(ctx, hex) {
    const g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    g.addColorStop(0, rgbaHex(hex, 0.15));
    g.addColorStop(0.5, rgbaHex(hex, 0.8));
    g.addColorStop(1, rgbaHex(hex, 1));
    return g;
  }

  function makeLineGradient(ctx, hex) {
    const g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    g.addColorStop(0, rgbaHex(hex, 0.35));
    g.addColorStop(1, rgbaHex(hex, 0.0));
    return g;
  }

  function aplicarFiltrosDashboard() {
    const desde = (document.getElementById("fDesde")?.value || "").trim();
    const hasta = (document.getElementById("fHasta")?.value || "").trim();
    const depto = (document.getElementById("fDepto")?.value || "").trim();
    const proceso = (document.getElementById("fProceso")?.value || "").trim();

    const url = new URL(window.location.href);
    url.searchParams.delete("desde");
    url.searchParams.delete("hasta");
    url.searchParams.delete("depto");
    url.searchParams.delete("proceso");

    if (desde) url.searchParams.set("desde", desde);
    if (hasta) url.searchParams.set("hasta", hasta);
    if (depto) url.searchParams.set("depto", depto);
    if (proceso) url.searchParams.set("proceso", proceso);

    window.location.href = url.toString();
  }

  function resetFiltrosDashboard() {
    const url = new URL(window.location.href);
    url.searchParams.delete("desde");
    url.searchParams.delete("hasta");
    url.searchParams.delete("depto");
    url.searchParams.delete("proceso");
    window.location.href = url.pathname;
  }

  document.addEventListener("DOMContentLoaded", function () {
    buildCharts();

    const btnFiltrar = document.getElementById("btnFiltrar");
    const btnReset = document.getElementById("btnReset");
    const fDesde = document.getElementById("fDesde");
    const fHasta = document.getElementById("fHasta");
    const fDepto = document.getElementById("fDepto");
    const fProceso = document.getElementById("fProceso");

    if (btnFiltrar) {
      btnFiltrar.addEventListener("click", aplicarFiltrosDashboard);
    }

    if (btnReset) {
      btnReset.addEventListener("click", resetFiltrosDashboard);
    }

    [fDesde, fHasta].forEach(el => {
      if (!el) return;
      el.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          aplicarFiltrosDashboard();
        }
      });
    });

    if (fProceso) {
      fProceso.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          aplicarFiltrosDashboard();
        }
      });
    }

    if (fDepto) {
      fDepto.addEventListener("change", function () {
        // aplicarFiltrosDashboard();
      });
    }
  });
})();