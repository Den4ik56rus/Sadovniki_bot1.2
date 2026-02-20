# src/services/db/invite_link_repo.py

"""
Репозиторий для инвайт-ссылок (campaign tracking).

Функции:
    - create_invite_link — создать именованную ссылку с уникальным кодом
    - get_invite_link_by_code — найти ссылку по коду (для обработки deep link)
    - track_user_invite_link — записать привязку пользователя к ссылке
    - get_invite_links_with_stats — все ссылки со статистикой (users + revenue)
    - get_user_active_discount — получить активную скидку пользователя
    - delete_invite_link — удалить ссылку
"""

import logging
import secrets
import string
from datetime import date as date_type
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _generate_code(length: int = 8) -> str:
    """Генерирует случайный alphanumeric код."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_invite_link(
    name: str,
    bonus_tokens: int = 0,
    discount_percent: int = 0,
    discount_duration_days: int = 0,
) -> Dict[str, Any]:
    """Создать новую инвайт-ссылку. Код генерируется автоматически."""
    pool = get_pool()
    async with pool.acquire() as conn:
        for _ in range(5):
            code = _generate_code()
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO invite_links (name, code, bonus_tokens, discount_percent, discount_duration_days)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id, name, code, bonus_tokens, discount_percent, discount_duration_days, created_at
                    """,
                    name, code, bonus_tokens, discount_percent, discount_duration_days,
                )
                return dict(row)
            except Exception:
                continue
        raise RuntimeError("Не удалось сгенерировать уникальный код для инвайт-ссылки")


async def get_invite_link_by_code(code: str) -> Optional[Dict[str, Any]]:
    """Найти инвайт-ссылку по коду. Возвращает None если не найдена."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, code, bonus_tokens, discount_percent, discount_duration_days, created_at
            FROM invite_links WHERE code = $1
            """,
            code.upper(),
        )
    if not row:
        return None
    return dict(row)


async def track_user_invite_link(invite_link_id: int, user_id: int) -> bool:
    """
    Записать привязку пользователя к инвайт-ссылке.
    Вычисляет discount_expires_at на основе настроек ссылки.
    ON CONFLICT DO NOTHING — если пользователь уже привязан, ничего не делаем.
    Возвращает True если записано, False если уже существовало.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            result = await conn.execute(
                """
                INSERT INTO invite_link_users (invite_link_id, user_id, discount_expires_at)
                SELECT $1, $2,
                    CASE WHEN il.discount_duration_days > 0 AND il.discount_percent > 0
                         THEN NOW() + (il.discount_duration_days || ' days')::INTERVAL
                         ELSE NULL
                    END
                FROM invite_links il
                WHERE il.id = $1
                ON CONFLICT (user_id) DO NOTHING
                """,
                invite_link_id, user_id,
            )
            return result == "INSERT 0 1"
        except Exception as e:
            logger.error(f"Ошибка привязки пользователя к инвайт-ссылке: {e}")
            return False


async def get_user_active_discount(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает активную скидку пользователя: {discount_percent, discount_expires_at}.
    discount_expires_at = None означает бессрочную скидку.
    Возвращает None если скидки нет.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT il.discount_percent, ilu.discount_expires_at
            FROM invite_link_users ilu
            JOIN invite_links il ON il.id = ilu.invite_link_id
            WHERE ilu.user_id = $1
              AND (ilu.discount_expires_at IS NULL OR ilu.discount_expires_at > NOW())
              AND il.discount_percent > 0
            LIMIT 1
            """,
            user_id,
        )
    if row:
        return {"discount_percent": row["discount_percent"], "discount_expires_at": row["discount_expires_at"]}
    return None


def _parse_date(s: str) -> date_type:
    """Парсинг строки YYYY-MM-DD в datetime.date для asyncpg."""
    parts = s.split('-')
    return date_type(int(parts[0]), int(parts[1]), int(parts[2]))


async def get_invite_links_with_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Получить все инвайт-ссылки со статистикой:
    - users_count: количество пользователей по ссылке
    - total_revenue_rub: сумма оплаченных платежей от этих пользователей
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        params: list = []
        date_filter_ilu = ""
        date_filter_pay = ""

        if start_date and end_date:
            sd = _parse_date(start_date)
            ed = _parse_date(end_date)
            params.extend([sd, ed])
            date_filter_ilu = "AND ilu.created_at >= $1::timestamp AND ilu.created_at < ($2::timestamp + INTERVAL '1 day')"
            params.extend([sd, ed])
            date_filter_pay = "AND p.paid_at >= $3::timestamp AND p.paid_at < ($4::timestamp + INTERVAL '1 day')"

        query = f"""
            SELECT
                il.id, il.name, il.code,
                il.bonus_tokens, il.discount_percent, il.discount_duration_days,
                il.created_at,
                COUNT(DISTINCT ilu.user_id) AS users_count,
                COALESCE(SUM(p.amount_rub) FILTER (WHERE p.paid = true), 0) AS total_revenue_rub
            FROM invite_links il
            LEFT JOIN invite_link_users ilu
                ON ilu.invite_link_id = il.id {date_filter_ilu}
            LEFT JOIN payments p
                ON p.user_id = ilu.user_id AND p.paid = true {date_filter_pay}
            GROUP BY il.id
            ORDER BY il.created_at DESC
        """

        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def get_invite_links_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Агрегированная статистика по всем инвайт-ссылкам."""
    pool = get_pool()
    async with pool.acquire() as conn:
        params: list = []
        date_filter_ilu = ""
        date_filter_pay = ""

        if start_date and end_date:
            sd = _parse_date(start_date)
            ed = _parse_date(end_date)
            params.extend([sd, ed])
            date_filter_ilu = "AND ilu.created_at >= $1::timestamp AND ilu.created_at < ($2::timestamp + INTERVAL '1 day')"
            params.extend([sd, ed])
            date_filter_pay = "AND p.paid_at >= $3::timestamp AND p.paid_at < ($4::timestamp + INTERVAL '1 day')"

        query = f"""
            SELECT
                (SELECT COUNT(*) FROM invite_links) AS total_links,
                COUNT(DISTINCT ilu.user_id) AS total_users,
                COALESCE(SUM(p.amount_rub) FILTER (WHERE p.paid = true), 0) AS total_revenue_rub
            FROM invite_link_users ilu
            LEFT JOIN payments p
                ON p.user_id = ilu.user_id AND p.paid = true {date_filter_pay}
            WHERE 1=1 {date_filter_ilu}
        """

        row = await conn.fetchrow(query, *params)

    return {
        "total_links": row["total_links"] if row else 0,
        "total_users": row["total_users"] if row else 0,
        "total_revenue_rub": float(row["total_revenue_rub"]) if row else 0.0,
    }


async def update_invite_link(
    link_id: int,
    name: str,
    bonus_tokens: int = 0,
    discount_percent: int = 0,
    discount_duration_days: int = 0,
) -> Optional[Dict[str, Any]]:
    """Обновить инвайт-ссылку. Возвращает обновлённую строку или None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE invite_links
            SET name = $1, bonus_tokens = $2, discount_percent = $3, discount_duration_days = $4
            WHERE id = $5
            RETURNING id, name, code, bonus_tokens, discount_percent, discount_duration_days, created_at
            """,
            name, bonus_tokens, discount_percent, discount_duration_days, link_id,
        )
    if not row:
        return None
    return dict(row)


async def delete_invite_link(link_id: int) -> bool:
    """Удалить инвайт-ссылку. CASCADE удалит привязки пользователей."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM invite_links WHERE id = $1",
            link_id,
        )
    return result == "DELETE 1"
