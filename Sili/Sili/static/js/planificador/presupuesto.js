// Lee los datos de presupuesto embebidos en el DOM (CSP-safe)
var presupSecciones = (function () {
  var el = document.getElementById('presup-secciones-data');
  if (!el) return [];
  try { return JSON.parse(el.textContent); } catch (e) { return []; }
})();

// Índice plano cc_id+tipo → meses para búsqueda rápida
var presupIdx = {};
presupSecciones.forEach(function (sec) {
  (sec.rows || []).forEach(function (row) {
    presupIdx[sec.tipo + '|' + row.cc_id] = row;
  });
});

// ── Agregar CC ────────────────────────────────────────────────
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-agregar-cc')) return;
  var sel = document.getElementById('sel-nuevo-cc');
  if (!sel || !sel.value) {
    alert('Seleccione un centro de costo para agregar.');
    return;
  }
  document.getElementById('form-agregar-cc-id').value = sel.value;
  document.getElementById('form-agregar-cc').submit();
});

// ── Abrir modal de edición mensual ───────────────────────────
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.btn-editar-cc');
  if (!btn) return;

  var ccId     = btn.dataset.ccId;
  var ccNombre = btn.dataset.ccNombre;
  var tipo     = btn.dataset.tipo;
  var row      = presupIdx[tipo + '|' + ccId];

  document.getElementById('modal-cc-id').value         = ccId;
  document.getElementById('modal-tipo-gasto').value    = tipo;
  document.getElementById('modal-cc-nombre').textContent = ccNombre;
  document.getElementById('modal-tipo-label').textContent = tipo;

  if (row && row.meses) {
    row.meses.forEach(function (m) {
      var input = document.getElementById('modal-mes-' + m.mes);
      if (input) input.value = parseFloat(m.monto_presupuestado).toFixed(2);
    });
  }

  var ejecEl = document.getElementById('modal-ejecutado');
  if (ejecEl) ejecEl.textContent = '$' + (row ? parseFloat(row.total_ejec) || 0 : 0).toFixed(2);

  _recalcularTotalModal();

  var modal = new bootstrap.Modal(document.getElementById('modalEditarCC'));
  modal.show();
});

// ── Recalcular total del modal (celda de la tabla + resumen + hint) ──
function _recalcularTotalModal() {
  var modal = document.getElementById('modalEditarCC');
  if (!modal) return;
  var total = 0;
  modal.querySelectorAll('.presup-input').forEach(function (inp) {
    total += parseFloat((inp.value || '0').replace(',', '.')) || 0;
  });

  var totalTxt = '$' + total.toFixed(2);
  var totalCell = modal.querySelector('.presup-total');
  if (totalCell) totalCell.textContent = totalTxt;
  var totalAnualEl = document.getElementById('modal-total-anual');
  if (totalAnualEl) totalAnualEl.textContent = totalTxt;

  var hintEl = document.getElementById('modal-hint');
  if (hintEl) {
    hintEl.textContent = total === 0
      ? 'Ingresa al menos un mes con monto.'
      : 'Los cambios se registran con tu usuario.';
  }
}

document.addEventListener('input', function (e) {
  if (!e.target.classList.contains('presup-input')) return;
  _recalcularTotalModal();
});

// ── "Repartir en 12 meses": reparte el total actual en partes iguales ──
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-repartir-meses')) return;
  var modal = document.getElementById('modalEditarCC');
  if (!modal) return;

  var inputs = modal.querySelectorAll('.presup-input');
  var total = 0;
  inputs.forEach(function (inp) { total += parseFloat((inp.value || '0').replace(',', '.')) || 0; });

  if (total <= 0) return;

  var base = Math.floor((total / 12) * 100) / 100;
  var acumulado = 0;
  inputs.forEach(function (inp, i) {
    var valor = (i === inputs.length - 1) ? Math.round((total - acumulado) * 100) / 100 : base;
    acumulado += valor;
    inp.value = valor.toFixed(2);
  });

  _recalcularTotalModal();
});

// ── "Limpiar": pone todos los meses en 0 ──────────────────────
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-limpiar-meses')) return;
  var modal = document.getElementById('modalEditarCC');
  if (!modal) return;
  modal.querySelectorAll('.presup-input').forEach(function (inp) { inp.value = '0.00'; });
  _recalcularTotalModal();
});

// ── "Ocultar meses en cero": oculta columnas de mes sin montos ─
document.addEventListener('click', function (e) {
  var btn = e.target.closest('#btn-ocultar-meses-cero');
  if (!btn) return;

  var activo = btn.classList.toggle('presup-toggle-activo');
  btn.classList.toggle('btn-outline-secondary', !activo);
  btn.classList.toggle('btn-primary', activo);

  if (!activo) {
    document.querySelectorAll('[data-mes]').forEach(function (el) { el.classList.remove('d-none'); });
    return;
  }

  // Meses con algún monto > 0 en cualquier tabla visible
  var mesesConDatos = {};
  document.querySelectorAll('td[data-mes][data-monto]').forEach(function (td) {
    if (parseFloat(td.dataset.monto) > 0) mesesConDatos[td.dataset.mes] = true;
  });

  document.querySelectorAll('[data-mes]').forEach(function (el) {
    el.classList.toggle('d-none', !mesesConDatos[el.dataset.mes]);
  });
});
