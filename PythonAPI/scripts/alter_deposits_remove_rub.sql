-- Убрать валюту RUB из каталога: удалить вклады в RUB и обновить ограничение CHECK.
-- Выполнить в pgAdmin на базе myfin (один раз, если таблица уже создана со старым CHECK).

DELETE FROM deposits WHERE currency = 'RUB';

ALTER TABLE deposits DROP CONSTRAINT IF EXISTS ck_deposits_currency;

ALTER TABLE deposits
    ADD CONSTRAINT ck_deposits_currency CHECK (currency IN ('BYN', 'USD', 'EUR'));
