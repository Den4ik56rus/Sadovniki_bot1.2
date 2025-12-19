"""
API handlers для управления промптами через админ-панель.

Endpoints:
    GET  /api/admin/prompts/groups        — список групп с подгруппами
    GET  /api/admin/prompts               — все промпты (с фильтрами)
    GET  /api/admin/prompts/{id}          — один промпт
    PUT  /api/admin/prompts/{id}          — обновить content
    PATCH /api/admin/prompts/{id}/toggle  — ВКЛ/ВЫКЛ
    GET  /api/admin/prompts/{id}/history  — история версий
    GET  /api/admin/prompts/{id}/history/{version}/diff — diff версии с актуальной
    POST /api/admin/prompts/{id}/revert   — откат к версии
"""

import difflib
import logging
from datetime import datetime
from typing import Any, Dict, List
from aiohttp import web

from src.services.db import prompt_repo

logger = logging.getLogger(__name__)


def _serialize_datetime(obj: Any) -> Any:
    """Конвертирует datetime в ISO string для JSON сериализации."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _serialize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Сериализует запись из БД для JSON ответа."""
    return {k: _serialize_datetime(v) for k, v in record.items()}


def _serialize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Сериализует список записей из БД для JSON ответа."""
    return [_serialize_record(r) for r in records]


async def get_prompt_groups(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/groups

    Возвращает все группы промптов с подгруппами и счётчиками.
    """
    try:
        groups = await prompt_repo.get_all_groups()
        return web.json_response({"groups": groups})
    except Exception as e:
        logger.error(f"Error getting prompt groups: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_prompts(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts

    Query params:
        group_id: int — фильтр по группе
        subgroup_id: int — фильтр по подгруппе
        is_enabled: bool — фильтр по включённости

    Возвращает список промптов.
    """
    try:
        # Парсим query параметры
        group_id = request.query.get("group_id")
        subgroup_id = request.query.get("subgroup_id")
        is_enabled = request.query.get("is_enabled")

        # Преобразуем типы
        group_id = int(group_id) if group_id else None
        subgroup_id = int(subgroup_id) if subgroup_id else None
        if is_enabled is not None:
            is_enabled = is_enabled.lower() in ("true", "1", "yes")

        prompts = await prompt_repo.get_all_prompts(
            group_id=group_id,
            subgroup_id=subgroup_id,
            is_enabled=is_enabled,
        )

        return web.json_response({"prompts": _serialize_records(prompts)})
    except Exception as e:
        logger.error(f"Error getting prompts: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_prompt(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/{id}

    Возвращает один промпт по ID.
    """
    try:
        prompt_id = int(request.match_info["id"])
        prompt = await prompt_repo.get_prompt_by_id(prompt_id)

        if not prompt:
            return web.json_response({"error": "Prompt not found"}, status=404)

        return web.json_response({"prompt": _serialize_record(prompt)})
    except ValueError:
        return web.json_response({"error": "Invalid prompt ID"}, status=400)
    except Exception as e:
        logger.error(f"Error getting prompt {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def update_prompt(request: web.Request) -> web.Response:
    """
    PUT /api/admin/prompts/{id}

    Body:
        content: str — новый текст промпта

    Обновляет содержимое промпта. История сохраняется автоматически.
    """
    try:
        prompt_id = int(request.match_info["id"])
        data = await request.json()

        content = data.get("content")
        if not content:
            return web.json_response({"error": "content is required"}, status=400)

        updated_by = data.get("updated_by", "admin")

        prompt = await prompt_repo.update_prompt(
            prompt_id=prompt_id,
            content=content,
            updated_by=updated_by,
        )

        if not prompt:
            return web.json_response({"error": "Prompt not found"}, status=404)

        logger.info(f"Prompt {prompt_id} updated by {updated_by}")
        return web.json_response({"prompt": _serialize_record(prompt), "success": True})
    except ValueError:
        return web.json_response({"error": "Invalid prompt ID"}, status=400)
    except Exception as e:
        logger.error(f"Error updating prompt {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def toggle_prompt_enabled(request: web.Request) -> web.Response:
    """
    PATCH /api/admin/prompts/{id}/toggle

    Body:
        enabled: bool — новое состояние

    Включает или выключает промпт.
    """
    try:
        prompt_id = int(request.match_info["id"])
        data = await request.json()

        enabled = data.get("enabled")
        if enabled is None:
            return web.json_response({"error": "enabled is required"}, status=400)

        prompt = await prompt_repo.toggle_prompt_enabled(
            prompt_id=prompt_id,
            enabled=bool(enabled),
        )

        if not prompt:
            return web.json_response({"error": "Prompt not found"}, status=404)

        logger.info(f"Prompt {prompt_id} toggled to enabled={enabled}")
        return web.json_response({"prompt": _serialize_record(prompt), "success": True})
    except ValueError:
        return web.json_response({"error": "Invalid prompt ID"}, status=400)
    except Exception as e:
        logger.error(f"Error toggling prompt {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def get_prompt_history(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/{id}/history

    Возвращает историю изменений промпта.
    """
    try:
        prompt_id = int(request.match_info["id"])
        history = await prompt_repo.get_prompt_history(prompt_id)

        return web.json_response({"history": _serialize_records(history)})
    except ValueError:
        return web.json_response({"error": "Invalid prompt ID"}, status=400)
    except Exception as e:
        logger.error(f"Error getting prompt history {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def revert_prompt_version(request: web.Request) -> web.Response:
    """
    POST /api/admin/prompts/{id}/revert

    Body:
        version: int — номер версии для отката

    Откатывает промпт к указанной версии.
    """
    try:
        prompt_id = int(request.match_info["id"])
        data = await request.json()

        version = data.get("version")
        if version is None:
            return web.json_response({"error": "version is required"}, status=400)

        reverted_by = data.get("reverted_by", "admin")

        prompt = await prompt_repo.revert_to_version(
            prompt_id=prompt_id,
            version=int(version),
            reverted_by=reverted_by,
        )

        if not prompt:
            return web.json_response({"error": "Version not found"}, status=404)

        logger.info(f"Prompt {prompt_id} reverted to version {version} by {reverted_by}")
        return web.json_response({"prompt": _serialize_record(prompt), "success": True})
    except ValueError:
        return web.json_response({"error": "Invalid prompt ID or version"}, status=400)
    except Exception as e:
        logger.error(f"Error reverting prompt {request.match_info.get('id')}: {e}")
        return web.json_response({"error": str(e)}, status=500)


def _generate_diff(old_content: str, new_content: str) -> Dict[str, Any]:
    """
    Генерирует diff между двумя версиями текста.

    Returns:
        {
            "unified": str,           # Unified diff (для отображения)
            "lines_added": int,       # Количество добавленных строк
            "lines_removed": int,     # Количество удалённых строк
            "changes": [              # Построчные изменения для визуализации
                {"type": "unchanged|added|removed", "line": str, "line_number": int}
            ]
        }
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Unified diff
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile='Выбранная версия',
        tofile='Актуальная версия',
        lineterm=''
    )
    unified = ''.join(diff)

    # Подсчёт изменений
    lines_added = 0
    lines_removed = 0
    changes = []

    # Используем SequenceMatcher для более детального анализа
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    old_line_num = 0
    new_line_num = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for i in range(i1, i2):
                old_line_num += 1
                new_line_num += 1
                changes.append({
                    "type": "unchanged",
                    "line": old_lines[i].rstrip('\n\r'),
                    "old_line_number": old_line_num,
                    "new_line_number": new_line_num,
                })
        elif tag == 'replace':
            # Сначала удалённые
            for i in range(i1, i2):
                old_line_num += 1
                lines_removed += 1
                changes.append({
                    "type": "removed",
                    "line": old_lines[i].rstrip('\n\r'),
                    "old_line_number": old_line_num,
                    "new_line_number": None,
                })
            # Потом добавленные
            for j in range(j1, j2):
                new_line_num += 1
                lines_added += 1
                changes.append({
                    "type": "added",
                    "line": new_lines[j].rstrip('\n\r'),
                    "old_line_number": None,
                    "new_line_number": new_line_num,
                })
        elif tag == 'delete':
            for i in range(i1, i2):
                old_line_num += 1
                lines_removed += 1
                changes.append({
                    "type": "removed",
                    "line": old_lines[i].rstrip('\n\r'),
                    "old_line_number": old_line_num,
                    "new_line_number": None,
                })
        elif tag == 'insert':
            for j in range(j1, j2):
                new_line_num += 1
                lines_added += 1
                changes.append({
                    "type": "added",
                    "line": new_lines[j].rstrip('\n\r'),
                    "old_line_number": None,
                    "new_line_number": new_line_num,
                })

    return {
        "unified": unified,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "changes": changes,
    }


async def get_version_diff(request: web.Request) -> web.Response:
    """
    GET /api/admin/prompts/{id}/history/{version}/diff

    Возвращает diff между указанной версией и актуальным контентом.
    """
    try:
        prompt_id = int(request.match_info["id"])
        version = int(request.match_info["version"])

        # Получаем текущий промпт
        prompt = await prompt_repo.get_prompt_by_id(prompt_id)
        if not prompt:
            return web.json_response({"error": "Prompt not found"}, status=404)

        # Получаем версию из истории
        version_data = await prompt_repo.get_prompt_version(prompt_id, version)
        if not version_data:
            return web.json_response({"error": "Version not found"}, status=404)

        # Генерируем diff
        diff = _generate_diff(
            old_content=version_data.get("content", ""),
            new_content=prompt.get("content", "")
        )

        return web.json_response({
            "diff": diff,
            "version": _serialize_record(version_data),
            "current_version": prompt.get("version"),
        })

    except ValueError:
        return web.json_response({"error": "Invalid prompt ID or version"}, status=400)
    except Exception as e:
        logger.error(f"Error getting diff for prompt {request.match_info.get('id')} version {request.match_info.get('version')}: {e}")
        return web.json_response({"error": str(e)}, status=500)
