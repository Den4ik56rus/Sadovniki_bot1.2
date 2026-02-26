import logging
from aiohttp import web
from src.services.db.pool import get_pool
from src.services.db.bot_settings_repo import get_setting, set_setting

logger = logging.getLogger(__name__)


async def get_ab_test_stats(request: web.Request) -> web.Response:
    """GET /api/admin/ab-test/stats — статистика по вариантам воронки"""
    pool = get_pool()
    async with pool.acquire() as conn:
        active_variant = await get_setting('active_funnel_variant', 'A')

        rows = await conn.fetch("""
            SELECT
                u.funnel_variant,
                COUNT(DISTINCT u.id) AS users,
                COUNT(DISTINCT CASE WHEN cfp.stage_key IN ('tried','trial_ended','saw_pricing') THEN u.id END) AS tried,
                COUNT(DISTINCT CASE WHEN cfp.stage_key IN ('trial_ended','saw_pricing') THEN u.id END) AS trial_ended,
                COUNT(DISTINCT CASE WHEN cfp.stage_key = 'saw_pricing' THEN u.id END) AS saw_pricing,
                COUNT(DISTINCT p.user_id) AS paid
            FROM users u
            LEFT JOIN client_funnel_position cfp ON cfp.user_id = u.id AND cfp.funnel_id = 'crm'
            LEFT JOIN payments p ON p.user_id = u.id AND p.status = 'paid'
            WHERE u.funnel_variant IS NOT NULL
            GROUP BY u.funnel_variant
            ORDER BY u.funnel_variant
        """)

        variants = {}
        for row in rows:
            variant = row['funnel_variant']
            users = row['users']
            paid = row['paid']
            tried = row['tried']
            trial_ended = row['trial_ended']
            saw_pricing = row['saw_pricing']
            conversion = round(paid / users * 100, 1) if users > 0 else 0.0
            variants[variant] = {
                'users': users,
                'tried': tried,
                'trial_ended': trial_ended,
                'saw_pricing': saw_pricing,
                'paid': paid,
                'conversion': conversion
            }

        # Гарантировать наличие обоих вариантов в ответе
        for v in ('A', 'B'):
            if v not in variants:
                variants[v] = {'users': 0, 'tried': 0, 'trial_ended': 0, 'saw_pricing': 0, 'paid': 0, 'conversion': 0.0}

        return web.json_response({
            'active_variant': active_variant,
            'variants': variants
        })


async def set_ab_test_variant(request: web.Request) -> web.Response:
    """POST /api/admin/ab-test/variant — переключить активный вариант"""
    try:
        data = await request.json()
        variant = data.get('variant')
        if variant not in ('A', 'B'):
            return web.json_response(
                {'error': 'variant must be A or B'}, status=400
            )
        await set_setting('active_funnel_variant', variant)
        logger.info(f"Active funnel variant switched to {variant}")
        return web.json_response({'active_variant': variant})
    except Exception as e:
        logger.error(f"Error setting ab-test variant: {e}")
        return web.json_response({'error': str(e)}, status=500)
