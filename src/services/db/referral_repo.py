# src/services/db/referral_repo.py

"""
Репозиторий для реферальной системы.

Функции:
    - get_or_create_referral_code — получить/создать реферальный код пользователя
    - get_user_id_by_referral_code — найти пользователя по реферальному коду
    - create_referral — создать реферальную связь
    - grant_referral_bonuses — начислить бонусы обоим
    - get_referral_stats — статистика рефералов для профиля
    - get_referrer_info — кто пригласил пользователя (для админки)
    - get_referrals_list — список приглашённых (для админки)
"""

import logging
import secrets
import string
from typing import Optional, Dict, Any, List

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


def _generate_code(length: int = 8) -> str:
    """Генерирует случайный alphanumeric код."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def get_or_create_referral_code(user_id: int) -> str:
    """Получить существующий или создать новый реферальный код."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Проверяем существующий код
        existing = await conn.fetchval(
            "SELECT referral_code FROM users WHERE id = $1",
            user_id,
        )
        if existing:
            return existing

        # Генерируем уникальный код (до 5 попыток на случай коллизии)
        for _ in range(5):
            code = _generate_code()
            try:
                await conn.execute(
                    "UPDATE users SET referral_code = $1 WHERE id = $2",
                    code, user_id,
                )
                return code
            except Exception:
                continue

        raise RuntimeError(f"Не удалось сгенерировать уникальный реферальный код для user {user_id}")


async def get_user_id_by_referral_code(code: str) -> Optional[int]:
    """Найти user_id по реферальному коду. Возвращает None если не найден."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT id FROM users WHERE referral_code = $1",
            code.upper(),
        )


async def create_referral(referrer_id: int, referee_id: int) -> bool:
    """
    Создать реферальную связь.
    Возвращает True если создана, False если уже существует.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO referrals (referrer_id, referee_id)
                VALUES ($1, $2)
                ON CONFLICT (referee_id) DO NOTHING
                """,
                referrer_id, referee_id,
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка создания реферала: {e}")
            return False


async def get_referral_bonus_amounts() -> tuple[int, int]:
    """Получить размеры бонусов из admin_settings."""
    from src.services.db import settings_repo
    try:
        referrer_bonus = int(await settings_repo.get_setting('referral_bonus_referrer', '3'))
        referee_bonus = int(await settings_repo.get_setting('referral_bonus_referee', '2'))
    except (ValueError, TypeError):
        referrer_bonus, referee_bonus = 3, 2
    return referrer_bonus, referee_bonus


async def grant_referral_bonuses(referrer_id: int, referee_id: int) -> tuple[int, int]:
    """
    Начислить бонусные токены обоим участникам.
    Возвращает (referrer_bonus, referee_bonus) — начисленные суммы.
    """
    from src.services.db.tokens_repo import add_tokens

    referrer_bonus, referee_bonus = await get_referral_bonus_amounts()

    pool = get_pool()
    async with pool.acquire() as conn:
        # Проверяем что бонусы ещё не начислены
        row = await conn.fetchrow(
            "SELECT referrer_bonus_granted, referee_bonus_granted FROM referrals WHERE referrer_id = $1 AND referee_id = $2",
            referrer_id, referee_id,
        )
        if not row:
            return (0, 0)

        granted_referrer = 0
        granted_referee = 0

        if not row["referrer_bonus_granted"] and referrer_bonus > 0:
            await add_tokens(
                user_id=referrer_id,
                amount=referrer_bonus,
                operation_type="referral_bonus",
                description=f"Бонус за приглашённого друга",
            )
            granted_referrer = referrer_bonus

        if not row["referee_bonus_granted"] and referee_bonus > 0:
            await add_tokens(
                user_id=referee_id,
                amount=referee_bonus,
                operation_type="referral_bonus",
                description=f"Бонус за регистрацию по реферальной ссылке",
            )
            granted_referee = referee_bonus

        # Помечаем бонусы как начисленные
        await conn.execute(
            """
            UPDATE referrals
            SET referrer_bonus_granted = TRUE,
                referee_bonus_granted = TRUE
            WHERE referrer_id = $1 AND referee_id = $2
            """,
            referrer_id, referee_id,
        )

    logger.info(
        f"Реферальные бонусы: referrer={referrer_id} +{granted_referrer}, "
        f"referee={referee_id} +{granted_referee}"
    )
    return (granted_referrer, granted_referee)


async def get_referral_stats(user_id: int) -> Dict[str, int]:
    """Статистика рефералов пользователя для профиля."""
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1",
            user_id,
        )
    return {"total_referrals": count or 0}


async def get_referrer_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Кто пригласил этого пользователя. Возвращает данные реферера или None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.username, u.first_name, u.last_name, r.created_at
            FROM referrals r
            JOIN users u ON u.id = r.referrer_id
            WHERE r.referee_id = $1
            """,
            user_id,
        )
    if not row:
        return None
    return dict(row)


async def get_referrals_list(user_id: int) -> List[Dict[str, Any]]:
    """Список приглашённых пользователей (для админки)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id, u.username, u.first_name, u.last_name,
                   r.created_at, r.referrer_bonus_granted, r.referee_bonus_granted
            FROM referrals r
            JOIN users u ON u.id = r.referee_id
            WHERE r.referrer_id = $1
            ORDER BY r.created_at DESC
            """,
            user_id,
        )
    return [dict(row) for row in rows]
