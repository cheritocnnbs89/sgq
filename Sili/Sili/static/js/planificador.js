/* planificador.js – sin inline handlers ni inline styles */
'use strict';

(function () {

  /* ── Leer datos del servidor desde data attributes ── */
  const dataEl      = document.getElementById('planner-data');
  const TODAY_STR   = dataEl ? dataEl.dataset.today    : '';
  const PERM_CREAR  = dataEl ? dataEl.dataset.permCrear === 'true' : false;
  const PUEDE_VER   = dataEl ? dataEl.dataset.puedeVer  === 'true' : false;
  let CAL_EVENTS    = [];
  try { CAL_EVENTS  = dataEl ? JSON.parse(dataEl.dataset.events) : []; } catch (_) {}

  /* Icono por tipo de solicitud */
  const TIPO_ICON = {
    'Recorrido / Motorizado': '🚗',
    'Voucher':                '🚕',
    'Vuelo':                  '✈️',
  };
  function tipoIcon(tipo) { return TIPO_ICON[tipo] || '📋'; }

  /* Escapar HTML para insertar en innerHTML */
  function _esc(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* ── Helpers de fecha ── */
  function getMonday(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    return d;
  }
  function addDays(d, n) {
    const r = new Date(d); r.setDate(r.getDate() + n); return r;
  }
  function toYMD(d) {
    return [
      d.getFullYear(),
      String(d.getMonth() + 1).padStart(2, '0'),
      String(d.getDate()).padStart(2, '0')
    ].join('-');
  }
  function fmtDate(d) {
    return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }).replace('.', '');
  }
  function pad(n) { return String(n).padStart(2, '0'); }

  /* ── Estado calendario ── */
  let weekStart = getMonday(TODAY_STR || toYMD(new Date()));
  const DAYS    = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'];
  const HOURS   = [8, 9, 10, 11, 12, 13, 14, 15, 16];

  function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    if (!grid) return;
    grid.innerHTML = '';

    const weekEnd = addDays(weekStart, 4);
    const title   = document.getElementById('weekTitle');
    if (title) title.textContent = 'Agenda semanal · ' + fmtDate(weekStart) + ' al ' + fmtDate(weekEnd);

    addHead(grid, 'Hora');
    DAYS.forEach(function (day, i) {
      const dt = addDays(weekStart, i);
      addHead(grid, day + '<small>' + fmtDate(dt) + '</small>');
    });

    HOURS.forEach(function (h) {
      const tc = document.createElement('div');
      tc.className   = 'time-cell';
      tc.textContent = pad(h) + ':00 – ' + pad(h + 1) + ':00';
      grid.appendChild(tc);

      DAYS.forEach(function (_, di) {
        const dateStr = toYMD(addDays(weekStart, di));
        const cell    = document.createElement('div');
        cell.className = 'cal-cell';

        if (PERM_CREAR) {
          cell.dataset.openModalDate = dateStr;
        }

        const evs = CAL_EVENTS.filter(function (e) {
          if (e.fecha !== dateStr) return false;
          // Parsear hora de inicio: acepta "HH:MM", "H:MM" o entero
          var hiStr = String(e.hi || '');
          var hiH   = parseInt(hiStr.split(':')[0], 10);
          return !isNaN(hiH) && hiH === h;
        });
        evs.forEach(function (ev) {
          var ocupado = (ev.area === 'Ocupado');
          var div = document.createElement('div');
          div.className = 'cal-event ' + ev.estado + (ocupado ? ' cal-event-ocupado' : '');

          if (ocupado) {
            /* Usuario regular: solo ve "Ocupado" */
            div.innerHTML = '<strong>🔒 Ocupado</strong>'
              + '<small>' + (ev.hi || '') + (ev.hf ? ' – ' + ev.hf : '') + '</small>';
          } else {
            /* Admin / coordinador / aprobador: ve detalle + icono tipo */
            var icon = tipoIcon(ev.tipo);
            div.innerHTML = '<strong>' + icon + ' ' + ev.tipo + '</strong>'
              + '<small>' + (ev.hi || '') + (ev.hf ? ' – ' + ev.hf : '') + '</small>'
              + '<small>' + (ev.area || '') + '</small>';
            div.dataset.openDetalle = ev.id;
          }
          cell.appendChild(div);
        });

        grid.appendChild(cell);
      });
    });
  }

  function addHead(grid, html) {
    const d = document.createElement('div');
    d.className = 'cal-head';
    d.innerHTML = html;
    grid.appendChild(d);
  }

  function changeWeek(dir) { weekStart = addDays(weekStart, dir * 7); renderCalendar(); }
  function goToday()       { weekStart = getMonday(TODAY_STR); renderCalendar(); }

  /* ── Modales ── */
  function openModal(id)  { const m = document.getElementById(id); if (m) m.classList.add('show'); }
  function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('show');
    if (id === 'modalNueva') resetModalNueva();
  }

  /* ── Selector de tipo de solicitud (iconos) ── */
  function selectTipoSolicitud(tipoVal) {
    var tipoInput = document.getElementById('tipoSolicitudInput');
    if (tipoInput) tipoInput.value = tipoVal;
    document.querySelectorAll('#tipoSolicitudPicker .tipo-icon-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.tipo === tipoVal);
    });
    var body = document.getElementById('camposSolicitudBody');
    if (body) body.classList.toggle('d-none', !tipoVal);
    var err = document.getElementById('errorTipoSolicitud');
    if (err) err.classList.add('d-none');
    toggleCampoVuelo(tipoVal);
    toggleCampoVoucher(tipoVal);
  }

  /* ── Selector rápido de fecha (Hoy / Mañana / Otra fecha) ── */
  function setFechaQuick(mode) {
    var nfecha = document.getElementById('nfecha');
    var picker = document.getElementById('fechaQuickPicker');
    if (!nfecha || !picker) return;
    picker.querySelectorAll('.quick-pick-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.fechaQuick === mode);
    });
    if (mode === 'hoy') {
      nfecha.value = TODAY_STR;
      nfecha.classList.add('d-none');
    } else if (mode === 'manana') {
      nfecha.value = toYMD(addDays(new Date(TODAY_STR + 'T00:00:00'), 1));
      nfecha.classList.add('d-none');
    } else if (mode === 'otra') {
      nfecha.classList.remove('d-none');
      nfecha.focus();
      if (typeof nfecha.showPicker === 'function') {
        try { nfecha.showPicker(); } catch (_) {}
      }
    }
  }

  /* ── Selector rápido de prioridad (Normal / Alta / Urgente) ── */
  function setPrioridad(val) {
    var input  = document.getElementById('prioridadInput');
    var picker = document.getElementById('prioridadPicker');
    if (!input || !picker) return;
    input.value = val;
    picker.querySelectorAll('.quick-pick-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.prioridad === val);
    });
  }

  function resetModalNueva() {
    var tipoInput = document.getElementById('tipoSolicitudInput');
    if (tipoInput) tipoInput.value = '';
    document.querySelectorAll('#tipoSolicitudPicker .tipo-icon-btn').forEach(function (btn) {
      btn.classList.remove('active');
    });
    var body = document.getElementById('camposSolicitudBody');
    if (body) body.classList.add('d-none');
    var err = document.getElementById('errorTipoSolicitud');
    if (err) err.classList.add('d-none');
    toggleCampoVuelo('');
    toggleCampoVoucher('');
    setFechaQuick('hoy');
    setPrioridad('Normal');
  }

  /* ── Nueva solicitud con fecha prellenada ── */
  function openModalNuevaWithDate(dateStr) {
    var nfecha = document.getElementById('nfecha');
    if (nfecha) nfecha.value = dateStr;
    var tomorrow = toYMD(addDays(new Date(TODAY_STR + 'T00:00:00'), 1));
    if (dateStr === TODAY_STR) setFechaQuick('hoy');
    else if (dateStr === tomorrow) setFechaQuick('manana');
    else setFechaQuick('otra');
    openModal('modalNueva');
  }

  /* ── Coordinar ── */
  function openCoordinar(sid, fecha, tipo) {
    /* Para Vuelo: modal especializado */
    if (tipo === 'Vuelo') {
      var fv = document.getElementById('formCoordinarVuelo');
      if (fv) fv.action = '/planificador/solicitudes/' + sid + '/vuelo/coordinar';
      var fr = document.getElementById('formReprogramarVuelo');
      if (fr) fr.action = '/planificador/solicitudes/' + sid + '/vuelo/coordinar';
      var iv = document.getElementById('vuelo-coordinar-info');
      if (iv) iv.textContent = '✈ #' + sid + ' · Vuelo · Fecha: ' + fecha;
      /* Reset hotel toggle */
      var chkH = document.getElementById('chkHotel');
      var txtH = document.getElementById('txtHotel');
      if (chkH) chkH.checked = false;
      if (txtH) { txtH.classList.add('d-none'); txtH.value = ''; txtH.required = false; }
      openModal('modalCoordinarVuelo');
      return;
    }

    const form = document.getElementById('formCoordinar');
    if (form) form.action = '/planificador/solicitudes/' + sid + '/coordinar';
    const info = document.getElementById('coordTipo');
    if (info) info.textContent = tipoIcon(tipo) + ' #' + sid + ' · ' + tipo + ' · ' + fecha;

    /* Resetear sección de agrupación */
    const grupoSection = document.getElementById('grupoSection');
    const grupoList    = document.getElementById('grupoCheckList');
    if (grupoSection) grupoSection.classList.add('grupo-section-hidden');
    if (grupoList)    grupoList.innerHTML = '';

    openModal('modalCoordinar');

    /* Cargar otras solicitudes pendientes del mismo tipo */
    fetch('/planificador/solicitudes/' + sid + '/pendientes-mismo-tipo', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function (r) { return r.json(); })
    .then(function (otros) {
      if (!grupoList) return;
      if (!otros || otros.length === 0) return;  // nada que agrupar

      if (grupoSection) grupoSection.classList.remove('grupo-section-hidden');

      var html = '';
      otros.forEach(function (o) {
        html += '<label class="grupo-check-item">' +
          '<input type="checkbox" name="grupo_ids" value="' + o.id + '" class="grupo-check-input">' +
          '<span class="grupo-check-body">' +
            '<span class="grupo-check-top">' +
              '<span class="grupo-check-id">#' + o.id + '</span>' +
              '<span class="grupo-check-area">' + _esc(o.area) + '</span>' +
              '<span class="grupo-check-fecha">' + o.fecha + '</span>' +
            '</span>' +
            '<span class="grupo-check-lugar"><i class="bi bi-geo-alt-fill"></i> ' + _esc(o.lugar) + '</span>' +
            (o.descripcion ? '<span class="grupo-check-desc">' + _esc(o.descripcion) + '</span>' : '') +
          '</span>' +
        '</label>';
      });
      grupoList.innerHTML = html;
    })
    .catch(function () { /* silencioso si falla */ });
  }

  /* ── Reagendar ── */
  function todayIso() {
    const d = new Date();
    return d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  function openReagendar(sid, fecha, tipo) {
    const form = document.getElementById('formReagendarModal');
    if (form) form.action = '/planificador/solicitudes/' + sid + '/reagendar';
    const info = document.getElementById('reagendarInfo');
    if (info) info.textContent = '#' + sid + ' · ' + tipo + ' · Fecha actual: ' + fecha;
    // Bloquear fechas anteriores a hoy
    const inp = form && form.querySelector('input[name="nueva_fecha"]');
    if (inp) { inp.min = todayIso(); inp.value = ''; }
    openModal('modalReagendar');
  }

  /* ── Aprobar Grupo ── */
  function openAprobarGrupo(grupoId, tipo) {
    const info = document.getElementById('aprobarGrupoInfo');
    if (info) info.textContent = tipoIcon(tipo) + ' Grupo #' + grupoId + ' · ' + tipo;
    const form = document.getElementById('formAprobarGrupo');
    if (form) form.action = '/planificador/solicitudes/grupo/' + grupoId + '/aprobar';
    openModal('modalAprobarGrupo');
  }

  /* ── Aprobar / Rechazar ── */
  function openAprobar(sid, tipo) {
    const info = document.getElementById('aprobarTipo');
    if (info) info.textContent = '#' + sid + ' · ' + tipo;
    const fA = document.getElementById('formAprobar');
    const fR = document.getElementById('formRechazar');
    if (fA) fA.action = '/planificador/solicitudes/' + sid + '/aprobar';
    if (fR) fR.action = '/planificador/solicitudes/' + sid + '/rechazar';
    const obs = document.getElementById('obsAprobador');
    if (obs) obs.value = '';
    openModal('modalAprobar');
  }

  /* ── Detalle via fetch ── */
  function openDetalle(sid) {
    const body = document.getElementById('detalleBody');
    if (body) body.innerHTML = '<div class="text-center text-muted py-4"><i class="bi bi-arrow-repeat"></i> Cargando...</div>';
    openModal('modalDetalle');
    fetch('/planificador/solicitudes/' + sid + '/detalle', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function (r) { return r.text(); })
    .then(function (html) {
      if (body) {
        body.innerHTML = html;
        _setupDetalleBody(body);
      }
    })
    .catch(function () { if (body) body.innerHTML = '<div class="text-danger p-3">Error al cargar el detalle.</div>'; });
  }

  function _setupDetalleBody(container) {
    _setupVoucherAjax(container);
    _setupCotizarVuelo(container);
    /* min=hoy en inputs con data-min-today (evita inline script) */
    container.querySelectorAll('[data-min-today]').forEach(function (el) {
      el.min = el.dataset.minToday;
    });
    /* Preview hora salida / regreso */
    var inpHI  = container.querySelector('#vueloHoraInicioDetalle');
    var inpHF  = container.querySelector('#vueloHoraFinDetalle');
    var preBox = container.querySelector('#vueloHoraPreviewDetalle');
    var preTxt = container.querySelector('#vueloHoraPreviewTextoDetalle');
    /* Leer fecha de solicitud desde el campo oculto si existe, o del texto visible */
    function _fmtFecha(isoStr) {
      if (!isoStr) return '';
      var p = isoStr.split('-');
      if (p.length < 3) return isoStr;
      return p[2] + '/' + p[1] + '/' + p[0];
    }
    function _actualizarPreviewHora() {
      if (!inpHI || !preBox || !preTxt) return;
      var hi = inpHI.value;
      if (!hi) { preBox.classList.add('d-none'); return; }
      var hf   = inpHF ? inpHF.value : '';
      var fech = preBox.dataset.fecha ? _fmtFecha(preBox.dataset.fecha) : '';
      var texto = fech ? fech + '  ·  Salida: ' + hi : 'Salida: ' + hi;
      if (hf) texto += '  —  Regreso: ' + hf;
      preTxt.textContent = texto;
      preBox.classList.remove('d-none');
    }
    if (inpHI) inpHI.addEventListener('change', _actualizarPreviewHora);
    if (inpHF) inpHF.addEventListener('change', _actualizarPreviewHora);
    /* Total acumulado en formulario de liquidación */
    var totalEl = container.querySelector('#vueloTotalLiquidacion');
    if (totalEl) {
      var _recalcularTotalLiquidacion = function () {
        var sum = 0;
        container.querySelectorAll('.tipo-costo-input').forEach(function (i) {
          sum += parseFloat(i.value) || 0;
        });
        totalEl.textContent = '$' + sum.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
      };
      container.querySelectorAll('.tipo-costo-input').forEach(function (inp) {
        inp.addEventListener('input', _recalcularTotalLiquidacion);
      });
      _recalcularTotalLiquidacion();
    }

    /* Entrega de vouchers: check por fila + botón deshabilitado hasta completar todos */
    var seqInputs = container.querySelectorAll('.entrega-seq-input');
    if (seqInputs.length) {
      var btnEntregar = container.querySelector('[data-entrega-submit]');
      var _actualizarEntrega = function () {
        var total  = seqInputs.length;
        var llenos = 0;
        seqInputs.forEach(function (inp) {
          var ok = inp.value.trim().length > 0;
          var row = inp.closest('.entrega-voucher-row');
          if (row) row.classList.toggle('entrega-voucher-row--ok', ok);
          if (ok) llenos++;
        });
        if (btnEntregar) {
          btnEntregar.disabled = llenos < total;
          btnEntregar.innerHTML = llenos >= total
            ? '<i class="bi bi-check2-circle me-1"></i>Entregar ' + total + ' voucher' + (total !== 1 ? 's' : '')
            : 'Complete los secuenciales';
        }
      };
      seqInputs.forEach(function (inp) { inp.addEventListener('input', _actualizarEntrega); });
      _actualizarEntrega();
    }
  }

  /* ── Mapa picker ── */
  var _mapTargetFieldId = null;
  var _lastMapQuery     = '';   // último query buscado en el mapa

  function openMapPicker(targetFieldId) {
    _mapTargetFieldId = targetFieldId;
    var srcField = document.getElementById(targetFieldId);
    var initVal  = srcField ? srcField.value.trim() : '';
    var searchEl = document.getElementById('mapSearchInput');
    if (searchEl) searchEl.value = initVal;
    _lastMapQuery = initVal;
    // Si hay texto inicial, cargar el mapa
    if (initVal) { updateMapFrame(initVal); }
    else {
      var fr = document.getElementById('mapFrame');
      if (fr) fr.src = 'about:blank';
    }
    openModal('modalMapa');
  }

  function updateMapFrame(query) {
    var fr = document.getElementById('mapFrame');
    if (!fr || !query.trim()) return;
    _lastMapQuery = query.trim();   // guardar siempre el último query
    fr.src = 'https://maps.google.com/maps?q=' + encodeURIComponent(query.trim()) + '&output=embed';
  }

  function geolocateField(fieldId) {
    if (!navigator.geolocation) {
      alert('Tu navegador no soporta geolocalización.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;
        // Llamar al proxy interno (mismo origen, sin violar CSP)
        fetch('/planificador/reverse-geocode?lat=' + lat + '&lng=' + lng)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.address) {
              var field = document.getElementById(fieldId);
              if (field) field.value = data.address;
              // Abrir mapa con la ubicación
              _mapTargetFieldId = fieldId;
              _lastMapQuery     = data.address;
              var searchEl = document.getElementById('mapSearchInput');
              if (searchEl) searchEl.value = data.address;
              updateMapFrame(data.address);
              openModal('modalMapa');
            }
          })
          .catch(function () { alert('No se pudo obtener la dirección. Ingresa manualmente.'); });
      },
      function () { alert('No se pudo obtener la ubicación. Verifica los permisos del navegador.'); }
    );
  }

  function useMapAddress() {
    var searchEl = document.getElementById('mapSearchInput');
    // Usar lo que hay en el input; si está vacío usar el último query buscado
    var val = (searchEl ? searchEl.value.trim() : '') || _lastMapQuery;
    if (!val) { alert('Busca una dirección primero y verifica en el mapa.'); return; }
    // Sincronizar el input por si estaba vacío
    if (searchEl && !searchEl.value.trim()) searchEl.value = val;
    if (_mapTargetFieldId) {
      var target = document.getElementById(_mapTargetFieldId);
      if (target) target.value = val;
    }
    closeModal('modalMapa');
  }

  /* ── syncObs (usado por el partial de detalle) ── */
  window.planificadorSyncObs = function (form, srcId, destId) {
    const val  = (document.getElementById(srcId) || {}).value || '';
    const dest = document.getElementById(destId);
    if (dest) dest.value = val;
    return true;
  };

  /* ── syncNombre (configuracion.html) ── */
  window.planificadorSyncNombre = function () {
    const sel = document.getElementById('selUsuario');
    const hid = document.getElementById('hidNombre');
    if (!sel || !hid) return;
    const opt = sel.options[sel.selectedIndex];
    hid.value = opt ? (opt.dataset.nombre || '') : '';
  };

  /* ──────────────────────────────────────────
     Event delegation global
  ────────────────────────────────────────── */
  /* ── data-sync-obs: copia textarea → hidden input antes de submit ── */
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-sync-obs]');
    if (btn) {
      const srcId  = btn.dataset.syncObs;
      const destId = btn.dataset.targetObs;
      const src    = document.getElementById(srcId);
      const dest   = document.getElementById(destId);
      if (src && dest) dest.value = src.value;
    }
  });

  /* ── data-toggle-rechazo: alterna caja "Motivo del rechazo" ↔ botones de decisión ── */
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-toggle-rechazo]');
    if (!btn) return;
    const box     = document.getElementById(btn.dataset.toggleRechazo);
    const actions = document.getElementById(btn.dataset.toggleActions);
    if (box) box.classList.toggle('d-none');
    if (actions) actions.classList.toggle('d-none');
  });

  document.addEventListener('click', function (e) {
    const el = e.target.closest('[data-open-modal]');
    if (el) { openModal(el.dataset.openModal); return; }

    const cl = e.target.closest('[data-close-modal]');
    if (cl) { closeModal(cl.dataset.closeModal); return; }

    const cd = e.target.closest('[data-open-detalle]');
    if (cd) { e.stopPropagation(); openDetalle(cd.dataset.openDetalle); return; }

    const co = e.target.closest('[data-open-coordinar]');
    if (co) { openCoordinar(co.dataset.sid, co.dataset.fecha, co.dataset.tipo); return; }

    const re = e.target.closest('[data-open-reagendar]');
    if (re) { openReagendar(re.dataset.sid, re.dataset.fecha, re.dataset.tipo); return; }

    const ap = e.target.closest('[data-open-aprobar]');
    if (ap) { openAprobar(ap.dataset.sid, ap.dataset.tipo); return; }

    const ag = e.target.closest('[data-open-aprobar-grupo]');
    if (ag) { openAprobarGrupo(ag.dataset.grupoId, ag.dataset.tipo); return; }

    /* Celdas del calendario */
    const cell = e.target.closest('[data-open-modal-date]');
    if (cell) { openModalNuevaWithDate(cell.dataset.openModalDate); return; }

    /* Semana nav */
    const wn = e.target.closest('[data-week-dir]');
    if (wn) { changeWeek(parseInt(wn.dataset.weekDir)); return; }

    const wt = e.target.closest('[data-week-today]');
    if (wt) { goToday(); return; }

    /* Geolocalización */
    const gl = e.target.closest('[data-geolocate]');
    if (gl) { geolocateField(gl.dataset.geolocate); return; }

    /* Mapa picker – abrir */
    const mp = e.target.closest('[data-open-map]');
    if (mp) { openMapPicker(mp.dataset.openMap); return; }

    /* Mapa picker – buscar */
    const ms = e.target.closest('[data-search-map]');
    if (ms) {
      var q = (document.getElementById('mapSearchInput') || {}).value || '';
      updateMapFrame(q); return;
    }

    /* Mapa picker – usar dirección */
    const mu = e.target.closest('[data-use-map-address]');
    if (mu) { useMapAddress(); return; }
  });

  /* Cierre al clic en backdrop — solo si el mousedown también fue en el backdrop
     (evita cerrar cuando el usuario arrastra texto desde dentro del modal) */
  var _backdropMouseDownEl = null;
  document.addEventListener('mousedown', function (e) {
    _backdropMouseDownEl = e.target.classList.contains('sgq-modal-backdrop') ? e.target : null;
  });
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('sgq-modal-backdrop') && _backdropMouseDownEl === e.target) {
      e.target.classList.remove('show');
      if (e.target.id === 'modalNueva') resetModalNueva();
    }
  });

  /* Confirmar submit con data-confirm + mostrar spinner */
  document.addEventListener('submit', function (e) {
    const form = e.target;

    // 1. Confirmación
    const msg = form.dataset.confirm;
    if (msg && !confirm(msg)) { e.preventDefault(); return; }

    // 2. Validaciones client-side que podrían cancelar
    //    (se ejecutan en los handlers de abajo; si se cancelan no llegan aquí)

    // 3. Mostrar overlay de carga
    var overlay = document.getElementById('plannerLoadingOverlay');
    if (overlay) overlay.classList.add('show');

    // 4. Deshabilitar el botón submit para evitar doble envío
    var btn = form.querySelector('[type=submit]');
    if (btn) {
      btn.classList.add('btn-loading');
      btn.innerHTML = '<span class="btn-spinner"></span>' + btn.textContent.trim();
      btn.disabled = true;
    }
  });

  /* Sync textarea obs → hidden inputs al aprobar/rechazar (modal principal) */
  document.addEventListener('submit', function (e) {
    const form = e.target;

    if (form.id === 'formAprobar') {
      const src  = document.getElementById('obsAprobador');
      const dest = document.getElementById('obsAprobacion');
      if (src && dest) dest.value = src.value;
    }

    if (form.id === 'formRechazar') {
      const src = document.getElementById('obsAprobador');
      const obs = src ? src.value.trim() : '';
      if (!obs) {
        e.preventDefault();
        alert('Para rechazar debe ingresar una observación.');
        return;
      }
      const dest = document.getElementById('obsRechazo');
      if (dest) dest.value = obs;
    }

    /* Sync del partial de detalle (cargado via AJAX) */
    if (form.id === 'formAprobarDetalle') {
      const src  = document.getElementById('obsAprobDetalle');
      const dest = document.getElementById('obsAprobHidden');
      if (src && dest) dest.value = src.value;
    }

    if (form.id === 'formRechazarDetalle') {
      const src = document.getElementById('obsAprobDetalle');
      const obs = src ? src.value.trim() : '';
      if (!obs) {
        e.preventDefault();
        alert('Para rechazar debe ingresar una observación.');
        return;
      }
      const dest = document.getElementById('obsRechDetalle');
      if (dest) dest.value = obs;
    }

    /* Gerente aprobar/rechazar */
    if (form.id === 'formAprobarGerenteDetalle') {
      const src  = document.getElementById('obsGerenteDetalle');
      const dest = document.getElementById('obsAprobGerenteHidden');
      if (src && dest) dest.value = src.value;
    }

    if (form.id === 'formRechazarGerenteDetalle') {
      const src = document.getElementById('obsGerenteDetalle');
      const obs = src ? src.value.trim() : '';
      if (!obs) {
        e.preventDefault();
        alert('Para rechazar debe ingresar una observación.');
        return;
      }
      const dest = document.getElementById('obsRechGerenteDetalle');
      if (dest) dest.value = obs;
    }
  });

  /* Sync nombre usuario en configuracion.html */
  document.addEventListener('change', function (e) {
    const sel = e.target.closest('[data-sync-nombre]');
    if (!sel) return;
    const opt = sel.options[sel.selectedIndex];
    const hid = document.getElementById(sel.dataset.syncNombre);
    if (hid) hid.value = opt ? (opt.dataset.nombre || '') : '';
  });

  /* Buscar en mapa con Enter */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.id === 'mapSearchInput') {
      e.preventDefault();
      var q = e.target.value.trim();
      if (q) { _lastMapQuery = q; updateMapFrame(q); }
    }
  });

  /* ── Paginación de tablas por tab ── */
  var PAGE_SIZE = 15;

  function initPagination(container) {
    var pg     = container.querySelector('.planner-pagination');
    var info   = container.querySelector('.planner-page-info');
    var nums   = container.querySelector('.planner-page-nums');
    var prev   = container.querySelector('.planner-page-prev');
    var next   = container.querySelector('.planner-page-next');

    if (!pg || !info || !nums || !prev || !next) return;

    var dataRows = [];
    var totalPages = 1;
    var current = 1;
    var bound = false;

    function refreshRows() {
      var rows = Array.from(container.querySelectorAll('tbody tr'));
      dataRows = rows.filter(function(r){ return r.cells.length > 1; });
      totalPages = Math.max(1, Math.ceil(dataRows.length / PAGE_SIZE));
    }

    function render(page) {
      current = page;
      var start = (page - 1) * PAGE_SIZE;
      var end   = start + PAGE_SIZE;
      dataRows.forEach(function(r, i) {
        if (i >= start && i < end) {
          r.classList.remove('pg-hidden');
        } else {
          r.classList.add('pg-hidden');
        }
      });

      info.textContent = 'Mostrando ' + (start + 1) + '–' + Math.min(end, dataRows.length) + ' de ' + dataRows.length;

      // Botones numéricos (máx 5 visibles con elipsis implícita)
      nums.innerHTML = '';
      var pages = buildPageRange(current, totalPages);
      pages.forEach(function(p) {
        if (p === '…') {
          var sp = document.createElement('span');
          sp.className = 'btn btn-sm disabled px-2';
          sp.textContent = '…';
          nums.appendChild(sp);
        } else {
          var btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'btn btn-sm ' + (p === current ? 'btn-secondary' : 'btn-outline-secondary');
          btn.textContent = p;
          btn.addEventListener('click', function(){ render(p); });
          nums.appendChild(btn);
        }
      });

      prev.disabled = current === 1;
      next.disabled = current === totalPages;
      pg.classList.remove('planner-pagination--hidden');
    }

    function buildPageRange(cur, total) {
      if (total <= 7) return Array.from({length: total}, function(_, i){ return i+1; });
      var pages = [];
      if (cur <= 4) {
        pages = [1,2,3,4,5,'…',total];
      } else if (cur >= total - 3) {
        pages = [1,'…',total-4,total-3,total-2,total-1,total];
      } else {
        pages = [1,'…',cur-1,cur,cur+1,'…',total];
      }
      return pages;
    }

    function refreshAndRender() {
      refreshRows();
      if (dataRows.length <= PAGE_SIZE) {
        pg.classList.add('planner-pagination--hidden');
        dataRows.forEach(function(r){ r.classList.remove('pg-hidden'); });
        return;
      }
      if (!bound) {
        prev.addEventListener('click', function(){ if (current > 1) render(current - 1); });
        next.addEventListener('click', function(){ if (current < totalPages) render(current + 1); });
        bound = true;
      }
      render(1);
    }

    refreshAndRender();
    // Expuesto para que el ordenamiento de columnas pueda re-paginar tras reordenar el tbody
    container._plannerRefreshAfterSort = refreshAndRender;
  }

  function initAllPaginations() {
    document.querySelectorAll('[data-paginated-table]').forEach(function(container) {
      initPagination(container);
    });
  }

  /* ── Ordenamiento de columnas por click en encabezado ── */
  function parseEsNumber(s) {
    if (!s) return 0;
    var n = s.replace(/\./g, '').replace(',', '.').replace(/[^\d.-]/g, '');
    var v = parseFloat(n);
    return isNaN(v) ? 0 : v;
  }

  function sortCellValue(tr, idx, type) {
    var td = tr.children[idx];
    if (!td) return '';
    if (td.hasAttribute('data-sort-value')) {
      var raw = td.getAttribute('data-sort-value');
      return type === 'num' ? parseEsNumber(raw) : raw.toLocaleLowerCase();
    }
    var txt = (td.textContent || '').trim();
    if (type === 'num') return parseEsNumber(txt);
    if (type === 'date') {
      var t = Date.parse(txt.replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$3-$2-$1'));
      if (isNaN(t)) t = Date.parse(txt);
      return isNaN(t) ? 0 : t;
    }
    return txt.toLocaleLowerCase();
  }

  function initSortableTable(container) {
    var table = container.querySelector('table');
    var thead = table && table.querySelector('thead');
    var tbody = table && table.querySelector('tbody');
    if (!thead || !tbody) return;

    var sortState = { index: -1, dir: 'asc' };

    function clearIcons() {
      thead.querySelectorAll('th').forEach(function (th) {
        th.classList.remove('sorted-asc', 'sorted-desc');
        var i = th.querySelector('.th-sortable i');
        if (i) {
          i.classList.remove('bi-chevron-up', 'bi-chevron-down');
          i.classList.add('bi-arrow-down-up');
        }
      });
    }

    function setIcon(th, dir) {
      var i = th.querySelector('.th-sortable i');
      if (!i) return;
      i.classList.remove('bi-arrow-down-up', 'bi-chevron-up', 'bi-chevron-down');
      i.classList.add(dir === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down');
    }

    function applySort(th, idx, type) {
      var same = idx === sortState.index;
      sortState.dir = same ? (sortState.dir === 'asc' ? 'desc' : 'asc') : 'asc';
      sortState.index = idx;

      var dataRows = Array.from(tbody.querySelectorAll('tr')).filter(function (r) {
        return r.cells.length > 1;
      });

      dataRows.sort(function (a, b) {
        var va = sortCellValue(a, idx, type);
        var vb = sortCellValue(b, idx, type);
        var c = 0;
        if (va > vb) c = 1; else if (va < vb) c = -1;
        return sortState.dir === 'asc' ? c : -c;
      });

      var frag = document.createDocumentFragment();
      dataRows.forEach(function (r) { frag.appendChild(r); });
      tbody.appendChild(frag);

      clearIcons();
      th.classList.add(sortState.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
      setIcon(th, sortState.dir);

      if (container._plannerRefreshAfterSort) container._plannerRefreshAfterSort();
    }

    thead.querySelectorAll('th[data-sort]').forEach(function (th) {
      var type = (th.getAttribute('data-sort') || 'text').toLowerCase();
      var clickable = th.querySelector('.th-sortable') || th;
      clickable.setAttribute('role', 'button');
      clickable.setAttribute('tabindex', '0');

      clickable.addEventListener('click', function () {
        var idx = Array.from(th.parentElement.children).indexOf(th);
        applySort(th, idx, type);
      });

      clickable.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); clickable.click(); }
      });
    });
  }

  function initAllSortableTables() {
    document.querySelectorAll('[data-paginated-table]').forEach(function(container) {
      initSortableTable(container);
    });
  }

  /* ── Tabs de secciones ── */
  document.addEventListener('click', function (e) {
    const tab = e.target.closest('[data-tab]');
    if (!tab) return;

    // Desactivar todos los tabs y contenidos
    document.querySelectorAll('.planner-tab').forEach(function (t) {
      t.classList.remove('active');
    });
    document.querySelectorAll('.planner-tab-content').forEach(function (c) {
      c.classList.remove('active');
    });

    // Activar el seleccionado
    tab.classList.add('active');
    var target = document.getElementById(tab.dataset.tab);
    if (target) target.classList.add('active');
  });

  /* ── Campos exclusivos de tipo Vuelo ── */
  var TIPO_VUELO = 'Vuelo';

  var VUELO_CAMPOS = [
    { divId: 'campoFechasVueloDiv',   inputId: null,                    required: false },
    { divId: 'campoPuntoSalidaDiv',   inputId: 'campoPuntoSalida',      required: true  },
    { divId: 'campoPuntoDestinoDiv',  inputId: 'campoPuntoDestino',     required: true  },
    { divId: 'campoOrdenServicioDiv', inputId: 'campoOrdenServicio',    required: false },
    { divId: 'campoHospedajeDiv',     inputId: 'campoRequiereHospedaje',required: false },
    { divId: 'campoMotivoVueloDiv',   inputId: 'campoMotivoVuelo',      required: true  },
    { divId: 'campoSaldoPresupDiv',   inputId: null,                    required: false },
  ];

  // Campos genéricos que NO aplican para Vuelo (se ocultan y dejan de ser requeridos)
  var CAMPOS_NO_VUELO = [
    { divId: 'campoPrioridadDiv', inputId: null,           required: false },
    { divId: 'campoLugarDiv',     inputId: 'nlugar',        required: true  },
  ];

  function toggleCampoVuelo(tipoVal) {
    var esVuelo = (tipoVal === TIPO_VUELO);

    // Intercambiar campo fecha normal ↔ date picker Vuelo
    var divFechaReg  = document.getElementById('campoFechaRegularDiv');
    var inpFechaReg  = document.getElementById('nfecha');
    var inpFechaVuelo = document.getElementById('nfechaVuelo');
    if (divFechaReg)  divFechaReg.classList.toggle('d-none', esVuelo);
    if (inpFechaReg) {
      inpFechaReg.required = !esVuelo;
      inpFechaReg.disabled = esVuelo;
      if (esVuelo) inpFechaReg.value = '';
    }
    if (inpFechaVuelo) {
      inpFechaVuelo.required = esVuelo;
      inpFechaVuelo.disabled = !esVuelo;
      if (!esVuelo) inpFechaVuelo.value = '';
    }

    // Mostrar / ocultar resto de campos Vuelo
    VUELO_CAMPOS.forEach(function (c) {
      var div = document.getElementById(c.divId);
      if (!div) return;
      div.classList.toggle('visible', esVuelo);
      if (c.inputId) {
        var inp = document.getElementById(c.inputId);
        if (inp) {
          inp.required = esVuelo && c.required;
          if (!esVuelo) {
            if (inp.type === 'checkbox') inp.checked = false;
            else inp.value = '';
          }
        }
      }
    });

    // Ocultar campos no relevantes para Vuelo
    var campoContactoDiv   = document.getElementById('campoContactoDiv');
    var campoDetalleDirDiv = document.getElementById('campoDetalleDirDiv');
    if (campoContactoDiv)   campoContactoDiv.classList.toggle('d-none', esVuelo);
    if (campoDetalleDirDiv) campoDetalleDirDiv.classList.toggle('d-none', esVuelo);

    // Campos genéricos que Vuelo NO usa (Prioridad, Lugar/destino)
    CAMPOS_NO_VUELO.forEach(function (c) {
      var div = document.getElementById(c.divId);
      if (div) div.classList.toggle('d-none', esVuelo);
      if (c.inputId) {
        var inp = document.getElementById(c.inputId);
        if (inp) {
          inp.required = !esVuelo && c.required;
          if (esVuelo) inp.value = '';
        }
      }
    });

    // "Descripción de la actividad" se llama "Observación" para Vuelo
    var lblDescripcion = document.getElementById('lblDescripcion');
    if (lblDescripcion) {
      lblDescripcion.textContent = esVuelo ? 'Observación *' : 'Descripción de la actividad *';
    }
    var campoDescripcion = document.getElementById('campoDescripcion');
    if (campoDescripcion) {
      campoDescripcion.placeholder = esVuelo
        ? 'Detalle la observación de la solicitud.'
        : 'Detalle qué debe entregar, recibir o gestionar.';
    }

    if (esVuelo) {
      fetchSaldoPresupuesto();
    } else {
      _setBloqueoSinCC(false);
    }

    // Mensaje informativo según tipo
    var noticeNormal = document.getElementById('recNoticeTxt');
    var noticeVuelo  = document.getElementById('recNoticeVuelo');
    if (noticeNormal) noticeNormal.classList.toggle('d-none', esVuelo);
    if (noticeVuelo)  noticeVuelo.classList.toggle('d-none', !esVuelo);
  }

  /* ── Campos exclusivos de tipo Voucher (taxi) ── */
  var TIPO_VOUCHER = 'Voucher';
  var MAX_VOUCHERS = 6;

  function actualizarFilasVoucherOD(numero) {
    var n = parseInt(numero, 10);
    if (isNaN(n)) n = 1;
    if (n > MAX_VOUCHERS) n = MAX_VOUCHERS;
    for (var i = 1; i <= MAX_VOUCHERS; i++) {
      var row = document.getElementById('voucherOdRow' + i);
      var inpO = document.getElementById('vOrigen' + i);
      var inpD = document.getElementById('vDestino' + i);
      var visible = (n > 0) && (i <= n);
      if (row) row.classList.toggle('d-none', !visible);
      if (inpO) inpO.required = visible;
      if (inpD) inpD.required = visible;
    }
  }

  function toggleCampoVoucher(tipoVal) {
    var esVoucher = (tipoVal === TIPO_VOUCHER);

    var divNumVouchers = document.getElementById('campoNumeroVouchersDiv');
    var inpNumVouchers = document.getElementById('campoNumeroVouchers');
    if (divNumVouchers) divNumVouchers.classList.toggle('d-none', !esVoucher);
    if (inpNumVouchers) {
      inpNumVouchers.required = esVoucher;
      if (!esVoucher) inpNumVouchers.value = '1';
    }

    // Filas de Origen/Destino por voucher (reemplazan al campo único Lugar/destino)
    var divVoucherOD = document.getElementById('camposVoucherOrigenDestinoDiv');
    if (divVoucherOD) divVoucherOD.classList.toggle('d-none', !esVoucher);
    if (esVoucher) {
      actualizarFilasVoucherOD(inpNumVouchers ? inpNumVouchers.value : 1);
    } else {
      actualizarFilasVoucherOD(0); // oculta y desmarca required las 6 filas
    }

    // Fecha >= hoy solo para Voucher (mensajería sigue sin restricción)
    var nfecha = document.getElementById('nfecha');
    if (nfecha) nfecha.min = esVoucher ? TODAY_STR : '';

    // Ocultar campos no aplicables a Voucher
    // Ocultar campos no aplicables a Voucher (sin tocar si el tipo es Vuelo, que los oculta por su cuenta)
    var tipoActual = (document.getElementById('tipoSolicitudInput') || {}).value || '';
    if (tipoActual !== TIPO_VUELO) {
      ['campoPrioridadDiv', 'campoContactoDiv', 'campoDetalleDirDiv'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.classList.toggle('d-none', esVoucher);
      });
      // El campo único "Lugar / destino" lo reemplazan las filas por voucher
      var campoLugarDiv = document.getElementById('campoLugarDiv');
      var inpLugar = document.getElementById('nlugar');
      if (campoLugarDiv) campoLugarDiv.classList.toggle('d-none', esVoucher);
      if (inpLugar) inpLugar.required = !esVoucher;
    }

    // Mensaje informativo específico de Voucher (se superpone al de toggleCampoVuelo)
    var noticeNormal  = document.getElementById('recNoticeTxt');
    var noticeVoucher = document.getElementById('recNoticeVoucher');
    if (esVoucher) {
      if (noticeNormal)  noticeNormal.classList.add('d-none');
      if (noticeVoucher) noticeVoucher.classList.remove('d-none');
    } else if (noticeVoucher) {
      noticeVoucher.classList.add('d-none');
    }

    // Para el tipo genérico (ni Vuelo ni Voucher, ej. Mensajería), la caja
    // "Importante" se reemplaza por una leyenda simple de horarios
    var esGenerico       = !esVoucher && tipoActual !== TIPO_VUELO;
    var noticeBox        = document.getElementById('recNoticeInfo');
    var captionGenerico  = document.getElementById('recCaptionGenerico');
    if (noticeBox)       noticeBox.classList.toggle('d-none', esGenerico);
    if (captionGenerico) captionGenerico.classList.toggle('d-none', !esGenerico);
  }

  function actualizarPlaceholderObservacionPorMotivo() {
    var selMotivo = document.getElementById('campoMotivoVuelo');
    var campoDescripcion = document.getElementById('campoDescripcion');
    if (!selMotivo || !campoDescripcion) return;
    if (selMotivo.value === 'Otros') {
      campoDescripcion.placeholder = 'Especifique el motivo de la solicitud.';
    }
  }

  function validarFechasVuelo() {
    var salida  = document.getElementById('nfechaVuelo');
    var regreso = document.getElementById('campoFechaRetorno');
    var err     = document.getElementById('errorFechaVuelo');
    if (!salida || !regreso || !err) return true;
    if (salida.value && regreso.value && regreso.value < salida.value) {
      err.classList.remove('d-none');
      regreso.setCustomValidity('La fecha de regreso no puede ser anterior a la de salida.');
      return false;
    }
    err.classList.add('d-none');
    regreso.setCustomValidity('');
    _checkDuplicadoVuelo();
    return true;
  }

  var _dupTimer = null;
  function _checkDuplicadoVuelo() {
    var salida  = document.getElementById('nfechaVuelo');
    var regreso = document.getElementById('campoFechaRetorno');
    var alerta  = document.getElementById('alertaDuplicadoVuelo');
    var btnEnviar = document.querySelector('#modalNueva [type="submit"]');
    if (!salida || !alerta) return;
    var fecha = salida.value;
    if (!fecha) { alerta.classList.add('d-none'); return; }
    var fechaRetorno = (regreso && regreso.value) ? regreso.value : '';
    clearTimeout(_dupTimer);
    _dupTimer = setTimeout(function () {
      var url = '/planificador/solicitudes/check-duplicado?tipo=Vuelo&fecha=' + fecha +
                (fechaRetorno ? '&fecha_retorno=' + fechaRetorno : '');
      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.duplicado) {
            alerta.querySelector('span, i').nextSibling.textContent =
              ' Ya tienes la solicitud #' + data.solicitud_id + ' activa de Vuelo en la fecha seleccionada' +
              ' (estado: ' + data.estado + '). No podrás guardar hasta que sea completada o rechazada.';
            alerta.classList.remove('d-none');
            if (btnEnviar) btnEnviar.disabled = true;
          } else {
            alerta.classList.add('d-none');
            if (btnEnviar) btnEnviar.disabled = false;
          }
        })
        .catch(function () { alerta.classList.add('d-none'); });
    }, 400);
  }

  function _setBloqueoSinCC(bloquear) {
    var alertSinCC = document.getElementById('alertSinCCVuelo');
    var formNueva   = document.querySelector('#modalNueva form');
    if (!formNueva) return;
    if (alertSinCC) alertSinCC.classList.toggle('visible', bloquear);

    var tipoInput = formNueva.querySelector('input[name="tipo"]');
    if (bloquear) {
      // Bloquea todo el formulario excepto "Tipo de solicitud" y "Cancelar",
      // para que el usuario no pierda tiempo llenando campos que no podrá enviar.
      formNueva.querySelectorAll('input, select, textarea, button').forEach(function (el) {
        if (el === tipoInput) return;
        if (el.classList.contains('tipo-icon-btn')) return;
        if (el.hasAttribute('data-close-modal')) return;
        if (!el.disabled) el.setAttribute('data-blocked-by-cc', '1');
        el.disabled = true;
      });
    } else {
      formNueva.querySelectorAll('[data-blocked-by-cc]').forEach(function (el) {
        el.disabled = false;
        el.removeAttribute('data-blocked-by-cc');
      });
    }
  }

  function fetchSaldoPresupuesto() {
    var ind = document.getElementById('indicadorPresup');
    if (!ind) return;
    ind.className = 'vuelo-presup-ind vuelo-presup-cargando';
    ind.querySelector('.vuelo-presup-label').textContent = 'Verificando presupuesto...';
    _setBloqueoSinCC(false);
    fetch('/planificador/presupuesto/saldo-usuario', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) {
          ind.className = 'vuelo-presup-ind vuelo-presup-sin-cc';
          ind.querySelector('.vuelo-presup-label').textContent = 'Sin centro de costo asignado';
          _setBloqueoSinCC(true);
          return;
        }
        var fmt = function (v) { return '$' + parseFloat(v).toLocaleString('es-EC', {minimumFractionDigits: 2, maximumFractionDigits: 2}); };
        var msgs = {
          verde:    'Presupuesto disponible — saldo ' + fmt(d.saldo) + ' de ' + fmt(d.presupuestado),
          amarillo: 'Presupuesto bajo — saldo ' + fmt(d.saldo) + ' de ' + fmt(d.presupuestado) + ' — verifique con su supervisor',
          rojo:     'Sin presupuesto — ejecutado ' + fmt(d.ejecutado) + ' de ' + fmt(d.presupuestado) + ' — requiere aprobación Gerencia General',
        };
        ind.className = 'vuelo-presup-ind vuelo-presup-' + d.semaforo;
        ind.querySelector('.vuelo-presup-label').textContent = msgs[d.semaforo] || '';
      })
      .catch(function () {
        ind.className = 'vuelo-presup-ind vuelo-presup-sin-cc';
        ind.querySelector('.vuelo-presup-label').textContent = 'No se pudo verificar presupuesto';
      });
  }

  /* ── Init ── */
  document.addEventListener('DOMContentLoaded', function () {
    initAllPaginations();
    initAllSortableTables();
    renderCalendar();

    /* Prellenar fecha de hoy en campo fecha regular (selector rápido) */
    setFechaQuick('hoy');
    var fechaQuickPicker = document.getElementById('fechaQuickPicker');
    if (fechaQuickPicker) {
      fechaQuickPicker.querySelectorAll('.quick-pick-btn').forEach(function (btn) {
        btn.addEventListener('click', function () { setFechaQuick(btn.dataset.fechaQuick); });
      });
    }

    /* Prellenar prioridad Normal (selector rápido) */
    setPrioridad('Normal');
    var prioridadPicker = document.getElementById('prioridadPicker');
    if (prioridadPicker) {
      prioridadPicker.querySelectorAll('.quick-pick-btn').forEach(function (btn) {
        btn.addEventListener('click', function () { setPrioridad(btn.dataset.prioridad); });
      });
    }
    var nfechaVuelo = document.getElementById('nfechaVuelo');
    if (nfechaVuelo) {
      nfechaVuelo.min = TODAY_STR;
      if (!nfechaVuelo.value) nfechaVuelo.value = TODAY_STR;
      nfechaVuelo.addEventListener('change', _checkDuplicadoVuelo);
    }
    var campoFechaRetorno = document.getElementById('campoFechaRetorno');
    if (campoFechaRetorno) {
      campoFechaRetorno.addEventListener('change', _checkDuplicadoVuelo);
    }

    /* Mostrar/ocultar campos según tipo de solicitud (iconos) */
    document.querySelectorAll('#tipoSolicitudPicker .tipo-icon-btn').forEach(function (btn) {
      btn.addEventListener('click', function () { selectTipoSolicitud(btn.dataset.tipo); });
    });

    /* N° de vouchers: máximo 6 (clamp silencioso) + sincroniza filas Origen/Destino visibles */
    var inpNumVouchers = document.getElementById('campoNumeroVouchers');
    if (inpNumVouchers) {
      inpNumVouchers.addEventListener('input', function () {
        var v = parseInt(this.value, 10);
        if (!isNaN(v) && v > MAX_VOUCHERS) {
          this.value = MAX_VOUCHERS;
        }
        actualizarFilasVoucherOD(this.value);
      });
    }

    /* Motivo de vuelo: pista visual cuando se elige "Otros" */
    var selectMotivoVuelo = document.getElementById('campoMotivoVuelo');
    if (selectMotivoVuelo) {
      selectMotivoVuelo.addEventListener('change', actualizarPlaceholderObservacionPorMotivo);
    }

    /* Validación de fechas Vuelo */
    var inpSalida  = document.getElementById('nfechaVuelo');
    var inpRegreso = document.getElementById('campoFechaRetorno');
    if (inpRegreso) inpRegreso.min = TODAY_STR;
    if (inpSalida) {
      inpSalida.addEventListener('change', function () {
        if (inpRegreso && inpRegreso.value && this.value > inpRegreso.value) {
          inpRegreso.value = this.value;
        }
        inpRegreso && (inpRegreso.min = this.value);
        validarFechasVuelo();
      });
    }
    if (inpRegreso) {
      inpRegreso.addEventListener('change', validarFechasVuelo);
    }

    /* Validar antes de enviar */
    var formNueva = document.querySelector('#modalNueva form');
    if (formNueva) {
      formNueva.addEventListener('submit', function (e) {
        var tipoInput = document.getElementById('tipoSolicitudInput');
        if (tipoInput && !tipoInput.value) {
          e.preventDefault();
          var err = document.getElementById('errorTipoSolicitud');
          if (err) err.classList.remove('d-none');
          var picker = document.getElementById('tipoSolicitudPicker');
          if (picker) picker.scrollIntoView({ behavior: 'smooth', block: 'center' });
          return;
        }
        var alertSinCC = document.getElementById('alertSinCCVuelo');
        if (alertSinCC && alertSinCC.classList.contains('visible')) {
          e.preventDefault();
          return;
        }
        if (!validarFechasVuelo()) e.preventDefault();
      });
    }

    /* Ocultar spinner si la página se restauró desde caché (botón atrás) */
    var overlay = document.getElementById('plannerLoadingOverlay');
    if (overlay) overlay.classList.remove('show');
  });

  /* También ocultar al cargar via pageshow (bfcache del navegador) */
  window.addEventListener('pageshow', function () {
    var overlay = document.getElementById('plannerLoadingOverlay');
    if (overlay) overlay.classList.remove('show');
  });

  /* Modal Vuelo: toggle hotel y botón reprogramar */
  document.addEventListener('DOMContentLoaded', function () {
    var chkHotel = document.getElementById('chkHotel');
    var txtHotel = document.getElementById('txtHotel');
    if (chkHotel && txtHotel) {
      chkHotel.addEventListener('change', function () {
        txtHotel.classList.toggle('d-none', !chkHotel.checked);
        txtHotel.required = chkHotel.checked;
        if (!chkHotel.checked) txtHotel.value = '';
      });
    }
    var btnRep = document.getElementById('btnAbrirReprogramar');
    if (btnRep) {
      btnRep.addEventListener('click', function () {
        closeModal('modalCoordinarVuelo');
        openModal('modalReprogramarVuelo');
      });
    }
  });

  /* Aprobación masiva: jefe vuelo y GG */
  document.addEventListener('DOMContentLoaded', function () {
    var checkAll = document.getElementById('check-all-aprobar');
    if (!checkAll) return;

    function syncIds(selector, divId) {
      var div = document.getElementById(divId);
      if (!div) return;
      div.innerHTML = '';
      document.querySelectorAll(selector + ':checked').forEach(function (cb) {
        var inp = document.createElement('input');
        inp.type = 'hidden';
        inp.name = 'ids[]';
        inp.value = cb.value;
        div.appendChild(inp);
      });
    }

    function actualizarBotones() {
      var nJefe = document.querySelectorAll('.check-jefe:checked').length;
      var nGG   = document.querySelectorAll('.check-gg:checked').length;
      var btnJ  = document.getElementById('btn-aprobar-masivo-jefe');
      var btnG  = document.getElementById('btn-aprobar-masivo-gg');
      var cntJ  = document.getElementById('cnt-jefe');
      var cntG  = document.getElementById('cnt-gg');
      if (btnJ) { btnJ.disabled = nJefe === 0; if (cntJ) cntJ.textContent = nJefe; }
      if (btnG) { btnG.disabled = nGG   === 0; if (cntG) cntG.textContent = nGG;   }
      syncIds('.check-jefe', 'aprobar-masivo-jefe-ids');
      syncIds('.check-gg',   'aprobar-masivo-gg-ids');
    }

    checkAll.addEventListener('change', function () {
      document.querySelectorAll('.check-aprobar').forEach(function (cb) {
        cb.checked = checkAll.checked;
      });
      actualizarBotones();
    });

    document.querySelectorAll('.check-aprobar').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var total  = document.querySelectorAll('.check-aprobar').length;
        var marked = document.querySelectorAll('.check-aprobar:checked').length;
        checkAll.indeterminate = marked > 0 && marked < total;
        checkAll.checked = marked === total;
        actualizarBotones();
      });
    });
  });

  // ── Voucher: confirmar sin salir de pantalla (AJAX) ──────────

  // Refleja en la barra de progreso y el pie ("Faltan N por resolver")
  // que un voucher más quedó resuelto (confirmado o no utilizado).
  function _avanzarProgresoVouchers(container) {
    var footer = container.querySelector('[data-voucher-footer]');
    if (!footer) return;

    var total = parseInt(footer.dataset.total || '0', 10);
    var resueltos = parseInt(footer.dataset.resueltos || '0', 10) + 1;
    footer.dataset.resueltos = String(resueltos);

    var pendientes = total - resueltos;
    var textEl = footer.querySelector('[data-voucher-footer-text]');
    if (textEl) {
      textEl.textContent = pendientes > 0
        ? ('Faltan ' + pendientes + ' voucher' + (pendientes !== 1 ? 's' : '') + ' por resolver.')
        : 'Todos los vouchers fueron resueltos.';
    }

    var btn = footer.querySelector('[data-voucher-finalizar]');
    if (btn && pendientes <= 0) { btn.disabled = false; }

    var fill = container.querySelector('[data-voucher-progress-fill]');
    if (fill && total > 0) { fill.style.width = Math.round((resueltos / total) * 100) + '%'; }

    var label = container.querySelector('[data-voucher-progress-label]');
    if (label) { label.textContent = resueltos + ' de ' + total + ' resueltos'; }
  }

  // Toggle "¿Se utilizó este voucher?" -> Sí / No revela el formulario correspondiente
  function _setupVoucherToggle(container) {
    container.querySelectorAll('[data-voucher-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var resolveBox = btn.closest('[data-voucher-resolve]');
        if (!resolveBox) return;

        var eleccion = btn.dataset.voucherToggle; // 'si' | 'no'

        resolveBox.querySelectorAll('[data-voucher-toggle]').forEach(function (b) {
          b.classList.toggle('voucher-toggle-btn--active', b === btn);
        });

        resolveBox.querySelectorAll('[data-voucher-panel]').forEach(function (panel) {
          panel.classList.toggle('d-none', panel.dataset.voucherPanel !== eleccion);
        });
      });
    });
  }

  // Dropzone de "Respaldo": clic o arrastrar-soltar un archivo
  function _setupVoucherDropzone(container) {
    container.querySelectorAll('[data-voucher-dropzone]').forEach(function (zone) {
      var input = zone.parentElement.querySelector('[data-voucher-dropzone-input]');
      var nameEl = zone.querySelector('[data-voucher-dropzone-filename]');
      if (!input) return;

      function mostrarArchivo() {
        if (nameEl) {
          nameEl.textContent = input.files && input.files.length ? input.files[0].name : '';
        }
      }

      zone.addEventListener('click', function () { input.click(); });
      input.addEventListener('change', mostrarArchivo);

      ['dragenter', 'dragover'].forEach(function (evt) {
        zone.addEventListener(evt, function (e) {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.add('voucher-dropzone--dragover');
        });
      });

      ['dragleave', 'dragend'].forEach(function (evt) {
        zone.addEventListener(evt, function (e) {
          e.preventDefault();
          e.stopPropagation();
          zone.classList.remove('voucher-dropzone--dragover');
        });
      });

      zone.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('voucher-dropzone--dragover');

        var archivos = e.dataTransfer && e.dataTransfer.files;
        if (archivos && archivos.length) {
          input.files = archivos;
          mostrarArchivo();
        }
      });
    });
  }

  // Botón "Finalizar solicitud": solo queda habilitado cuando ya no
  // faltan vouchers por resolver; recarga para reflejar el nuevo estado
  // de la solicitud de inmediato (si no, la propia acción del último
  // voucher ya dispara la recarga automática un poco después).
  function _setupVoucherFinalizar(container) {
    container.querySelectorAll('[data-voucher-finalizar]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.disabled) return;
        location.reload();
      });
    });
  }

  // ── Vuelo: cotización del coordinador (total en vivo, obs. plegable) ──
  function _setupCotizarVuelo(container) {
    var form = container.querySelector('[data-cotizar-vuelo-form]');
    if (!form) return;

    var pasajeInp   = form.querySelector('[data-cotizar-pasaje]');
    var hospedajeInp = form.querySelector('[data-cotizar-hospedaje]');
    var totalEl     = form.querySelector('[data-cotizar-total]');
    var totalHintEl = form.querySelector('[data-cotizar-total-hint]');
    var submitBtn   = form.querySelector('[data-cotizar-submit]');
    var hintEl      = form.querySelector('[data-cotizar-hint]');

    function _recalcular() {
      // "Pasaje aéreo" es texto libre (aerolínea, detalle del vuelo, valor…),
      // no un campo numérico puro: se extrae el primer monto que contenga
      // como estimado, igual que ya se hace en otros lados del modulo para
      // sugerir valores desde texto libre similar.
      var pasajeTxt = (pasajeInp.value || '').trim();
      var m = pasajeTxt.match(/\d+(?:[.,]\d+)?/);
      var pasajeNum = m ? parseFloat(m[0].replace(',', '.')) : 0;
      var hospedajeNum = parseFloat((hospedajeInp.value || '0').replace(',', '.')) || 0;
      var total = (pasajeNum || 0) + hospedajeNum;

      if (totalEl) totalEl.textContent = '$' + total.toFixed(2);
      if (totalHintEl) {
        totalHintEl.textContent = pasajeTxt
          ? 'Estimado a partir del monto detectado en el pasaje'
          : 'Ingresa el pasaje para ver el impacto en el presupuesto';
      }

      var listo = pasajeTxt.length > 0;
      if (submitBtn) submitBtn.disabled = !listo;
      if (hintEl) hintEl.textContent = listo ? '' : 'Ingresa el valor del pasaje aéreo.';
    }

    if (pasajeInp) pasajeInp.addEventListener('input', _recalcular);
    if (hospedajeInp) hospedajeInp.addEventListener('input', _recalcular);
    _recalcular();

    var obsToggle = form.querySelector('[data-cotizar-obs-toggle]');
    var obsField  = form.querySelector('[data-cotizar-obs]');
    if (obsToggle && obsField) {
      obsToggle.addEventListener('click', function () {
        obsField.classList.remove('d-none');
        obsToggle.classList.add('d-none');
        obsField.focus();
      });
    }
  }

  function _setupVoucherAjax(container) {
    _setupVoucherToggle(container);
    _setupVoucherDropzone(container);
    _setupVoucherFinalizar(container);

    container.querySelectorAll('form[data-voucher-form="confirmar"]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();

        var fileInput = form.querySelector('[name="adjunto_voucher"]');
        if (!fileInput || !fileInput.files.length) return;

        var statusEl = form.querySelector('.voucher-upload-status');
        var btn      = form.querySelector('[type="submit"]');
        var card     = form.closest('.voucher-item');

        if (statusEl) { statusEl.className = 'voucher-upload-status uploading'; statusEl.textContent = 'Subiendo…'; }
        if (btn) { btn.disabled = true; }

        var fd = new FormData(form);
        fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd,
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) throw new Error(data.msg || 'Error');

          // Actualizar badge del estado
          var badgeEl = card.querySelector('.voucher-item-badge');
          if (badgeEl) {
            badgeEl.innerHTML = '<span class="vbadge vbadge--confirmado">'
              + '<i class="bi bi-hourglass-split me-1"></i>Confirmado, pend. liquidar</span>';
          }

          // Actualizar borde de la tarjeta
          card.classList.remove('voucher-item--entregado', 'voucher-item--pendiente');
          card.classList.add('voucher-item--confirmado');

          // Mostrar adjunto subido
          var adjRow = card.querySelector('.voucher-adjunto-row');
          if (adjRow) {
            adjRow.classList.remove('d-none');
            var vv = adjRow.querySelector('.vmeta-v');
            if (vv) vv.textContent = data.adjunto_nombre || '';
          }

          // Quitar la pregunta Sí/No y ambos formularios; ya no hay nada que resolver en este item
          if (statusEl) { statusEl.className = 'voucher-upload-status ok'; statusEl.textContent = '¡Confirmado!'; }
          var resolveBox = form.closest('[data-voucher-resolve]');
          setTimeout(function () { if (resolveBox) resolveBox.remove(); }, 1200);

          _avanzarProgresoVouchers(container);

          // Si con este ya quedaron todos los vouchers de la solicitud
          // resueltos, el backend movió el estado de la solicitud a
          // "Pend. liquidación (coordinador)". El badge de estado (arriba
          // del modal y en la fila de la tabla) quedaría desactualizado
          // hasta un refresh manual, así que recargamos para reflejarlo.
          if (data.todos_confirmados) {
            if (statusEl) { statusEl.textContent = '¡Confirmado! Actualizando…'; }
            setTimeout(function () { location.reload(); }, 1400);
          }
        })
        .catch(function (err) {
          if (statusEl) { statusEl.className = 'voucher-upload-status err'; statusEl.textContent = err.message || 'Error al subir'; }
          if (btn) { btn.disabled = false; }
        });
      });
    });

    container.querySelectorAll('form[data-voucher-form="no-utilizado"]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();

        var obsInput = form.querySelector('[name="observacion"]');
        if (!obsInput || !obsInput.value.trim()) {
          if (obsInput) obsInput.reportValidity();
          return;
        }

        var statusEl = form.querySelector('.voucher-nouse-status');
        var btn      = form.querySelector('[type="submit"]');
        var card     = form.closest('.voucher-item');

        if (statusEl) { statusEl.className = 'voucher-upload-status uploading'; statusEl.textContent = 'Guardando…'; }
        if (btn) { btn.disabled = true; }

        var fd = new FormData(form);
        fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd,
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) throw new Error(data.msg || 'Error');

          var badgeEl = card.querySelector('.voucher-item-badge');
          if (badgeEl) {
            badgeEl.innerHTML = '<span class="vbadge vbadge--no-utilizado">'
              + '<i class="bi bi-slash-circle me-1"></i>No utilizado</span>';
          }

          card.classList.remove('voucher-item--entregado', 'voucher-item--pendiente', 'voucher-item--confirmado');
          card.classList.add('voucher-item--no-utilizado');

          if (statusEl) { statusEl.className = 'voucher-upload-status ok'; statusEl.textContent = 'Marcado como no utilizado.'; }
          var resolveBox = form.closest('[data-voucher-resolve]');
          setTimeout(function () { if (resolveBox) resolveBox.remove(); }, 1200);

          _avanzarProgresoVouchers(container);

          // Igual que en "confirmar": si esto dejó todos los vouchers
          // resueltos, el estado de la solicitud avanzó en el backend
          // (a liquidación pendiente, o directo a Completada si ninguno
          // requería costo) y hay que recargar para que el badge de
          // estado no se quede mostrando "Pend. confirmación (usuario)".
          if (data.todos_confirmados) {
            if (statusEl) { statusEl.textContent = data.completada
              ? 'Listo, la solicitud quedó completada. Actualizando…'
              : 'Marcado como no utilizado. Actualizando…'; }
            setTimeout(function () { location.reload(); }, 1400);
          }
        })
        .catch(function (err) {
          if (statusEl) { statusEl.className = 'voucher-upload-status err'; statusEl.textContent = err.message || 'Error'; }
          if (btn) { btn.disabled = false; }
        });
      });
    });
  }

  // ── Calendario acordeón ──────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('calendarAccordionHeader');
    if (!toggle) return;
    var body = document.getElementById(toggle.getAttribute('data-calendar-toggle'));
    if (!body) return;

    toggle.addEventListener('click', function () {
      var open = !body.hidden;
      body.hidden = open;
      toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
    });
  });

  // ── Voucher: carga masiva de costos (Excel del proveedor) ─────
  document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('modalCargaMasivaVouchers');
    if (!modal) return;

    var url          = modal.dataset.url || '';
    var inpArchivo   = document.getElementById('cargaMasivaArchivo');
    var btnProcesar  = document.getElementById('btnCargaMasivaProcesar');
    var btnDescargar = document.getElementById('btnCargaMasivaDescargar');
    var statusEl     = document.getElementById('cargaMasivaStatus');
    var resultadoEl  = document.getElementById('cargaMasivaResultado');
    var resumenEl    = document.getElementById('cargaMasivaResumen');
    var tablaBody    = document.querySelector('#cargaMasivaTablaErrores tbody');

    var ultimoResultado = null;

    function limpiarResultado() {
      resultadoEl.classList.add('d-none');
      tablaBody.innerHTML = '';
      resumenEl.textContent = '';
      ultimoResultado = null;
    }

    function mostrarResultado(data) {
      ultimoResultado = data;
      var exitosos = data.exitosos || 0;
      var procesados = data.procesados || 0;
      var errores = data.errores || [];

      resumenEl.textContent = 'Hoja "' + (data.hoja || '') + '": ' + exitosos + ' de ' +
        procesados + ' vouchers cargados correctamente' +
        (errores.length ? ', ' + errores.length + ' con error.' : '.');

      tablaBody.innerHTML = '';
      errores.forEach(function (e) {
        var tr = document.createElement('tr');
        var tdFila = document.createElement('td');
        tdFila.textContent = e.fila;
        var tdVoucher = document.createElement('td');
        tdVoucher.textContent = e.voucher;
        var tdMotivo = document.createElement('td');
        tdMotivo.textContent = e.motivo;
        tr.appendChild(tdFila);
        tr.appendChild(tdVoucher);
        tr.appendChild(tdMotivo);
        tablaBody.appendChild(tr);
      });

      resultadoEl.classList.remove('d-none');
    }

    if (btnProcesar) {
      btnProcesar.addEventListener('click', function () {
        if (!inpArchivo || !inpArchivo.files.length) {
          statusEl.className = 'small mb-2 text-danger';
          statusEl.textContent = 'Selecciona primero un archivo Excel.';
          return;
        }

        limpiarResultado();
        statusEl.className = 'small mb-2 text-primary';
        statusEl.textContent = 'Procesando archivo…';
        btnProcesar.disabled = true;

        var fd = new FormData();
        var csrfEl = document.getElementById('cargaMasivaCsrf');
        if (csrfEl) fd.append('csrf_token', csrfEl.value);
        fd.append('archivo_excel', inpArchivo.files[0]);

        fetch(url, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: fd,
        })
        .then(function (r) {
          return r.json().catch(function () {
            throw new Error('El servidor no devolvió una respuesta válida (posible sesión expirada o token CSRF inválido). Recarga la página e intenta de nuevo.');
          }).then(function (data) { return { status: r.status, data: data }; });
        })
        .then(function (res) {
          if (!res.data.ok) throw new Error(res.data.msg || 'No se pudo procesar el archivo.');
          statusEl.className = 'small mb-2 text-success';
          statusEl.textContent = '¡Archivo procesado!';
          mostrarResultado(res.data);
        })
        .catch(function (err) {
          statusEl.className = 'small mb-2 text-danger';
          statusEl.textContent = err.message || 'Error al procesar el archivo.';
        })
        .finally(function () {
          btnProcesar.disabled = false;
        });
      });
    }

    if (btnDescargar) {
      btnDescargar.addEventListener('click', function () {
        if (!ultimoResultado) return;

        var lineas = [];
        lineas.push('Carga masiva de costos de vouchers');
        lineas.push('Hoja: ' + (ultimoResultado.hoja || ''));
        lineas.push('Procesados: ' + (ultimoResultado.procesados || 0));
        lineas.push('Exitosos: ' + (ultimoResultado.exitosos || 0));
        lineas.push('Errores: ' + (ultimoResultado.errores || []).length);
        lineas.push('');
        if ((ultimoResultado.errores || []).length) {
          lineas.push('Fila\tVoucher\tMotivo');
          ultimoResultado.errores.forEach(function (e) {
            lineas.push(e.fila + '\t' + e.voucher + '\t' + e.motivo);
          });
        } else {
          lineas.push('Sin errores.');
        }

        var blob = new Blob([lineas.join('\n')], { type: 'text/plain;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'carga_masiva_vouchers_' + new Date().toISOString().slice(0, 10) + '.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 500);
      });
    }

    // Al reabrir el modal, empezar limpio
    document.addEventListener('click', function (e) {
      var opener = e.target.closest('[data-open-modal="modalCargaMasivaVouchers"]');
      if (opener) {
        limpiarResultado();
        statusEl.className = 'small mb-2';
        statusEl.textContent = '';
        if (inpArchivo) inpArchivo.value = '';
      }
    });

    // Si al menos un voucher se cargó con éxito, recargar la página al
    // cerrar el modal para que las pestañas/KPIs reflejen los cambios
    // (la carga en sí no recarga la pantalla, solo su propio resultado).
    modal.querySelectorAll('[data-close-modal="modalCargaMasivaVouchers"]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (ultimoResultado && ultimoResultado.exitosos > 0) {
          location.reload();
        }
      });
    });
  });

})();
