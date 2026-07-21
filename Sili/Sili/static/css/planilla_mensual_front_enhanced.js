document.addEventListener('DOMContentLoaded', () => {
  const table = document.querySelector('.planilla');
  const wrap  = document.querySelector('.planilla-wrap');
  if (!table || !wrap) return;

  /* ===== 1) Highlight por columna ===== */
  function setHoverCol(idx){
    if (!idx) { table.removeAttribute('data-hover-col'); table.style.setProperty('--hover-col', -1); return; }
    table.setAttribute('data-hover-col', '1');
    table.style.setProperty('--hover-col', idx);
  }
  table.addEventListener('mouseover', (ev) => {
    const th = ev.target.closest('th[data-col]');
    const td = ev.target.closest('td[data-col]');
    const idx = (th && th.dataset.col) || (td && td.dataset.col);
    setHoverCol(idx);
  });
  table.addEventListener('mouseleave', () => setHoverCol(null));

  /* ===== 2) Resaltar HOY usando data-date del head ===== */
  const todayISO = new Date().toISOString().slice(0,10);
  const headToday = table.querySelector(`th.day-col[data-date="${todayISO}"]`);
  if (headToday){
    headToday.classList.add('is-today');
    const col = headToday.dataset.col;
    table.querySelectorAll(`td.day-cell[data-col="${col}"]`).forEach(td => td.classList.add('is-today'));
  }

  /* ===== 3) Bandas por semana (alternando por fila) ===== */
  table.querySelectorAll('tbody tr').forEach((tr, i) => {
    tr.classList.add((i % 2) ? 'week-band-even' : 'week-band-odd');
  });

  /* ===== 4) Progreso por fila ===== */
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
    const pctLabel = tr.querySelector('.row-pct');
    if (pctLabel) pctLabel.textContent = pct + '%';
  }
  table.querySelectorAll('tbody tr').forEach(updateRowProgress);
  table.addEventListener('change', (ev) => {
    if (ev.target.classList.contains('tick')){
      const tr = ev.target.closest('tr'); updateRowProgress(tr);
    }
  });

  /* ===== 5) Clamp con “ver más / ver menos” automático ===== */
  table.querySelectorAll('.act-title').forEach(box => {
    const text = box.querySelector('.act-text');
    if (!text) return;
    requestAnimationFrame(() => {
      if (text.scrollHeight > text.clientHeight + 4){
        const exp = document.createElement('span');
        exp.className = 'expander';
        exp.textContent = 'ver más';
        exp.addEventListener('click', () => {
          const open = box.classList.toggle('expanded');
          exp.textContent = open ? 'ver menos' : 'ver más';
        });
        box.appendChild(exp);
      }
    });
  });

  /* ===== 6) Densidad con Alt+1/2/3 (persistente) ===== */
  const KEY_DENS = 'ui.planilla.density';
  function setDensity(v){
    wrap.classList.remove('compact','cosy','comfy');
    wrap.classList.add(v);
    localStorage.setItem(KEY_DENS, v);
  }
  setDensity(localStorage.getItem(KEY_DENS) || 'cosy');
  document.addEventListener('keydown', (e) => {
    if (!e.altKey) return;
    if (e.key === '1') setDensity('compact');
    if (e.key === '2') setDensity('cosy');
    if (e.key === '3') setDensity('comfy');
  });

  /* ===== 7) Tooltips Bootstrap si deseas usarlos ===== */
  if (window.bootstrap){
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
  }
});
