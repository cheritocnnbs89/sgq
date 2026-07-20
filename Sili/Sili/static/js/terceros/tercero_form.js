document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('terceroForm');
  if (!form) return;

  const nombre = form.querySelector('input[name="nombre"]');
  if (nombre) {
    nombre.addEventListener('input', function () {
      nombre.value = nombre.value.replace(/^\s+/, '');
    });
  }
});