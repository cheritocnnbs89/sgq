document.addEventListener('DOMContentLoaded', function () {
  var input = document.getElementById('evidencias');
  var preview = document.getElementById('previewArchivoEvidencia');

  function formatearTamano(bytes) {
    var kb = bytes / 1024;
    if (kb < 1024) { return kb.toFixed(1) + ' KB'; }
    return (kb / 1024).toFixed(1) + ' MB';
  }

  function actualizarPreview() {
    preview.innerHTML = '';
    if (!input.files || input.files.length === 0) { return; }

    for (var i = 0; i < input.files.length; i++) {
      var file = input.files[i];
      var linea = document.createElement('div');
      linea.className = 'small text-muted';
      linea.innerHTML = '<i class="bi bi-file-earmark"></i> ' +
        file.name + ' (' + formatearTamano(file.size) + ')';
      preview.appendChild(linea);
    }
  }

  if (input && preview) {
    input.addEventListener('change', actualizarPreview);
  }

  var dropzone = document.getElementById('dropzoneEvidencia');
  if (dropzone && input) {
    dropzone.addEventListener('click', function () { input.click(); });

    ['dragover', 'dragleave', 'drop'].forEach(function (evento) {
      dropzone.addEventListener(evento, function (e) {
        e.preventDefault();
        e.stopPropagation();
      });
    });

    dropzone.addEventListener('dragover', function () {
      dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', function () {
      dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', function (e) {
      dropzone.classList.remove('is-dragover');
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event('change'));
      }
    });
  }
});
