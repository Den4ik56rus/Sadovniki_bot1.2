# src/api/routes.py
"""
Регистрация API routes.
"""

from aiohttp import web

from src.api.handlers import events, plantings, user, admin, documents, sse, crm, buyers, funnels, articles, expenses, prompt_documents, rag_documents, prompts, prompt_preview, webhooks, payments, settings, invite_links, guides, server_metrics, openai_balance, moderation, broadcasts, automation, presentations, batch_presentations, batch_articles, batch_article_presentations, image_generator


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
    app.router.add_patch("/api/admin/crm/clients/{id}/billing", crm.update_client_billing)
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

    # CRM: Funnel & Quiz
    app.router.add_patch("/api/admin/crm/clients/{id}/funnel-variant", crm.update_client_funnel_variant)
    app.router.add_put("/api/admin/crm/clients/{id}/quiz-answers", crm.update_client_quiz_answers)
    app.router.add_delete("/api/admin/crm/clients/{id}/quiz-answers", crm.reset_client_quiz)
    app.router.add_delete("/api/admin/crm/clients/{id}", crm.delete_client)

    # CRM: Рефералы
    app.router.add_get("/api/admin/crm/clients/{id}/referrals", crm.get_client_referrals)

    # CRM: Лента активности
    app.router.add_get("/api/admin/crm/clients/{id}/activity", crm.get_client_activity)
    app.router.add_get("/api/admin/crm/clients/{id}/chat", crm.get_client_chat_history)
    app.router.add_post("/api/admin/crm/clients/{id}/send-message", crm.send_message_to_client)
    app.router.add_post("/api/admin/crm/clients/{id}/send-payment-link", crm.send_payment_link_to_client)
    app.router.add_get("/api/admin/crm/products", crm.get_available_products)

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

    # Funnels: Триггеры этапов (автоматическая отправка рассылок)
    app.router.add_get("/api/admin/funnels/{id}/triggers", funnels.get_funnel_triggers)
    app.router.add_get("/api/admin/funnels/{id}/stages/{key}/triggers", funnels.get_stage_triggers)
    app.router.add_post("/api/admin/funnels/{id}/stages/{key}/triggers", funnels.create_stage_trigger)
    app.router.add_delete(r"/api/admin/funnels/triggers/{id:\d+}", funnels.delete_stage_trigger)
    app.router.add_patch(r"/api/admin/funnels/triggers/{id:\d+}", funnels.toggle_stage_trigger)

    # Admin Articles API (статьи, сгенерированные админом)
    app.router.add_post("/api/admin/articles/generate", articles.generate_article_api)
    app.router.add_get("/api/admin/articles/definitions", batch_articles.get_definitions)
    app.router.add_get("/api/admin/articles/by-culture", articles.get_articles_by_culture)
    app.router.add_get("/api/admin/articles/by-keys", articles.get_article_by_keys)
    # Article Batches API (пакетная генерация статей)
    app.router.add_post("/api/admin/articles/batches", batch_articles.create_batch_api)
    app.router.add_get("/api/admin/articles/batches", batch_articles.get_batches)
    app.router.add_get(r"/api/admin/articles/batches/{id:\d+}", batch_articles.get_batch)
    app.router.add_post(r"/api/admin/articles/batches/{id:\d+}/cancel", batch_articles.cancel_batch_api)
    app.router.add_delete(r"/api/admin/articles/batches/{id:\d+}", batch_articles.delete_batch_api)
    app.router.add_get("/api/admin/articles", articles.get_articles)
    app.router.add_get("/api/admin/articles/by-admin/{telegram_id}", articles.get_articles_by_admin)
    app.router.add_get(r"/api/admin/articles/{id:\d+}", articles.get_article)
    app.router.add_put(r"/api/admin/articles/{id:\d+}", articles.update_article_api)

    # Presentations API (AI-генерация слайдов)
    app.router.add_post("/api/admin/presentations", presentations.create_presentation_api)
    app.router.add_get("/api/admin/presentations", presentations.get_presentations)
    app.router.add_get("/api/admin/presentations/styles", presentations.get_styles)
    app.router.add_post("/api/admin/presentations/styles", presentations.create_style_api)
    app.router.add_put(r"/api/admin/presentations/styles/{id:\d+}", presentations.update_style_api)
    app.router.add_delete(r"/api/admin/presentations/styles/{id:\d+}", presentations.delete_style_api)
    app.router.add_get("/api/admin/presentations/problems", presentations.get_problem_definitions)
    app.router.add_get("/api/admin/presentations/default-system-prompt", presentations.get_default_system_prompt)
    app.router.add_get("/api/admin/presentations/templates", presentations.get_templates)
    app.router.add_post("/api/admin/presentations/templates", presentations.create_template_api)
    app.router.add_put(r"/api/admin/presentations/templates/{id:\d+}", presentations.update_template_api)
    app.router.add_delete(r"/api/admin/presentations/templates/{id:\d+}", presentations.delete_template_api)
    app.router.add_get(r"/api/admin/presentations/slides/versions/{id:\d+}/image", presentations.get_slide_image)
    app.router.add_post(r"/api/admin/presentations/slides/{id:\d+}/edit", presentations.edit_slide_api)
    # Presentation Batches API (пакетная генерация по проблемам)
    app.router.add_post("/api/admin/presentations/batches", batch_presentations.create_batch_api)
    app.router.add_get("/api/admin/presentations/batches", batch_presentations.get_batches)
    app.router.add_get(r"/api/admin/presentations/batches/{id:\d+}", batch_presentations.get_batch)
    app.router.add_post(r"/api/admin/presentations/batches/{id:\d+}/cancel", batch_presentations.cancel_batch_api)
    app.router.add_delete(r"/api/admin/presentations/batches/{id:\d+}", batch_presentations.delete_batch_api)
    # Presentation Article Batches API (пакетная генерация по статьям)
    app.router.add_get("/api/admin/presentations/article-batches/definitions", batch_article_presentations.get_definitions)
    app.router.add_post("/api/admin/presentations/article-batches", batch_article_presentations.create_batch_api)
    app.router.add_get("/api/admin/presentations/article-batches", batch_article_presentations.get_batches_api)
    app.router.add_get(r"/api/admin/presentations/article-batches/{id:\d+}", batch_article_presentations.get_batch_api)
    app.router.add_post(r"/api/admin/presentations/article-batches/{id:\d+}/cancel", batch_article_presentations.cancel_batch_api)
    app.router.add_post(r"/api/admin/presentations/article-batches/{id:\d+}/run", batch_article_presentations.run_batch_api)
    app.router.add_delete(r"/api/admin/presentations/article-batches/{id:\d+}", batch_article_presentations.delete_batch_api)
    app.router.add_get(r"/api/admin/presentations/{id:\d+}", presentations.get_presentation)
    app.router.add_delete(r"/api/admin/presentations/{id:\d+}", presentations.delete_presentation_api)
    app.router.add_post(r"/api/admin/presentations/{id:\d+}/generate", presentations.generate_presentation_api)
    app.router.add_get(r"/api/admin/presentations/{id:\d+}/pdf", presentations.download_pdf)
    app.router.add_post(r"/api/admin/presentations/{id:\d+}/pdf/rebuild", presentations.rebuild_pdf_api)
    app.router.add_get("/api/admin/presentations/image-models", presentations.get_image_models)

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

    # Moderation API (модерация вопросов/ответов + управление базой знаний)
    app.router.add_get("/api/admin/moderation/queue", moderation.get_queue)
    app.router.add_get("/api/admin/moderation/stats", moderation.get_moderation_stats)
    app.router.add_get("/api/admin/moderation/kb", moderation.get_kb_entries)
    app.router.add_get("/api/admin/moderation/kb/categories", moderation.get_kb_categories)
    app.router.add_get("/api/admin/moderation/kb/subcategories", moderation.get_kb_subcategories)
    app.router.add_get(r"/api/admin/moderation/queue/{id:\d+}", moderation.get_queue_item)
    app.router.add_patch(r"/api/admin/moderation/queue/{id:\d+}/category", moderation.set_category)
    app.router.add_patch(r"/api/admin/moderation/queue/{id:\d+}/answer", moderation.update_answer)
    app.router.add_post(r"/api/admin/moderation/queue/{id:\d+}/edit-ai", moderation.edit_answer_ai)
    app.router.add_post(r"/api/admin/moderation/queue/{id:\d+}/approve", moderation.approve_item)
    app.router.add_post(r"/api/admin/moderation/queue/{id:\d+}/reject", moderation.reject_item)
    app.router.add_get(r"/api/admin/moderation/kb/{id:\d+}", moderation.get_kb_entry)
    app.router.add_patch(r"/api/admin/moderation/kb/{id:\d+}", moderation.update_kb_entry)

    # Invite Links API (инвайт-ссылки для отслеживания кампаний)
    app.router.add_get("/api/admin/invite-links", invite_links.get_invite_links)
    app.router.add_post("/api/admin/invite-links", invite_links.create_invite_link)
    app.router.add_patch(r"/api/admin/invite-links/{id:\d+}", invite_links.update_invite_link)
    app.router.add_patch(r"/api/admin/invite-links/{id:\d+}/toggle", invite_links.toggle_invite_link)
    app.router.add_delete(r"/api/admin/invite-links/{id:\d+}", invite_links.delete_invite_link)

    # Broadcasts API (рассылки из админ-панели)
    app.router.add_get("/api/admin/broadcasts", broadcasts.get_broadcasts)
    app.router.add_post("/api/admin/broadcasts", broadcasts.create_broadcast)
    app.router.add_post("/api/admin/broadcasts/preview-count", broadcasts.preview_recipient_count)
    app.router.add_get("/api/admin/broadcasts/users", broadcasts.get_broadcast_users)
    app.router.add_post("/api/admin/broadcasts/bulk-delete", broadcasts.delete_broadcasts_bulk)
    app.router.add_post("/api/admin/broadcasts/upload-photo", broadcasts.upload_broadcast_photo)
    app.router.add_get(r"/api/admin/broadcasts/photo/{filename}", broadcasts.get_broadcast_photo)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}", broadcasts.get_broadcast)
    app.router.add_put(r"/api/admin/broadcasts/{id:\d+}", broadcasts.update_broadcast)
    app.router.add_delete(r"/api/admin/broadcasts/{id:\d+}", broadcasts.delete_broadcast)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/send", broadcasts.send_broadcast)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/test-send", broadcasts.test_send_broadcast)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/schedule", broadcasts.schedule_broadcast)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/cancel", broadcasts.cancel_broadcast)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/recipients", broadcasts.get_broadcast_recipients)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/stats", broadcasts.get_broadcast_stats)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/stats/users", broadcasts.get_broadcast_stat_users)

    # Broadcasts: Повторные запуски (runs)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/resend", broadcasts.resend_broadcast)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/runs", broadcasts.get_broadcast_runs)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/runs/{run_id:\d+}/stats", broadcasts.get_run_stats)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/runs/{run_id:\d+}/stats/users", broadcasts.get_run_stat_users)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/runs/{run_id:\d+}/recipients", broadcasts.get_run_recipients)

    # Broadcasts: Напоминалки (reminders)
    app.router.add_get(r"/api/admin/broadcasts/{id:\d+}/reminders", broadcasts.get_broadcast_reminders)
    app.router.add_post(r"/api/admin/broadcasts/{id:\d+}/reminders/{rid:\d+}/cancel", broadcasts.cancel_reminder)

    # SSE: Broadcast progress
    app.router.add_get(r"/api/admin/events/broadcast/{broadcast_id:\d+}", sse.broadcast_stream)

    # SSE: Presentation generation progress
    app.router.add_get(r"/api/admin/events/presentation/{presentation_id:\d+}", sse.presentation_stream)

    # SSE: Batch generation progress
    app.router.add_get(r"/api/admin/events/batch/{batch_id:\d+}", sse.batch_stream)

    # SSE: Article batch generation progress
    app.router.add_get(r"/api/admin/events/article-batch/{batch_id:\d+}", sse.article_batch_stream)

    # Automation Triggers API (универсальные триггеры автоматизации)
    app.router.add_get("/api/admin/triggers", automation.get_triggers)
    app.router.add_post("/api/admin/triggers", automation.create_trigger)
    app.router.add_post("/api/admin/triggers/preview-users", automation.preview_users)
    app.router.add_get(r"/api/admin/triggers/{id:\d+}", automation.get_trigger)
    app.router.add_put(r"/api/admin/triggers/{id:\d+}", automation.update_trigger)
    app.router.add_delete(r"/api/admin/triggers/{id:\d+}", automation.delete_trigger)
    app.router.add_patch(r"/api/admin/triggers/{id:\d+}/toggle", automation.toggle_trigger)
    app.router.add_get(r"/api/admin/triggers/{id:\d+}/log", automation.get_trigger_log)

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

    # OpenAI Balance API (мониторинг расходов OpenAI)
    app.router.add_get("/api/admin/openai-balance", openai_balance.get_openai_balance)
    app.router.add_patch("/api/admin/openai-balance/budget", openai_balance.update_openai_budget)

    # Broadcast URL redirect (публичный, для трекинга кликов по ссылкам)
    app.router.add_get(r"/api/r/{broadcast_id:\d+}/{option_key}", broadcasts.redirect_broadcast_url)

    # A/B тестирование воронок
    from src.api.handlers.ab_test import get_ab_test_stats, set_ab_test_variant
    app.router.add_get('/api/admin/ab-test/stats', get_ab_test_stats)
    app.router.add_post('/api/admin/ab-test/variant', set_ab_test_variant)

    # Image Generator API
    app.router.add_post("/api/admin/image-generator/generate", image_generator.generate_image_api)
    app.router.add_post("/api/admin/image-generator/generate-direct", image_generator.generate_direct_api)
    app.router.add_post("/api/admin/image-generator/upload-reference", image_generator.upload_reference_api)
    app.router.add_get("/api/admin/image-generator/history", image_generator.get_history)
    app.router.add_get(r"/api/admin/image-generator/image/{filename}", image_generator.get_image_file)
    app.router.add_delete(r"/api/admin/image-generator/{id:\d+}", image_generator.delete_generation_api)
    app.router.add_get("/api/admin/image-generator/presets", image_generator.get_presets)
    app.router.add_get(r"/api/admin/events/image-generator/{gen_id:\d+}", sse.image_generator_stream)

    # Health check endpoint
    app.router.add_get("/api/health", health_check)


async def health_check(_request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})
