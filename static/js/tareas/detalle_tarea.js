document.addEventListener('DOMContentLoaded', () => {
  const responsableSearch = document.getElementById('responsableSearch');
  const responsableSelect = document.getElementById('responsableSelect');

  if (!responsableSearch || !responsableSelect) return;

  responsableSearch.addEventListener('input', event => {
    const term = event.target.value.toLowerCase().trim();
    const options = responsableSelect.querySelectorAll('option');

    options.forEach(option => {
      const searchValue = option.getAttribute('data-search') || '';
      option.hidden = !(searchValue.includes(term) || option.value === '');
    });
  });
});
