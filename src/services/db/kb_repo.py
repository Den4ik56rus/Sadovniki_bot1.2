from typing import Optional, List  # Для типов параметров и возвращаемых значений

from src.services.db.pool import get_pool  # Пул подключений


# Жёстко фиксируем размерность под колонку embedding VECTOR(1536)
KB_VECTOR_DIM = 1536


def _normalize_embedding(embedding: List[float]) -> List[float]:
    """
    Приводит эмбеддинг к размерности KB_VECTOR_DIM:
      - если вектор длиннее — обрезаем;
      - если короче — дополняем нулями.
    Это убирает ошибку вида: expected 1536 dimensions, not 3072.
    """
    if embedding is None:
        return [0.0] * KB_VECTOR_DIM

    emb = list(embedding)
    n = len(emb)

    if n == KB_VECTOR_DIM:
        return emb
    elif n > KB_VECTOR_DIM:
        # Обрезаем лишнее
        return emb[:KB_VECTOR_DIM]
    else:
        # Дополняем нулями
        return emb + [0.0] * (KB_VECTOR_DIM - n)


async def kb_insert(
    *,
    category: str,              # Основная категория (тип консультации: 'питание растений', 'посадка и уход' и т.п.)
    subcategory: Optional[str], # Подкатегория (культура: 'малина', 'голубика' и т.п., может быть None)
    question: Optional[str],    # Вопрос (полный вопрос, может быть None)
    answer: str,                # Ответ (обязателен)
    embedding: List[float],     # Список чисел — эмбеддинг
    source_type: str = "manual" # Тип источника ('manual', 'faq', 'admin_qa' и т.п.)
) -> int:
    """
    Создаёт новую запись в таблице knowledge_base и возвращает её id.
    """
    pool = get_pool()

    # Нормализуем размерность эмбеддинга под VECTOR(1536)
    norm_embedding = _normalize_embedding(embedding)

    # Превращаем список чисел в строку формата "[0.123456,0.654321,...]" для pgvector
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO knowledge_base (
                category,
                subcategory,
                question,
                answer,
                source_type,
                embedding
            )
            VALUES ($1, $2, $3, $4, $5, $6::vector)
            RETURNING id;
            """,
            category,    # $1
            subcategory, # $2
            question,    # $3
            answer,      # $4
            source_type, # $5
            vector_str,  # $6 — строка, которую pgvector приведёт к vector(1536)
        )

    return row["id"]


async def kb_search(
    *,
    category: str,                 # Тип консультации (например, 'питание растений')
    query_embedding: List[float],  # Эмбеддинг запроса
    subcategory: Optional[str] = None,          # Культура ('малина', 'голубика' и т.п.) или None
    limit: int = 3,                             # Сколько записей максимум вернуть
    distance_threshold: Optional[float] = 0.35, # Порог расстояния (чем меньше, тем ближе)
):
    """
    Поиск похожих фрагментов в knowledge_base по эмбеддингу.

    Фильтрация:
        - ВСЕГДА по category (тип консультации: 'питание растений' и т.п.),
        - ДОПОЛНИТЕЛЬНО по subcategory, если она передана (культура: 'малина', 'голубика' и т.п.).

    Если subcategory=None — будет поиск по всем культурам внутри категории.
    """
    pool = get_pool()

    # Нормализуем эмбеддинг запроса под VECTOR(1536)
    norm_embedding = _normalize_embedding(query_embedding)

    # Строка формата "[0.1234,0.5678,...]" для pgvector
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                category,
                subcategory,
                question,
                answer,
                embedding <=> $1::vector AS distance
            FROM knowledge_base
            WHERE is_active = TRUE
              AND category = $2
              AND ($3::text IS NULL OR subcategory = $3)
            ORDER BY embedding <=> $1::vector
            LIMIT $4;
            """,
            vector_str,   # $1 — эмбеддинг запроса
            category,     # $2 — тип консультации
            subcategory,  # $3 — культура (или NULL: тогда по всем культурам)
            limit,        # $4 — лимит количества строк
        )

    # Если задан порог distance_threshold, фильтруем результаты.
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return rows


async def kb_get_distinct_categories(limit: int = 50, only_valid: bool = True) -> List[str]:
    """
    Возвращает список уникальных ЗНАЧЕНИЙ category из базы знаний (knowledge_base).

    Сейчас category используется как КУЛЬТУРА:
        'клубника общая', 'клубника летняя', 'малина общая' и т.п.

    Args:
        limit: Максимум записей
        only_valid: Если True, вернёт только категории из валидного списка

    Внимание: служебные bootstrap-записи с is_active=FALSE всё равно попадут сюда,
    если у них заполнено поле category.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT category
            FROM knowledge_base
            WHERE category IS NOT NULL
            ORDER BY category
            LIMIT $1;
            """,
            limit,
        )

    categories = [r["category"] for r in rows]

    # Если требуется - отфильтровать только валидные категории культур
    if only_valid:
        valid_set = {
            "клубника общая",
            "клубника летняя",
            "клубника ремонтантная",
            "малина общая",
            "малина летняя",
            "малина ремонтантная",
            "смородина",
            "голубика",
            "жимолость",
            "крыжовник",
            "ежевика",
            "общая информация",
        }
        categories = [c for c in categories if c in valid_set]

    return categories


