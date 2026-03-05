# src/services/llm/season_plan_llm.py

"""
Генерация сезонного плана по статьям культуры.

Читает все 6 статей для культуры → GPT извлекает конкретные задачи/обработки/удобрения
→ структурирует по фазам роста.
"""

import logging
from typing import List, Dict, Any, Optional

from src.services.llm.core_llm import (
    create_chat_completion_with_retry,
    calculate_openai_price,
)

logger = logging.getLogger(__name__)

SEASON_PLAN_SYSTEM_PROMPT = """Ты — агроном-практик. Тебе даны 6 статей по одной ягодной культуре (питание, посадка и уход, защита, почва, сорта, обрезка).

Твоя задача: извлечь ВСЕ конкретные действия, обработки и удобрения из статей и организовать их в сезонный план по фазам роста.

## Формат выхода

Для каждой фазы выведи конкретные задачи. Каждая задача — одно действие с указанием препарата/удобрения/инструмента если есть.

### Фазы роста (в порядке следования):
1. **Ранняя весна (до распускания почек)** — санитарная обрезка, первые обработки, подготовка почвы
2. **Весна (распускание почек — цветение)** — подкормки, профилактика, мульчирование
3. **Цветение** — опыление, обработки (только безопасные для пчёл), полив
4. **Плодоношение** — сбор, подкормки, защита от болезней
5. **После сбора урожая** — восстановительные подкормки, обрезка, обработки
6. **Осень (подготовка к зиме)** — укрытие, финальные обработки, посадка

## Правила:
- ТОЛЬКО конкретные действия из статей — никаких общих фраз и теории
- Указывай конкретные препараты, дозировки, если они упомянуты в статьях
- Если действие относится к нескольким фазам — укажи в каждой
- Не придумывай ничего сверх того, что есть в статьях
- Формат: маркированный список задач внутри каждой фазы
- Пиши кратко и по делу, как памятка для садовода"""


async def generate_season_plan(
    culture_label: str,
    articles: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    reasoning_effort: str = "medium",
) -> Dict[str, Any]:
    """
    Генерирует сезонный план по статьям культуры.

    Args:
        culture_label: Русское название культуры (напр. "Клубника летняя")
        articles: Список статей [{category_key, topic, article_text}, ...]
        model: LLM модель (по умолчанию gpt-5.1)
        reasoning_effort: Уровень reasoning (low/medium/high)

    Returns:
        {
            "plan_text": str,
            "cost_usd": float,
            "prompt_tokens": int,
            "completion_tokens": int,
        }
    """
    model = model or "gpt-5.1"

    # Собираем все статьи в один текст
    articles_text = ""
    for art in articles:
        cat_label = art.get("topic") or art.get("category_key", "")
        text = art.get("article_text", "")
        articles_text += f"\n\n--- СТАТЬЯ: {cat_label} ---\n{text}"

    user_message = (
        f"Культура: {culture_label}\n\n"
        f"Статьи ({len(articles)} шт.):\n{articles_text}\n\n"
        f"Составь сезонный план действий по этой культуре на основе статей выше."
    )

    messages = [
        {"role": "system", "content": SEASON_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    result = await create_chat_completion_with_retry(
        messages=messages,
        model=model,
        reasoning_effort=reasoning_effort,
    )

    plan_text = result["content"]
    prompt_tokens = result["prompt_tokens"]
    completion_tokens = result["completion_tokens"]
    cost = calculate_openai_price(model, prompt_tokens, completion_tokens)

    logger.info(
        f"[season_plan_llm] План для {culture_label}: "
        f"{len(plan_text)} символов, {prompt_tokens}+{completion_tokens} токенов, ${cost:.4f}"
    )

    return {
        "plan_text": plan_text,
        "cost_usd": cost,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
