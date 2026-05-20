document.addEventListener("DOMContentLoaded", function () {
  const accordion = document.getElementById("sidebarAccordion");

  if (accordion && window.bootstrap) {
    const saved = localStorage.getItem("sidebarState");

    if (saved) {
      try {
        const state = JSON.parse(saved);

        Object.keys(state).forEach((id) => {
          const el = document.getElementById(id);
          if (!el) return;

          const c = new bootstrap.Collapse(el, { toggle: false });
          if (state[id]) c.show();
          else c.hide();
        });
      } catch (e) {
        console.warn("No se pudo restaurar sidebarState:", e);
      }
    }

    const save = (id, on) => {
      let s = {};
      try {
        s = JSON.parse(localStorage.getItem("sidebarState")) || {};
      } catch (e) {
        s = {};
      }

      s[id] = on;
      localStorage.setItem("sidebarState", JSON.stringify(s));
    };

    accordion.addEventListener("shown.bs.collapse", (ev) => {
      if (ev.target?.id) save(ev.target.id, true);
    });

    accordion.addEventListener("hidden.bs.collapse", (ev) => {
      if (ev.target?.id) save(ev.target.id, false);
    });
  }
});

(function () {
  function markFilled(el) {
    const hasValue = !!(el.value && el.value.toString().trim().length);
    el.classList.toggle("filled", hasValue);
  }

  function bind(container = document) {
    const fields = container.querySelectorAll(
      "input.form-control, textarea.form-control, select.form-select"
    );

    fields.forEach((el) => {
      markFilled(el);
      el.addEventListener("input", () => markFilled(el));
      el.addEventListener("change", () => markFilled(el));
      el.addEventListener("blur", () => markFilled(el));
    });
  }

  document.addEventListener("DOMContentLoaded", () => bind());
})();

(function () {
  const shell = document.querySelector(".app-shell");
  const btnOpen = document.getElementById("btnOpen");
  const btnClose = document.getElementById("btnClose");
  const scrim = document.getElementById("sidebarScrim");

  if (!shell || !btnOpen || !btnClose || !scrim) return;

  const KEY = "ui.sidebar.open";
  const isMobile = () => window.matchMedia("(max-width: 992px)").matches;

  function setOpen(open) {
    shell.classList.toggle("open", open);
    if (!isMobile()) {
      localStorage.setItem(KEY, open ? "1" : "0");
    }
  }

  const saved = localStorage.getItem(KEY);
  if (saved !== null && !isMobile()) setOpen(saved === "1");
  else setOpen(!isMobile());

  btnOpen.addEventListener("click", () => setOpen(true));
  btnClose.addEventListener("click", () => setOpen(false));
  scrim.addEventListener("click", () => setOpen(false));

  window.addEventListener("resize", () => {
    if (isMobile()) setOpen(false);
    else setOpen((localStorage.getItem(KEY) ?? "1") === "1");
  });
})();

