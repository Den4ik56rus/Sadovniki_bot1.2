# src/services/db/article_repo.py

"""
Репозиторий для работы с таблицей admin_articles.

Хранит статьи, сгенерированные администратором в режиме написания статей.
"""

import json
import logging
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def save_article(
    *,
    admin_telegram_id: int,
    topic: str,
    article_text: str,
    rag_snippets: Optional[List[Dict[str, Any]]] = None,
    rag_snippets_count: int = 0,
    system_prompt: Optional[str] = None,
    embedding_tokens: int = 0,
    llm_prompt_tokens: int = 0,
    llm_completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    llm_model: Optional[str] = None,
    culture_key: Optional[str] = None,
    variety_key: Optional[str] = None,
    category_key: Optional[str] = None,
    batch_id: Optional[int] = None,
) -> int:
    """
    Сохраняет сгенерированную статью в БД.

    Возвращает:
        ID созданной записи
    """
    pool = get_pool()

    query = """
        INSERT INTO admin_articles (
            admin_telegram_id,
            topic,
            article_text,
            rag_snippets,
            rag_snippets_count,
            system_prompt,
            embedding_tokens,
            llm_prompt_tokens,
            llm_completion_tokens,
            total_tokens,
            cost_usd,
            llm_model,
            culture_key,
            variety_key,
            category_key,
            batch_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        RETURNING id
    """

    rag_snippets_json = json.dumps(rag_snippets) if rag_snippets else None

    row = await pool.fetchrow(
        query,
        admin_telegram_id,
        topic,
        article_text,
        rag_snippets_json,
        rag_snippets_count,
        system_prompt,
        embedding_tokens,
        llm_prompt_tokens,
        llm_completion_tokens,
        total_tokens,
        cost_usd,
        llm_model,
        culture_key,
        variety_key,
        category_key,
        batch_id,
    )

    article_id = row["id"]
    logger.info(f"[article_repo] Статья сохранена: id={article_id}, topic='{topic[:50]}...'")

    return article_id


async def get_article_by_id(article_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает статью по ID.
    """
    pool = get_pool()

    query = """
        SELECT
            id,
            admin_telegram_id,
            topic,
            article_text,
            rag_snippets,
            rag_snippets_count,
            system_prompt,
            embedding_tokens,
            llm_prompt_tokens,
            llm_completion_tokens,
            total_tokens,
            cost_usd,
            llm_model,
            created_at
        FROM admin_articles
        WHERE id = $1
    """

    row = await pool.fetchrow(query, article_id)

    if not row:
        return None

    return dict(row)


async def get_articles_list(
    *,
    admin_telegram_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Получает список статей с пагинацией.

    Параметры:
        admin_telegram_id: Фильтр по админу (опционально)
        limit: Максимальное количество записей
        offset: Смещение для пагинации

    Возвращает:
        Список статей (без полного текста для экономии трафика)
    """
    pool = get_pool()

    if admin_telegram_id:
        query = """
            SELECT
                id,
                admin_telegram_id,
                topic,
                LENGTH(article_text) as article_length,
                rag_snippets_count,
                total_tokens,
                cost_usd,
                llm_model,
                created_at
            FROM admin_articles
            WHERE admin_telegram_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        rows = await pool.fetch(query, admin_telegram_id, limit, offset)
    else:
        query = """
            SELECT
                id,
                admin_telegram_id,
                topic,
                LENGTH(article_text) as article_length,
                rag_snippets_count,
                total_tokens,
                cost_usd,
                llm_model,
                created_at
            FROM admin_articles
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        rows = await pool.fetch(query, limit, offset)

    return [dict(row) for row in rows]


async def get_articles_count(admin_telegram_id: Optional[int] = None) -> int:
    """
    Получает общее количество статей.
    """
    pool = get_pool()

    if admin_telegram_id:
        query = "SELECT COUNT(*) FROM admin_articles WHERE admin_telegram_id = $1"
        row = await pool.fetchrow(query, admin_telegram_id)
    else:
        query = "SELECT COUNT(*) FROM admin_articles"
        row = await pool.fetchrow(query)

    return row["count"]


async def update_article_text(article_id: int, new_text: str) -> bool:
    """Обновляет текст статьи."""
    pool = get_pool()
    result = await pool.execute(
        "UPDATE admin_articles SET article_text = $2 WHERE id = $1",
        article_id, new_text,
    )
    success = result == "UPDATE 1"
    if success:
        logger.info(f"[article_repo] Текст статьи {article_id} обновлён ({len(new_text)} симв.)")
    return success


async def get_articles_by_culture(
    culture_key: str,
    variety_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Получает все статьи для конкретной культуры."""
    pool = get_pool()

    if variety_key:
        rows = await pool.fetch(
            """
            SELECT id, topic, culture_key, variety_key, category_key,
                   LENGTH(article_text) as article_length,
                   rag_snippets_count, cost_usd, llm_model, created_at
            FROM admin_articles
            WHERE culture_key = $1 AND variety_key = $2
            ORDER BY category_key, created_at DESC
            """,
            culture_key, variety_key,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT id, topic, culture_key, variety_key, category_key,
                   LENGTH(article_text) as article_length,
                   rag_snippets_count, cost_usd, llm_model, created_at
            FROM admin_articles
            WHERE culture_key = $1 AND variety_key IS NULL
            ORDER BY category_key, created_at DESC
            """,
            culture_key,
        )

    return [dict(row) for row in rows]
