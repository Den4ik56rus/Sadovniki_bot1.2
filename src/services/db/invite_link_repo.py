# src/services/db/invite_link_repo.py

"""
Репозиторий для инвайт-ссылок (campaign tracking).

Функции:
    - create_invite_link — создать именованную ссылку с уникальным кодом
    - get_invite_link_by_code — найти ссылку по коду (для обработки deep link)
    - track_user_invite_link — записать привязку пользователя к ссылке
    - get_invite_links_with_stats — все ссылки со статистикой (users + revenue)
    - get_user_active_discount — получить активную скидку пользователя
    - get_user_active_token_bonus — получить активный бонус токенов (%) пользователя
    - delete_invite_link — удалить ссылку
"""

import logging
import secrets
import string
from datetime import date as date_type
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# Общий список колонок для SELECT/RETURNING
_INVITE_LINK_COLUMNS = (
    "id, name, code, bonus_tokens, discount_percent, discount_duration_days, "
    "max_users, is_active, token_bonus_percent, "
    "allow_existing_users, existing_user_bonus_tokens, existing_user_discount, existing_user_token_bonus, "
    "created_at"
)


def _generate_code(length: int = 8) -> str:
    """Генерирует случайный alphanumeric код."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_invite_link(
    name: str,
    bonus_tokens: int = 0,
    discount_percent: int = 0,
    discount_duration_days: int = 0,
    max_users: int = 0,
    token_bonus_percent: int = 0,
    allow_existing_users: bool = False,
    existing_user_bonus_tokens: bool = True,
    existing_user_discount: bool = True,
    existing_user_token_bonus: bool = True,
) -> Dict[str, Any]:
    """Создать новую инвайт-ссылку. Код генерируется автоматически."""
    pool = get_pool()
    async with pool.acquire() as conn:
        for _ in range(5):
            code = _generate_code()
            try:
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO invite_links (
                        name, code, bonus_tokens, discount_percent, discount_duration_days,
                        max_users, token_bonus_percent,
                        allow_existing_users, existing_user_bonus_tokens, existing_user_discount, existing_user_token_bonus
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING {_INVITE_LINK_COLUMNS}
                    """,
                    name, code, bonus_tokens, discount_percent, discount_duration_days,
                    max_users, token_bonus_percent,
                    allow_existing_users, existing_user_bonus_tokens, existing_user_discount, existing_user_token_bonus,
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
            f"""
            SELECT {_INVITE_LINK_COLUMNS}
            FROM invite_links WHERE code = $1
            """,
            code.upper(),
        )
    if not row:
        return None
    return dict(row)


async def track_user_invite_link(
    invite_link_id: int,
    user_id: int,
    is_existing_user: bool = False,
) -> tuple[bool, bool]:
    """
    Записать привязку пользователя к инвайт-ссылке.
    Вычисляет discount_expires_at на основе настроек ссылки.
    Проверяет лимит пользователей: если max_users > 0 и лимит исчерпан — не записывает.
    ON CONFLICT DO NOTHING — если пользователь уже привязан к этой ссылке, ничего не делаем.

    Возвращает (was_new, is_limit_reached):
        was_new = True если запись добавлена впервые
        is_limit_reached = True если лимит исчерпан (пользователь не добавлен)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            async with conn.transaction():
                # Получаем настройки ссылки и текущий счётчик
                row = await conn.fetchrow(
                    """
                    SELECT il.max_users,
                           COUNT(ilu.id) AS current_count
                    FROM invite_links il
                    LEFT JOIN invite_link_users ilu ON ilu.invite_link_id = il.id
                    WHERE il.id = $1
                    GROUP BY il.max_users
                    """,
                    invite_link_id,
                )
                if not row:
                    return False, False

                max_users = row['max_users']
                current_count = row['current_count']

                # Проверяем лимит (max_users=0 означает без лимита)
                if max_users > 0 and current_count >= max_users:
                    return False, True

                result = await conn.execute(
                    """
                    INSERT INTO invite_link_users (invite_link_id, user_id, is_existing_user, discount_expires_at)
                    SELECT $1, $2, $3,
                        CASE WHEN il.discount_duration_days > 0
                                  AND (il.discount_percent > 0 OR il.token_bonus_percent > 0)
                             THEN NOW() + (il.discount_duration_days || ' days')::INTERVAL
                             ELSE NULL
                        END
                    FROM invite_links il
                    WHERE il.id = $1
                    ON CONFLICT (invite_link_id, user_id) DO NOTHING
                    """,
                    invite_link_id, user_id, is_existing_user,
                )
                was_new = result == "INSERT 0 1"
                return was_new, False
        except Exception as e:
            logger.error(f"Ошибка привязки пользователя к инвайт-ссылке: {e}")
            return False, False


async def get_user_active_discount(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает лучшую активную скидку пользователя:
    {discount_percent, token_bonus_percent, discount_expires_at}.
    Учитывает флаги existing_user_discount для существующих пользователей.
    Возвращает None если скидки нет.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT il.discount_percent, il.token_bonus_percent, ilu.discount_expires_at
            FROM invite_link_users ilu
            JOIN invite_links il ON il.id = ilu.invite_link_id
            WHERE ilu.user_id = $1
              AND (ilu.discount_expires_at IS NULL OR ilu.discount_expires_at > NOW())
              AND il.discount_percent > 0
              AND (ilu.is_existing_user = FALSE OR il.existing_user_discount = TRUE)
            ORDER BY il.discount_percent DESC
            LIMIT 1
            """,
            user_id,
        )
    if row:
        return {
            "discount_percent": row["discount_percent"],
            "token_bonus_percent": row["token_bonus_percent"],
            "discount_expires_at": row["discount_expires_at"],
        }
    return None


