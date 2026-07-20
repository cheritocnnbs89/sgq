document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.js-delete-planilla-tarea-form').forEach(form => {
    form.addEventListener('submit', event => {
      const ok = confirm('¿Eliminar esta tarea? Se borrarán sus checks del mes.');
      if (!ok) {
        event.preventDefault();
      }
    });
  });
});
