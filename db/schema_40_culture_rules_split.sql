-- Schema 40: Split culture_rules into known/undefined variants
-- Allows conditional culture rules based on whether culture is known

-- Insert culture_rules_known (content from _section_culture_rules_with_context)
INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, is_system, updated_by)
SELECT g.id, NULL, 'culture_rules_known', 'Правила работы с культурой (известна)',
       'Используется когда культура определена из контекста',
       'КРИТИЧЕСКИ ВАЖНО - Работа с известной культурой:

✅ Культура ИЗВЕСТНА и указана в контексте консультации
- ИСПОЛЬЗУЙ эту культуру для всех ответов
- НИКОГДА не спрашивай "о какой культуре идёт речь"
- НИКОГДА не спрашивай "какая у вас клубника/малина: летняя или ремонтантная?"
- Даже если в текущем вопросе культура не упомянута явно — используй культуру из контекста
- Даже если информации в базе знаний недостаточно — дай ПОЛНЫЙ ответ на основе агрономических знаний + пометка о модерации
- ЗАПРЕЩЕНО задавать уточняющие вопросы — сразу отвечай на заданный вопрос',
       TRUE, TRUE, 'migration'
FROM prompt_groups g
WHERE g.slug = 'base';

-- Insert culture_rules_undefined (content from _section_culture_rules_undefined)
INSERT INTO prompts (group_id, subgroup_id, slug, name, description, content, is_enabled, is_system, updated_by)
SELECT g.id, NULL, 'culture_rules_undefined', 'Правила работы с культурой (не определена)',
       'Используется когда культура не определена',
       'КРИТИЧЕСКИ ВАЖНО - Определение культуры:

❌ Культура НЕ ОПРЕДЕЛЕНА из вопроса
- ОБЯЗАТЕЛЬНО уточни культуру ПЕРЕД ответом
- Спроси: "Подскажите, о какой культуре идёт речь: клубника, малина, смородина, голубика, жимолость или крыжовник?"
- Не давай рекомендации пока культура не определена
- Будь кратким — ТОЛЬКО вопрос для уточнения',
       TRUE, TRUE, 'migration'
FROM prompt_groups g
WHERE g.slug = 'base';
