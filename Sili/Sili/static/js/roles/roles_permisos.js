document.addEventListener('DOMContentLoaded', function () {
  const cfg = document.getElementById('roles-permisos-config');
  const showSaved = cfg ? JSON.parse(cfg.dataset.showSaved || 'false') : false;

  if (showSaved) {
    const toastEl = document.getElementById('saveToast');
    if (toastEl && window.bootstrap && bootstrap.Toast) {
      const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
      toast.show();
    } else {
      alert('Permisos guardados correctamente.');
    }
  }

  const table = document.getElementById('tabla-permisos');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const th = document.getElementById('th-opcion');
  if (!th || !tbody) return;

  let dir = 'asc';

  function clearSortClasses() {
    th.classList.remove('sorted-asc', 'sorted-desc');
  }

  function setIcon() {
    const icon = th.querySelector('.th-sortable i');
    if (!icon) return;
    icon.classList.remove('bi-arrow-down-up', 'bi-chevron-up', 'bi-chevron-down');
    icon.classList.add(dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down');
  }

  th.addEventListener('click', function () {
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort(function (a, b) {
      const ta = (a.children[0].textContent || '').trim().toLowerCase();
      const tb = (b.children[0].textContent || '').trim().toLowerCase();

      if (ta < tb) return dir === 'asc' ? -1 : 1;
      if (ta > tb) return dir === 'asc' ? 1 : -1;
      return 0;
    });

    rows.forEach(function (row) {
      tbody.appendChild(row);
    });

    dir = dir === 'asc' ? 'desc' : 'asc';
    clearSortClasses();
    th.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
    setIcon();
  });

  setIcon();
});

document.addEventListener('DOMContentLoaded', function () {
  const cfg = document.getElementById('roles-permisos-config');
  const showSaved = cfg ? JSON.parse(cfg.dataset.showSaved || 'false') : false;

  if (showSaved) {
    const toastEl = document.getElementById('saveToast');
    if (toastEl && window.bootstrap && bootstrap.Toast) {
      const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
      toast.show();
    } else {
      alert('Permisos guardados correctamente.');
    }
  }

  const rolSelector = document.getElementById('rolSelector');
  if (rolSelector) {
    rolSelector.addEventListener('change', function () {
      const form = rolSelector.closest('form');
      if (form) form.submit();
    });
  }

  const table = document.getElementById('tabla-permisos');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  const th = document.getElementById('th-opcion');
  if (!th || !tbody) return;

  let dir = 'asc';

  function clearSortClasses() {
    th.classList.remove('sorted-asc', 'sorted-desc');
  }

  function setIcon() {
    const icon = th.querySelector('.th-sortable i');
    if (!icon) return;
    icon.classList.remove('bi-arrow-down-up', 'bi-chevron-up', 'bi-chevron-down');
    icon.classList.add(dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down');
  }

  th.addEventListener('click', function () {
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort(function (a, b) {
      const ta = (a.children[0].textContent || '').trim().toLowerCase();
      const tb = (b.children[0].textContent || '').trim().toLowerCase();

      if (ta < tb) return dir === 'asc' ? -1 : 1;
      if (ta > tb) return dir === 'asc' ? 1 : -1;
      return 0;
    });

    rows.forEach(function (row) {
      tbody.appendChild(row);
    });

    dir = dir === 'asc' ? 'desc' : 'asc';
    clearSortClasses();
    th.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
    setIcon();
  });

  setIcon();
});