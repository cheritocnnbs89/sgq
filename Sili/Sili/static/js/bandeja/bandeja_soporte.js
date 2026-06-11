(() => {
  // ── Confirmación para formularios de descartar ─────────────────
  document.querySelectorAll('.bs-form-descartar').forEach(form => {
    form.addEventListener('submit', e => {
      if (!window.confirm('¿Descartar este correo sin crear tarea?')) {
        e.preventDefault();
      }
    });
  });

  // ── Validación + indicador de procesando al asignar ────────────
  document.querySelectorAll('.bs-form-asignar').forEach(form => {
    form.addEventListener('submit', e => {
      const sel = form.querySelector('select[name="responsable_id"]');
      if (!sel || !sel.value) {
        e.preventDefault();
        sel?.focus();
        alert('Selecciona un responsable antes de asignar.');
        return;
      }
      // NOTA: el select NO se deshabilita — los campos disabled no se envían en el POST
      const btn = form.querySelector('.btn-asignar');
      if (btn) {
        btn.disabled = true;
        btn.classList.add('btn-asignar--procesando');
        btn.innerHTML = '<span class="bs-spinner"></span> Procesando…';
      }
    });
  });

  // ── Modal de detalle ───────────────────────────────────────────
  const backdrop        = document.getElementById('bsModalBackdrop');
  const modalClose      = document.getElementById('bsModalClose');
  const attachWrap      = document.getElementById('bsModalAttachWrap');
  const loadAttachBtn   = document.getElementById('bsLoadAttachBtn');
  const attachList      = document.getElementById('bsAttachList');
  const repliesWrap     = document.getElementById('bsModalRepliesWrap');
  const repliesList     = document.getElementById('bsRepliesList');
  const repliesCount    = document.getElementById('bsRepliesCount');
  const modalIframe     = document.getElementById('bsModalIframe');

  let _currentMessageId = '';
  let _currentInboxId   = '';
  let _attachLoaded     = false;

  function openModal(btn) {
    const inboxId  = btn.dataset.inboxId;
    const messageId = btn.dataset.messageId || '';
    const subject  = btn.dataset.subject  || '';
    const from     = btn.dataset.from     || '';
    const email    = btn.dataset.email    || '';
    const fecha    = btn.dataset.fecha    || '';
    const nReplies = parseInt(btn.dataset.replies || '0', 10);

    _currentMessageId = messageId;
    _currentInboxId   = inboxId;
    _attachLoaded     = false;

    document.getElementById('bsModalTicket').textContent = `TK-${String(inboxId).padStart(5, '0')}`;
    document.getElementById('bsModalTitle').textContent  = subject;
    document.getElementById('bsModalMeta').innerHTML =
      `<span><i class="bi bi-person"></i> ${from}</span>` +
      `<span><i class="bi bi-envelope"></i> ${email}</span>` +
      `<span><i class="bi bi-calendar3"></i> ${fecha}</span>`;

    // Cargar cuerpo HTML en iframe
    if (modalIframe) {
      modalIframe.src = `/tareas/bandeja-soporte/${inboxId}/body`;
    }

    // Adjuntos: mostrar botón "Cargar" si hay messageId
    attachList.innerHTML = '';
    if (messageId) {
      attachWrap.hidden = false;
      if (loadAttachBtn) loadAttachBtn.hidden = false;
    } else {
      attachWrap.hidden = true;
    }

    // Respuestas
    repliesList.innerHTML = '<div class="bs-replies-loading"><span class="bs-spinner-dark"></span> Cargando...</div>';
    repliesWrap.hidden = true;

    backdrop.classList.add('visible');
    document.body.classList.add('bs-modal-open');

    // Cargar respuestas
    if (nReplies > 0) {
      loadReplies(inboxId);
    }
  }

  function closeModal() {
    backdrop.classList.remove('visible');
    document.body.classList.remove('bs-modal-open');
    if (modalIframe) modalIframe.src = 'about:blank';
  }

  // Carga respuestas vía AJAX
  function loadReplies(inboxId) {
    fetch(`/tareas/bandeja-soporte/${inboxId}/replies.json`, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (!Array.isArray(data) || data.length === 0) {
          repliesWrap.hidden = true;
          return;
        }
        repliesCount.textContent = `(${data.length} respuesta${data.length > 1 ? 's' : ''})`;
        repliesList.innerHTML = data.map(r => `
          <div class="bs-reply-item">
            <div class="bs-reply-header">
              <span class="bs-reply-from"><i class="bi bi-person-circle"></i> ${escHtml(r.from_name)}</span>
              <span class="bs-reply-email">${escHtml(r.from_email)}</span>
              <span class="bs-reply-date"><i class="bi bi-clock"></i> ${escHtml(r.received_at)}</span>
              ${r.has_attachments ? '<span class="bs-reply-attach-tag"><i class="bi bi-paperclip"></i> Con adjuntos</span>' : ''}
            </div>
            <pre class="bs-reply-body">${escHtml(r.body_text)}</pre>
          </div>
        `).join('');
        repliesWrap.hidden = false;
      })
      .catch(() => {
        repliesWrap.hidden = true;
      });
  }

  // Carga lista de adjuntos e imágenes vía AJAX
  function loadAttachments() {
    if (_attachLoaded || !_currentMessageId) return;
    _attachLoaded = true;
    if (loadAttachBtn) {
      loadAttachBtn.disabled = true;
      loadAttachBtn.innerHTML = '<span class="bs-spinner"></span>';
    }
    attachList.innerHTML = '<div class="bs-attach-loading"><span class="bs-spinner-dark"></span> Cargando adjuntos...</div>';

    fetch(`/tareas/bandeja-soporte/attachments/${encodeURIComponent(_currentMessageId)}.json`, { credentials: 'same-origin' })
      .then(r => r.json())
      .then(items => {
        if (!Array.isArray(items) || items.length === 0) {
          attachList.innerHTML = '<span class="bs-attach-empty">No se encontraron adjuntos.</span>';
          return;
        }
        attachList.innerHTML = items.map(a => {
          const isImg = a.content_type && a.content_type.startsWith('image/');
          const imgUrl = `/tareas/bandeja-soporte/img/${encodeURIComponent(_currentMessageId)}/${encodeURIComponent(a.attachment_id)}`;
          if (isImg) {
            return `<div class="bs-attach-img-wrap">
              <img src="${imgUrl}" alt="${escHtml(a.name)}" class="bs-attach-img" loading="lazy">
              <div class="bs-attach-img-name">${escHtml(a.name)}</div>
            </div>`;
          }
          const sizeKb = a.size ? `${Math.ceil(a.size / 1024)} KB` : '';
          return `<a href="${imgUrl}" target="_blank" class="bs-attach-file">
            <i class="bi bi-file-earmark"></i>
            <span class="bs-attach-file-name">${escHtml(a.name)}</span>
            ${sizeKb ? `<span class="bs-attach-file-size">${sizeKb}</span>` : ''}
          </a>`;
        }).join('');
        if (loadAttachBtn) loadAttachBtn.hidden = true;
      })
      .catch(() => {
        attachList.innerHTML = '<span class="bs-attach-empty">No se pudieron cargar los adjuntos.</span>';
        if (loadAttachBtn) {
          loadAttachBtn.disabled = false;
          loadAttachBtn.innerHTML = '<i class="bi bi-cloud-download"></i> Reintentar';
        }
      });
  }

  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  document.querySelectorAll('.btn-ver-detalle').forEach(btn => {
    btn.addEventListener('click', () => openModal(btn));
  });

  if (modalClose)    modalClose.addEventListener('click', closeModal);
  if (loadAttachBtn) loadAttachBtn.addEventListener('click', loadAttachments);

  if (backdrop) {
    backdrop.addEventListener('click', e => {
      if (e.target === backdrop) closeModal();
    });
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });
})();
