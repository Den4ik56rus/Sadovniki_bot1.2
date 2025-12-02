# src/services/db/moderation_repo.py

from typing import Optional, List  # Для аннотаций типов (Optional, List)

# Импорт функции, которая возвращает пул подключений к БД
from src.services.db.pool import get_pool  # Пул подключений asyncpg


async def moderation_add(
    *,
    user_id: int,                 # Автор вопроса/ответа (users.id)
    topic_id: Optional[int],      # Тема диалога (topics.id), может быть None
    question: str,                # Вопрос пользователя (мы будем передавать СЮДА full_question)
    answer: str,                  # Ответ бота (answer_text)
    category_guess: Optional[str] # Предполагаемая категория (мы будем передавать сюда культуру или тип вроде "nutrition")
) -> None:
    """
    Добавить новый кандидат в moderation_queue.

    ВАЖНО (для нашей новой логики по питанию растений):
        - параметр question:
            сюда будем передавать УЖЕ СОБРАННЫЙ ПОЛНЫЙ ВОПРОС (full_question),
            который включает:
                * рут-вопрос,
                * ответы на уточняющие вопросы,
                * при необходимости — служебные заголовки.

        - параметр category_guess:
            сюда можем передавать:
                * либо культуру (например, "малина", "клубника садовая"),
                * либо сочетание типа "nutrition / малина",
                * либо просто None, если пока не определили.
    """
    # Берём пул соединений с БД (asyncpg.Pool), который уже был инициализирован
    pool = get_pool()

    # Открываем соединение из пула
    async with pool.acquire() as conn:
        # Выполняем INSERT-запрос в таблицу moderation_queue
        await conn.execute(
            """
            INSERT INTO moderation_queue (
                user_id,      -- кто задал вопрос / получил ответ
                topic_id,     -- в рамках какой темы диалога
                question,     -- текст вопроса (у нас: full_question)
                answer,       -- текст ответа бота
                category_guess-- предполагаемая категория (у нас: культура / тип)
            )
            VALUES ($1, $2, $3, $4, $5);
            """,
            user_id,        # $1 → user_id
            topic_id,       # $2 → topic_id
            question,       # $3 → question (full_question)
            answer,         # $4 → answer (ответ бота)
            category_guess, # $5 → category_guess (культура / тип / None)
        )


async def moderation_get_next_pending():
    """
    Получить следующую запись со статусом 'pending' или None.
    Используется в админке для показа следующего кандидата.
    """
    # Берём пул соединений
    pool = get_pool()

    # Открываем соединение из пула
    async with pool.acquire() as conn:
        # Берём самую старую запись со статусом 'pending'
        row = await conn.fetchrow(
            """
            SELECT
                id,
                user_id,
                topic_id,
                category_guess,
                question,
                answer,
                status,
                admin_id,
                kb_id,
                created_at
            FROM moderation_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1;
            """
        )
        # Может вернуть asyncpg.Record или None
        return row


async def moderation_get_by_id(item_id: int):
    """
    Получить запись moderation_queue по id или None.
    Используется при обработке конкретного кандидата в админке.
    """
    # Берём пул
    pool = get_pool()

    # Открываем соединение
    async with pool.acquire() as conn:
        # Достаём конкретную запись по id
        row = await conn.fetchrow(
            """
            SELECT
                id,
                user_id,
                topic_id,
                category_guess,
                question,
                answer,
                status,
                admin_id,
                kb_id,
                created_at
            FROM moderation_queue
            WHERE id = $1;
            """,
            item_id,  # $1 — id записи
        )
        return row


async def moderation_update_status(
    item_id: int,              # id записи в moderation_queue
    *,
    status: str,               # Новый статус ('approved', 'rejected' и т.п.)
    admin_id: Optional[int] = None,  # id админа, обработавшего запись
    kb_id: Optional[int] = None,     # id записи в knowledge_base (если добавлена)
) -> None:
    """
    Обновить статус записи moderation_queue.

    Например:
        - при одобрении: status='approved', kb_id=id записи в knowledge_base
        - при отклонении: status='rejected'
    """
    # Берём пул
    pool = get_pool()

    # Открываем соединение
    async with pool.acquire() as conn:
        # Обновляем статус и связанные поля
        await conn.execute(
            """
            UPDATE moderation_queue
            SET status     = $2,
                admin_id   = COALESCE($3, admin_id),
                kb_id      = COALESCE($4, kb_id),
                updated_at = NOW()
            WHERE id = $1;
            """,
            item_id,  # $1 — id записи
            status,   # $2 — новый статус
            admin_id, # $3 — id админа (если None, оставляем старое значение)
            kb_id,    # $4 — id записи в kb (если None, оставляем старое значение)
        )


async def moderation_set_category(item_id: int, category: str) -> None:
    """
    Обновляет поле category_guess у записи в moderation_queue.

    Используется, когда админ задаёт или меняет категорию кандидата.
    В нашем случае сюда можно будет передать:
        - культуру (например, "малина"),
        - или более точную категорию типа "nutrition / малина".
    """
    # Берём пул
    pool = get_pool()

    # Открываем соединение и выполняем UPDATE
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE moderation_queue
            SET category_guess = $2,
                updated_at     = NOW()
            WHERE id = $1;
            """,
            item_id,  # $1 — id записи
            category, # $2 — новая категория
        )


async def moderation_count_pending() -> int:
    """
    Вернёт количество записей в moderation_queue со статусом 'pending'.
    Используется для вывода:
        'В очереди на проверку: N вопросов.'
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM moderation_queue
            WHERE status = 'pending';
            """
        )
        return int(row["cnt"]) if row and row["cnt"] is not None else 0


async def moderation_update_answer(item_id: int, new_answer: str) -> None:
    """
    Обновляет ответ в записи moderation_queue.

    Используется при редактировании ответа через LLM модератором.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE moderation_queue
            SET answer = $2, updated_at = NOW()
            WHERE id = $1;
            """,
            item_id,
            new_answer,
        )
