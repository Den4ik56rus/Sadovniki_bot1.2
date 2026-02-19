# src/services/llm/complexity_llm.py

"""
Классификация сложности вопроса с помощью LLM.

Задача detect_answer_complexity:
    - По тексту вопроса, категории и культуре определить уровень сложности ответа.
    - Уровни: short_answer (1 кредит), long_answer (2 кредита).
    - Для long_answer: ИИ сам определяет фазу (кроме "весь сезон" — с весны).
    - Различать Тип B (1 фаза) и Тип C (несколько фаз / весь сезон).
"""

import json
import logging
from typing import TypedDict, Optional

from src.services.llm.core_llm import create_chat_completion_with_usage, calculate_cost
from src.services.db.settings_repo import (
    get_model_for_task,
    get_temperature_for_task,
    get_reasoning_effort_for_task,
)

logger = logging.getLogger(__name__)


class ComplexityResult(TypedDict):
    """Результат классификации сложности вопроса."""
    tier: str                          # short_answer | long_answer
    metadata: dict                     # current_phase, next_phase, topics, user_requested_more, total_phases, multi_topic
    suggest_turnkey: bool              # True если нужно предложить готовое решение
    cost_usd: float                    # Стоимость LLM вызова
    tokens: int                        # Количество использованных токенов
    confirm_message: str               # Персонализированное сообщение для пользователя
    phase_button_label: str            # Короткая подпись для кнопки фазы (макс 35 символов)
    phase_eligible: bool               # True если short_answer, но можно ответить подробнее по фазам


# Фазы сезона
SEASONAL_PHASES = [
    "весна-цветение",
    "цветение-плодоношение",
    "плодоношение-зима",
]

PHASE_NEXT = {
    "весна-цветение": "цветение-плодоношение",
    "цветение-плодоношение": "плодоношение-зима",
    "плодоношение-зима": None,
}


