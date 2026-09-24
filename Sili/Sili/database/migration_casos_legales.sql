-- ============================================================================
-- Módulo "Casos Legales" -- DDL manual (correr una sola vez en SQL Server)
-- Eliminaciones lógicas: activo = 0 (nunca DELETE físico).
-- ============================================================================

-- Si corriste una versión anterior de este script, las tablas (vacías) se recrean con las columnas nuevas.
IF OBJECT_ID('dbo.casos_legales', 'U') IS NOT NULL AND COL_LENGTH('dbo.casos_legales', 'tipo_tramite') IS NOT NULL
BEGIN
    IF EXISTS (SELECT 1 FROM dbo.casos_legales)
        THROW 50001, 'casos_legales tiene datos con la estructura anterior: no se recrea. Avisa para migrarlos.', 1;
    IF OBJECT_ID('dbo.casos_legales_adjuntos', 'U') IS NOT NULL DROP TABLE dbo.casos_legales_adjuntos;
    IF OBJECT_ID('dbo.casos_legales_avances', 'U') IS NOT NULL DROP TABLE dbo.casos_legales_avances;
    DROP TABLE dbo.casos_legales;
END
GO

IF OBJECT_ID('dbo.casos_legales', 'U') IS NULL
CREATE TABLE dbo.casos_legales (
    id                 INT IDENTITY(1,1) PRIMARY KEY,
    tipo               VARCHAR(10)   NOT NULL,            -- INTERNO / EXTERNO / TTH
    fecha              DATE          NOT NULL,            -- Fecha
    tipo_tarea         NVARCHAR(150) NOT NULL,            -- Tipo de Tarea
    descripcion        NVARCHAR(MAX) NOT NULL,            -- Descripción
    tercero_tipo       CHAR(1)       NULL,                -- C = Cliente, P = Proveedor (terceros.tipo)
    tercero_id         BIGINT        NULL,                -- terceros.id
    cliente_proveedor  NVARCHAR(255) NULL,                -- nombre del tercero al momento de registrar
    tiempo_asignado    DECIMAL(6,2)  NULL,                -- Tiempo asignado (horas)
    requirente_id      INT           NULL,                -- usuarios.id (Usuario solicitante)
    requirente         NVARCHAR(150) NULL,                -- nombre del usuario solicitante
    fecha_fin          DATE          NOT NULL CONSTRAINT DF_casos_legales_ffin DEFAULT (CAST(GETDATE() AS DATE)),
    estado             VARCHAR(10)   NOT NULL CONSTRAINT DF_casos_legales_estado DEFAULT 'ABIERTO',
    creado_por_id      INT           NOT NULL,
    creado_por_nombre  NVARCHAR(150) NOT NULL,
    fecha_creacion     DATETIME      NOT NULL CONSTRAINT DF_casos_legales_fcrea DEFAULT GETDATE(),
    cerrado_por_id     INT           NULL,
    cerrado_por_nombre NVARCHAR(150) NULL,
    fecha_cierre       DATETIME      NULL,
    observacion_cierre NVARCHAR(MAX) NULL,
    activo             BIT           NOT NULL CONSTRAINT DF_casos_legales_activo DEFAULT 1
);
GO

-- Si ya tenías la versión intermedia (con columnas del Excel), solo se agregan las columnas nuevas (sin perder datos).
IF OBJECT_ID('dbo.casos_legales', 'U') IS NOT NULL AND COL_LENGTH('dbo.casos_legales', 'tercero_tipo') IS NULL
BEGIN
    ALTER TABLE dbo.casos_legales ADD tercero_tipo CHAR(1) NULL, tercero_id BIGINT NULL, requirente_id INT NULL;
    ALTER TABLE dbo.casos_legales ALTER COLUMN cliente_proveedor NVARCHAR(255) NULL;
END
GO

IF OBJECT_ID('dbo.casos_legales_avances', 'U') IS NULL
CREATE TABLE dbo.casos_legales_avances (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    caso_id         INT           NOT NULL,
    observacion     NVARCHAR(MAX) NOT NULL,
    usuario_id      INT           NOT NULL,
    usuario_nombre  NVARCHAR(150) NOT NULL,
    fecha           DATETIME      NOT NULL CONSTRAINT DF_casos_legales_av_fecha DEFAULT GETDATE(),
    activo          BIT           NOT NULL CONSTRAINT DF_casos_legales_av_activo DEFAULT 1,
    CONSTRAINT FK_casos_legales_av_caso FOREIGN KEY (caso_id) REFERENCES dbo.casos_legales(id)
);

GO

IF OBJECT_ID('dbo.casos_legales_adjuntos', 'U') IS NULL
CREATE TABLE dbo.casos_legales_adjuntos (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    caso_id          INT           NOT NULL,
    avance_id        INT           NULL,                    -- solo para etapa AVANCE
    etapa            VARCHAR(10)   NOT NULL,                -- REGISTRO / AVANCE / CIERRE
    nombre_original  NVARCHAR(255) NOT NULL,
    nombre_guardado  NVARCHAR(255) NOT NULL,
    tamano           INT           NOT NULL,
    usuario_id       INT           NOT NULL,
    usuario_nombre   NVARCHAR(150) NOT NULL,
    fecha            DATETIME      NOT NULL CONSTRAINT DF_casos_legales_ad_fecha DEFAULT GETDATE(),
    activo           BIT           NOT NULL CONSTRAINT DF_casos_legales_ad_activo DEFAULT 1,
    CONSTRAINT FK_casos_legales_ad_caso FOREIGN KEY (caso_id) REFERENCES dbo.casos_legales(id)
);

GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_casos_legales_estado')
    CREATE INDEX IX_casos_legales_estado ON dbo.casos_legales (estado, activo);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_casos_legales_av_caso')
    CREATE INDEX IX_casos_legales_av_caso ON dbo.casos_legales_avances (caso_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_casos_legales_ad_caso')
    CREATE INDEX IX_casos_legales_ad_caso ON dbo.casos_legales_adjuntos (caso_id);
GO

-- ============================================================================
-- Opción de menú (ajusta parent_id si lo quieres dentro de un grupo; NULL = raíz).
-- El permiso 'casos_legales' aparece solo en Roles y permisos al arrancar la app:
--   ver = lista/abre casos · crear = registra · editar = editar caso, avances y cierre · eliminar = elimina (lógico)
-- Cada caso solo lo ve quien lo registró, su jefe directo (usuarios.jefe_id) y admin.
-- Editar/avances/cierre/eliminar: solo quien lo registró y admin (el jefe directo solo consulta).
-- Los avisos van al jefe directo de quien registra (y a quien registra cuando actúa otro).
-- ============================================================================
-- INSERT INTO dbo.menu_items (parent_id, label, endpoint, icon, order_no, permission, active_key, is_group, is_collaps)
-- VALUES (NULL, N'Casos Legales', 'casos_legales.casos_lista', 'bi bi-briefcase', 90, 'casos_legales', 'casos_legales', 0, 0);
