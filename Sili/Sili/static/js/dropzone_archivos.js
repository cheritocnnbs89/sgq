/* Zonas de carga de archivos: arrastrar y soltar o seleccionar, acumulando varios archivos.
   Valida extension, tamano y cantidad y avisa con una alerta (nunca en silencio).
   Componente compartido: templates/partials/dropzone.html. Sin codigo inline (CSP). */
(function () {
  'use strict';

  function formatoTamano(b) {
    return b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
  }

  function extension(nombre) {
    var i = nombre.lastIndexOf('.');
    return i >= 0 ? nombre.slice(i).toLowerCase() : '';
  }

  function iniciar(dz) {
    if (dz.getAttribute('data-dz-listo') === '1') { return; }
    dz.setAttribute('data-dz-listo', '1');

    var input = dz.querySelector('input[type="file"]');
    var lista = dz.querySelector('.dz-lista');
    var alertas = dz.querySelector('.dz-alertas');
    if (!input) { return; }

    var maxBytes = parseInt(dz.getAttribute('data-max-bytes'), 10) || 0;
    var maxArchivos = parseInt(dz.getAttribute('data-max-archivos'), 10) || 0;
    var permitidas = (dz.getAttribute('data-extensiones') || '').toLowerCase().split(',')
      .map(function (x) { return x.trim(); }).filter(Boolean);
    var multiple = input.multiple;
    var acumulado = [];

    function aviso(texto) {
      var a = document.createElement('div');
      a.className = 'alert alert-warning alert-dismissible fade show mt-2 mb-0';
      a.setAttribute('role', 'alert');
      var t = document.createElement('span');
      t.textContent = texto;
      a.appendChild(t);
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn-close';
      b.setAttribute('data-bs-dismiss', 'alert');
      b.setAttribute('aria-label', 'Close');
      a.appendChild(b);
      alertas.appendChild(a);
    }

    function render() {
      if (!lista) { return; }
      lista.textContent = '';
      acumulado.forEach(function (f, i) {
        var li = document.createElement('li');
        var ico = document.createElement('i');
        ico.className = 'bi bi-file-earmark-check';
        var nombre = document.createElement('span');
        nombre.textContent = f.name;
        var tam = document.createElement('span');
        tam.className = 'text-muted';
        tam.textContent = '(' + formatoTamano(f.size) + ')';
        var quitar = document.createElement('button');
        quitar.type = 'button';
        quitar.className = 'btn-close dz-quitar';
        quitar.setAttribute('aria-label', 'Quitar ' + f.name);
        quitar.addEventListener('click', function () {
          acumulado.splice(i, 1);
          sincronizar();
        });
        li.appendChild(ico);
        li.appendChild(nombre);
        li.appendChild(tam);
        li.appendChild(quitar);
        lista.appendChild(li);
      });
    }

    function sincronizar() {
      var dt = new DataTransfer();
      acumulado.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
      render();
    }

    function agregar(archivos) {
      var rechazos = [];
      var excedido = false;
      Array.prototype.forEach.call(archivos, function (f) {
        if (permitidas.length && permitidas.indexOf(extension(f.name)) === -1) {
          rechazos.push("'" + f.name + "': tipo de archivo no permitido.");
          return;
        }
        if (f.size <= 0 || (maxBytes && f.size > maxBytes)) {
          rechazos.push("'" + f.name + "': supera " + Math.round(maxBytes / 1048576) + ' MB o est\u00e1 vac\u00edo.');
          return;
        }
        var repetido = acumulado.some(function (x) {
          return x.name === f.name && x.size === f.size && x.lastModified === f.lastModified;
        });
        if (repetido) { return; }
        if (!multiple) { acumulado = []; }
        if (maxArchivos && acumulado.length >= maxArchivos) { excedido = true; return; }
        acumulado.push(f);
      });
      if (excedido) { rechazos.push('M\u00e1ximo ' + maxArchivos + ' archivos; se ignoraron los dem\u00e1s.'); }
      alertas.textContent = '';
      rechazos.forEach(aviso);
      sincronizar();
    }

    input.addEventListener('change', function () { agregar(input.files); });

    ['dragenter', 'dragover'].forEach(function (evt) {
      dz.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        dz.classList.add('is-dragover');
      });
    });
    ['dragleave', 'dragend'].forEach(function (evt) {
      dz.addEventListener(evt, function (e) {
        e.preventDefault();
        e.stopPropagation();
        dz.classList.remove('is-dragover');
      });
    });
    dz.addEventListener('drop', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.remove('is-dragover');
      var soltados = e.dataTransfer && e.dataTransfer.files;
      if (soltados && soltados.length) { agregar(soltados); }
    });
  }

  window.Dropzones = {
    iniciar: function (raiz) {
      (raiz || document).querySelectorAll('[data-dz]').forEach(iniciar);
    }
  };
  window.Dropzones.iniciar(document);
})();
