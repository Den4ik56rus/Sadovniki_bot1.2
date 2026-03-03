-- schema_86_presentation_image_model.sql
-- Добавляем выбор модели изображений и тестовый режим (1 слайд)

ALTER TABLE presentations ADD COLUMN IF NOT EXISTS image_model TEXT;
ALTER TABLE presentations ADD COLUMN IF NOT EXISTS test_slide_index INTEGER;
-- test_slide_index: если NOT NULL — генерируем только этот слайд (0-based)
