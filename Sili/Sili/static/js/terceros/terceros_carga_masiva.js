document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('tercerosCargaMasivaForm');
  if (!form) return;

  const sepInput = form.querySelector('input[name="sep"]');
  if (sepInput) {
    sepInput.addEventListener('input', function () {
      if (sepInput.value.length > 1) {
        sepInput.value = sepInput.value.slice(0, 1);
      }
    });
  }
});