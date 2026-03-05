# src/api/handlers/articles.py

"""
API handlers для админских статей.

Endpoints:
    POST   /api/admin/articles/generate  — сгенерировать статью (webapp)
    GET    /api/admin/articles           — список статей
    GET    /api/admin/articles/{id}      — получить статью
    GET    /api/admin/articles/by-admin/{telegram_id} — статьи конкретного админа
"""

import logging
from decimal import Decimal
from aiohttp import web

from src.services.db import article_repo
from src.services.llm.article_llm import generate_article

logger = logging.getLogger(__name__)


def _serialize_article(article: dict) -> dict:
    """Конвертирует non-serializable типы (Decimal, datetime) в JSON-совместимые."""
    result = {}
    for k, v in article.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif hasattr(v, 'isoformat'):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def generate_article_api(request: web.Request) -> web.Response:
    """
    Сгенерировать статью через webapp.

    Body (JSON):
        topic: str                 — обязательно
        category: str | null       — категория (фильтр RAG, None = вся база)
        culture: str | null        — культура (subcategory, None = без фильтра)
        model_override: str | null — переопределить модель
        use_scripts: bool = True   — использовать article_prompt
        use_rag: bool = True       — использовать RAG-поиск

    Response:
        { article_id: int, article: AdminArticle }
    """
    try:
        data = await request.json()

        topic = (data.get("topic") or "").strip()
        if not topic:
            return web.json_response({"error": "topic is required"}, status=400)

        category = data.get("category") or None
        culture = data.get("culture") or None
        model_override = data.get("model_override") or None
        use_scripts = bool(data.get("use_scripts", True))
        use_problem_solving = bool(data.get("use_problem_solving", False))
        use_rag = bool(data.get("use_rag", True))

        # Webapp-генерация — admin_telegram_id = 0 (не привязана к конкретному Telegram аккаунту)
        WEBAPP_ADMIN_ID = 0

        _article_text, article_id = await generate_article(
            topic=topic,
            telegram_user_id=WEBAPP_ADMIN_ID,
            category=category,
            culture=culture,
            use_scripts=use_scripts,
            use_problem_solving=use_problem_solving,
            skip_rag=not use_rag,
            model_override=model_override,
        )

        article = await article_repo.get_article_by_id(article_id)
        if not article:
            return web.json_response({"error": "Article not found after generation"}, status=500)

        return web.json_response({
            "article_id": article_id,
            "article": _serialize_article(article),
        })
    except Exception as e:
        logger.error(f"Error generating article via webapp: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_articles(request: web.Request) -> web.Response:
    """
    Получить список статей с пагинацией.

    Query params:
        limit: int = 50
        offset: int = 0
        admin_telegram_id: int (optional)
    """
    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        admin_telegram_id = request.query.get("admin_telegram_id")

        if admin_telegram_id:
            admin_telegram_id = int(admin_telegram_id)

        articles = await article_repo.get_articles_list(
            admin_telegram_id=admin_telegram_id,
            limit=limit,
            offset=offset
        )

        total = await article_repo.get_articles_count(admin_telegram_id)

        return web.json_response({
            "articles": [_serialize_article(a) for a in articles],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_article(request: web.Request) -> web.Response:
    """Получить статью по ID с полным текстом и деталями."""
    article_id = int(request.match_info.get("id"))

    try:
        article = await article_repo.get_article_by_id(article_id)

        if not article:
            return web.json_response({"error": "Article not found"}, status=404)

        return web.json_response(_serialize_article(article))
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_article_api(request: web.Request) -> web.Response:
    """Обновить текст статьи."""
    try:
        article_id = int(request.match_info["id"])
        data = await request.json()

        new_text = data.get("article_text")
        if not new_text:
            return web.json_response({"error": "article_text is required"}, status=400)

        success = await article_repo.update_article_text(article_id, new_text)
        if not success:
            return web.json_response({"error": "Article not found"}, status=404)

        article = await article_repo.get_article_by_id(article_id)
        return web.json_response(_serialize_article(article) if article else {"success": True})

    except Exception as e:
        logger.error(f"Error updating article {request.match_info.get('id')}: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_articles_by_culture(request: web.Request) -> web.Response:
    """Получить статьи по культуре."""
    try:
        culture_key = request.query.get("culture_key")
        variety_key = request.query.get("variety_key") or None

        if not culture_key:
            return web.json_response({"error": "culture_key is required"}, status=400)

        articles = await article_repo.get_articles_by_culture(culture_key, variety_key)
        return web.json_response({
            "articles": [_serialize_article(a) for a in articles],
            "total": len(articles),
        })

    except Exception as e:
        logger.error(f"Error getting articles by culture: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_articles_by_admin(request: web.Request) -> web.Response:
    """Получить статьи конкретного админа."""
    admin_telegram_id = int(request.match_info.get("telegram_id"))

    try:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))

        articles = await article_repo.get_articles_list(
            admin_telegram_id=admin_telegram_id,
            limit=limit,
            offset=offset
        )

        total = await article_repo.get_articles_count(admin_telegram_id)

        return web.json_response({
            "articles": [_serialize_article(a) for a in articles],
            "total": total,
            "admin_telegram_id": admin_telegram_id
        })
    except Exception as e:
        logger.error(f"Error getting articles for admin {admin_telegram_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)
