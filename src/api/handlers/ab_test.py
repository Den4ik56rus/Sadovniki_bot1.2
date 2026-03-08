import logging
from aiohttp import web
from src.services.db.pool import get_pool
from src.services.db.bot_settings_repo import get_setting, set_setting
from src.services.db.client_crm_repo import get_all_tags
from src.services.db import funnel_repo

logger = logging.getLogger(__name__)


async def get_ab_test_stats(request: web.Request) -> web.Response:
    """GET /api/admin/ab-test/stats — статистика по вариантам воронки, с фильтром по тегу.

    Этапы загружаются динамически из funnel_stages (CRM-воронка).
    """
    pool = get_pool()
    tag_id = request.query.get('tag_id')
    tag_id = int(tag_id) if tag_id else None

    async with pool.acquire() as conn:
        active_variant = await get_setting('active_funnel_variant', 'A')

        # Загружаем этапы CRM-воронки динамически
        crm_stages = await funnel_repo.get_funnel_stages('crm')
        stages_info = [
            {'stage_key': s['stage_key'], 'title': s['title'], 'color': s['color']}
            for s in crm_stages
        ]
        stage_keys = [s['stage_key'] for s in crm_stages]

        # Считаем общее количество пользователей по варианту
        if tag_id:
            user_rows = await conn.fetch("""
                SELECT u.funnel_variant, COUNT(DISTINCT u.id) AS users
                FROM users u
                JOIN client_tag_links ctl ON ctl.user_id = u.id AND ctl.tag_id = $1
                WHERE u.funnel_variant IS NOT NULL
                GROUP BY u.funnel_variant
            """, tag_id)
        else:
            user_rows = await conn.fetch("""
                SELECT u.funnel_variant, COUNT(DISTINCT u.id) AS users
                FROM users u
                WHERE u.funnel_variant IS NOT NULL
                GROUP BY u.funnel_variant
            """)

        user_counts = {row['funnel_variant']: row['users'] for row in user_rows}

        # Считаем количество пользователей на каждом этапе по варианту
        if tag_id:
            stage_rows = await conn.fetch("""
                SELECT u.funnel_variant, cfp.stage_key, COUNT(DISTINCT u.id) AS cnt
                FROM users u
                JOIN client_tag_links ctl ON ctl.user_id = u.id AND ctl.tag_id = $1
                JOIN client_funnel_position cfp ON cfp.user_id = u.id AND cfp.funnel_id = 'crm'
                WHERE u.funnel_variant IS NOT NULL
                GROUP BY u.funnel_variant, cfp.stage_key
            """, tag_id)
        else:
            stage_rows = await conn.fetch("""
                SELECT u.funnel_variant, cfp.stage_key, COUNT(DISTINCT u.id) AS cnt
                FROM users u
                JOIN client_funnel_position cfp ON cfp.user_id = u.id AND cfp.funnel_id = 'crm'
                WHERE u.funnel_variant IS NOT NULL
                GROUP BY u.funnel_variant, cfp.stage_key
            """)

        # Группируем по варианту
        stage_data = {}
        for row in stage_rows:
            variant = row['funnel_variant']
            if variant not in stage_data:
                stage_data[variant] = {}
            stage_data[variant][row['stage_key']] = row['cnt']

        # Собираем результат
        variants = {}
        # Последний этап — для конверсии
        last_stage_key = stage_keys[-1] if stage_keys else None

        for v in ('A', 'B'):
            users = user_counts.get(v, 0)
            v_stages = stage_data.get(v, {})

            # Заполняем нулями все этапы
            stages_dict = {sk: v_stages.get(sk, 0) for sk in stage_keys}

            # Конверсия = % пользователей на последнем этапе
            last_count = stages_dict.get(last_stage_key, 0) if last_stage_key else 0
            conversion = round(last_count / users * 100, 1) if users > 0 else 0.0

            variants[v] = {
                'users': users,
                'stages': stages_dict,
                'conversion': conversion,
            }

        # Список доступных тегов для фильтра
        all_tags = await get_all_tags()
        available_tags = [{'id': t['id'], 'name': t['name'], 'color': t['color']} for t in all_tags]

        return web.json_response({
            'active_variant': active_variant,
            'stages': stages_info,
            'variants': variants,
            'available_tags': available_tags,
            'selected_tag_id': tag_id,
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
