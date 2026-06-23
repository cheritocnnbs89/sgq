-- ============================================================
-- Migración: Frecuencia anual en plan_tareas
-- Ejecutar una sola vez en SQL Server Management Studio
-- ============================================================

-- Agrega columna mes_anual (1-12) para tareas con frecuencia Anual
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'plan_tareas' AND COLUMN_NAME = 'mes_anual'
)
BEGIN
    ALTER TABLE plan_tareas ADD mes_anual INT NULL;
    PRINT 'Columna mes_anual agregada a plan_tareas';
END
ELSE
    PRINT 'Columna mes_anual ya existe';
