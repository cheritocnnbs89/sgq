document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.js-menu-delete-form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const confirmed = window.confirm('¿Eliminar esta opción?');

      if (!confirmed) {
        event.preventDefault();
      }
    });
  });
});