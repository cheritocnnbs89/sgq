// UI avanzada: KPIs, búsqueda, densidad, ir a hoy y marcar columna
document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('grid');
  const wrap  = document.getElementById('gridWrap');
  if (!table || !wrap) return;

  const kCumpl = document.getElementById('kpiCumplimiento');
  const kHechos = document.getElementById('kpiHechos');
  const kPend = document.getElementById('kpiPendientes');
  const inputSearch = document.getElementById('fltActividad');
  const btnHoy = document.getElementById('btnHoy');
  const btnLimpiar = document.getElementById('btnLimpiar');

  /* ========= KPIs ========= */
  function computeKPIs(){
    const ticks = table.querySelectorAll('tbody .tick');
    const total = ticks.length;
    const done  = Array.from(ticks).filter(t => t.checked).length;
    const pend  = total - done;
    const pct   = total ? Math.round(done * 100 / total) : 0;

    if (kCumpl) kCumpl.textContent = `${pct}% cumplido`;
    if (kHechos) kHechos.textContent = `${done} hechos`;
    if (kPend) kPend.textContent = `${pend} pendientes`;
  }
  computeKPIs();

  // Recalcular al cambiar un check (tu script original seguirá guardando)
  table.addEventListener('change', ev => {
    if (ev.target.classList.contains('tick')) computeKPIs();
  });

  /* ========= Búsqueda instantánea ========= */
  function normalize(s){ return (s||'').toString().toLowerCase(); }
  function applyFilter(q){
    const query = normalize(q);
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(tr => {
      const act = tr.querySelector('.act-text')?.textContent || '';
      const res = tr.querySelector('.chip-text')?.textContent || '';
      const fre = tr.querySelector('.badge')?.textContent || '';
      const hit = [act,res,fre].some(x => normalize(x).includes(query));
      tr.style.display = hit ? '' : 'none';
    });
  }
  inputSearch?.addEventListener('input', () => applyFilter(inputSearch.value));
  btnLimpiar?.addEventListener('click', () => { inputSearch.value=''; applyFilter(''); inputSearch.focus(); });
  document.addEventListener('keydown', (e) => {
    if (e.key==='Escape'){ inputSearch.value=''; applyFilter(''); }
    if (e.altKey && (e.key==='h' || e.key==='H')) scrollToToday();
  });

  /* ========= Densidad (con botones y atajos) ========= */
  const KEY_DENS = 'ui.planilla.density';
  function setDensity(v){
    wrap.classList.remove('compact','cosy','comfy');
    wrap.classList.add(v);
    localStorage.setItem(KEY_DENS, v);
    document.querySelectorAll('.js-dens').forEach(b => b.classList.toggle('active', b.dataset.d === v));
  }
  setDensity(localStorage.getItem(KEY_DENS) || 'cosy');
  document.querySelectorAll('.js-dens').forEach(b => b.addEventListener('click', () => setDensity(b.dataset.d)));
  document.addEventListener('keydown', (e) => {
    if (!e.altKey) return;
    if (e.key==='1') setDensity('compact');
    if (e.key==='2') setDensity('cosy');
    if (e.key==='3') setDensity('comfy');
  });

  /* ========= Ir a hoy + highlight ========= */
  function scrollToToday(){
    const th = table.querySelector('th.day-col.is-today') ||
               (()=>{ // detecta hoy por fecha si aún no está marcado
                 const todayISO = new Date().toISOString().slice(0,10);
                 return table.querySelector(`th.day-col[data-date="${todayISO}"]`);
               })();
    if (!th) return;
    th.classList.add('is-today');
    const col = th.dataset.col;
    // Scroll suave dentro del wrap
    const rect = th.getBoundingClientRect();
    const wrapRect = wrap.getBoundingClientRect();
    wrap.scrollTo({ left: wrap.scrollLeft + (rect.left - wrapRect.left) - 120, behavior: 'smooth' });
    // Destello suave
    th.animate([{background:'#fff'},{background:'#f1f5ff'},{background:'#fff'}], {duration:800});
  }
  btnHoy?.addEventListener('click', scrollToToday);

  /* ========= Hover column highlight (compat con enhanced.js) ========= */
  function setHoverCol(idx){
    if (!idx) { table.removeAttribute('data-hover-col'); table.style.setProperty('--hover-col', -1); return; }
    table.setAttribute('data-hover-col', '1');
    table.style.setProperty('--hover-col', idx);
  }
  table.addEventListener('mouseover', (ev) => {
    const th = ev.target.closest('th[data-col]'); const td = ev.target.closest('td[data-col]');
    const idx = (th && th.dataset.col) || (td && td.dataset.col);
    setHoverCol(idx);
  });
  table.addEventListener('mouseleave', () => setHoverCol(null));

  /* ========= Click en cabecera: marcar/desmarcar columna ========= */
  table.querySelectorAll('th.js-col-toggle').forEach(th => {
    th.addEventListener('click', () => toggleColumn(th.dataset.col));
    th.addEventListener('dblclick', () => { // ir a esa fecha
      th.scrollIntoView({ behavior:'smooth', inline:'center', block:'nearest' });
    });
  });

  function toggleColumn(colIdx){
    const cells = table.querySelectorAll(`td.day-cell[data-col="${colIdx}"] .tick`);
    if (!cells.length) return;
    // Decide acción: si mayoría está marcada, desmarca; si no, marca
    const marked = Array.from(cells).filter(c => c.checked).length;
    const actionCheck = marked < (cells.length / 2);
    cells.forEach(c => {
      if (c.checked !== actionCheck){
        c.checked = actionCheck;
        // dispara change para que tu planilla_mensual.js persista
        c.dispatchEvent(new Event('change', { bubbles:true }));
      }
    });
    computeKPIs();
  }

  /* ========= Progreso por fila (compat con enhanced.js) ========= */
  function updateRowProgress(tr){
    const ticks = tr.querySelectorAll('td.day-cell .tick');
    if (!ticks.length) return;
    const done = Array.from(ticks).filter(c => c.checked).length;
    const pct  = Math.round(done * 100 / ticks.length);
    const bar  = tr.querySelector('.row-progress');
    if (bar){
      bar.style.setProperty('--p', pct + '%');
      bar.setAttribute('title', pct + '% completado');
    }
  }
  table.querySelectorAll('tbody tr').forEach(updateRowProgress);
  table.addEventListener('change', (ev) => {
    if (ev.target.classList.contains('tick')){
      updateRowProgress(ev.target.closest('tr'));
    }
  });

  // Inicial: marcar hoy si existe y calcular KPIs
  (function initToday(){
    const todayISO = new Date().toISOString().slice(0,10);
    const th = table.querySelector(`th.day-col[data-date="${todayISO}"]`);
    if (th){
      th.classList.add('is-today');
      const col = th.dataset.col;
      table.querySelectorAll(`td.day-cell[data-col="${col}"]`).forEach(td => td.classList.add('is-today'));
    }
  })();
});
