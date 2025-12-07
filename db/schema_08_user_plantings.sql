-- schema_08_user_plantings.sql
-- Таблица посадок пользователя и регион

-- Добавить регион в таблицу users
ALTER TABLE users ADD COLUMN IF NOT EXISTS region TEXT
  CHECK (region IN ('south', 'central', 'north'));

COMMENT ON COLUMN users.region IS 'Регион пользователя: south (Юг), central (Средняя полоса), north (Север)';

-- Таблица посадок пользователя
CREATE TABLE IF NOT EXISTS user_plantings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Культура и сорт
    culture_type TEXT NOT NULL CHECK (culture_type IN (
        'strawberry',   -- Клубника
        'raspberry',    -- Малина
        'blackberry',   -- Ежевика
        'currant',      -- Смородина
        'blueberry',    -- Голубика
        'honeysuckle',  -- Жимолость
        'gooseberry'    -- Крыжовник
    )),

    -- Сорт (зависит от культуры)
    -- strawberry: early, mid, late, remontant
    -- raspberry/blackberry: summer, remontant
    -- остальные: NULL
    variety TEXT CHECK (
        (culture_type = 'strawberry' AND variety IN ('early', 'mid', 'late', 'remontant'))
        OR (culture_type IN ('raspberry', 'blackberry') AND variety IN ('summer', 'remontant'))
        OR (culture_type IN ('currant', 'blueberry', 'honeysuckle', 'gooseberry') AND variety IS NULL)
    ),

    -- Даты плодоношения
    fruiting_start DATE,
    fruiting_end DATE,

    -- Метаданные
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_user_plantings_user_id ON user_plantings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_plantings_culture ON user_plantings(user_id, culture_type);

-- Комментарии
COMMENT ON TABLE user_plantings IS 'Посадки пользователя';
COMMENT ON COLUMN user_plantings.culture_type IS 'Тип культуры: strawberry, raspberry, blackberry, currant, blueberry, honeysuckle, gooseberry';
COMMENT ON COLUMN user_plantings.variety IS 'Сорт: early/mid/late/remontant (клубника), summer/remontant (малина/ежевика), NULL для остальных';
COMMENT ON COLUMN user_plantings.fruiting_start IS 'Дата начала последнего плодоношения';
COMMENT ON COLUMN user_plantings.fruiting_end IS 'Дата конца последнего плодоношения';
