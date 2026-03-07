# src/services/db/tripwire_followup_repo.py

"""
Репозиторий для воронки дожима tripwire (99₽ план).

DB-backed scheduling: записи с send_at, фоновый loop каждые 30 сек.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# Задержки для каждого этапа (от момента показа оффера)
STAGE_1_DELAY = timedelta(minutes=15)
STAGE_3_DELAY = timedelta(hours=2, minutes=30)
STAGE_4_DELAY = timedelta(hours=24)


async def enroll_user(
    user_id: int,
    telegram_user_id: int,
    culture: str,
    problem: str,
    problem_key: str,
    offer_shown_at: datetime,
) -> None:
    """
    Зарегистрировать пользователя в воронке дожима.
    Создаёт 3 записи: stage 1 (15 мин), stage 3 (2.5 ч), stage 4 (24 ч).
    Stage 2 создаётся динамически после выбора причины.

    ON CONFLICT DO NOTHING — защита от дублирования.
    """
    pool = get_pool()

    stages = [
        (1, offer_shown_at + STAGE_1_DELAY),
        (3, offer_shown_at + STAGE_3_DELAY),
        (4, offer_shown_at + STAGE_4_DELAY),
    ]

    async with pool.acquire() as conn:
        for stage, send_at in stages:
            await conn.execute(
                """
                INSERT INTO tripwire_followup
                    (user_id, telegram_user_id, culture, problem, problem_key,
                     stage, send_at, offer_shown_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                """,
                user_id, telegram_user_id, culture, problem, problem_key,
                stage, send_at, offer_shown_at,
            )

    logger.info(
        f"[followup] Enrolled user {user_id} (tg={telegram_user_id}): "
        f"culture={culture}, problem={problem}"
    )


async def cancel_and_reenroll(
    user_id: int,
    telegram_user_id: int,
    culture: str,
    problem: str,
    problem_key: str,
) -> None:
    """
    Отменить все pending-записи и создать новые в одной транзакции.
    Используется при смене культуры/проблемы.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    stages = [
        (1, now + STAGE_1_DELAY),
        (3, now + STAGE_3_DELAY),
        (4, now + STAGE_4_DELAY),
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Отменяем существующие pending
            result = await conn.execute(
                """
                UPDATE tripwire_followup
                SET status = 'cancelled', updated_at = NOW()
                WHERE user_id = $1 AND status = 'pending'
                """,
                user_id,
            )
            count = int(result.split()[-1]) if result else 0
            if count > 0:
                logger.info(f"[followup] Cancelled {count} pending follow-ups for user {user_id} (reenroll)")

            # Создаём новые записи
            for stage, send_at in stages:
                await conn.execute(
                    """
                    INSERT INTO tripwire_followup
                        (user_id, telegram_user_id, culture, problem, problem_key,
                         stage, send_at, offer_shown_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    user_id, telegram_user_id, culture, problem, problem_key,
                    stage, send_at, now,
                )

    logger.info(
        f"[followup] Enrolled user {user_id} (tg={telegram_user_id}): "
        f"culture={culture}, problem={problem}"
    )


async def get_pending_due(limit: int = 50) -> List[Dict[str, Any]]:
    """Получить pending-записи, время отправки которых наступило."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, user_id, telegram_user_id, culture, problem, problem_key,
                   stage, non_buyer_reason, offer_shown_at
            FROM tripwire_followup
            WHERE status = 'pending' AND send_at <= NOW()
            ORDER BY send_at ASC
            LIMIT $1
            """,
            limit,
        )
    return [dict(row) for row in rows]


async def mark_sent(followup_id: int) -> None:
    """Пометить запись как отправленную."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tripwire_followup
            SET status = 'sent', sent_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            followup_id,
        )


async def mark_failed(followup_id: int, error_message: str) -> None:
    """Пометить запись как неудачную."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tripwire_followup
            SET status = 'failed', error_message = $2, updated_at = NOW()
            WHERE id = $1
            """,
            followup_id, error_message[:500],
        )


async def cancel_all_pending(user_id: int) -> int:
    """
    Отменить все pending-записи пользователя.
    Вызывается при оплате quiz_plan и при перезапуске воронки.
    Возвращает количество отменённых.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE tripwire_followup
            SET status = 'cancelled', updated_at = NOW()
            WHERE user_id = $1 AND status = 'pending'
            """,
            user_id,
        )
    count = int(result.split()[-1]) if result else 0
    if count > 0:
        logger.info(f"[followup] Cancelled {count} pending follow-ups for user {user_id}")
    return count


async def set_reason_and_create_stage2(
    user_id: int,
    telegram_user_id: int,
    reason: str,
) -> Optional[Dict[str, Any]]:
    """
    Сохранить причину отказа в stage=1 и создать stage=2 для немедленной отправки.
    Выполняется в транзакции. Возвращает данные stage-1 записи (culture, problem).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Обновляем stage 1: сохраняем причину
            row = await conn.fetchrow(
                """
                UPDATE tripwire_followup
                SET non_buyer_reason = $2, updated_at = NOW()
                WHERE user_id = $1 AND stage = 1 AND status IN ('pending', 'sent')
                RETURNING culture, problem, problem_key, offer_shown_at
                """,
                user_id, reason,
            )
            if not row:
                return None

            # Создаём stage 2 сразу как sent (handler отправит мгновенно)
            await conn.execute(
                """
                INSERT INTO tripwire_followup
                    (user_id, telegram_user_id, culture, problem, problem_key,
                     stage, non_buyer_reason, send_at, sent_at, status, offer_shown_at)
                VALUES ($1, $2, $3, $4, $5, 2, $6, NOW(), NOW(), 'sent', $7)
                ON CONFLICT DO NOTHING
                """,
                user_id, telegram_user_id,
                row['culture'], row['problem'], row['problem_key'],
                reason, row['offer_shown_at'],
            )

    return dict(row)


async def mark_support_requested(user_id: int) -> None:
    """Пометить что пользователь запросил поддержку."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE tripwire_followup
            SET support_requested = true, updated_at = NOW()
            WHERE user_id = $1 AND status IN ('pending', 'sent')
            """,
            user_id,
        )


async def has_user_paid_quiz_plan(user_id: int) -> bool:
    """Проверить, оплатил ли пользователь quiz_plan."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1 FROM payments
            WHERE user_id = $1 AND payment_type = 'quiz_plan' AND paid = true
            LIMIT 1
            """,
            user_id,
        )
    return row is not None