def _build_complexity_prompt() -> str:
    """Строит системный промпт для классификатора сложности."""
    return """Ты — классификатор сложности вопросов по ягодным культурам.
Твоя задача: определить уровень сложности ответа, который потребуется для вопроса пользователя.

2 УРОВНЯ СЛОЖНОСТИ:

1. short_answer (Тип A — простой вопрос, 1 кредит) — ЭТО ВАРИАНТ ПО УМОЛЧАНИЮ
   Критерии (хотя бы ОДИН):
   - Точечный вопрос с конкретным ответом
   - Вопрос про ОДНО действие, ОДИН препарат, ОДИН момент
   - Вопрос "чем/когда/как" без слов "план", "схема", "последовательность", "расписать"
   - Не содержит явного запроса на ПЛАН, СХЕМУ, КАЛЕНДАРЬ
   - Вопрос, на который можно ответить 3-5 пунктами

   ВАЖНО: Если сомневаешься между short_answer и long_answer — ВСЕГДА выбирай short_answer.
   long_answer только когда пользователь ЯВНО просит план, схему или расписание.

   Примеры short_answer:
     * "Какая кислотность почвы нужна для голубики?"
     * "Как подкислить почву?"
     * "Какие сорта малины самые урожайные?"
     * "Когда лучше обрезать малину?"
     * "Чем обработать клубнику от серой гнили?"
     * "Как укрыть клубнику на зиму?"
     * "Чем подкормить клубнику весной?" — ЭТО short_answer! (конкретное действие, один сезон)
     * "Чем обработать малину от вредителей?" — short_answer (конкретное действие)
     * "Когда и чем подкормить голубику?" — short_answer (конкретный вопрос)
     * "Какие удобрения нужны для малины весной?" — short_answer
     * "Нужно ли мульчировать клубнику?" — short_answer

   ДОПОЛНИТЕЛЬНО для short_answer — определи phase_eligible (true/false):

   phase_eligible=true — вопрос простой, НО ответ МОЖЕТ быть значительно полезнее,
   если расписать его по фазам роста. Тема вопроса естественно меняется в зависимости от сезона.
   Критерии phase_eligible=true (хотя бы ОДИН):
   - Вопрос про ПИТАНИЕ/ПОДКОРМКИ культуры (разные удобрения в разные фазы)
   - Вопрос про ЗАЩИТУ/ОБРАБОТКИ (разные препараты в разные фазы)
   - Вопрос про ОБРЕЗКУ (разная обрезка весной/летом/осенью)
   - Вопрос про ПОЛИВ (разный режим по фазам)
   - Общий вопрос про уход за культурой (питание клубники, уход за малиной)

   Примеры phase_eligible=true:
     * "Питание клубники" — можно кратко перечислить удобрения ИЛИ расписать по фазам
     * "Чем подкормить малину?" — можно кратко ИЛИ подробно по фазам роста
     * "Обработка голубики от вредителей" — разные обработки в разные фазы
     * "Как поливать клубнику?" — режим полива меняется по фазам

   phase_eligible=false — вопрос имеет один конкретный ответ, НЕ зависящий от фазы роста.
   Примеры phase_eligible=false:
     * "Какая кислотность почвы нужна для голубики?" — факт, не зависит от сезона
     * "Какие сорта малины самые урожайные?" — подбор сорта не по фазам
     * "Нужно ли мульчировать клубнику?" — да/нет вопрос
     * "Как укрыть клубнику на зиму?" — конкретное одноразовое действие
     * "На каком расстоянии сажать малину?" — факт

   ОБЯЗАТЕЛЬНО для ВСЕХ short_answer заполни confirm_message:
   - Для phase_eligible=true: 2-3 предложения, объясни что ответ зависит от фазы роста.
     Пример: "Вопрос о питании клубники — тема, которая сильно зависит от фазы роста. Я могу дать краткий ответ с основными рекомендациями или подробно расписать подкормки по фазам развития."
   - Для phase_eligible=false: 2-3 предложения, объясни суть вопроса и что можно дать краткий или развёрнутый ответ.
     Пример: "Вопрос о кислотности почвы для голубики — конкретный вопрос с точным ответом. Я могу дать краткий ответ или более развёрнутую рекомендацию с пояснениями."
   - НЕ упоминай стоимость, варианты ответа или кнопки — это добавится отдельно.
   - Тон: дружелюбный, экспертный. Укажи культуру в правильном падеже.

   Если phase_eligible=true, заполни также:
   - phase_button_label: короткая подпись (макс 35 символов), формат "Подробно: [тема] по фазам"
     Пример: "Подробно: подкормки по фазам"

2. long_answer (Тип B/C — фазовый/сезонный вопрос, 2 кредита за фазу)
   Критерии — ОБЯЗАТЕЛЬНО наличие ЯВНОГО запроса на:
   - ПЛАН подкормок/обработок (слова: "план", "схема", "расписать", "распиши")
   - ПОСЛЕДОВАТЕЛЬНОСТЬ работ на период (слова: "последовательность", "по порядку", "пошагово")
   - КАЛЕНДАРЬ действий (слова: "календарь", "график", "по месяцам", "по неделям")
   - ПОЛНУЮ схему на фазу или сезон (слова: "полная схема", "на сезон", "на весь год")
   - Ответ ограничивается ОДНОЙ фазой даже если просят больше

   ВАЖНО — определи количество фаз (total_phases):
   - total_phases=1 (Тип B): вопрос про ОДНУ фазу/период
     Примеры: "Распиши план подкормок клубники на весну", "Дай схему обработок малины летом"
   - total_phases=2-3 (Тип C): вопрос про ВЕСЬ СЕЗОН или несколько фаз
     Примеры: "Дай план защиты на сезон", "Распиши подкормки на весь год"
     Ключевые слова: "на сезон", "на весь год", "план на сезон", "в течение сезона"

   НЕ путай: "Чем подкормить весной?" = short_answer (конкретный вопрос, нет слова "план/схема")

   ОПРЕДЕЛЕНИЕ ФАЗЫ:
   - Для Тип B (total_phases=1): НЕ определяй current_phase. Поставь current_phase=null.
     Следующая ИИ-модель сама выберет наиболее подходящую фазу.
   - Для Тип C (total_phases=2-3, весь сезон): current_phase="весна-цветение" (всегда начинаем с первой фазы).

ОПРЕДЕЛЕНИЕ ТЕМ (topics):
Каждый ответ = ОДНА тема. Возможные темы:
- "питание" — подкормки, удобрения
- "защита" — обработки, болезни, вредители
- "уход" — обрезка, полив, мульчирование, укрытие, посадка

Если пользователь упоминает НЕСКОЛЬКО тем в одном вопросе — установи multi_topic=true.
Примеры multi_topic:
- "Дай план питания и защиты" → multi_topic=true, topics=["питание", "защита"]
- "Нужен план подкормок и обработок" → multi_topic=true, topics=["питание", "защита"]
- "Чем подкормить весной?" → multi_topic=false, topics=["питание"]

ПЕРСОНАЛИЗИРОВАННОЕ СООБЩЕНИЕ:

1. confirm_message (2-3 предложения):
   - Для short_answer: см. правила выше (ОБЯЗАТЕЛЬНО для всех short_answer!)
   - Для long_answer: "Ответ на данный вопрос подразумевает ответ по фазам роста растения."
     Добавь 1 предложение о сути вопроса. НЕ указывай конкретную фазу.
     Пример Тип B: "Ответ на данный вопрос подразумевает ответ по фазам роста растения. Для составления плана подкормок клубники потребуется развёрнутый ответ."
     Пример Тип C: "Ответ на данный вопрос подразумевает ответ по фазам роста растения. Составлю полный план защиты на сезон, начиная с первой фазы."
   - НЕ упоминай стоимость, варианты ответа или кнопки — это добавится отдельно
   - Тон: дружелюбный, экспертный

2. phase_button_label (макс. 35 символов):
   - Для long_answer формат: "План [тема] по фазам роста" (без указания конкретной фазы!)
   - Для phase_eligible=true формат: "Подробно: [тема] по фазам"
   - Для short_answer(phase_eligible=false) — пустая строка ""
   - Примеры: "План подкормок по фазам роста", "Подробно: подкормки по фазам"

ФОРМАТ ОТВЕТА — ТОЛЬКО JSON:

Для short_answer (phase_eligible=false):
{
    "tier": "short_answer",
    "phase_eligible": false,
    "metadata": {
        "current_phase": null,
        "next_phase": null,
        "topics": ["уход"],
        "user_requested_more": false,
        "total_phases": 0,
        "multi_topic": false
    },
    "suggest_turnkey": false,
    "confirm_message": "Вопрос о кислотности почвы для голубики — конкретный вопрос с точным ответом. Я могу дать краткий ответ или более развёрнутую рекомендацию с пояснениями.",
    "phase_button_label": ""
}

Для short_answer (phase_eligible=true):
{
    "tier": "short_answer",
    "phase_eligible": true,
    "metadata": {
        "current_phase": null,
        "next_phase": null,
        "topics": ["питание"],
        "user_requested_more": false,
        "total_phases": 0,
        "multi_topic": false
    },
    "suggest_turnkey": false,
    "confirm_message": "Вопрос о питании клубники — тема, которая сильно зависит от фазы роста. Я могу дать краткий ответ с основными рекомендациями или подробно расписать подкормки по фазам развития.",
    "phase_button_label": "Подробно: подкормки по фазам"
}

Для long_answer (Тип B — одна фаза):
{
    "tier": "long_answer",
    "phase_eligible": false,
    "metadata": {
        "current_phase": null,
        "next_phase": null,
        "topics": ["питание"],
        "user_requested_more": false,
        "total_phases": 1,
        "multi_topic": false
    },
    "suggest_turnkey": false,
    "confirm_message": "Ответ на данный вопрос подразумевает ответ по фазам роста растения. Для составления плана подкормок клубники потребуется развёрнутый ответ.",
    "phase_button_label": "План подкормок по фазам роста"
}

Для long_answer (Тип C — весь сезон):
{
    "tier": "long_answer",
    "phase_eligible": false,
    "metadata": {
        "current_phase": "весна-цветение",
        "next_phase": "цветение-плодоношение",
        "topics": ["защита"],
        "user_requested_more": true,
        "total_phases": 3,
        "multi_topic": false
    },
    "suggest_turnkey": false,
    "confirm_message": "Ответ на данный вопрос подразумевает ответ по фазам роста растения. Составлю полный план защиты на сезон, начиная с первой фазы.",
    "phase_button_label": "План защиты по фазам роста"
}

БЕЗ комментариев, БЕЗ дополнительного текста — ТОЛЬКО JSON!"""


