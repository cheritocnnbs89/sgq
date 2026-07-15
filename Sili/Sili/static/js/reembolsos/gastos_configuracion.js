document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('form[data-confirm-message]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      const ok = window.confirm(form.dataset.confirmMessage);
      if (!ok) {
        ev.preventDefault();
      }
    });
  });
});
