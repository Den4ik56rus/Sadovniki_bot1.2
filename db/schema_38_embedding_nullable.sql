-- =============================================================================
-- Schema 38: RAG v2.5 — Сделать embedding nullable для двухэтапной обработки
-- Поддерживает двухэтапную обработку: chunking → embedding
-- =============================================================================

-- Делаем embedding nullable (для двухэтапной обработки)
ALTER TABLE document_chunks
ALTER COLUMN embedding DROP NOT NULL;

-- Комментарий для документирования
COMMENT ON COLUMN document_chunks.embedding IS
'Векторное представление чанка для RAG-поиска.
NULL для чанков в процессе обработки (статус документа: chunked).
Заполняется на этапе embedding (статус документа: completed).
Двухэтапная обработка: chunking (embedding=NULL) → embedding (embedding!=NULL).';