def _default_result(cost_usd: float = 0.0, tokens: int = 0) -> ComplexityResult:
    """Возвращает результат по умолчанию (short_answer) при ошибках."""
    return {
        "tier": "short_answer",
        "metadata": {
            "current_phase": None,
            "next_phase": None,
            "topics": [],
            "user_requested_more": False,
            "total_phases": 0,
            "multi_topic": False,
        },
        "suggest_turnkey": False,
        "cost_usd": cost_usd,
        "tokens": tokens,
        "confirm_message": "",
        "phase_button_label": "",
        "phase_eligible": False,
    }


def _parse_complexity_response(raw: str) -> dict:
    """Парсит JSON ответ LLM. При ошибке возвращает дефолт."""
    try:
        json_str = raw.strip()
        # Очищаем от markdown
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        data = json.loads(json_str)

        # Валидация tier (turnkey_solution временно отключен → long_answer)
        tier = data.get("tier", "short_answer")
        if tier == "turnkey_solution":
            tier = "long_answer"
        if tier not in ("short_answer", "long_answer"):
            tier = "short_answer"

        # Валидация metadata
        metadata = data.get("metadata", {})
        current_phase = metadata.get("current_phase")
        if current_phase and current_phase not in SEASONAL_PHASES:
            current_phase = None

        next_phase = PHASE_NEXT.get(current_phase) if current_phase else None

        topics = metadata.get("topics", [])
        if not isinstance(topics, list):
            topics = []

        user_requested_more = bool(metadata.get("user_requested_more", False))
        suggest_turnkey = bool(data.get("suggest_turnkey", False))

        # total_phases: 0 для short/turnkey, 1-3 для long_answer
        total_phases = metadata.get("total_phases", 0)
        if not isinstance(total_phases, int) or total_phases < 0:
            total_phases = 0
        if tier == "long_answer":
            if total_phases == 0:
                # Определяем по user_requested_more
                total_phases = 3 if user_requested_more else 1
            total_phases = max(1, min(3, total_phases))

        # Для long_answer Тип C (весь сезон) — фиксируем начальную фазу
        if tier == "long_answer" and total_phases >= 2 and not current_phase:
            current_phase = "весна-цветение"
            next_phase = "цветение-плодоношение"
        # Для long_answer Тип B (одна фаза) — НЕ ставим дефолтную фазу, ИИ сам решит

        # multi_topic
        multi_topic = bool(metadata.get("multi_topic", False))
        # Автоматически определяем если topics > 1
        if len(topics) > 1:
            multi_topic = True

        # Персонализированные поля
        confirm_message = str(data.get("confirm_message", "")).strip()
        phase_button_label = str(data.get("phase_button_label", "")).strip()
        if len(phase_button_label) > 35:
            phase_button_label = phase_button_label[:35]

        # phase_eligible: только для short_answer
        phase_eligible = bool(data.get("phase_eligible", False))
        if tier != "short_answer":
            phase_eligible = False

        # Fallback confirm_message для short_answer без сообщения
        if tier == "short_answer" and not confirm_message:
            confirm_message = "Выберите формат ответа на ваш вопрос."

        return {
            "tier": tier,
            "metadata": {
                "current_phase": current_phase,
                "next_phase": next_phase,
                "topics": topics,
                "user_requested_more": user_requested_more,
                "total_phases": total_phases,
                "multi_topic": multi_topic,
            },
            "suggest_turnkey": suggest_turnkey,
            "confirm_message": confirm_message,
            "phase_button_label": phase_button_label,
            "phase_eligible": phase_eligible,
        }

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"[complexity_llm] Ошибка парсинга JSON: {e}, raw={raw[:200]}")
        return {
            "tier": "short_answer",
            "metadata": {
                "current_phase": None,
                "next_phase": None,
                "topics": [],
                "user_requested_more": False,
                "total_phases": 0,
                "multi_topic": False,
            },
            "suggest_turnkey": False,
            "confirm_message": "",
            "phase_button_label": "",
            "phase_eligible": False,
        }


