-- schema_25_paid_by_both.sql
-- Добавление опции 'Оба' для paid_by в расходах

-- Удаляем старый constraint
ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_paid_by_check;

-- Добавляем новый constraint с опцией 'Оба'
ALTER TABLE expenses ADD CONSTRAINT expenses_paid_by_check
    CHECK (paid_by IN ('Денис', 'Данил', 'Оба'));
