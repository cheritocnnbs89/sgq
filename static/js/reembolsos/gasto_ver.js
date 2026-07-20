document.addEventListener('DOMContentLoaded', () => {
  const linksAdjuntos = document.querySelectorAll('.gasto-ver-adjuntos a[target="_blank"]');

  linksAdjuntos.forEach((link) => {
    link.setAttribute('rel', 'noopener noreferrer');
  });
});