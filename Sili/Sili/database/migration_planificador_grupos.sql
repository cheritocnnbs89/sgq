-- ============================================================
-- Migración: Grupos de coordinación para Planificador
-- Ejecutar una sola vez en SQL Server Management Studio
-- ============================================================

-- 1. Tabla de grupos
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'planificador_grupos'
)
BEGIN
    CREATE TABLE planificador_grupos (
        id                 INT IDENTITY(1,1) PRIMARY KEY,
        tipo               NVARCHAR(200)  NOT NULL,
        fecha              DATE           NOT NULL,
        hora_inicio        NVARCHAR(10),
        hora_fin           NVARCHAR(10),
        coordinador_id     INT,
        coordinador_nombre NVARCHAR(200),
        observacion        NVARCHAR(MAX),
        fecha_creacion     DATETIME2      DEFAULT GETDATE()
    );
    PRINT 'Tabla planificador_grupos creada.';
END
ELSE
    PRINT 'Tabla planificador_grupos ya existe.';

-- 2. Columna grupo_id en solicitudes
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'planificador_solicitudes'
      AND COLUMN_NAME = 'grupo_id'
)
BEGIN
    ALTER TABLE planificador_solicitudes
        ADD grupo_id INT NULL
        CONSTRAINT fk_sol_grupo FOREIGN KEY REFERENCES planificador_grupos(id);
    PRINT 'Columna grupo_id agregada a planificador_solicitudes.';
END
ELSE
    PRINT 'Columna grupo_id ya existe.';

PRINT '=== Migración completada ===';