async def detect_answer_complexity(
    question: str,
    category: str,
    culture: str,
) -> ComplexityResult:
    """
    Определяет уровень сложности ответа на вопрос.

    Args:
        question: Текст вопроса пользователя
        category: Категория консультации (питание растений, защита и т.д.)
        culture: Культура (клубника летняя, малина и т.д.)

    Returns:
        ComplexityResult с полями tier, metadata, suggest_turnkey, cost_usd, tokens
    """
    if not question or not question.strip():
        return _default_result()

    system_prompt = _build_complexity_prompt()

    user_prompt = (
        f"Категория консультации: {category}\n"
        f"Культура: {culture}\n\n"
        f"Вопрос пользователя:\n{question}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await create_chat_completion_with_usage(
            messages=messages,
            model=await get_model_for_task("complexity"),
            temperature=await get_temperature_for_task("complexity"),
            reasoning_effort=await get_reasoning_effort_for_task("complexity"),
        )

        cost_usd = calculate_cost(
            model=response["model"],
            prompt_tokens=response["prompt_tokens"],
            completion_tokens=response["completion_tokens"],
        )
        tokens = response["total_tokens"]

        raw = (response.get("content", "") or "").strip()
        if not raw:
            logger.warning(f"[complexity_llm] Пустой ответ для вопроса: {question[:100]}")
            return _default_result(cost_usd, tokens)

        parsed = _parse_complexity_response(raw)

        result: ComplexityResult = {
            **parsed,
            "cost_usd": cost_usd,
            "tokens": tokens,
        }

        logger.info(
            f"[complexity_llm] question={question[:80]!r} "
            f"-> tier={result['tier']}, phase_eligible={result.get('phase_eligible')}, "
            f"phase={result['metadata'].get('current_phase')}, "
            f"total_phases={result['metadata'].get('total_phases')}, "
            f"multi_topic={result['metadata'].get('multi_topic')}, "
            f"cost=${cost_usd:.6f}, tokens={tokens}"
        )

        return result

    except Exception as e:
        logger.error(f"[complexity_llm] Ошибка классификации: {e}, question={question[:100]!r}")
        return _default_result()
