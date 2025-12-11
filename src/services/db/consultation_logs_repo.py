# src/services/db/consultation_logs_repo.py

"""
Репозиторий для работы с таблицей consultation_logs.

Функции:
    - log_consultation: Записать лог консультации
    - get_users_with_stats: Список пользователей со статистикой консультаций
    - get_topics_by_user: Топики пользователя
    - get_logs_by_topic: Логи консультации по топику
    - get_recent_logs: Последние логи (для live feed)
    - get_stats_summary: Общая статистика
"""

import json
import logging
from typing import Optional, List, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def log_consultation(
    user_id: int,
    user_message: str,
    bot_response: str,
    system_prompt: str,
    rag_snippets: List[Dict],
    llm_params: Dict[str, Any],
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: int,
    topic_id: Optional[int] = None,
    message_id: Optional[int] = None,
    consultation_category: Optional[str] = None,
    culture: Optional[str] = None,
    embedding_tokens: int = 0,
    embedding_cost_usd: float = 0.0,
    embedding_model: Optional[str] = None,
    composed_question: Optional[str] = None,
    compose_cost_usd: float = 0.0,
    compose_tokens: int = 0,
    classification_cost_usd: float = 0.0,
    classification_tokens: int = 0,
) -> int:
    """
    Записывает лог консультации в БД.

    Возвращает id созданной записи.
    """
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO consultation_logs (
                    user_id, topic_id, message_id,
                    user_message, bot_response, system_prompt,
                    rag_snippets, llm_params,
                    prompt_tokens, completion_tokens, cost_usd, latency_ms,
                    consultation_category, culture,
                    embedding_tokens, embedding_cost_usd, embedding_model,
                    composed_question, compose_cost_usd, compose_tokens,
                    classification_cost_usd, classification_tokens
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                RETURNING id, created_at
                """,
                user_id,
                topic_id,
                message_id,
                user_message,
                bot_response,
                system_prompt,
                json.dumps(rag_snippets, ensure_ascii=False),
                json.dumps(llm_params, ensure_ascii=False),
                prompt_tokens,
                completion_tokens,
                cost_usd,
                latency_ms,
                consultation_category,
                culture,
                embedding_tokens,
                embedding_cost_usd,
                embedding_model,
                composed_question,
                compose_cost_usd,
                compose_tokens,
                classification_cost_usd,
                classification_tokens,
            )
            log_id = row["id"]
            created_at = row["created_at"]

            # Получаем информацию о пользователе для SSE события
            user_row = await conn.fetchrow(
                """
                SELECT telegram_user_id, username, first_name
                FROM users
                WHERE id = $1
                """,
                user_id,
            )

            # Broadcast SSE event для live-feed и конкретного топика
            try:
                from src.api.sse_manager import sse_manager
                import json as json_lib

                # Формируем данные лога для SSE
                total_tokens = prompt_tokens + completion_tokens

                # Calculate llm_cost_usd (same logic as in get_logs_by_topic line 445)
                llm_cost_usd = max(0, float(cost_usd) - float(embedding_cost_usd) - float(compose_cost_usd) - float(classification_cost_usd))

                # Парсим JSON поля если они строки
                parsed_rag_snippets = rag_snippets
                if isinstance(rag_snippets, str):
                    try:
                        parsed_rag_snippets = json_lib.loads(rag_snippets)
                    except:
                        parsed_rag_snippets = []

                parsed_llm_params = llm_params
                if isinstance(llm_params, str):
                    try:
                        parsed_llm_params = json_lib.loads(llm_params)
                    except:
                        parsed_llm_params = {}

                log_data = {
                    "id": log_id,
                    "user_id": user_id,
                    "topic_id": topic_id,
                    "user_message": user_message,
                    "bot_response": bot_response,
                    "system_prompt": system_prompt or "",
                    "rag_snippets": parsed_rag_snippets or [],
                    "llm_params": parsed_llm_params or {},
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": float(cost_usd),
                    "llm_cost_usd": float(llm_cost_usd) if llm_cost_usd else 0.0,
                    "latency_ms": latency_ms,
                    "consultation_category": consultation_category,
                    "culture": culture,
                    "composed_question": composed_question or "",
                    "compose_tokens": compose_tokens or 0,
                    "compose_cost_usd": float(compose_cost_usd) if compose_cost_usd else 0.0,
                    "embedding_tokens": embedding_tokens or 0,
                    "embedding_cost_usd": float(embedding_cost_usd) if embedding_cost_usd else 0.0,
                    "classification_tokens": classification_tokens or 0,
                    "classification_cost_usd": float(classification_cost_usd) if classification_cost_usd else 0.0,
                    "created_at": created_at.isoformat() if created_at else None,
                    "user": {
                        "username": user_row["username"] if user_row else None,
                        "first_name": user_row["first_name"] if user_row else None,
                        "telegram_user_id": user_row["telegram_user_id"] if user_row else None,
                    },
                }

                # Broadcast для live-feed (все клиенты)
                await sse_manager.broadcast(
                    event_type='new_log',
                    data=log_data,
                    endpoint_type='live-feed'
                )

                # Broadcast для конкретного топика (если есть)
                if topic_id:
                    await sse_manager.broadcast(
                        event_type='new_log',
                        data=log_data,
                        endpoint_type='logs',
                        entity_id=topic_id
                    )

                logger.debug(f"SSE broadcast sent for log {log_id}, llm_cost_usd={log_data.get('llm_cost_usd', 'MISSING')}, composed_question={bool(log_data.get('composed_question'))}")

            except Exception as e:
                # Не падаем если SSE broadcast не сработал
                logger.warning(f"Failed to broadcast SSE event for log {log_id}: {e}")

            return log_id
    except Exception as e:
        logger.error(f"[consultation_logs_repo] Ошибка записи лога: {e}")
        return -1


async def get_users_with_stats(
    limit: int = 50,
    offset: int = 0,
    search: str = "",
) -> Dict[str, Any]:
    """
    Возвращает список пользователей со статистикой консультаций.

    Результат:
        {
            "users": [...],
            "total": int,
            "limit": int,
            "offset": int
        }
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Подсчёт общего количества
        if search:
            count_row = await conn.fetchrow(
                """
                SELECT COUNT(DISTINCT u.id) AS cnt
                FROM users u
                LEFT JOIN consultation_logs cl ON cl.user_id = u.id
                WHERE u.username ILIKE $1 OR u.first_name ILIKE $1
                """,
                f"%{search}%",
            )
        else:
            count_row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS cnt FROM users
                """
            )

        total = count_row["cnt"] if count_row else 0

        # Получение пользователей со статистикой
        if search:
            rows = await conn.fetch(
                """
                SELECT
                    u.id,
                    u.telegram_user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.token_balance,
                    COALESCE(COUNT(cl.id), 0) AS total_consultations,
                    COALESCE(SUM(cl.total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(cl.cost_usd), 0) AS total_cost_usd,
                    MAX(cl.created_at) AS last_consultation_at
                FROM users u
                LEFT JOIN consultation_logs cl ON cl.user_id = u.id
                WHERE u.username ILIKE $1 OR u.first_name ILIKE $1
                GROUP BY u.id
                ORDER BY last_consultation_at DESC NULLS LAST
                LIMIT $2 OFFSET $3
                """,
                f"%{search}%",
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    u.id,
                    u.telegram_user_id,
                    u.username,
                    u.first_name,
                    u.last_name,
                    u.token_balance,
                    COALESCE(COUNT(cl.id), 0) AS total_consultations,
                    COALESCE(SUM(cl.total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(cl.cost_usd), 0) AS total_cost_usd,
                    MAX(cl.created_at) AS last_consultation_at
                FROM users u
                LEFT JOIN consultation_logs cl ON cl.user_id = u.id
                GROUP BY u.id
                ORDER BY last_consultation_at DESC NULLS LAST
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

        users = []
        for row in rows:
            users.append({
                "id": row["id"],
                "telegram_user_id": row["telegram_user_id"],
                "username": row["username"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "token_balance": row["token_balance"],
                "total_consultations": row["total_consultations"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": float(row["total_cost_usd"]) if row["total_cost_usd"] else 0,
                "last_consultation_at": row["last_consultation_at"].isoformat() if row["last_consultation_at"] else None,
            })

        return {
            "users": users,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


async def get_topics_by_user(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    Возвращает топики пользователя с базовой статистикой.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                t.id,
                t.session_id,
                t.status,
                t.culture,
                t.created_at,
                t.updated_at,
                COALESCE(COUNT(cl.id), 0) AS message_count,
                COALESCE(SUM(cl.total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cl.cost_usd), 0) AS total_cost_usd,
                MAX(cl.consultation_category) AS category
            FROM topics t
            LEFT JOIN consultation_logs cl ON cl.topic_id = t.id
            WHERE t.user_id = $1
            GROUP BY t.id
            ORDER BY t.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )

        topics = []
        for row in rows:
            topics.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "status": row["status"],
                "culture": row["culture"],
                "category": row["category"],
                "message_count": row["message_count"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": float(row["total_cost_usd"]) if row["total_cost_usd"] else 0,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            })

        return topics


async def get_logs_by_topic(topic_id: int) -> Dict[str, Any]:
    """
    Возвращает полный лог консультации по топику.

    Результат:
        {
            "topic": {...},
            "logs": [...]
        }
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # Получаем информацию о топике
        topic_row = await conn.fetchrow(
            """
            SELECT
                t.id,
                t.session_id,
                t.status,
                t.culture,
                t.created_at,
                t.updated_at,
                u.username,
                u.first_name,
                u.telegram_user_id
            FROM topics t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = $1
            """,
            topic_id,
        )

        if not topic_row:
            return {"topic": None, "logs": []}

        topic = {
            "id": topic_row["id"],
            "session_id": topic_row["session_id"],
            "status": topic_row["status"],
            "culture": topic_row["culture"],
            "created_at": topic_row["created_at"].isoformat() if topic_row["created_at"] else None,
            "updated_at": topic_row["updated_at"].isoformat() if topic_row["updated_at"] else None,
            "user": {
                "username": topic_row["username"],
                "first_name": topic_row["first_name"],
                "telegram_user_id": topic_row["telegram_user_id"],
            },
        }

        # Получаем логи консультации
        log_rows = await conn.fetch(
            """
            SELECT
                id, user_message, bot_response, system_prompt,
                rag_snippets, llm_params,
                prompt_tokens, completion_tokens, total_tokens,
                cost_usd, latency_ms,
                consultation_category, culture, created_at,
                composed_question,
                embedding_tokens, embedding_cost_usd, embedding_model,
                COALESCE(compose_cost_usd, 0) AS compose_cost_usd,
                COALESCE(compose_tokens, 0) AS compose_tokens,
                COALESCE(classification_cost_usd, 0) AS classification_cost_usd,
                COALESCE(classification_tokens, 0) AS classification_tokens
            FROM consultation_logs
            WHERE topic_id = $1
            ORDER BY created_at ASC
            """,
            topic_id,
        )

        logs = []
        for row in log_rows:
            # Парсим JSONB поля (asyncpg может вернуть строку)
            rag_snippets = row["rag_snippets"]
            if isinstance(rag_snippets, str):
                rag_snippets = json.loads(rag_snippets) if rag_snippets else []
            elif rag_snippets is None:
                rag_snippets = []

            llm_params = row["llm_params"]
            if isinstance(llm_params, str):
                llm_params = json.loads(llm_params) if llm_params else {}
            elif llm_params is None:
                llm_params = {}

            # Вычисляем llm_cost_usd как разницу между общей стоимостью и отдельными компонентами
            cost_usd = float(row["cost_usd"]) if row["cost_usd"] else 0
            embedding_cost_usd = float(row["embedding_cost_usd"]) if row["embedding_cost_usd"] else 0
            compose_cost_usd = float(row["compose_cost_usd"]) if row["compose_cost_usd"] else 0
            classification_cost_usd = float(row["classification_cost_usd"]) if row["classification_cost_usd"] else 0
            llm_cost_usd = max(0, cost_usd - embedding_cost_usd - compose_cost_usd - classification_cost_usd)

            logs.append({
                "id": row["id"],
                "user_message": row["user_message"],
                "bot_response": row["bot_response"],
                "system_prompt": row["system_prompt"],
                "rag_snippets": rag_snippets,
                "llm_params": llm_params,
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "cost_usd": cost_usd,
                "latency_ms": row["latency_ms"],
                "consultation_category": row["consultation_category"],
                "culture": row["culture"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "composed_question": row["composed_question"],
                # Детализация стоимости и токенов по шагам
                "embedding_tokens": row["embedding_tokens"] or 0,
                "embedding_cost_usd": embedding_cost_usd,
                "embedding_model": row["embedding_model"],
                "compose_cost_usd": compose_cost_usd,
                "compose_tokens": row["compose_tokens"] or 0,
                "classification_cost_usd": classification_cost_usd,
                "classification_tokens": row["classification_tokens"] or 0,
                "llm_cost_usd": llm_cost_usd,
            })

        # Получаем все сообщения топика (переписку)
        message_rows = await conn.fetch(
            """
            SELECT id, direction, text, created_at
            FROM messages
            WHERE topic_id = $1
            ORDER BY created_at ASC
            """,
            topic_id,
        )

        messages = []
        for row in message_rows:
            messages.append({
                "id": row["id"],
                "direction": row["direction"],
                "text": row["text"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        return {"topic": topic, "logs": logs, "messages": messages}


async def get_logs_since_id(
    since_id: int,
    limit: int = 50,
    topic_id: Optional[int] = None
) -> List[Dict]:
    """
    Возвращает логи консультаций созданные после since_id.

    Используется для SSE reconnect — получение пропущенных событий.

    Параметры:
        since_id: вернуть только записи с id > since_id
        limit: максимальное количество записей
        topic_id: опционально фильтровать по топику
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if topic_id:
            rows = await conn.fetch(
                """
                SELECT
                    cl.id, cl.user_id, cl.topic_id,
                    cl.user_message, cl.bot_response,
                    cl.prompt_tokens, cl.completion_tokens, cl.total_tokens,
                    cl.cost_usd, cl.latency_ms,
                    cl.consultation_category, cl.culture, cl.created_at,
                    u.username, u.first_name, u.telegram_user_id
                FROM consultation_logs cl
                JOIN users u ON u.id = cl.user_id
                WHERE cl.id > $1 AND cl.topic_id = $2
                ORDER BY cl.id ASC
                LIMIT $3
                """,
                since_id,
                topic_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    cl.id, cl.user_id, cl.topic_id,
                    cl.user_message, cl.bot_response,
                    cl.prompt_tokens, cl.completion_tokens, cl.total_tokens,
                    cl.cost_usd, cl.latency_ms,
                    cl.consultation_category, cl.culture, cl.created_at,
                    u.username, u.first_name, u.telegram_user_id
                FROM consultation_logs cl
                JOIN users u ON u.id = cl.user_id
                WHERE cl.id > $1
                ORDER BY cl.id ASC
                LIMIT $2
                """,
                since_id,
                limit,
            )

        logs = []
        for row in rows:
            logs.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "topic_id": row["topic_id"],
                "user_message": row["user_message"],
                "bot_response": row["bot_response"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "cost_usd": float(row["cost_usd"]) if row["cost_usd"] else 0,
                "latency_ms": row["latency_ms"],
                "consultation_category": row["consultation_category"],
                "culture": row["culture"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "user": {
                    "username": row["username"],
                    "first_name": row["first_name"],
                    "telegram_user_id": row["telegram_user_id"],
                },
            })

        return logs


async def get_recent_logs(
    limit: int = 50,
    since_id: Optional[int] = None,
) -> List[Dict]:
    """
    Возвращает последние логи консультаций (для live feed).

    Параметры:
        limit: максимальное количество записей
        since_id: вернуть только записи с id > since_id (для polling)
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        if since_id:
            rows = await conn.fetch(
                """
                SELECT
                    cl.id, cl.user_id, cl.topic_id,
                    cl.user_message, cl.bot_response,
                    cl.prompt_tokens, cl.completion_tokens, cl.total_tokens,
                    cl.cost_usd, cl.latency_ms,
                    cl.consultation_category, cl.culture, cl.created_at,
                    u.username, u.first_name, u.telegram_user_id
                FROM consultation_logs cl
                JOIN users u ON u.id = cl.user_id
                WHERE cl.id > $1
                ORDER BY cl.id ASC
                LIMIT $2
                """,
                since_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    cl.id, cl.user_id, cl.topic_id,
                    cl.user_message, cl.bot_response,
                    cl.prompt_tokens, cl.completion_tokens, cl.total_tokens,
                    cl.cost_usd, cl.latency_ms,
                    cl.consultation_category, cl.culture, cl.created_at,
                    u.username, u.first_name, u.telegram_user_id
                FROM consultation_logs cl
                JOIN users u ON u.id = cl.user_id
                ORDER BY cl.created_at DESC
                LIMIT $1
                """,
                limit,
            )

        logs = []
        for row in rows:
            logs.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "topic_id": row["topic_id"],
                "user_message": row["user_message"],
                "bot_response": row["bot_response"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "cost_usd": float(row["cost_usd"]) if row["cost_usd"] else 0,
                "latency_ms": row["latency_ms"],
                "consultation_category": row["consultation_category"],
                "culture": row["culture"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "user": {
                    "username": row["username"],
                    "first_name": row["first_name"],
                    "telegram_user_id": row["telegram_user_id"],
                },
            })

        return logs


async def get_stats_summary(period: str = "all") -> Dict[str, Any]:
    """
    Возвращает общую статистику по консультациям.

    Параметры:
        period: 'day' | 'week' | 'month' | 'all'
    """
    pool = get_pool()

    # Определяем фильтр по периоду
    period_filter = ""
    if period == "day":
        period_filter = "WHERE cl.created_at >= CURRENT_DATE"
    elif period == "week":
        period_filter = "WHERE cl.created_at >= CURRENT_DATE - INTERVAL '7 days'"
    elif period == "month":
        period_filter = "WHERE cl.created_at >= CURRENT_DATE - INTERVAL '30 days'"

    async with pool.acquire() as conn:
        # Общая статистика
        overview_row = await conn.fetchrow(
            f"""
            SELECT
                COUNT(*) AS total_consultations,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(cost_usd), 0) AS total_cost_usd,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms
            FROM consultation_logs cl
            {period_filter}
            """
        )

        # Статистика за сегодня
        today_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS consultations,
                COALESCE(SUM(total_tokens), 0) AS tokens,
                COALESCE(SUM(cost_usd), 0) AS cost_usd
            FROM consultation_logs
            WHERE created_at >= CURRENT_DATE
            """
        )

        # Топ культур
        culture_rows = await conn.fetch(
            f"""
            SELECT culture, COUNT(*) AS count
            FROM consultation_logs cl
            {period_filter}
            {"AND" if period_filter else "WHERE"} culture IS NOT NULL
            GROUP BY culture
            ORDER BY count DESC
            LIMIT 10
            """
        )

        # Топ категорий
        category_rows = await conn.fetch(
            f"""
            SELECT consultation_category AS category, COUNT(*) AS count
            FROM consultation_logs cl
            {period_filter}
            {"AND" if period_filter else "WHERE"} consultation_category IS NOT NULL
            GROUP BY consultation_category
            ORDER BY count DESC
            LIMIT 10
            """
        )

        return {
            "overview": {
                "total_consultations": overview_row["total_consultations"] if overview_row else 0,
                "total_tokens": overview_row["total_tokens"] if overview_row else 0,
                "total_cost_usd": float(overview_row["total_cost_usd"]) if overview_row and overview_row["total_cost_usd"] else 0,
                "avg_latency_ms": int(overview_row["avg_latency_ms"]) if overview_row and overview_row["avg_latency_ms"] else 0,
            },
            "today": {
                "consultations": today_row["consultations"] if today_row else 0,
                "tokens": today_row["tokens"] if today_row else 0,
                "cost_usd": float(today_row["cost_usd"]) if today_row and today_row["cost_usd"] else 0,
            },
            "by_culture": [
                {"culture": row["culture"], "count": row["count"]}
                for row in culture_rows
            ],
            "by_category": [
                {"category": row["category"], "count": row["count"]}
                for row in category_rows
            ],
        }


async def get_embedding_stats(period: str = "all") -> Dict[str, Any]:
    """
    Возвращает статистику по embeddings (документы + консультации).

    Параметры:
        period: 'day' | 'week' | 'month' | 'all'
    """
    pool = get_pool()

    # Определяем фильтр по периоду
    period_filter = ""
    if period == "day":
        period_filter = "WHERE created_at >= CURRENT_DATE"
    elif period == "week":
        period_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
    elif period == "month":
        period_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'"

    async with pool.acquire() as conn:
        # Статистика embeddings консультаций
        consultations_row = await conn.fetchrow(
            f"""
            SELECT
                COALESCE(SUM(embedding_tokens), 0) AS tokens,
                COALESCE(SUM(embedding_cost_usd), 0) AS cost_usd
            FROM consultation_logs
            {period_filter}
            """
        )

        # Статистика embeddings документов
        docs_period_filter = period_filter.replace("created_at", "d.created_at") if period_filter else ""
        documents_row = await conn.fetchrow(
            f"""
            SELECT
                COALESCE(SUM(embedding_tokens), 0) AS tokens,
                COALESCE(SUM(embedding_cost_usd), 0) AS cost_usd
            FROM documents d
            WHERE processing_status = 'completed'
            {"AND d.created_at >= CURRENT_DATE" if period == "day" else ""}
            {"AND d.created_at >= CURRENT_DATE - INTERVAL '7 days'" if period == "week" else ""}
            {"AND d.created_at >= CURRENT_DATE - INTERVAL '30 days'" if period == "month" else ""}
            """
        )

        # Статистика по моделям (консультации)
        by_model_consultations = await conn.fetch(
            f"""
            SELECT
                embedding_model AS model,
                COALESCE(SUM(embedding_tokens), 0) AS tokens,
                COALESCE(SUM(embedding_cost_usd), 0) AS cost_usd
            FROM consultation_logs
            {period_filter}
            {"AND" if period_filter else "WHERE"} embedding_model IS NOT NULL
            GROUP BY embedding_model
            ORDER BY cost_usd DESC
            """
        )

        # Статистика по моделям (документы)
        by_model_documents = await conn.fetch(
            f"""
            SELECT
                embedding_model AS model,
                COALESCE(SUM(embedding_tokens), 0) AS tokens,
                COALESCE(SUM(embedding_cost_usd), 0) AS cost_usd
            FROM documents
            WHERE processing_status = 'completed' AND embedding_model IS NOT NULL
            {"AND created_at >= CURRENT_DATE" if period == "day" else ""}
            {"AND created_at >= CURRENT_DATE - INTERVAL '7 days'" if period == "week" else ""}
            {"AND created_at >= CURRENT_DATE - INTERVAL '30 days'" if period == "month" else ""}
            GROUP BY embedding_model
            ORDER BY cost_usd DESC
            """
        )

        # Объединяем статистику по моделям
        model_stats = {}
        for row in by_model_consultations:
            model = row["model"]
            model_stats[model] = {
                "model": model,
                "consultations_tokens": row["tokens"],
                "consultations_cost_usd": float(row["cost_usd"]) if row["cost_usd"] else 0,
                "documents_tokens": 0,
                "documents_cost_usd": 0,
            }
        for row in by_model_documents:
            model = row["model"]
            if model in model_stats:
                model_stats[model]["documents_tokens"] = row["tokens"]
                model_stats[model]["documents_cost_usd"] = float(row["cost_usd"]) if row["cost_usd"] else 0
            else:
                model_stats[model] = {
                    "model": model,
                    "consultations_tokens": 0,
                    "consultations_cost_usd": 0,
                    "documents_tokens": row["tokens"],
                    "documents_cost_usd": float(row["cost_usd"]) if row["cost_usd"] else 0,
                }

        # Добавляем total для каждой модели
        by_model = []
        for model, stats in model_stats.items():
            stats["total_tokens"] = stats["consultations_tokens"] + stats["documents_tokens"]
            stats["total_cost_usd"] = stats["consultations_cost_usd"] + stats["documents_cost_usd"]
            by_model.append(stats)

        # Сортируем по общей стоимости
        by_model.sort(key=lambda x: x["total_cost_usd"], reverse=True)

        consultations_tokens = consultations_row["tokens"] if consultations_row else 0
        consultations_cost = float(consultations_row["cost_usd"]) if consultations_row and consultations_row["cost_usd"] else 0
        documents_tokens = documents_row["tokens"] if documents_row else 0
        documents_cost = float(documents_row["cost_usd"]) if documents_row and documents_row["cost_usd"] else 0

        return {
            "consultations": {
                "tokens": consultations_tokens,
                "cost_usd": consultations_cost,
            },
            "documents": {
                "tokens": documents_tokens,
                "cost_usd": documents_cost,
            },
            "total": {
                "tokens": consultations_tokens + documents_tokens,
                "cost_usd": consultations_cost + documents_cost,
            },
            "by_model": by_model,
        }
