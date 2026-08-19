(() => {
  document.addEventListener('DOMContentLoaded', function () {
    // Año/mes se auto-envían al cambiar, para no necesitar un botón aparte.
    const filtrosForm = document.getElementById('carteraFiltrosForm');
    ['carteraAnio', 'carteraMes'].forEach((id) => {
      const el = document.getElementById(id);
      if (el && filtrosForm) {
        el.addEventListener('change', () => filtrosForm.submit());
      }
    });

    // Barras con ancho dinámico: el CSP bloquea style="" inline, así que
    // el % viaja en data-pct y acá se traduce a la variable CSS que ya
    // consume .cartera-bar-fill / .cartera-timeline-bar-fill (mismo
    // patrón que .okr-bar-fill en planilla/dashboard.js).
    document.querySelectorAll('[data-pct]').forEach((el) => {
      const pct = Math.max(0, Math.min(100, parseFloat(el.dataset.pct) || 0));
      el.style.setProperty('--bar-pct', pct + '%');
    });

    // Buscador de la tabla de ranking: filtra en el navegador, sin ir al
    // servidor (la lista de clientes ya está completa en la página).
    const search = document.getElementById('carteraRankingSearch');
    const rows = document.querySelectorAll('.cartera-ranking-row');
    const emptyMsg = document.getElementById('carteraRankingEmpty');

    if (search && rows.length) {
      search.addEventListener('input', function () {
        const term = search.value.trim().toLowerCase();
        let visibles = 0;

        rows.forEach((row) => {
          const haystack = (row.dataset.search || '').toLowerCase();
          const match = !term || haystack.includes(term);
          row.style.display = match ? '' : 'none';
          if (match) visibles += 1;
        });

        if (emptyMsg) {
          emptyMsg.classList.toggle('d-none', visibles !== 0);
        }
      });
    }

    // Detalle de cobros por factura (acordeón en la línea de tiempo): se
    // carga con fetch la primera vez que se expande, no de entrada — la
    // mayoría de las facturas nunca se llegan a abrir.
    document.querySelectorAll('.cartera-timeline-detail').forEach((el) => {
      el.addEventListener('show.bs.collapse', function () {
        if (el.dataset.loaded === '1') return;
        el.dataset.loaded = '1';

        const body = el.querySelector('.cartera-timeline-detail-body');
        const url = el.dataset.loadUrl;
        if (!body || !url) return;

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then((r) => r.text())
          .then((html) => {
            body.innerHTML = html;
            // Las barras que puedan venir en el HTML cargado también
            // necesitan su --bar-pct (el listener de DOMContentLoaded ya
            // pasó, así que se repite acá solo para lo recién insertado).
            body.querySelectorAll('[data-pct]').forEach((bar) => {
              const pct = Math.max(0, Math.min(100, parseFloat(bar.dataset.pct) || 0));
              bar.style.setProperty('--bar-pct', pct + '%');
            });
          })
          .catch(() => {
            body.innerHTML = '<div class="text-danger small py-2">No se pudo cargar el detalle.</div>';
          });
      });
    });
  });
})();
