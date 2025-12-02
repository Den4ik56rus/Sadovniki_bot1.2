# src/services/llm/question_builder_llm.py

"""
Хелпер для сборки ПОЛНОГО вопроса с помощью LLM.

Задача:
    - взять корневой вопрос (root_question),
    - взять ответы на уточняющие вопросы (details_text),
    - вернуть ОДИН компактный, логичный вопрос / запрос на русском,
      где уже учтены:
        * культура,
        * регион,
        * возраст,
        * условия выращивания и т.п.
"""

from typing import Optional

from src.services.llm.core_llm import create_chat_completion
from src.config import settings


async def build_full_question(
    root_question: str,
    details_text: str,
    topic: Optional[str] = None,
) -> str:
    """
    Собирает полный вопрос через LLM.

    Пример входа:
        root_question = "Как питать голубику?"
        details_text = "Голубика садовая, север, первый год"

    Пример выхода:
        "Как правильно питать садовую голубику на севере в первый год после посадки?"
    """

    root_clean = (root_question or "").strip()
    details_clean = (details_text or "").strip()

    # Если уточнений нет — просто возвращаем корень
    if not details_clean:
        return root_clean

    topic_part = f"Тема консультации: {topic}.\n" if topic else ""

    system_prompt = (
        "Ты агроном-консультант и формулируешь окончательный вопрос клиента.\n"
        "У тебя есть:\n"
        "  1) исходный вопрос пользователя;\n"
        "  2) дополнительные детали (культура, регион, возраст растений, условия и т.п.).\n\n"
        "Твоя задача:\n"
        "  - объединить это в ОДИН компактный, понятный вопрос на русском языке;\n"
        "  - вопрос должен содержать конкретную культуру, условия и т.п.;\n"
        "  - не использовать списки, не делать несколько абзацев;\n"
        "  - НИКАКИХ пояснений от себя, только сам итоговый вопрос;\n"
        "  - без приветствий и заключений, только один-два предложения.\n\n"
        "Примеры:\n"
        "  Вход:\n"
        "    исходный: \"Как питать голубику?\"\n"
        "    детали:   \"Голубика садовая, север, первый год\"\n"
        "  Выход:\n"
        "    \"Как правильно питать садовую голубику на севере в первый год после посадки?\"\n\n"
        "  Вход:\n"
        "    исходный: \"Что дать малине весной?\"\n"
        "    детали:   \"Малина ремонтантная, Подмосковье, кусты 3 года, прошлой осенью плохо плодоносила\"\n"
        "  Выход:\n"
        "    \"Какие удобрения и в каких дозах лучше дать ремонтантной малине в Подмосковье весной, "
        "если кустам 3 года и прошлой осенью они плохо плодоносили?\""
    )

    user_content = (
        f"{topic_part}"
        f"Исходный вопрос пользователя:\n"
        f"{root_clean}\n\n"
        f"Дополнительные детали (ответы на уточняющие вопросы):\n"
        f"{details_clean}\n\n"
        f"Сформулируй ОДИН окончательный вопрос с учётом всех деталей."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        llm_answer = await create_chat_completion(
            messages=messages,
            model=settings.openai_model,
            temperature=0.3,
        )

        full = (llm_answer or "").strip()
        # Подстраховка: если модель вернула пусто — ручной фолбэк
        if not full:
            return f"{root_clean}. {details_clean}".strip()

        # На всякий случай уберём лишние переносы строк
        full = " ".join(full.split())
        return full

    except Exception as e:
        print(f"[build_full_question][ERROR] {e} | root={root_clean!r}, details={details_clean!r}")
        # Фолбэк: старое поведение
        return f"{root_clean}. {details_clean}".strip()
