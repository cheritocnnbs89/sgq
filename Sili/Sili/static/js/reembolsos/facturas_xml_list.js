document.addEventListener('DOMContentLoaded', function () {
  const table = document.getElementById('tabla-xml');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const headers = table.querySelectorAll('th.sort-col');
  if (!tbody || !headers.length) return;

  function getDataRows() {
    return Array.from(tbody.querySelectorAll('tr')).filter(function (tr) {
      return tr.dataset.empty !== '1';
    });
  }

  function parseDateDMY(s) {
    if (!s) return 0;

    const parts = s.split('/');
    if (parts.length !== 3) return 0;

    const d = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10) - 1;
    const y = parseInt(parts[2], 10);
    const dt = new Date(y, m, d);

    return dt.getTime() || 0;
  }

  function resetIcons() {
    headers.forEach(function (th) {
      const icon = th.querySelector('.sort-icon i');
      if (!icon) return;

      icon.classList.remove('bi-arrow-up', 'bi-arrow-down');
      if (!icon.classList.contains('bi-arrow-down-up')) {
        icon.classList.add('bi-arrow-down-up');
      }
    });
  }

  function setIcon(th, asc) {
    const icon = th.querySelector('.sort-icon i');
    if (!icon) return;

    icon.classList.remove('bi-arrow-down-up', 'bi-arrow-up', 'bi-arrow-down');
    icon.classList.add(asc ? 'bi-arrow-up' : 'bi-arrow-down');
  }

  headers.forEach(function (th) {
    th.addEventListener('click', function () {
      const key = th.dataset.sort;
      if (!key) return;

      const currentAsc = th.dataset.asc === 'true';
      const asc = !currentAsc;
      th.dataset.asc = asc ? 'true' : 'false';

      const rows = getDataRows();

      rows.sort(function (a, b) {
        let va = (a.dataset[key] || '').toString();
        let vb = (b.dataset[key] || '').toString();

        if (key === 'fecha') {
          const ta = parseDateDMY(va);
          const tb = parseDateDMY(vb);
          return asc ? (ta - tb) : (tb - ta);
        }

        if (key === 'total') {
          const na = parseFloat(va.replace(/,/g, '')) || 0;
          const nb = parseFloat(vb.replace(/,/g, '')) || 0;
          return asc ? (na - nb) : (nb - na);
        }

        va = va.toLowerCase();
        vb = vb.toLowerCase();

        if (va < vb) return asc ? -1 : 1;
        if (va > vb) return asc ? 1 : -1;
        return 0;
      });

      rows.forEach(function (r) {
        tbody.appendChild(r);
      });

      resetIcons();
      setIcon(th, asc);
    });
  });


  
});

document.addEventListener('DOMContentLoaded', function () {
  const btnSeed = document.getElementById('btn-seedbilling-consumir');

  if (!btnSeed) return;

  btnSeed.addEventListener('click', async function () {
    const url = btnSeed.dataset.url;
    const csrfInput = document.getElementById('csrf-token-seedbilling');
    const csrfToken = csrfInput ? csrfInput.value : '';

    if (!url) {
      alert('No se encontró la URL del consumo SeedBilling.');
      return;
    }

    const confirmar = confirm(
      '¿Deseas consumir ahora el API de SeedBilling?\n\n' +
      'El proceso leerá comprobantes pendientes, insertará los XML de Quimpac y marcará como entregados los procesados.'
    );

    if (!confirmar) return;

    const originalHtml = btnSeed.innerHTML;

    btnSeed.disabled = true;
    btnSeed.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Consumiendo...';

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'X-CSRF-Token': csrfToken,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      });

      const data = await resp.json().catch(function () {
        return {};
      });

      if (!resp.ok || !data.ok) {
        alert(data.msg || 'Ocurrió un error consumiendo SeedBilling.');
        return;
      }

      alert(data.msg || 'Consumo SeedBilling finalizado correctamente.');

      window.location.reload();

    } catch (err) {
      console.error(err);
      alert('Error de comunicación consumiendo SeedBilling.');

    } finally {
      btnSeed.disabled = false;
      btnSeed.innerHTML = originalHtml;
    }
  });
});