-- Добавление колонок для синхронизации с внешними API (если таблица deposits уже создана без них).
-- Выполнить в pgAdmin на базе myfin: Query Tool → Execute.

ALTER TABLE deposits ADD COLUMN IF NOT EXISTS external_source VARCHAR(32);
ALTER TABLE deposits ADD COLUMN IF NOT EXISTS external_id VARCHAR(32);

COMMENT ON COLUMN deposits.external_source IS 'Источник: belarusbank_api и т.п.; NULL — не из автосинхронизации';
COMMENT ON COLUMN deposits.external_id IS 'Внешний идентификатор продукта (например vklad_id)';

CREATE INDEX IF NOT EXISTS ix_deposits_external_source ON deposits (external_source);
CREATE INDEX IF NOT EXISTS ix_deposits_external_id ON deposits (external_id);