window.TableKit = (function () {
  const norm = (s) =>
    (s || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "");

  function init(opts) {
    const {
      table,
      filterInput,
      btnSearch,
      btnClear,
      pagerContainer,
      infoContainer,
      pageLenKey = "tablekit_page_len",
      densityKey = "tablekit_density",
      defaultPageLen = 10,
    } = opts;

    const elTable = typeof table === "string" ? document.querySelector(table) : table;
    if (!elTable) return null;

    elTable.classList.add("tablekit");

    const tbody = elTable.querySelector("tbody");
    if (!tbody) return null;

    const rows = [...tbody.querySelectorAll('tr[data-row="1"]')];
    const infoEl = infoContainer ? document.querySelector(infoContainer) : null;
    const pagerEl = pagerContainer ? document.querySelector(pagerContainer) : null;

    const applyDensity = (mode) => {
      if (mode === "compact") elTable.classList.add("table-compact");
      else elTable.classList.remove("table-compact");

      localStorage.setItem(densityKey, mode);
    };

    applyDensity(localStorage.getItem(densityKey) || "normal");

    let pageLength = parseInt(localStorage.getItem(pageLenKey) || defaultPageLen, 10);
    let currentPage = 1;

    const visibles = () => rows.filter((r) => r.style.display !== "none");

    function updateInfo(start, end, total) {
      if (infoEl) {
        infoEl.textContent = `Mostrando ${total ? start + 1 : 0} a ${end} de ${total}`;
      }
    }

    function mk(label, page, disabled = false, active = false) {
      const li = document.createElement("li");
      li.className =
        "page-item" + (disabled ? " disabled" : "") + (active ? " active" : "");

      const a = document.createElement("a");
      a.className = "page-link";
      a.href = "#";
      a.textContent = label;
      a.addEventListener("click", (e) => {
        e.preventDefault();
        if (!disabled) go(page);
      });

      li.appendChild(a);
      return li;
    }

    function render(totalPages) {
      if (!pagerEl) return;

      pagerEl.innerHTML = "";
      pagerEl.classList.add("tablekit-pager");

      const tp = Math.max(1, totalPages);
      pagerEl.appendChild(mk("Anterior", currentPage - 1, currentPage === 1));

      const max = 7;
      const start = Math.max(1, currentPage - 3);
      const end = Math.min(tp, start + max - 1);

      for (let p = start; p <= end; p++) {
        pagerEl.appendChild(mk(String(p), p, false, p === currentPage));
      }

      pagerEl.appendChild(mk("Siguiente", currentPage + 1, currentPage === tp));
    }

    function go(page) {
      const v = visibles();
      const total = v.length;
      const tp = Math.max(1, Math.ceil(total / pageLength));
      currentPage = Math.min(Math.max(1, page), tp);

      v.forEach((r, i) => {
        const start = (currentPage - 1) * pageLength;
        const end = start + pageLength;
        r.style.display = i >= start && i < end ? "" : "none";
      });

      const start = (currentPage - 1) * pageLength;
      const endCount = Math.min(start + pageLength, total);

      updateInfo(start, endCount, total);
      render(tp);
    }

    const qEl = filterInput ? document.querySelector(filterInput) : null;
    let tId = null;

    const applyFilterNow = () => {
      const term = norm(qEl?.value || "").trim();

      rows.forEach((r) => {
        const txt = norm(r.innerText);
        r.style.display = term ? (txt.includes(term) ? "" : "none") : "";
      });

      go(1);
    };

    const applyFilterDebounced = () => {
      clearTimeout(tId);
      tId = setTimeout(applyFilterNow, 120);
    };

    if (qEl) qEl.addEventListener("input", applyFilterDebounced);
    if (btnSearch) {
      const el = document.querySelector(btnSearch);
      if (el) el.addEventListener("click", applyFilterNow);
    }
    if (btnClear) {
      const el = document.querySelector(btnClear);
      if (el) {
        el.addEventListener("click", () => {
          if (qEl) {
            qEl.value = "";
            applyFilterNow();
            qEl.focus();
          }
        });
      }
    }

    return {
      go,
      applyFilterNow,
      setDensity: (mode) => applyDensity(mode),
      setPageLength: (n) => {
        pageLength = +n;
        localStorage.setItem(pageLenKey, String(pageLength));
        go(1);
      },
    };
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", function () {
  const STORAGE_KEY = "sili.dismissedAlerts";
  let dismissed = [];

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    dismissed = raw ? JSON.parse(raw) : [];
  } catch (e) {
    dismissed = [];
  }

  const alerts = document.querySelectorAll(".alert[data-alert-key]");

  alerts.forEach((alert) => {
    const key = alert.getAttribute("data-alert-key");
    if (!key) return;

    if (dismissed.includes(key)) {
      alert.remove();
      return;
    }

    const btn = alert.querySelector('[data-bs-dismiss="alert"]');
    if (btn) {
      btn.addEventListener("click", () => {
        if (!dismissed.includes(key)) {
          dismissed.push(key);
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed));
          } catch (e) {
            console.warn("No se pudo persistir cierre de alerta:", e);
          }
        }
      });
    }
  });
});