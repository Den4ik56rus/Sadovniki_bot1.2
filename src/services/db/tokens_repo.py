# src/services/db/tokens_repo.py
"""
Репозиторий для работы с токенами пользователей.

Split-balance система:
    - subscription_token_balance — токены от подписки (с лимитом переноса)
    - purchased_token_balance — купленные токены (без ограничений)
    - token_balance — суммарный баланс (денормализованный, для обратной совместимости)

Порядок списания: сначала подписочные, потом купленные.

Функции:
    - get_token_balance — получить суммарный баланс
    - get_split_balance — получить раздельный баланс
    - has_sufficient_tokens — проверить достаточность
    - deduct_tokens — списать токены (split-aware)
    - add_tokens — начислить токены (в purchased по умолчанию)
    - add_subscription_tokens — начислить подписочные токены
    - add_purchased_tokens — начислить купленные токены
    - reset_subscription_tokens_with_carryover — обновить подписочные при продлении
"""

import logging
from typing import Optional, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def get_token_balance(user_id: int) -> int:
    """
    Получает суммарный баланс токенов пользователя.

    Args:
        user_id: внутренний ID пользователя (users.id)

    Returns:
        Количество токенов (0 если пользователь не найден)
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT token_balance FROM users WHERE id = $1",
            user_id,
        )
        return row["token_balance"] if row else 0


async def get_split_balance(user_id: int) -> Dict[str, int]:
    """
    Получает раздельный баланс токенов.

    Returns:
        {subscription_tokens, purchased_tokens, total}
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT token_balance,
                   COALESCE(subscription_token_balance, 0) AS subscription_token_balance,
                   COALESCE(purchased_token_balance, 0) AS purchased_token_balance
            FROM users WHERE id = $1
            """,
            user_id,
        )
        if not row:
            return {"subscription_tokens": 0, "purchased_tokens": 0, "total": 0}
        return {
            "subscription_tokens": row["subscription_token_balance"],
            "purchased_tokens": row["purchased_token_balance"],
            "total": row["token_balance"],
        }


async def has_sufficient_tokens(user_id: int, required: int) -> bool:
    """
    Проверяет, достаточно ли токенов для операции.

    Args:
        user_id: внутренний ID пользователя
        required: необходимое количество токенов

    Returns:
        True если баланс >= required
    """
    balance = await get_token_balance(user_id)
    return balance >= required


async def deduct_tokens(
    user_id: int,
    amount: int,
    operation_type: str,
    description: Optional[str] = None,
) -> bool:
    """
    Списывает токены с баланса пользователя (split-aware).

    Порядок: сначала подписочные токены, затем купленные.
    Использует транзакцию с блокировкой строки для атомарности.

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов для списания
        operation_type: тип операции ('new_topic', 'buy_questions')
        description: описание операции (опционально)

    Returns:
        True если списание успешно, False если недостаточно токенов
    """
    pool = get_pool()
    from_sub = 0
    from_pur = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT token_balance,
                       COALESCE(subscription_token_balance, 0) AS sub_bal,
                       COALESCE(purchased_token_balance, 0) AS pur_bal
                FROM users WHERE id = $1 FOR UPDATE
                """,
                user_id,
            )
            if not row:
                return False

            sub_bal = max(row["sub_bal"], 0)  # защита от отрицательных
            pur_bal = max(row["pur_bal"], 0)
            real_balance = sub_bal + pur_bal

            if real_balance < amount:
                return False

            # Списываем сначала из подписочных, потом из купленных
            from_sub = min(sub_bal, amount)
            from_pur = amount - from_sub

            # Пересчитываем token_balance из реальных данных (не инкремент)
            new_total = real_balance - amount
            await conn.execute(
                """
                UPDATE users
                SET token_balance = $1,
                    subscription_token_balance = $2,
                    purchased_token_balance = $3
                WHERE id = $4
                """,
                new_total, sub_bal - from_sub, pur_bal - from_pur, user_id,
            )

            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, -amount, operation_type, description,
            )

    # Логируем системное сообщение в ленту чата (вне транзакции)
    try:
        from src.services.db.messages_repo import log_system_message

        token_word = "токена" if 2 <= amount <= 4 else "токенов" if amount >= 5 else "токен"
        parts = []
        if from_sub > 0:
            parts.append(f"{from_sub} подписочных")
        if from_pur > 0:
            parts.append(f"{from_pur} купленных")
        balance_detail = " + ".join(parts) if parts else str(amount)

        msg_text = f"Списано {amount} {token_word} ({balance_detail})"
        if description:
            msg_text += f" — {description}"

        await log_system_message(
            user_id=user_id,
            text=msg_text,
            meta={
                "type": "token_deduction",
                "amount": amount,
                "from_sub": from_sub,
                "from_pur": from_pur,
                "operation_type": operation_type,
                "description": description,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log token deduction system message: {e}")

    return True


async def add_tokens(
    user_id: int,
    amount: int,
    operation_type: str = "admin_credit",
    description: Optional[str] = None,
) -> int:
    """
    Начисляет токены на баланс (в purchased_token_balance).

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов
        operation_type: тип операции
        description: описание

    Returns:
        Новый суммарный баланс
    """
    return await add_purchased_tokens(user_id, amount, operation_type, description)


async def add_subscription_tokens(
    user_id: int,
    amount: int,
    operation_type: str = "subscription_activation",
    description: Optional[str] = None,
) -> int:
    """
    Начисляет подписочные токены.

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов
        operation_type: тип операции
        description: описание

    Returns:
        Новый суммарный баланс
    """
    pool = get_pool()
    new_balance = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE users
                SET token_balance = token_balance + $1,
                    subscription_token_balance = COALESCE(subscription_token_balance, 0) + $1
                WHERE id = $2
                RETURNING token_balance
                """,
                amount, user_id,
            )

            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, amount, operation_type, description,
            )

            new_balance = row["token_balance"] if row else 0

    # Системное сообщение в ленту чата
    try:
        from src.services.db.messages_repo import log_system_message
        token_word = "токена" if 2 <= amount <= 4 else "токенов" if amount >= 5 else "токен"
        op_labels = {
            "subscription_activation": "Активация подписки",
            "admin_credit": "Начисление администратором",
            "referral_bonus": "Реферальный бонус",
            "trial_grant": "Пробный доступ",
            "invite_bonus": "Бонус по приглашению",
            "refund": "Возврат токенов",
        }
        op_label = op_labels.get(operation_type, operation_type)
        msg_text = f"Начислено {amount} {token_word} (подписочные) — {description or op_label}"
        await log_system_message(
            user_id=user_id,
            text=msg_text,
            meta={
                "type": "token_credit",
                "amount": amount,
                "token_type": "subscription",
                "operation_type": operation_type,
                "description": description,
                "new_balance": new_balance,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log token credit system message: {e}")

    return new_balance


async def add_purchased_tokens(
    user_id: int,
    amount: int,
    operation_type: str = "admin_credit",
    description: Optional[str] = None,
) -> int:
    """
    Начисляет купленные токены.

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов
        operation_type: тип операции
        description: описание

    Returns:
        Новый суммарный баланс
    """
    pool = get_pool()
    new_balance = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE users
                SET token_balance = token_balance + $1,
                    purchased_token_balance = COALESCE(purchased_token_balance, 0) + $1
                WHERE id = $2
                RETURNING token_balance
                """,
                amount, user_id,
            )

            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, amount, operation_type, description,
            )

            new_balance = row["token_balance"] if row else 0

    # Системное сообщение в ленту чата
    try:
        from src.services.db.messages_repo import log_system_message
        token_word = "токена" if 2 <= amount <= 4 else "токенов" if amount >= 5 else "токен"
        op_labels = {
            "admin_credit": "Начисление администратором",
            "payment_yookassa": "Покупка токенов",
            "referral_bonus": "Реферальный бонус",
            "trial_grant": "Пробный доступ",
            "invite_bonus": "Бонус по приглашению",
            "refund": "Возврат токенов",
        }
        op_label = op_labels.get(operation_type, operation_type)
        msg_text = f"Начислено {amount} {token_word} (купленные) — {description or op_label}"
        await log_system_message(
            user_id=user_id,
            text=msg_text,
            meta={
                "type": "token_credit",
                "amount": amount,
                "token_type": "purchased",
                "operation_type": operation_type,
                "description": description,
                "new_balance": new_balance,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log token credit system message: {e}")

    return new_balance


async def reset_subscription_tokens_with_carryover(
    user_id: int,
    new_amount: int,
    max_carryover: int,
) -> Dict[str, int]:
    """
    Обновляет подписочные токены при продлении подписки с переносом.

    Вычисляет: carryover = min(current_subscription_token_balance, max_carryover)
    Устанавливает: subscription_token_balance = new_amount + carryover

    Args:
        user_id: внутренний ID пользователя
        new_amount: количество новых токенов от подписки
        max_carryover: максимум переноса с прошлого периода

    Returns:
        {carryover, new_subscription_balance, total_balance}
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT token_balance,
                       COALESCE(subscription_token_balance, 0) AS sub_bal,
                       COALESCE(purchased_token_balance, 0) AS pur_bal
                FROM users WHERE id = $1 FOR UPDATE
                """,
                user_id,
            )
            if not row:
                return {"carryover": 0, "new_subscription_balance": 0, "total_balance": 0}

            old_sub = row["sub_bal"]
            pur_bal = row["pur_bal"]

            carryover = min(old_sub, max_carryover)
            new_sub_balance = new_amount + carryover
            new_total = new_sub_balance + pur_bal

            await conn.execute(
                """
                UPDATE users
                SET subscription_token_balance = $1,
                    token_balance = $2
                WHERE id = $3
                """,
                new_sub_balance, new_total, user_id,
            )

            # Лог начисления подписочных токенов
            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, new_amount,
                "subscription_activation",
                f"Активация подписки: +{new_amount} токенов",
            )

            # Лог переноса (если был)
            if carryover > 0:
                await conn.execute(
                    """
                    INSERT INTO token_transactions
                    (user_id, amount, operation_type, description)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id, 0,
                    "carryover",
                    f"Перенос {carryover} из {old_sub} неиспользованных (макс. {max_carryover})",
                )

    # Системное сообщение в ленту чата
    try:
        from src.services.db.messages_repo import log_system_message
        token_word = "токена" if 2 <= new_amount <= 4 else "токенов" if new_amount >= 5 else "токен"
        msg_text = f"Активация подписки: +{new_amount} {token_word}"
        if carryover > 0:
            msg_text += f" + перенос {carryover}"
        msg_text += f" (итого {new_sub_balance} подписочных)"
        await log_system_message(
            user_id=user_id,
            text=msg_text,
            meta={
                "type": "subscription_activation",
                "new_amount": new_amount,
                "carryover": carryover,
                "new_sub_balance": new_sub_balance,
                "total_balance": new_total,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to log subscription activation system message: {e}")

    return {
                "carryover": carryover,
                "new_subscription_balance": new_sub_balance,
                "total_balance": new_total,
            }
