-- schema_76: Исправление испорченных target_user_ids (двойная JSON-сериализация)
-- Проблема: target_user_ids хранился как '"[1]"' вместо '[1]'

-- Для broadcasts: извлекаем числовые элементы из испорченного массива
UPDATE broadcasts
SET target_user_ids = (
    SELECT jsonb_agg(DISTINCT elem::int)
    FROM jsonb_array_elements_text(
        CASE
            WHEN jsonb_typeof(target_user_ids) = 'string'
                THEN target_user_ids::text::jsonb
            ELSE target_user_ids
        END
    ) AS elem
    WHERE elem ~ '^\d+$'
)
WHERE target_user_ids IS NOT NULL
  AND target_type = 'manual';

-- Для broadcast_runs: аналогично
UPDATE broadcast_runs
SET target_user_ids = (
    SELECT jsonb_agg(DISTINCT elem::int)
    FROM jsonb_array_elements_text(
        CASE
            WHEN jsonb_typeof(target_user_ids) = 'string'
                THEN target_user_ids::text::jsonb
            ELSE target_user_ids
        END
    ) AS elem
    WHERE elem ~ '^\d+$'
)
WHERE target_user_ids IS NOT NULL
  AND target_type = 'manual';
