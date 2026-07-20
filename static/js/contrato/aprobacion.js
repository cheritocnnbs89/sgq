document.addEventListener('change', (event) => {
  const el = event.target;

  if (!(el instanceof HTMLInputElement)) {
    return;
  }

  if (!el.classList.contains('toggle-gf')) {
    return;
  }

  const payload = {
    tipo: el.dataset.tipo,
    id: el.dataset.id,
    valor: el.checked
  };

  fetch(el.dataset.url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
    .then((response) => {
      if (!response.ok) {
        return Promise.reject();
      }

      return response.json();
    })
    .catch(() => {
      el.checked = !el.checked;
      window.alert('No se pudo guardar la Aprob. GF.');
    });
});