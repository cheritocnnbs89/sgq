(function () {
  function fmtUSD(v) {
    try {
      return new Intl.NumberFormat('es-EC', {
        style: 'currency',
        currency: 'USD'
      }).format(v || 0);
    } catch (e) {
      return '$ ' + Number(v || 0).toFixed(2);
    }
  }

  function parseJSONAttr(el, name, fallback) {
    try {
      const raw = el.getAttribute(name);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const dataEl = document.getElementById('gastos-dashboard-data');
    if (!dataEl || typeof Chart === 'undefined') return;

    const serieDiasLabels = parseJSONAttr(dataEl, 'data-serie-dias-labels', []);
    const serieDiasTotals = parseJSONAttr(dataEl, 'data-serie-dias-totals', []);

    const porMesLabels = parseJSONAttr(dataEl, 'data-por-mes-labels', []);
    const porMesCon = parseJSONAttr(dataEl, 'data-por-mes-con', []);
    const porMesSin = parseJSONAttr(dataEl, 'data-por-mes-sin', []);

    const ccb = Number(dataEl.getAttribute('data-ccb') || 0);
    const noCcb = Number(dataEl.getAttribute('data-no-ccb') || 0);

    const nTotal = Number(dataEl.getAttribute('data-n-total') || 0);
    const nSinSap = Number(dataEl.getAttribute('data-n-sin-sap') || 0);
    const nGa = Number(dataEl.getAttribute('data-n-ga') || 0);
    const nGf = Number(dataEl.getAttribute('data-n-gf') || 0);
    const nGg = Number(dataEl.getAttribute('data-n-gg') || 0);

    const serieUsuariosLabels = parseJSONAttr(dataEl, 'data-serie-usuarios-labels', []);
    const serieUsuariosTotals = parseJSONAttr(dataEl, 'data-serie-usuarios-totals', []);

    const depMesLabels = parseJSONAttr(dataEl, 'data-dep-mes-labels', []);
    const depMesSeries = parseJSONAttr(dataEl, 'data-dep-mes-series', []);

    (function () {
      const el = document.getElementById('evolucion');
      if (!el) return;

      new Chart(el, {
        type: 'line',
        data: {
          labels: serieDiasLabels,
          datasets: [{
            label: 'Total con IVA',
            data: serieDiasTotals,
            tension: 0.25,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            tooltip: {
              callbacks: {
                label: function (c) {
                  return fmtUSD(c.parsed.y);
                }
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true
            }
          }
        }
      });
    })();

    (function () {
      const el = document.getElementById('stackMes');
      if (!el) return;

      new Chart(el, {
        type: 'bar',
        data: {
          labels: porMesLabels,
          datasets: [
            {
              label: 'Con soporte',
              data: porMesCon,
              stack: 's'
            },
            {
              label: 'Sin soporte',
              data: porMesSin,
              stack: 's'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true
            },
            y: {
              stacked: true,
              beginAtZero: true
            }
          },
          plugins: {
            tooltip: {
              callbacks: {
                label: function (c) {
                  return c.dataset.label + ': ' + fmtUSD(c.parsed.y);
                }
              }
            }
          }
        }
      });
    })();

    (function () {
      const el = document.getElementById('pieCCB');
      if (!el) return;

      new Chart(el, {
        type: 'doughnut',
        data: {
          labels: ['CCB', 'No CCB'],
          datasets: [{
            data: [ccb, noCcb]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom'
            },
            tooltip: {
              callbacks: {
                label: function (c) {
                  return c.label + ': ' + fmtUSD(c.parsed);
                }
              }
            }
          }
        }
      });
    })();

    (function () {
      const el = document.getElementById('embudo');
      if (!el) return;

      new Chart(el, {
        type: 'bar',
        data: {
          labels: ['Total', 'Sin SAP', 'Aprob. GA', 'Aprob. GF', 'Aprob. GG'],
          datasets: [{
            data: [nTotal, nSinSap, nGa, nGf, nGg],
            label: 'Registros'
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            }
          },
          scales: {
            x: {
              beginAtZero: true
            }
          }
        }
      });
    })();

    (function () {
      const el = document.getElementById('porUsuario');
      if (!el) return;

      new Chart(el, {
        type: 'bar',
        data: {
          labels: serieUsuariosLabels,
          datasets: [{
            label: 'Total con IVA',
            data: serieUsuariosTotals
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: false
            },
            tooltip: {
              callbacks: {
                label: function (c) {
                  return fmtUSD(c.parsed.y);
                }
              }
            }
          },
          scales: {
            x: {
              ticks: {
                autoSkip: false,
                maxRotation: 45
              }
            },
            y: {
              beginAtZero: true
            }
          }
        }
      });
    })();

    (function () {
      const el = document.getElementById('depMes');
      if (!el) return;

      const datasets = (depMesSeries || []).map(function (s, i) {
        return {
          label: s.name || ('Depto ' + (i + 1)),
          data: (s.data || []).map(function (v) {
            return Number(v || 0);
          }),
          stack: 'dept',
          borderWidth: 1
        };
      });

      if (!depMesLabels.length || !datasets.length) {
        if (el.parentElement) {
          el.parentElement.innerHTML = '<div class="text-muted small">Sin datos para este rango.</div>';
        }
        return;
      }

      new Chart(el, {
        type: 'bar',
        data: {
          labels: depMesLabels,
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true
            },
            y: {
              stacked: true,
              beginAtZero: true
            }
          },
          plugins: {
            legend: {
              position: 'bottom'
            },
            tooltip: {
              callbacks: {
                label: function (ctx) {
                  return ctx.dataset.label + ': ' + fmtUSD(ctx.parsed.y);
                }
              }
            }
          }
        }
      });
    })();
  });
})();