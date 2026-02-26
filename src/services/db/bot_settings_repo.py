from src.services.db.pool import get_pool


async def get_setting(key: str, default: str = None) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM bot_settings WHERE key = $1", key
        )
        if row:
            return row['value']
        return default


async def set_setting(key: str, value: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO bot_settings (key, value, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
        """, key, value)
