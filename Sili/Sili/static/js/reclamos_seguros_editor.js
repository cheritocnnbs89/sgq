/* Editores de texto enriquecido (Quill) de Reclamos Seguros. Soporta varios por pagina
   (cada uno con data-rs-editor). Las imagenes se suben al servidor. Sin codigo inline (CSP). */
(function () {
  'use strict';

  if (typeof Quill === 'undefined') { return; }

  var MAX_BYTES = 5 * 1024 * 1024;
  var PREFIJO = '/reclamos-seguros/imagen/';
  var Delta = Quill.import('delta');
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  function dataUrlAFile(src) {
    var m = /^data:(image\/[a-z+.\-]+);base64,(.+)$/i.exec(src);
    if (!m) { return null; }
    try {
      var bin = atob(m[2]);
      var arr = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) { arr[i] = bin.charCodeAt(i); }
      return new File([arr], 'imagen.' + (m[1].split('/')[1] || 'png').replace('jpeg', 'jpg'), { type: m[1] });
    } catch (e) {
      return null;
    }
  }

  function archivosImagen(lista) {
    return Array.prototype.filter.call(lista || [], function (f) { return /^image\//.test(f.type); });
  }

  function iniciar(cont) {
    var hidden = document.getElementById(cont.getAttribute('data-input'));
    var avisos = document.getElementById(cont.getAttribute('data-alertas'));
    if (!hidden) { return; }
    var form = hidden.closest('form');
    var uploadUrl = cont.getAttribute('data-upload-url') || '';
    var mensajeVacio = cont.getAttribute('data-mensaje-vacio') || 'Este campo es obligatorio.';
    var pendientes = 0;
    var avisoSubida = null;
    var quill = null;

    function mostrarAviso(texto, tipo) {
      if (!avisos) { window.alert(texto); return null; }
      var a = document.createElement('div');
      a.className = 'alert alert-' + (tipo || 'danger') + ' alert-dismissible fade show';
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
      avisos.appendChild(a);
      return a;
    }

    function quitarAviso(a) {
      if (a && a.parentNode) { a.parentNode.removeChild(a); }
    }

    function subirArchivo(file) {
      return new Promise(function (resolve, reject) {
        if (!/^image\/(png|jpeg|gif|webp)$/.test(file.type)) {
          reject(new Error('Solo se permiten im\u00e1genes PNG, JPG, GIF o WEBP.'));
          return;
        }
        if (file.size > MAX_BYTES) {
          reject(new Error('La imagen supera 5 MB.'));
          return;
        }
        var fd = new FormData();
        fd.append('imagen', file, file.name || 'captura.png');
        fetch(uploadUrl, {
          method: 'POST', body: fd, credentials: 'same-origin',
          headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (!r.ok || !d.ok) { throw new Error(d.msg || ('Error al subir la imagen (HTTP ' + r.status + ').')); }
            return d.url;
          });
        }).then(resolve, reject);
      });
    }

    function posicion(indice) {
      if (typeof indice === 'number') { return indice; }
      var sel = quill.getSelection();
      return sel ? sel.index : Math.max(0, quill.getLength() - 1);
    }

    function insertarImagen(file, indice) {
      pendientes++;
      if (!avisoSubida) { avisoSubida = mostrarAviso('Subiendo imagen\u2026', 'info'); }
      var pos = posicion(indice);
      subirArchivo(file).then(function (url) {
        quill.insertEmbed(pos, 'image', url, 'user');
        quill.setSelection(pos + 1, 0, 'user');
      }).catch(function (err) {
        mostrarAviso(err.message || 'No se pudo subir la imagen.');
      }).then(function () {
        pendientes--;
        if (pendientes <= 0) { quitarAviso(avisoSubida); avisoSubida = null; pendientes = 0; }
      });
    }

    function elegirImagen() {
      var inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = 'image/png,image/jpeg,image/gif,image/webp';
      inp.multiple = true;
      inp.addEventListener('change', function () {
        var sel = quill.getSelection(true);
        var idx = sel ? sel.index : 0;
        Array.prototype.forEach.call(inp.files, function (f, i) { insertarImagen(f, idx + i); });
      });
      inp.click();
    }

    quill = new Quill(cont, {
      theme: 'snow',
      placeholder: cont.getAttribute('data-placeholder') || '',
      formats: ['bold', 'italic', 'underline', 'strike', 'list', 'blockquote', 'link', 'image'],
      modules: { toolbar: { container: '#' + cont.getAttribute('data-toolbar'), handlers: { image: elegirImagen } } }
    });

    // Imagenes dentro de HTML pegado (Word, Outlook, web): las base64 se suben al servidor;
    // las externas se descartan (el servidor tampoco las aceptaria).
    quill.clipboard.addMatcher('img', function (node, delta) {
      var src = node.getAttribute('src') || '';
      if (src.indexOf(PREFIJO) === 0) { return delta; }
      if (/^data:image\//i.test(src)) {
        var f = dataUrlAFile(src);
        if (f) { insertarImagen(f); }
      }
      return new Delta();
    });

    // Captura de pantalla pegada (solo imagen, sin texto): se sube como imagen.
    quill.root.addEventListener('paste', function (ev) {
      var cd = ev.clipboardData;
      if (!cd) { return; }
      var imgs = archivosImagen(cd.files);
      if (!imgs.length || (cd.getData('text/plain') || '').trim()) { return; }
      ev.preventDefault();
      ev.stopPropagation();
      var idx = posicion();
      imgs.forEach(function (f, i) { insertarImagen(f, idx + i); });
    }, true);

    quill.root.addEventListener('drop', function (ev) {
      var imgs = archivosImagen(ev.dataTransfer && ev.dataTransfer.files);
      if (!imgs.length) { return; }
      ev.preventDefault();
      ev.stopPropagation();
      var idx = posicion();
      imgs.forEach(function (f, i) { insertarImagen(f, idx + i); });
    }, true);

    if (hidden.value && hidden.value.trim()) {
      quill.clipboard.dangerouslyPasteHTML(hidden.value, 'silent');
    }

    form.addEventListener('submit', function (ev) {
      if (avisos) { avisos.textContent = ''; avisoSubida = null; }
      if (pendientes > 0) {
        ev.preventDefault();
        mostrarAviso('Espera a que termine de subirse la imagen antes de guardar.');
        return;
      }
      var hayTexto = quill.getText().trim().length > 0;
      var hayImagen = quill.root.querySelector('img') !== null;
      if (!hayTexto && !hayImagen) {
        ev.preventDefault();
        mostrarAviso(mensajeVacio);
        quill.focus();
        return;
      }
      hidden.value = quill.getSemanticHTML();
    });
  }

  document.querySelectorAll('[data-rs-editor]').forEach(iniciar);
})();
