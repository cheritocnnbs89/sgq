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
  function closeModal(id) { const m = document.getElementById(id); if (m) m.classList.remove('show'); }

  /* ── Nueva solicitud con fecha prellenada ── */
  function openModalNuevaWithDate(dateStr) {
    const f = document.getElementById('nfecha');
    if (f) f.value = dateStr;
    openModal('modalNueva');
  }

  /* ── Coordinar ── */
  function openCoordinar(sid, fecha, tipo) {
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
    .then(function (html) { if (body) body.innerHTML = html; })
    .catch(function () { if (body) body.innerHTML = '<div class="text-danger p-3">Error al cargar el detalle.</div>'; });
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

  /* Cierre al clic en backdrop */
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('sgq-modal-backdrop')) {
      e.target.classList.remove('show');
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
    var rows   = Array.from(container.querySelectorAll('tbody tr'));
    var pg     = container.querySelector('.planner-pagination');
    var info   = container.querySelector('.planner-page-info');
    var nums   = container.querySelector('.planner-page-nums');
    var prev   = container.querySelector('.planner-page-prev');
    var next   = container.querySelector('.planner-page-next');

    if (!pg || !info || !nums || !prev || !next) return;

    // Si no hay suficientes filas (o solo el "empty" row) no mostrar paginación
    var dataRows = rows.filter(function(r){ return r.cells.length > 1; });
    if (dataRows.length <= PAGE_SIZE) {
      pg.classList.add('planner-pagination--hidden');
      return;
    }

    var totalPages = Math.ceil(dataRows.length / PAGE_SIZE);
    var current = 1;

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

    prev.addEventListener('click', function(){ if (current > 1) render(current - 1); });
    next.addEventListener('click', function(){ if (current < totalPages) render(current + 1); });

    render(1);
  }

  function initAllPaginations() {
    document.querySelectorAll('[data-paginated-table]').forEach(function(container) {
      initPagination(container);
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

  /* ── Campo Presupuesto Base Cero (solo tipo Vuelo) ── */
  var TIPO_VUELO = 'Vuelo';
  function toggleCampoVuelo(tipoVal) {
    var div   = document.getElementById('campoPptoBaseDiv');
    var input = document.getElementById('campoPptoBase');
    if (!div || !input) return;
    var esVuelo = (tipoVal === TIPO_VUELO);
    div.classList.toggle('visible', esVuelo);
    input.required = esVuelo;
    if (!esVuelo) input.value = '';
  }

  /* ── Init ── */
  document.addEventListener('DOMContentLoaded', function () {
    initAllPaginations();
    renderCalendar();

    /* Prellenar fecha de hoy en modal nueva */
    const nfecha = document.getElementById('nfecha');
    if (nfecha && !nfecha.value) nfecha.value = TODAY_STR;

    /* Mostrar/ocultar campo Presupuesto Base Cero según tipo */
    var selectTipo = document.querySelector('#modalNueva select[name="tipo"]');
    if (selectTipo) {
      selectTipo.addEventListener('change', function () {
        toggleCampoVuelo(this.value);
      });
      toggleCampoVuelo(selectTipo.value);
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

})();
