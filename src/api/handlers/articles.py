# src/api/handlers/articles.py

"""
API handlers для админских статей.

Endpoints:
    GET    /api/admin/articles           — список статей
    GET    /api/admin/articles/{id}      — получить статью
    GET    /api/admin/articles/by-admin/{telegram_id} — статьи конкретного админа
"""

import logging
from aiohttp import web

from src.services.db import article_repo

logger = logging.getLogger(__name__)


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

        # Сериализуем datetime
        for article in articles:
            if article.get("created_at"):
                article["created_at"] = article["created_at"].isoformat()

        return web.json_response({
            "articles": articles,
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

        # Сериализуем datetime
        if article.get("created_at"):
            article["created_at"] = article["created_at"].isoformat()

        return web.json_response(article)
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
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

        # Сериализуем datetime
        for article in articles:
            if article.get("created_at"):
                article["created_at"] = article["created_at"].isoformat()

        return web.json_response({
            "articles": articles,
            "total": total,
            "admin_telegram_id": admin_telegram_id
        })
    except Exception as e:
        logger.error(f"Error getting articles for admin {admin_telegram_id}: {e}")
        return web.json_response({"error": str(e)}, status=500)
