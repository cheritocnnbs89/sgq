-- Recordatorio del día
UPDATE notify_templates
SET tipo='hoy'
WHERE LOWER(tipo) IN ('recordatorio del día','recordatorio del dia','hoy');

-- Resumen semanal
UPDATE notify_templates
SET tipo='resumen_semanal'
WHERE LOWER(tipo) IN ('resumen semanal','semanal');

-- Resumen mensual
UPDATE notify_templates
SET tipo='resumen_mensual'
WHERE LOWER(tipo) IN ('resumen mensual','mensual');

-- Vencidas
UPDATE notify_templates
SET tipo='vencida'
WHERE LOWER(tipo) IN ('tarea vencida','vencidas','vencida');