async def get_user_active_token_bonus(user_id: int) -> Optional[int]:
    """
    Возвращает максимальный активный бонус токенов (%) пользователя.
    Нужна отдельная функция потому что лучшая скидка и лучший бонус токенов
    могут быть на разных ссылках.
    Возвращает None если бонуса нет.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT MAX(il.token_bonus_percent) AS token_bonus_percent
            FROM invite_link_users ilu
            JOIN invite_links il ON il.id = ilu.invite_link_id
            WHERE ilu.user_id = $1
              AND (ilu.discount_expires_at IS NULL OR ilu.discount_expires_at > NOW())
              AND il.token_bonus_percent > 0
              AND (ilu.is_existing_user = FALSE OR il.existing_user_token_bonus = TRUE)
            """,
            user_id,
        )
    if row and row["token_bonus_percent"]:
        return row["token_bonus_percent"]
    return None


async def get_user_active_invite_promo(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает сводку по активным бонусам инвайт-ссылки пользователя:
    {name, discount_percent, token_bonus_percent, discount_expires_at}.
    Берёт ссылку с наибольшей суммой бонусов (discount + token_bonus).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT il.name,
                   CASE WHEN ilu.is_existing_user = FALSE OR il.existing_user_discount = TRUE
                        THEN il.discount_percent ELSE 0 END AS discount_percent,
                   CASE WHEN ilu.is_existing_user = FALSE OR il.existing_user_token_bonus = TRUE
                        THEN il.token_bonus_percent ELSE 0 END AS token_bonus_percent,
                   ilu.discount_expires_at
            FROM invite_link_users ilu
            JOIN invite_links il ON il.id = ilu.invite_link_id
            WHERE ilu.user_id = $1
              AND (ilu.discount_expires_at IS NULL OR ilu.discount_expires_at > NOW())
              AND (il.discount_percent > 0 OR il.token_bonus_percent > 0)
            ORDER BY (CASE WHEN ilu.is_existing_user = FALSE OR il.existing_user_discount = TRUE
                           THEN il.discount_percent ELSE 0 END)
                   + (CASE WHEN ilu.is_existing_user = FALSE OR il.existing_user_token_bonus = TRUE
                           THEN il.token_bonus_percent ELSE 0 END) DESC
            LIMIT 1
            """,
            user_id,
        )
    if row and (row["discount_percent"] > 0 or row["token_bonus_percent"] > 0):
        return {
            "name": row["name"],
            "discount_percent": row["discount_percent"],
            "token_bonus_percent": row["token_bonus_percent"],
            "discount_expires_at": row["discount_expires_at"],
        }
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
                il.bonus_tokens, il.discount_percent, il.discount_duration_days, il.max_users,
                il.is_active, il.token_bonus_percent,
                il.allow_existing_users, il.existing_user_bonus_tokens, il.existing_user_discount, il.existing_user_token_bonus,
                il.created_at,
                COUNT(DISTINCT ilu.user_id) AS users_count,
                COALESCE(SUM(p.amount_rub) FILTER (WHERE p.paid = true), 0) AS total_revenue_rub,
                (SELECT COUNT(DISTINCT user_id) FROM invite_link_users WHERE invite_link_id = il.id) AS total_users_count
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
    max_users: int = 0,
    token_bonus_percent: int = 0,
    allow_existing_users: bool = False,
    existing_user_bonus_tokens: bool = True,
    existing_user_discount: bool = True,
    existing_user_token_bonus: bool = True,
    is_active: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Обновить инвайт-ссылку. Возвращает обновлённую строку или None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if is_active is not None:
            row = await conn.fetchrow(
                f"""
                UPDATE invite_links
                SET name = $1, bonus_tokens = $2, discount_percent = $3, discount_duration_days = $4,
                    max_users = $5, token_bonus_percent = $6,
                    allow_existing_users = $7, existing_user_bonus_tokens = $8,
                    existing_user_discount = $9, existing_user_token_bonus = $10,
                    is_active = $11
                WHERE id = $12
                RETURNING {_INVITE_LINK_COLUMNS}
                """,
                name, bonus_tokens, discount_percent, discount_duration_days,
                max_users, token_bonus_percent,
                allow_existing_users, existing_user_bonus_tokens,
                existing_user_discount, existing_user_token_bonus,
                is_active, link_id,
            )
        else:
            row = await conn.fetchrow(
                f"""
                UPDATE invite_links
                SET name = $1, bonus_tokens = $2, discount_percent = $3, discount_duration_days = $4,
                    max_users = $5, token_bonus_percent = $6,
                    allow_existing_users = $7, existing_user_bonus_tokens = $8,
                    existing_user_discount = $9, existing_user_token_bonus = $10
                WHERE id = $11
                RETURNING {_INVITE_LINK_COLUMNS}
                """,
                name, bonus_tokens, discount_percent, discount_duration_days,
                max_users, token_bonus_percent,
                allow_existing_users, existing_user_bonus_tokens,
                existing_user_discount, existing_user_token_bonus,
                link_id,
            )
    if not row:
        return None
    return dict(row)


async def toggle_invite_link_active(link_id: int, is_active: bool) -> Optional[Dict[str, Any]]:
    """Включить/выключить инвайт-ссылку. Возвращает обновлённую строку или None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE invite_links SET is_active = $1 WHERE id = $2
            RETURNING {_INVITE_LINK_COLUMNS}
            """,
            is_active, link_id,
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
