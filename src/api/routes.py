# src/api/routes.py
"""
Регистрация API routes.
"""

from aiohttp import web

from src.api.handlers import events, plantings, user, admin, documents, sse, crm, buyers, funnels, articles, expenses, prompt_documents, rag_documents, prompts, prompt_preview, webhooks, payments, settings, invite_links, guides, server_metrics


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

    # CRM: Рефералы
    app.router.add_get("/api/admin/crm/clients/{id}/referrals", crm.get_client_referrals)

    # CRM: Лента активности
    app.router.add_get("/api/admin/crm/clients/{id}/activity", crm.get_client_activity)
    app.router.add_get("/api/admin/crm/clients/{id}/chat", crm.get_client_chat_history)
    app.router.add_post("/api/admin/crm/clients/{id}/send-message", crm.send_message_to_client)

    # CRM: Колонки воронки (Kanban)
    app.router.add_get("/api/admin/crm/columns", crm.get_funnel_columns)
    app.router.add_post("/api/admin/crm/columns", crm.create_funnel_column)
    app.router.add_put("/api/admin/crm/columns/reorder", crm.reorder_funnel_columns)
    app.router.add_put("/api/admin/crm/columns/{id}", crm.update_funnel_column)
    app.router.add_delete("/api/admin/crm/columns/{id}", crm.delete_funnel_column)

    # Buyers API (Покупатели - Kanban-доска)
    app.router.add_get("/api/admin/buyers", buyers.get_buyers)
    app.router.add_get("/api/admin/buyers/stats", buyers.get_buyer_stats)
    app.router.add_get("/api/admin/buyers/columns", buyers.get_buyer_columns)
    app.router.add_post("/api/admin/buyers/columns", buyers.create_buyer_column)
    app.router.add_put("/api/admin/buyers/columns/reorder", buyers.reorder_buyer_columns)
    app.router.add_put("/api/admin/buyers/columns/{id}", buyers.update_buyer_column)
    app.router.add_delete("/api/admin/buyers/columns/{id}", buyers.delete_buyer_column)
    app.router.add_get("/api/admin/buyers/{id}", buyers.get_buyer)
    app.router.add_get("/api/admin/buyers/{id}/full", buyers.get_buyer_full)
    app.router.add_patch("/api/admin/buyers/{id}/status", buyers.update_buyer_status)
    app.router.add_get("/api/admin/buyers/{id}/topics", buyers.get_buyer_topics)
    app.router.add_get("/api/admin/buyers/{id}/activity", buyers.get_buyer_activity)

    # SSE endpoints (Server-Sent Events для real-time обновлений)
    app.router.add_get("/api/admin/events/live-feed", sse.live_feed_stream)
    app.router.add_get(r"/api/admin/events/logs/{topic_id:\d+}", sse.topic_logs_stream)
    app.router.add_get(r"/api/admin/events/documents/{document_id:\d+}", sse.document_status_stream)
    app.router.add_get("/api/admin/events/funnel/{funnel_id}", sse.funnel_stream)
    app.router.add_get(r"/api/admin/events/client/{user_id:\d+}", sse.client_stream)
    app.router.add_get("/api/admin/events/stats", sse.sse_stats)

    # Documents API (загрузка документов в базу знаний)
    app.router.add_post("/api/admin/documents/upload", documents.upload_document)
    app.router.add_get("/api/admin/documents", documents.get_documents_list)
    app.router.add_get("/api/admin/documents/{id}/status", documents.get_document_status)
    app.router.add_delete("/api/admin/documents/{id}", documents.delete_document)

    # Unified Funnels API (новая универсальная система воронок)
    app.router.add_get("/api/admin/funnels", funnels.get_funnels)
    app.router.add_post("/api/admin/funnels", funnels.create_funnel)
    app.router.add_put("/api/admin/funnels/reorder", funnels.reorder_funnels)
    app.router.add_get("/api/admin/funnels/{id}", funnels.get_funnel)
    app.router.add_put("/api/admin/funnels/{id}", funnels.update_funnel)
    app.router.add_delete("/api/admin/funnels/{id}", funnels.delete_funnel)

    # Funnels: Этапы (stages)
    app.router.add_get("/api/admin/funnels/{id}/stages", funnels.get_funnel_stages)
    app.router.add_post("/api/admin/funnels/{id}/stages", funnels.create_funnel_stage)
    app.router.add_put("/api/admin/funnels/{id}/stages/reorder", funnels.reorder_funnel_stages)
    app.router.add_put("/api/admin/funnels/{id}/stages/{key}", funnels.update_funnel_stage)
    app.router.add_delete("/api/admin/funnels/{id}/stages/{key}", funnels.delete_funnel_stage)

    # Funnels: Клиенты
    app.router.add_get("/api/admin/funnels/{id}/clients", funnels.get_funnel_clients)
    app.router.add_get("/api/admin/funnels/{id}/stats", funnels.get_funnel_stats)
    app.router.add_patch("/api/admin/funnels/{id}/clients/{uid}/stage", funnels.move_client_stage)
    app.router.add_post("/api/admin/funnels/{id}/clients/{uid}/transfer", funnels.transfer_client)
    app.router.add_post("/api/admin/funnels/{id}/clients/{uid}", funnels.add_client_to_funnel)
    app.router.add_delete("/api/admin/funnels/{id}/clients/{uid}", funnels.remove_client_from_funnel)

    # Funnels: Воронки клиента
    app.router.add_get("/api/admin/clients/{uid}/funnels", funnels.get_client_funnels)

    # Admin Articles API (статьи, сгенерированные админом)
    app.router.add_get("/api/admin/articles", articles.get_articles)
    app.router.add_get("/api/admin/articles/by-admin/{telegram_id}", articles.get_articles_by_admin)
    app.router.add_get(r"/api/admin/articles/{id:\d+}", articles.get_article)

    # Expenses API (учёт расходов проекта)
    app.router.add_get("/api/admin/expenses", expenses.get_expenses)
    app.router.add_post("/api/admin/expenses", expenses.create_expense)
    app.router.add_get("/api/admin/expenses/stats", expenses.get_expense_stats)
    app.router.add_get("/api/admin/expenses/categories", expenses.get_expense_categories)
    app.router.add_post("/api/admin/expenses/categories", expenses.create_expense_category)
    app.router.add_put(r"/api/admin/expenses/categories/{id:\d+}", expenses.update_expense_category)
    app.router.add_delete(r"/api/admin/expenses/categories/{id:\d+}", expenses.delete_expense_category)
    app.router.add_get(r"/api/admin/expenses/{id:\d+}", expenses.get_expense)
    app.router.add_put(r"/api/admin/expenses/{id:\d+}", expenses.update_expense)
    app.router.add_delete(r"/api/admin/expenses/{id:\d+}", expenses.delete_expense)

    # Payments API (платежи и подписки)
    app.router.add_get("/api/admin/payments", payments.get_all_payments)
    app.router.add_get(r"/api/admin/payments/user/{id:\d+}", payments.get_user_payments)
    app.router.add_get("/api/admin/payments/stats", payments.get_payment_stats)

    # Prompt Documents API (документы для промптов)
    app.router.add_get("/api/admin/prompt-documents/cultures", prompt_documents.get_cultures)
    app.router.add_get("/api/admin/prompt-documents/subcultures", prompt_documents.get_subcultures)
    app.router.add_get("/api/admin/prompt-documents/work-types", prompt_documents.get_work_types)
    app.router.add_get("/api/admin/prompt-documents", prompt_documents.get_documents)
    app.router.add_post("/api/admin/prompt-documents/upload", prompt_documents.upload_document)
    app.router.add_get(r"/api/admin/prompt-documents/{id:\d+}", prompt_documents.get_document)
    app.router.add_get(r"/api/admin/prompt-documents/{id:\d+}/content", prompt_documents.get_document_content)
    app.router.add_delete(r"/api/admin/prompt-documents/{id:\d+}", prompt_documents.delete_document)
    app.router.add_put(r"/api/admin/prompt-documents/{id:\d+}/replace", prompt_documents.replace_document)

    # RAG Documents API v2.0 (паспортизация чанков)
    app.router.add_get("/api/admin/rag-documents", rag_documents.get_rag_documents)
    app.router.add_get("/api/admin/rag-documents/passport-options", rag_documents.get_passport_options_handler)
    app.router.add_delete("/api/admin/rag-documents/clear-all", rag_documents.clear_all_rag_documents)
    app.router.add_get(r"/api/admin/rag-documents/{id:\d+}", rag_documents.get_rag_document)
    app.router.add_get(r"/api/admin/rag-documents/{id:\d+}/chunks", rag_documents.get_document_chunks)
    app.router.add_patch(r"/api/admin/rag-documents/{id:\d+}/subcategory", rag_documents.update_document_subcategory)
    app.router.add_delete(r"/api/admin/rag-documents/{id:\d+}", rag_documents.delete_rag_document)
    app.router.add_patch(r"/api/admin/rag-documents/chunks/{id:\d+}/passport", rag_documents.update_chunk_passport_handler)
    app.router.add_post(r"/api/admin/rag-documents/chunks/{id:\d+}/generate-context", rag_documents.generate_chunk_context_handler)
    app.router.add_post(r"/api/admin/rag-documents/{id:\d+}/embed", rag_documents.embed_document_handler)

    # Prompt Preview API (превью собранного промпта)
    app.router.add_get("/api/admin/prompts/preview/options", prompt_preview.get_preview_options)
    app.router.add_get("/api/admin/prompts/preview", prompt_preview.get_prompt_preview)

    # Prompts API (редактор промптов)
    app.router.add_get("/api/admin/prompts/groups", prompts.get_prompt_groups)
    app.router.add_get("/api/admin/prompts", prompts.get_prompts)
    app.router.add_get(r"/api/admin/prompts/{id:\d+}", prompts.get_prompt)
    app.router.add_put(r"/api/admin/prompts/{id:\d+}", prompts.update_prompt)
    app.router.add_patch(r"/api/admin/prompts/{id:\d+}/toggle", prompts.toggle_prompt_enabled)
    app.router.add_get(r"/api/admin/prompts/{id:\d+}/history", prompts.get_prompt_history)
    app.router.add_get(r"/api/admin/prompts/{id:\d+}/history/{version:\d+}/diff", prompts.get_version_diff)
    app.router.add_post(r"/api/admin/prompts/{id:\d+}/revert", prompts.revert_prompt_version)

    # Admin Settings API (глобальные настройки)
    app.router.add_get("/api/admin/settings/llm", settings.get_llm_config)
    app.router.add_get("/api/admin/settings", settings.get_settings)
    app.router.add_patch("/api/admin/settings/{key}", settings.update_setting)

    # Pricing API (управление тарифами)
    app.router.add_get("/api/admin/settings/pricing/plans", settings.get_subscription_plans)
    app.router.add_post("/api/admin/settings/pricing/plans", settings.create_subscription_plan)
    app.router.add_put(r"/api/admin/settings/pricing/plans/{id:\d+}", settings.update_subscription_plan)
    app.router.add_get("/api/admin/settings/pricing/packages", settings.get_token_packages)
    app.router.add_post("/api/admin/settings/pricing/packages", settings.create_token_package)
    app.router.add_put(r"/api/admin/settings/pricing/packages/{id:\d+}", settings.update_token_package)

    # Guides API (Готовые решения — PDF-гайды)
    app.router.add_get("/api/admin/guides", guides.get_guides)
    app.router.add_get("/api/admin/guides/stats", guides.get_guide_stats)
    app.router.add_get(r"/api/admin/guides/{id:\d+}", guides.get_guide_detail)

    # Invite Links API (инвайт-ссылки для отслеживания кампаний)
    app.router.add_get("/api/admin/invite-links", invite_links.get_invite_links)
    app.router.add_post("/api/admin/invite-links", invite_links.create_invite_link)
    app.router.add_patch(r"/api/admin/invite-links/{id:\d+}", invite_links.update_invite_link)
    app.router.add_delete(r"/api/admin/invite-links/{id:\d+}", invite_links.delete_invite_link)

    # Webhooks (платежные системы)
    app.router.add_post("/api/webhooks/yookassa", webhooks.yookassa_webhook)
    app.router.add_post("/api/webhooks/yookassa/test", webhooks.yookassa_webhook_test)

    # Статические файлы: аватары пользователей
    import os
    avatars_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    app.router.add_static('/api/admin/avatars', avatars_dir, show_index=False)

    # Server Metrics API (мониторинг сервера)
    app.router.add_get("/api/admin/server-metrics", server_metrics.get_server_metrics)
    app.router.add_get("/api/admin/server-metrics/history", server_metrics.get_server_metrics_history)

    # Health check endpoint
    app.router.add_get("/api/health", health_check)


async def health_check(_request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})
