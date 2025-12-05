# src/services/db/tokens_repo.py
"""
Репозиторий для работы с токенами пользователей.

Функции:
    - get_token_balance — получить текущий баланс
    - has_sufficient_tokens — проверить достаточность токенов
    - deduct_tokens — списать токены (с логированием)
    - add_tokens — начислить токены (для админа)
"""

from typing import Optional

from src.services.db.pool import get_pool


async def get_token_balance(user_id: int) -> int:
    """
    Получает текущий баланс токенов пользователя.

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
    Списывает токены с баланса пользователя.

    Использует транзакцию с блокировкой строки для атомарности.
    Логирует операцию в таблицу token_transactions.

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов для списания
        operation_type: тип операции ('new_topic', 'buy_questions')
        description: описание операции (опционально)

    Returns:
        True если списание успешно, False если недостаточно токенов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Проверяем баланс с блокировкой строки
            row = await conn.fetchrow(
                "SELECT token_balance FROM users WHERE id = $1 FOR UPDATE",
                user_id,
            )
            if not row or row["token_balance"] < amount:
                return False

            # Списываем токены
            await conn.execute(
                """
                UPDATE users
                SET token_balance = token_balance - $1
                WHERE id = $2
                """,
                amount,
                user_id,
            )

            # Логируем транзакцию
            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                -amount,  # отрицательное значение = списание
                operation_type,
                description,
            )

            return True


async def add_tokens(
    user_id: int,
    amount: int,
    operation_type: str = "admin_credit",
    description: Optional[str] = None,
) -> int:
    """
    Начисляет токены на баланс пользователя.

    Используется администратором для пополнения баланса.
    Логирует операцию в таблицу token_transactions.

    Args:
        user_id: внутренний ID пользователя
        amount: количество токенов для начисления
        operation_type: тип операции (по умолчанию 'admin_credit')
        description: описание операции (опционально)

    Returns:
        Новый баланс токенов
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Начисляем токены
            row = await conn.fetchrow(
                """
                UPDATE users
                SET token_balance = token_balance + $1
                WHERE id = $2
                RETURNING token_balance
                """,
                amount,
                user_id,
            )

            # Логируем транзакцию
            await conn.execute(
                """
                INSERT INTO token_transactions
                (user_id, amount, operation_type, description)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                amount,  # положительное значение = начисление
                operation_type,
                description,
            )

            return row["token_balance"] if row else 0