async def kb_get_distinct_subcategories(limit: int = 200) -> List[str]:
    """
    Возвращает список уникальных ЗНАЧЕНИЙ subcategory из базы знаний (knowledge_base).

    subcategory в нашей схеме — это КУЛЬТУРА:
        'малина', 'клубника садовая', 'голубика', 'жимолость' и т.п.

    Используется, например, для подсказки LLM-классификатору культур
    (detect_culture_name), чтобы он ориентировался на реальные культуры
    из базы знаний, а не на типы консультаций.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT subcategory
            FROM knowledge_base
            WHERE subcategory IS NOT NULL
            ORDER BY subcategory
            LIMIT $1;
            """,
            limit,
        )

    return [r["subcategory"] for r in rows]


async def kb_search_all(
    *,
    query_embedding: List[float],
    limit: int = 3,
    distance_threshold: Optional[float] = 0.4,
):
    """
    Поиск Q&A пар БЕЗ фильтрации по category/subcategory.
    Используется в режиме написания статей для администратора.

    Параметры:
        query_embedding: Эмбеддинг запроса
        limit: Максимум записей
        distance_threshold: Порог расстояния (чем меньше, тем ближе)

    Возвращает:
        Список словарей с найденными Q&A записями
    """
    pool = get_pool()

    # Нормализуем эмбеддинг запроса под VECTOR(1536)
    norm_embedding = _normalize_embedding(query_embedding)

    # Строка формата "[0.1234,0.5678,...]" для pgvector
    vector_str = "[" + ",".join(f"{x:.6f}" for x in norm_embedding) + "]"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                category,
                subcategory,
                question,
                answer,
                embedding <=> $1::vector AS distance
            FROM knowledge_base
            WHERE is_active = TRUE
            ORDER BY embedding <=> $1::vector
            LIMIT $2;
            """,
            vector_str,  # $1 — эмбеддинг запроса
            limit,       # $2 — лимит количества строк
        )

    # Фильтруем по порогу расстояния, если задан
    if distance_threshold is not None:
        rows = [r for r in rows if r["distance"] <= distance_threshold]

    return rows


async def kb_get_list(
    *,
    search: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple:
    """
    Список записей knowledge_base для браузера KB.
    Возвращает (items, total_count).
    """
    pool = get_pool()

    conditions = []
    params: list = []
    idx = 1

    if search:
        conditions.append(f"(question ILIKE ${idx} OR answer ILIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1
    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if subcategory:
        conditions.append(f"subcategory = ${idx}")
        params.append(subcategory)
        idx += 1
    if is_active is not None:
        conditions.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with pool.acquire() as conn:
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) AS cnt FROM knowledge_base {where}",
            *params,
        )
        total = int(count_row["cnt"]) if count_row else 0

        items_sql = f"""
            SELECT id, category, subcategory, question, answer,
                   source_type, is_active, created_at
            FROM knowledge_base
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])
        rows = await conn.fetch(items_sql, *params)

    return rows, total


async def kb_get_by_id(kb_id: int):
    """Получить одну запись KB по id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT id, category, subcategory, question, answer,
                   source_type, is_active, created_at
            FROM knowledge_base
            WHERE id = $1
            """,
            kb_id,
        )


async def kb_update(
    kb_id: int,
    *,
    question: Optional[str] = None,
    answer: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[dict]:
    """Обновить поля KB-записи. Возвращает обновлённую запись."""
    pool = get_pool()

    sets = []
    params: list = []
    idx = 1

    if question is not None:
        sets.append(f"question = ${idx}")
        params.append(question)
        idx += 1
    if answer is not None:
        sets.append(f"answer = ${idx}")
        params.append(answer)
        idx += 1
    if category is not None:
        sets.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if subcategory is not None:
        sets.append(f"subcategory = ${idx}")
        params.append(subcategory)
        idx += 1
    if is_active is not None:
        sets.append(f"is_active = ${idx}")
        params.append(is_active)
        idx += 1

    if not sets:
        return await kb_get_by_id(kb_id)

    params.append(kb_id)
    set_clause = ", ".join(sets)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE knowledge_base
            SET {set_clause}
            WHERE id = ${idx}
            RETURNING id, category, subcategory, question, answer,
                      source_type, is_active, created_at
            """,
            *params,
        )
    return row
