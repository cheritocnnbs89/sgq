-- Migración: campo aws_enviado para sincronización de vouchers de taxi con AWS DynamoDB
-- Tabla: planificador_solicitudes
-- Nota: es una columna independiente de gastos_tarjeta.aws_enviado (migration_aws_sync.sql);
-- push_voucher_taxi_inmediato() y push_vouchers_taxi_a_aws() en aws_sync.py leen/escriben
-- esta columna sobre planificador_solicitudes, no sobre gastos_tarjeta.

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='planificador_solicitudes' AND COLUMN_NAME='aws_enviado')
    ALTER TABLE planificador_solicitudes ADD aws_enviado BIT DEFAULT 0;
