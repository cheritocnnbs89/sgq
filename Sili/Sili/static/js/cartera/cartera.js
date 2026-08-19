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
  });
})();
