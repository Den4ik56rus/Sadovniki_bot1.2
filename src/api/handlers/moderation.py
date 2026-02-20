# src/api/handlers/moderation.py
"""
API handlers для модерации вопросов/ответов и управления базой знаний.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from aiohttp import web

from src.services.db.moderation_repo import (
    moderation_get_list,
    moderation_get_by_id,
    moderation_get_by_id_extended,
    moderation_get_stats,
    moderation_update_status,
    moderation_set_category,
    moderation_update_answer,
    moderation_count_pending,
)
from src.services.db.kb_repo import (
    kb_insert,
    kb_get_list,
    kb_get_by_id,
    kb_update,
    kb_get_distinct_categories,
    kb_get_distinct_subcategories,
)
from src.services.llm.gemini_embeddings import get_gemini_embedding
from src.services.llm.core_llm import create_chat_completion

logger = logging.getLogger(__name__)


# ---------- helpers ----------

def _serialize_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_dict(d) -> dict:
    return {k: _serialize_value(v) for k, v in dict(d).items()}


# Валидные категории культур (дубликат из moderation.py для изоляции)
VALID_CULTURE_CATEGORIES = [
    "клубника общая", "клубника летняя", "клубника ремонтантная",
    "малина общая", "малина летняя", "малина ремонтантная",
    "смородина", "голубика", "жимолость", "крыжовник", "ежевика",
    "общая информация",
]


def _normalize_culture_category(raw_category: str) -> str:
    text = raw_category.strip().lower()
    for valid_cat in VALID_CULTURE_CATEGORIES:
        if text == valid_cat.lower():
            return valid_cat
    mapping = {
        "малина": "малина общая",
        "клубника": "клубника общая",
        "земляника": "клубника общая",
    }
    return mapping.get(text, text if text else "общая информация")


# ---------- Queue endpoints ----------

async def get_queue(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/queue"""
    try:
        status = request.query.get("status", "pending")
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        sort = request.query.get("sort", "oldest")

        rows, total = await moderation_get_list(
            status=status, limit=limit, offset=offset, sort=sort,
        )
        pending_count = await moderation_count_pending()

        items = [_serialize_dict(r) for r in rows]
        return web.json_response({
            "items": items,
            "total": total,
            "pending_count": pending_count,
        })
    except Exception as e:
        logger.error(f"get_queue error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_queue_item(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/queue/{id}"""
    try:
        item_id = int(request.match_info["id"])
        row = await moderation_get_by_id_extended(item_id)
        if not row:
            return web.json_response({"error": "Not found"}, status=404)
        return web.json_response(_serialize_dict(row))
    except Exception as e:
        logger.error(f"get_queue_item error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def set_category(request: web.Request) -> web.Response:
    """PATCH /api/admin/moderation/queue/{id}/category"""
    try:
        item_id = int(request.match_info["id"])
        data = await request.json()
        category = data.get("category", "").strip()
        if not category:
            return web.json_response({"error": "category required"}, status=400)

        await moderation_set_category(item_id, category)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"set_category error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def update_answer(request: web.Request) -> web.Response:
    """PATCH /api/admin/moderation/queue/{id}/answer"""
    try:
        item_id = int(request.match_info["id"])
        data = await request.json()
        answer = data.get("answer", "").strip()
        if not answer:
            return web.json_response({"error": "answer required"}, status=400)

        await moderation_update_answer(item_id, answer)
        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"update_answer error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def edit_answer_ai(request: web.Request) -> web.Response:
    """POST /api/admin/moderation/queue/{id}/edit-ai"""
    try:
        item_id = int(request.match_info["id"])
        data = await request.json()
        instructions = data.get("instructions", "").strip()
        if not instructions:
            return web.json_response({"error": "instructions required"}, status=400)

        item = await moderation_get_by_id(item_id)
        if not item:
            return web.json_response({"error": "Not found"}, status=404)

        question = item["question"] or ""
        original_answer = item["answer"] or ""

        # Системный промпт из moderation.py _generate_improved_answer
        system_prompt = (
            "Ты редактор текстов для базы знаний агрономического бота по ягодным культурам.\n\n"
            "КРИТИЧЕСКИ ВАЖНО:\n"
            "- Ты НЕ консультант. Ты технический редактор текстов.\n"
            "- Твоя ЕДИНСТВЕННАЯ задача — выполнить инструкции модератора ТОЧНО.\n"
            "- Если модератор просит заменить ответ на конкретный текст — используй ИМЕННО этот текст.\n"
            "- Если модератор просит сократить до одного слова — сократи до одного слова.\n"
            "- НИКОГДА не отказывайся редактировать текст.\n"
            "- НИКОГДА не пиши отказы типа 'я могу помочь только с...', 'это не моя тема' и т.п.\n"
            "- НЕ копируй вопрос пользователя в свой ответ.\n"
            "- НЕ копируй инструкции модератора в свой ответ.\n"
            "- НЕ добавляй ничего от себя — только то, что просит модератор.\n"
            "- Верни ТОЛЬКО отредактированный текст ответа бота.\n\n"
            "Базовые требования (если модератор не просит иное):\n"
            "- Экспертный тон агронома-консультанта\n"
            "- Конкретика и структурированность\n"
            "- Без общих фраз типа 'если у вас есть вопросы...'\n"
            "- Сохрани важную информацию из оригинала\n"
            "- Примени изменения из инструкций модератора ТОЧНО как указано"
        )

        user_message = (
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ (для контекста, НЕ копируй его):\n{question}\n\n"
            f"ТЕКУЩИЙ ОТВЕТ БОТА (отредактируй этот текст):\n{original_answer}\n\n"
            f"ИНСТРУКЦИИ МОДЕРАТОРА (выполни их ТОЧНО):\n{instructions}\n\n"
            f"———\n"
            f"Верни ТОЛЬКО результат редактирования согласно инструкциям модератора. "
            f"Без вопроса, без инструкций, без комментариев — только отредактированный ответ."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        improved = await create_chat_completion(messages=messages, temperature=0.3)
        return web.json_response({"improved_answer": improved.strip()})
    except Exception as e:
        logger.error(f"edit_answer_ai error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def approve_item(request: web.Request) -> web.Response:
    """POST /api/admin/moderation/queue/{id}/approve"""
    try:
        item_id = int(request.match_info["id"])

        item = await moderation_get_by_id(item_id)
        if not item:
            return web.json_response({"error": "Not found"}, status=404)

        if item["status"] != "pending":
            return web.json_response(
                {"error": f"Item already {item['status']}"}, status=400
            )

        raw_cat = item["category_guess"]
        category = "unknown"
        subcategory = "общая информация"

        if raw_cat:
            text = raw_cat.strip()
            if " / " in text:
                raw_topic, raw_plant = text.split(" / ", 1)
                category = raw_topic.strip()
                subcategory = _normalize_culture_category(raw_plant)
            else:
                category = "unknown"
                subcategory = _normalize_culture_category(text)

        question = item["question"] or ""
        answer = item["answer"] or ""

        embedding = await get_gemini_embedding(question)

        kb_id = await kb_insert(
            category=category,
            subcategory=subcategory,
            question=question,
            answer=answer,
            embedding=embedding,
            source_type="admin_qa",
        )

        await moderation_update_status(
            item_id,
            status="approved",
            admin_id=None,
            kb_id=kb_id,
        )

        return web.json_response({
            "success": True,
            "kb_id": kb_id,
            "category": category,
            "subcategory": subcategory,
        })
    except Exception as e:
        logger.error(f"approve_item error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def reject_item(request: web.Request) -> web.Response:
    """POST /api/admin/moderation/queue/{id}/reject"""
    try:
        item_id = int(request.match_info["id"])

        item = await moderation_get_by_id(item_id)
        if not item:
            return web.json_response({"error": "Not found"}, status=404)

        await moderation_update_status(
            item_id,
            status="rejected",
            admin_id=None,
        )

        return web.json_response({"success": True})
    except Exception as e:
        logger.error(f"reject_item error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_moderation_stats(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/stats"""
    try:
        stats = await moderation_get_stats()
        return web.json_response(stats)
    except Exception as e:
        logger.error(f"get_moderation_stats error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


# ---------- KB Browser endpoints ----------

async def get_kb_entries(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/kb"""
    try:
        search = request.query.get("search")
        category = request.query.get("category")
        subcategory = request.query.get("subcategory")
        is_active_str = request.query.get("is_active")
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        is_active = None
        if is_active_str is not None:
            is_active = is_active_str.lower() in ("true", "1", "yes")

        rows, total = await kb_get_list(
            search=search,
            category=category,
            subcategory=subcategory,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )

        items = [_serialize_dict(r) for r in rows]
        return web.json_response({"items": items, "total": total})
    except Exception as e:
        logger.error(f"get_kb_entries error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_kb_entry(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/kb/{id}"""
    try:
        kb_id = int(request.match_info["id"])
        row = await kb_get_by_id(kb_id)
        if not row:
            return web.json_response({"error": "Not found"}, status=404)
        return web.json_response(_serialize_dict(row))
    except Exception as e:
        logger.error(f"get_kb_entry error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def update_kb_entry(request: web.Request) -> web.Response:
    """PATCH /api/admin/moderation/kb/{id}"""
    try:
        kb_id = int(request.match_info["id"])
        data = await request.json()

        row = await kb_update(
            kb_id,
            question=data.get("question"),
            answer=data.get("answer"),
            category=data.get("category"),
            subcategory=data.get("subcategory"),
            is_active=data.get("is_active"),
        )

        if not row:
            return web.json_response({"error": "Not found"}, status=404)

        return web.json_response({"success": True, "entry": _serialize_dict(row)})
    except Exception as e:
        logger.error(f"update_kb_entry error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_kb_categories(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/kb/categories"""
    try:
        categories = await kb_get_distinct_categories(only_valid=False)
        return web.json_response({"categories": categories})
    except Exception as e:
        logger.error(f"get_kb_categories error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_kb_subcategories(request: web.Request) -> web.Response:
    """GET /api/admin/moderation/kb/subcategories"""
    try:
        subcategories = await kb_get_distinct_subcategories()
        return web.json_response({"subcategories": subcategories})
    except Exception as e:
        logger.error(f"get_kb_subcategories error: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)
