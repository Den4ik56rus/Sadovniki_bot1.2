"""
Репозиторий для работы со словарём терминов.
"""
from typing import List, Optional
from src.services.db.pool import get_pool


async def get_all_terminology() -> List[dict]:
    """
    Получить все термины из словаря.

    Returns:
        List[dict]: Список словарей с полями {id, term, preferred_phrase, description}
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, term, preferred_phrase, description
            FROM terminology
            ORDER BY term
            """
        )
        return [dict(row) for row in rows]


async def add_terminology(term: str, preferred_phrase: str, description: Optional[str] = None) -> int:
    """
    Добавить новый термин в словарь.

    Args:
        term: Исходный термин
        preferred_phrase: Предпочитаемая формулировка
        description: Описание (опционально)

    Returns:
        int: ID созданной записи
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO terminology (term, preferred_phrase, description)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            term, preferred_phrase, description
        )
        return row['id']


async def delete_terminology(terminology_id: int) -> bool:
    """
    Удалить термин из словаря.

    Args:
        terminology_id: ID термина

    Returns:
        bool: True если удалено, False если не найдено
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM terminology
            WHERE id = $1
            """,
            terminology_id
        )
        return result == "DELETE 1"
