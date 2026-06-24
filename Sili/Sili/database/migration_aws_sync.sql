-- Migración: campos para sincronización con AWS DynamoDB
-- Tabla: gastos_tarjeta (cubre tarjeta, caja_chica y reembolso)

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='aws_enviado')
    ALTER TABLE gastos_tarjeta ADD aws_enviado BIT DEFAULT 0;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='ga_aws_sync')
    ALTER TABLE gastos_tarjeta ADD ga_aws_sync BIT DEFAULT 0;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='gf_aws_sync')
    ALTER TABLE gastos_tarjeta ADD gf_aws_sync BIT DEFAULT 0;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='gg_aws_sync')
    ALTER TABLE gastos_tarjeta ADD gg_aws_sync BIT DEFAULT 0;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='ga_aprobado_origen')
    ALTER TABLE gastos_tarjeta ADD ga_aprobado_origen VARCHAR(10) NULL;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='gf_aprobado_origen')
    ALTER TABLE gastos_tarjeta ADD gf_aprobado_origen VARCHAR(10) NULL;

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='gastos_tarjeta' AND COLUMN_NAME='gg_aprobado_origen')
    ALTER TABLE gastos_tarjeta ADD gg_aprobado_origen VARCHAR(10) NULL;
