-- Настройка БД myfin для АИСПВИ (PostgreSQL 18, pgAdmin)
--
-- Рабочая база проекта — myfin. Все шаги ниже выполняйте в Query Tool,
-- подключённом к базе myfin (пользователь postgres или другой суперпользователь).
--
-- Предполагается: база myfin уже создана в pgAdmin.
-- Скрипт создаёт роль приложения aispvi, передаёт ей владение БД myfin
-- и при необходимости выдаёт права на схему public.
--
-- ШАГ 1. pgAdmin: Servers → PostgreSQL 18 → Databases → myfin → ПКМ → Query Tool → Execute (F5).
--
-- Смените пароль в CREATE ROLE на свой и укажите тот же в .env (DATABASE_URL).

CREATE ROLE aispvi WITH
    LOGIN
    PASSWORD 'secret'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    INHERIT
    NOREPLICATION
    CONNECTION LIMIT -1;

ALTER DATABASE myfin OWNER TO aispvi;

-- ШАГ 2. Если роль aispvi уже существует, первая команда выдаст ошибку —
--   тогда выполните только: ALTER DATABASE myfin OWNER TO aispvi;
--   и задайте пароль: ALTER ROLE aispvi PASSWORD 'secret';

-- ШАГ 3 (при ошибках прав на схему public в PG 15+). Тот же Query Tool, база myfin:
--
-- GRANT ALL ON SCHEMA public TO aispvi;
-- GRANT CREATE ON SCHEMA public TO aispvi;
