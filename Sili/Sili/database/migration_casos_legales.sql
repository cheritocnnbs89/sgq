-- ============================================================================
-- Módulo "Casos Legales" -- DDL manual (correr una sola vez en SQL Server)
-- Eliminaciones lógicas: activo = 0 (nunca DELETE físico).
-- ============================================================================

IF OBJECT_ID('dbo.casos_legales', 'U') IS NULL
CREATE TABLE dbo.casos_legales (
    id                   INT IDENTITY(1,1) PRIMARY KEY,
    tipo                 VARCHAR(10)   NOT NULL,            -- INTERNO / EXTERNO / TTH
    tipo_tramite         NVARCHAR(150) NOT NULL,            -- "Tipo Trámite/Caso"
    estudio_juridico     NVARCHAR(200) NULL,
    observacion          NVARCHAR(MAX) NOT NULL,
    fecha_tramite        DATE          NOT NULL,
    fecha_fin_tentativa  DATE          NULL,
    estado               VARCHAR(10)   NOT NULL CONSTRAINT DF_casos_legales_estado DEFAULT 'ABIERTO',
    creado_por_id        INT           NOT NULL,
    creado_por_nombre    NVARCHAR(150) NOT NULL,
    fecha_creacion       DATETIME      NOT NULL CONSTRAINT DF_casos_legales_fcrea DEFAULT GETDATE(),
    cerrado_por_id       INT           NULL,
    cerrado_por_nombre   NVARCHAR(150) NULL,
    fecha_cierre         DATETIME      NULL,
    observacion_cierre   NVARCHAR(MAX) NULL,
    activo               BIT           NOT NULL CONSTRAINT DF_casos_legales_activo DEFAULT 1
);

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

CREATE INDEX IX_casos_legales_estado ON dbo.casos_legales (estado, activo);
CREATE INDEX IX_casos_legales_av_caso ON dbo.casos_legales_avances (caso_id);
CREATE INDEX IX_casos_legales_ad_caso ON dbo.casos_legales_adjuntos (caso_id);

-- ============================================================================
-- Gestores a los que se notifica cada caso nuevo (ids de `usuarios`, separados por coma).
-- Internos -> Sandra Chambers. Busca su id y reemplaza <ID_SANDRA>.
-- ============================================================================
-- SELECT id, username, nombre_completo FROM usuarios WHERE nombre_completo LIKE '%Chambers%';
-- INSERT INTO configuracion (clave, valor) VALUES ('casos_legales_gestores_INTERNO', '<ID_SANDRA>');
-- INSERT INTO configuracion (clave, valor) VALUES ('casos_legales_gestores_EXTERNO', '');   -- Financiero (por definir)
-- INSERT INTO configuracion (clave, valor) VALUES ('casos_legales_gestores_TTH', '');       -- TTH (por definir)

-- ============================================================================
-- Opción de menú (ajusta parent_id si lo quieres dentro de un grupo; NULL = raíz).
-- El permiso 'casos_legales' aparece solo en Roles y permisos al arrancar la app:
--   ver = lista sus casos · crear = registra casos · editar = gestor (ve todos los casos)
-- ============================================================================
-- INSERT INTO dbo.menu_items (parent_id, label, endpoint, icon, order_no, permission, active_key, is_group, is_collaps)
-- VALUES (NULL, N'Casos Legales', 'casos_legales.casos_lista', 'bi bi-briefcase', 90, 'casos_legales', 'casos_legales', 0, 0);
