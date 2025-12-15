# src/api/routes.py
"""
Регистрация API routes.
"""

from aiohttp import web

from src.api.handlers import events, plantings, user, admin, documents, sse, crm


def setup_routes(app: web.Application) -> None:
    """Регистрирует все API routes."""
    # Events
    app.router.add_get("/api/events", events.get_events)
    app.router.add_get("/api/events/{id}", events.get_event)
    app.router.add_post("/api/events", events.create_event)
    app.router.add_put("/api/events/{id}", events.update_event)
    app.router.add_delete("/api/events/{id}", events.delete_event)
    app.router.add_patch("/api/events/{id}/status", events.update_event_status)

    # Plantings
    app.router.add_get("/api/plantings", plantings.get_plantings)
    app.router.add_get("/api/plantings/{id}", plantings.get_planting)
    app.router.add_post("/api/plantings", plantings.create_planting)
    app.router.add_put("/api/plantings/{id}", plantings.update_planting)
    app.router.add_delete("/api/plantings/{id}", plantings.delete_planting)

    # User settings
    app.router.add_get("/api/user/region", user.get_region)
    app.router.add_put("/api/user/region", user.update_region)

    # Admin panel API (мониторинг консультаций)
    app.router.add_get("/api/admin/users", admin.get_users_list)
    app.router.add_get("/api/admin/users/{id}/topics", admin.get_user_topics)
    app.router.add_get("/api/admin/topics/{id}/logs", admin.get_topic_logs)
    app.router.add_get("/api/admin/logs/recent", admin.get_recent_logs)
    app.router.add_get("/api/admin/stats", admin.get_stats)
    app.router.add_get("/api/admin/stats/embeddings", admin.get_embedding_stats)

    # CRM API (Kanban-доска и карточки клиентов)
    app.router.add_get("/api/admin/crm/clients", crm.get_crm_clients)
    app.router.add_get("/api/admin/crm/clients/{id}", crm.get_crm_client)
    app.router.add_get("/api/admin/crm/clients/{id}/full", crm.get_client_full)
    app.router.add_patch("/api/admin/crm/clients/{id}/status", crm.update_crm_client_status)
    app.router.add_patch("/api/admin/crm/clients/{id}/priority", crm.update_client_priority)
    app.router.add_patch("/api/admin/crm/clients/{id}/source", crm.update_client_source)
    app.router.add_get("/api/admin/crm/clients/{id}/topics", crm.get_crm_client_topics)
    app.router.add_get("/api/admin/crm/stats", crm.get_funnel_stats)

    # CRM: Кастомные поля
    app.router.add_get("/api/admin/crm/custom-fields", crm.get_custom_fields)
    app.router.add_post("/api/admin/crm/custom-fields", crm.create_custom_field)
    app.router.add_put("/api/admin/crm/custom-fields/{id}", crm.update_custom_field)
    app.router.add_delete("/api/admin/crm/custom-fields/{id}", crm.delete_custom_field)
    app.router.add_get("/api/admin/crm/clients/{id}/fields", crm.get_client_field_values)
    app.router.add_put("/api/admin/crm/clients/{id}/fields", crm.update_client_field_values)

    # CRM: Теги
    app.router.add_get("/api/admin/crm/tags", crm.get_tags)
    app.router.add_post("/api/admin/crm/tags", crm.create_tag)
    app.router.add_put("/api/admin/crm/tags/{id}", crm.update_tag)
    app.router.add_delete("/api/admin/crm/tags/{id}", crm.delete_tag)
    app.router.add_get("/api/admin/crm/clients/{id}/tags", crm.get_client_tags)
    app.router.add_put("/api/admin/crm/clients/{id}/tags", crm.update_client_tags)

    # CRM: Задачи
    app.router.add_get("/api/admin/crm/clients/{id}/tasks", crm.get_client_tasks)
    app.router.add_post("/api/admin/crm/clients/{id}/tasks", crm.create_task)
    app.router.add_get("/api/admin/crm/tasks/{id}", crm.get_task)
    app.router.add_put("/api/admin/crm/tasks/{id}", crm.update_task)
    app.router.add_delete("/api/admin/crm/tasks/{id}", crm.delete_task)
    app.router.add_post("/api/admin/crm/tasks/{id}/complete", crm.complete_task)

    # CRM: Заметки
    app.router.add_get("/api/admin/crm/clients/{id}/notes", crm.get_client_notes)
    app.router.add_post("/api/admin/crm/clients/{id}/notes", crm.create_note)
    app.router.add_delete("/api/admin/crm/notes/{id}", crm.delete_note)

    # CRM: Лента активности
    app.router.add_get("/api/admin/crm/clients/{id}/activity", crm.get_client_activity)

    # SSE endpoints (Server-Sent Events для real-time обновлений)
    app.router.add_get("/api/admin/events/live-feed", sse.live_feed_stream)
    app.router.add_get(r"/api/admin/events/logs/{topic_id:\d+}", sse.topic_logs_stream)
    app.router.add_get(r"/api/admin/events/documents/{document_id:\d+}", sse.document_status_stream)
    app.router.add_get("/api/admin/events/stats", sse.sse_stats)

    # Documents API (загрузка документов в базу знаний)
    app.router.add_post("/api/admin/documents/upload", documents.upload_document)
    app.router.add_get("/api/admin/documents", documents.get_documents_list)
    app.router.add_get("/api/admin/documents/{id}/status", documents.get_document_status)
    app.router.add_delete("/api/admin/documents/{id}", documents.delete_document)

    # Health check endpoint
    app.router.add_get("/api/health", health_check)


async def health_check(_request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})
