# src/services/documents/semantic_chunker.py

"""
Semantic Chunker v3 — двухфазный structure-first подход.

Фаза 1 (структурная, бесплатно):
  Текст → разбить по \\n\\n → параграфы (structural blocks)
  → определить заголовки → определить списки
  → каждый блок помечен: paragraph | heading | list

Фаза 2 (семантическая, Gemini API):
  Эмбеддинги для параграфов (10-50 вызовов вместо 200-500)
  → cosine similarity между соседними блоками
  → жадное слияние: заголовок = новый чанк, similarity >= порог = сливаем

Преимущества перед v1:
- Сохраняет структуру документа (абзацы, заголовки, списки)
- Абсолютный порог similarity (не percentile) — предсказуемый результат
- 5x дешевле (эмбеддинги параграфов, а не предложений)
- Overlap между чанками для контекста при поиске
"""

import re
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Literal

from src.services.llm.gemini_embeddings import get_embeddings_for_similarity_with_usage
from src.services.documents.boundary_detector import (
    detect_list_boundaries,
    detect_headings,
)


# ============================================================
# Structural Block — единица Фазы 1
# ============================================================

@dataclass
class StructuralBlock:
    """Структурный блок текста (параграф, заголовок или список)."""
    text: str
    block_type: Literal["paragraph", "heading", "list"]
    start_pos: int
    end_pos: int
    heading_level: Optional[int] = None

    @property
    def size(self) -> int:
        return len(self.text)


# ============================================================
# SemanticChunkerV2 — двухфазный подход
# ============================================================

class SemanticChunkerV2:
    """
    Двухфазный семантический чанкер.

    Фаза 1: Структурная декомпозиция (бесплатно)
    Фаза 2: Семантическое слияние (Gemini embeddings)
    """

    def __init__(
        self,
        merge_threshold: float = 0.5,
        min_chunk_size: int = 300,
        max_chunk_size: int = 2000,
        overlap_sentences: int = 2,
        embedding_batch_size: int = 50,
        embedding_truncate_chars: int = 500,
    ):
        """
        Параметры:
            merge_threshold: Абсолютный порог cosine similarity для слияния блоков.
                >= порога → сливаем, < порога → новый чанк.
                0.3-0.4: агрессивное слияние, крупные чанки
                0.5-0.6: баланс (рекомендуется)
                0.7-0.8: больше разбиений, мелкие чанки
            min_chunk_size: Минимальный размер чанка в символах.
            max_chunk_size: Максимальный размер чанка в символах.
            overlap_sentences: Количество предложений overlap между чанками.
            embedding_batch_size: Размер батча для Gemini API.
            embedding_truncate_chars: Обрезка текста блока для эмбеддинга (экономия токенов).
        """
        self.merge_threshold = merge_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences
        self.embedding_batch_size = embedding_batch_size
        self.embedding_truncate_chars = embedding_truncate_chars

    async def chunk(
        self,
        text: str,
        list_boundaries: Optional[List[Dict]] = None,
        headings: Optional[List[Dict]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Разбивает текст на семантические чанки.

        Параметры:
            text: Текст для разбиения
            list_boundaries: Границы списков (из docx_parser или boundary_detector)
            headings: Заголовки (из docx_parser или boundary_detector)

        Возвращает:
            Tuple[chunks, stats]:
            - chunks: Список чанков (chunk_index, chunk_text, chunk_size, start_pos, end_pos, sentences_count)
            - stats: Статистика (sentences_count, chunking_tokens, chunking_cost_usd, blocks_count)
        """
        empty_stats = {
            "sentences_count": 0,
            "chunking_tokens": 0,
            "chunking_cost_usd": 0.0,
            "blocks_count": 0,
        }

        if not text or len(text.strip()) < self.min_chunk_size:
            chunks = [{
                "chunk_index": 0,
                "chunk_text": text.strip(),
                "chunk_size": len(text.strip()),
                "start_pos": 0,
                "end_pos": len(text),
                "sentences_count": 1,
            }] if text.strip() else []
            return chunks, {**empty_stats, "sentences_count": 1 if text.strip() else 0}

        # Фаза 1: Структурная декомпозиция
        if list_boundaries is None:
            list_boundaries = detect_list_boundaries(text)
        if headings is None:
            headings = detect_headings(text)

        blocks = self._split_into_structural_blocks(text, headings, list_boundaries)
        print(f"[SemanticChunkerV2] Фаза 1: {len(blocks)} структурных блоков")

        if not blocks:
            return [], empty_stats

        # Разбить большие блоки по предложениям (до Фазы 2)
        blocks = self._split_oversized_blocks(blocks)
        print(f"[SemanticChunkerV2] После разбиения крупных: {len(blocks)} блоков")

        # Если всего 1 блок — вернуть как есть
        if len(blocks) == 1:
            chunk_text = blocks[0].text.strip()
            sentences_count = self._count_sentences(chunk_text)
            chunks = [{
                "chunk_index": 0,
                "chunk_text": chunk_text,
                "chunk_size": len(chunk_text),
                "start_pos": blocks[0].start_pos,
                "end_pos": blocks[0].end_pos,
                "sentences_count": sentences_count,
            }]
            return chunks, {**empty_stats, "sentences_count": sentences_count, "blocks_count": 1}

        # Фаза 2: Семантическое слияние
        embeddings, chunking_tokens, chunking_cost = await self._get_block_embeddings(blocks)
        print(f"[SemanticChunkerV2] Фаза 2: эмбеддинги для {len(blocks)} блоков, {chunking_tokens} токенов, ${chunking_cost:.6f}")

        # Вычисляем similarity и строим план слияния
        groups = self._compute_merge_plan(blocks, embeddings)
        print(f"[SemanticChunkerV2] План слияния: {len(groups)} групп из {len(blocks)} блоков")

        # Собираем чанки
        chunks = self._assemble_chunks(blocks, groups)

        # Пост-обработка: сливаем мелкие чанки
        chunks = self._merge_tiny_chunks(chunks)

        # Пост-обработка: overlap
        if self.overlap_sentences > 0:
            chunks = self._add_overlap(chunks)

        # Пересчитываем индексы
        for idx, chunk in enumerate(chunks):
            chunk["chunk_index"] = idx

        total_sentences = sum(c["sentences_count"] for c in chunks)
        stats = {
            "sentences_count": total_sentences,
            "chunking_tokens": chunking_tokens,
            "chunking_cost_usd": chunking_cost,
            "blocks_count": len(blocks),
        }

        print(f"[SemanticChunkerV2] Итого: {len(chunks)} чанков, средний размер {sum(c['chunk_size'] for c in chunks) // max(len(chunks), 1)} символов")
        return chunks, stats

    # ============================================================
    # Фаза 1: Структурная декомпозиция
    # ============================================================

    def _split_into_structural_blocks(
        self,
        text: str,
        headings: List[Dict],
        list_boundaries: List[Dict],
    ) -> List[StructuralBlock]:
        """
        Разбивает текст на структурные блоки по \\n\\n, заголовкам и спискам.
        """
        # Собираем позиции заголовков для быстрого поиска
        heading_positions = {}
        for h in headings:
            heading_positions[h["start"]] = h

        # Собираем позиции списков
        list_ranges = [(lb["start"], lb["end"]) for lb in list_boundaries]

        # Разбиваем по \n\n
        raw_paragraphs = self._split_by_double_newline(text)

        if len(raw_paragraphs) < 3:
            # Fallback: мало абзацев — попробовать по \n с короткими строками
            raw_paragraphs = self._split_by_structural_newlines(text)

        blocks: List[StructuralBlock] = []

        for para_text, para_start, para_end in raw_paragraphs:
            if not para_text.strip():
                continue

            # Определяем тип блока
            block_type = "paragraph"
            heading_level = None

            # Проверяем, является ли блок заголовком
            if self._is_heading_block(para_text, para_start, heading_positions):
                block_type = "heading"
                h = self._find_heading_at(para_start, heading_positions)
                if h:
                    heading_level = h.get("level", 1)

            # Проверяем, попадает ли блок внутрь списка
            elif self._is_inside_list(para_start, para_end, list_ranges):
                block_type = "list"

            blocks.append(StructuralBlock(
                text=para_text.strip(),
                block_type=block_type,
                start_pos=para_start,
                end_pos=para_end,
                heading_level=heading_level,
            ))

        return blocks

    def _split_by_double_newline(self, text: str) -> List[Tuple[str, int, int]]:
        """Разбивает текст по \\n\\n, возвращая (text, start_pos, end_pos)."""
        result = []
        parts = re.split(r'(\n\s*\n)', text)

        current_pos = 0
        for part in parts:
            part_len = len(part)
            # Пропускаем разделители (\n\n)
            if re.match(r'^\n\s*\n$', part):
                current_pos += part_len
                continue

            if part.strip():
                result.append((part, current_pos, current_pos + part_len))
            current_pos += part_len

        return result

    def _split_by_structural_newlines(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Fallback: разбивает по \\n там, где строка короткая (< 120 символов)
        или выглядит как заголовок. Используется когда нет \\n\\n.
        """
        lines = text.split('\n')
        result = []
        current_block = []
        block_start = 0
        current_pos = 0

        for i, line in enumerate(lines):
            line_len = len(line) + 1  # +1 для \n

            # Определяем, нужен ли разрыв перед этой строкой
            should_break = False

            if current_block:
                stripped = line.strip()
                # Короткая строка после длинного блока → вероятно заголовок
                if (stripped and len(stripped) < 120 and
                        not stripped[0].islower() and
                        not stripped.startswith(('- ', '• ', '* ')) and
                        len('\n'.join(current_block)) > 200):
                    # Проверяем что это не продолжение предложения
                    prev_text = current_block[-1].rstrip()
                    if prev_text and prev_text[-1] in '.!?:;':
                        should_break = True

            if should_break and current_block:
                block_text = '\n'.join(current_block)
                result.append((block_text, block_start, current_pos))
                current_block = []
                block_start = current_pos

            current_block.append(line)
            current_pos += line_len

        # Последний блок
        if current_block:
            block_text = '\n'.join(current_block)
            result.append((block_text, block_start, current_pos))

        return result

    def _is_heading_block(
        self,
        text: str,
        start_pos: int,
        heading_positions: Dict[int, Dict],
    ) -> bool:
        """Проверяет, является ли блок заголовком.

        Блок считается заголовком ТОЛЬКО если весь текст блока — это
        заголовок (короткий текст). Если блок длинный и просто начинается
        с текста, совпадающего с заголовком — это НЕ heading-блок.
        """
        stripped = text.strip()

        # Блок длиннее 150 символов — точно не заголовок
        if len(stripped) > 150:
            return False

        # Точное совпадение позиции с detected heading
        if start_pos in heading_positions:
            return True

        # Без дополнительной эвристики — доверяем только detect_headings.
        # Эвристика создавала ложные срабатывания на элементах списков
        # ("Кора средней фракции", "Мульчирующая пленка" и т.д.)

        return False

    def _find_heading_at(self, start_pos: int, heading_positions: Dict) -> Optional[Dict]:
        """Находит заголовок по позиции."""
        return heading_positions.get(start_pos)

    def _is_inside_list(self, start: int, end: int, list_ranges: List[Tuple[int, int]]) -> bool:
        """Проверяет, находится ли блок внутри списка."""
        for ls, le in list_ranges:
            if start >= ls and end <= le:
                return True
        return False

    # ============================================================
    # Разбиение больших блоков
    # ============================================================

    def _split_oversized_blocks(self, blocks: List[StructuralBlock]) -> List[StructuralBlock]:
        """Разбивает блоки > max_chunk_size по предложениям."""
        result = []

        for block in blocks:
            if block.size <= self.max_chunk_size:
                result.append(block)
                continue

            # Разбиваем по предложениям
            sentences = self._split_sentences(block.text)
            current_text = ""
            current_start = block.start_pos

            for sentence in sentences:
                candidate = (current_text + "\n" + sentence).strip() if current_text else sentence

                if len(candidate) > self.max_chunk_size and current_text:
                    result.append(StructuralBlock(
                        text=current_text.strip(),
                        block_type=block.block_type,
                        start_pos=current_start,
                        end_pos=current_start + len(current_text.strip()),
                        heading_level=block.heading_level,
                    ))
                    current_start += len(current_text)
                    current_text = sentence
                else:
                    current_text = candidate

            if current_text.strip():
                result.append(StructuralBlock(
                    text=current_text.strip(),
                    block_type="paragraph",  # Куски больших блоков = параграфы
                    start_pos=current_start,
                    end_pos=current_start + len(current_text.strip()),
                ))

        return result

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """
        Разбивает текст на предложения (для разбиения больших блоков).
        Сохраняет внутренние \\n.
        """
        # Защищаем сокращения
        protected = text
        abbreviations = [
            (r'\bт\.е\.', 'Т_Е_'), (r'\bт\.п\.', 'Т_П_'),
            (r'\bт\.д\.', 'Т_Д_'), (r'\bт\.к\.', 'Т_К_'),
            (r'\bи др\.', 'И_ДР_'), (r'\bи пр\.', 'И_ПР_'),
            (r'\bг\.', 'Г_'), (r'\bмл\.', 'МЛ_'),
            (r'\bст\.', 'СТ_'), (r'\bв\.', 'В_'),
        ]
        for pattern, replacement in abbreviations:
            protected = re.sub(pattern, replacement, protected)

        # Защищаем числа с точками
        protected = re.sub(r'(\d)\.(\d)', r'\1_DOT_\2', protected)

        # Разбиваем по предложениям: .!? + пробел/перенос + заглавная
        sentences = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])', protected)

        # Восстанавливаем сокращения
        restore = [
            ('Т_Е_', 'т.е.'), ('Т_П_', 'т.п.'),
            ('Т_Д_', 'т.д.'), ('Т_К_', 'т.к.'),
            ('И_ДР_', 'и др.'), ('И_ПР_', 'и пр.'),
            ('Г_', 'г.'), ('МЛ_', 'мл.'),
            ('СТ_', 'ст.'), ('В_', 'в.'),
            ('_DOT_', '.'),
        ]
        result = []
        for s in sentences:
            for old, new in restore:
                s = s.replace(old, new)
            s = s.strip()
            if s:
                result.append(s)

        return result

    # ============================================================
    # Фаза 2: Семантическое слияние
    # ============================================================

    async def _get_block_embeddings(
        self,
        blocks: List[StructuralBlock],
    ) -> Tuple[List[List[float]], int, float]:
        """
        Получает embeddings для структурных блоков через Gemini API.
        Обрезает длинные блоки до embedding_truncate_chars символов.
        """
        # Подготавливаем тексты: обрезаем для экономии токенов
        texts = []
        for block in blocks:
            t = block.text[:self.embedding_truncate_chars]
            texts.append(t)

        all_embeddings = []
        total_tokens = 0
        total_cost = 0.0

        for i in range(0, len(texts), self.embedding_batch_size):
            batch = texts[i:i + self.embedding_batch_size]
            batch_embeddings, tokens, cost = await get_embeddings_for_similarity_with_usage(
                texts=batch,
                output_dimensionality=768,
            )
            all_embeddings.extend(batch_embeddings)
            total_tokens += tokens
            total_cost += cost

        return all_embeddings, total_tokens, total_cost

    def _compute_merge_plan(
        self,
        blocks: List[StructuralBlock],
        embeddings: List[List[float]],
    ) -> List[List[int]]:
        """
        Строит план слияния: жадный проход слева направо.

        Правила:
        1. Заголовок → ВСЕГДА начинает новый чанк
        2. similarity >= merge_threshold И размер <= max_chunk_size → сливаем
        3. similarity < merge_threshold → новый чанк
        4. Размер > max_chunk_size → новый чанк
        """
        if not blocks:
            return []

        groups: List[List[int]] = []
        current_group = [0]
        current_size = blocks[0].size

        for i in range(1, len(blocks)):
            block = blocks[i]

            # Правило 1: Заголовок всегда начинает новый чанк
            if block.block_type == "heading":
                groups.append(current_group)
                current_group = [i]
                current_size = block.size
                continue

            # Правило 4: Превышает лимит → новый чанк
            combined_size = current_size + block.size + 2  # +2 для \n\n
            if combined_size > self.max_chunk_size:
                groups.append(current_group)
                current_group = [i]
                current_size = block.size
                continue

            # Правило 2-3: Семантическая проверка
            sim = self._cosine_similarity(embeddings[i - 1], embeddings[i])
            if sim >= self.merge_threshold:
                # Сливаем
                current_group.append(i)
                current_size = combined_size
            else:
                # Новый чанк
                groups.append(current_group)
                current_group = [i]
                current_size = block.size

        # Последняя группа
        if current_group:
            groups.append(current_group)

        return groups

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Cosine similarity между двумя векторами."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))

    # ============================================================
    # Сборка чанков
    # ============================================================

    def _assemble_chunks(
        self,
        blocks: List[StructuralBlock],
        groups: List[List[int]],
    ) -> List[Dict[str, Any]]:
        """Собирает чанки из групп блоков, сохраняя форматирование."""
        chunks = []
        chunk_index = 0

        for group in groups:
            group_blocks = [blocks[i] for i in group]

            # Соединяем блоки через \n\n (сохраняем структуру)
            chunk_text = "\n\n".join(b.text for b in group_blocks)
            chunk_text = chunk_text.strip()

            if not chunk_text:
                continue

            start_pos = group_blocks[0].start_pos
            end_pos = group_blocks[-1].end_pos
            sentences_count = self._count_sentences(chunk_text)

            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "chunk_size": len(chunk_text),
                "start_pos": start_pos,
                "end_pos": end_pos,
                "sentences_count": sentences_count,
            })
            chunk_index += 1

        return chunks

    # ============================================================
    # Пост-обработка
    # ============================================================

    def _merge_tiny_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Объединяет чанки < min_chunk_size с соседними."""
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0

        while i < len(chunks):
            current = chunks[i].copy()

            # Сливаем со следующим пока маленький
            while (current["chunk_size"] < self.min_chunk_size and
                   i + 1 < len(chunks)):
                i += 1
                next_chunk = chunks[i]
                current["chunk_text"] += "\n\n" + next_chunk["chunk_text"]
                current["chunk_size"] = len(current["chunk_text"])
                current["end_pos"] = next_chunk["end_pos"]
                current["sentences_count"] += next_chunk["sentences_count"]

            merged.append(current)
            i += 1

        return merged

    def _add_overlap(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Добавляет overlap: последние N предложений предыдущего чанка
        вставляются в начало следующего.

        НЕ добавляет overlap если чанк начинается с заголовка.
        Ограничивает overlap до MAX_OVERLAP_CHARS символов.
        """
        MAX_OVERLAP_CHARS = 200

        if len(chunks) <= 1 or self.overlap_sentences <= 0:
            return chunks

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            current = chunks[i].copy()
            prev_text = chunks[i - 1]["chunk_text"]

            # Не добавляем overlap если текущий чанк начинается как заголовок
            first_line = current["chunk_text"].split('\n')[0].strip()
            if (len(first_line) < 100 and first_line and
                    first_line[-1] not in '.!?,;'):
                # Похоже на заголовок — пропускаем overlap
                result.append(current)
                continue

            # Извлекаем последние N предложений из предыдущего чанка
            prev_sentences = self._split_sentences(prev_text)
            overlap_sentences = prev_sentences[-self.overlap_sentences:] if prev_sentences else []

            if overlap_sentences:
                overlap_text = " ".join(overlap_sentences)
                # Ограничиваем размер overlap
                if len(overlap_text) > MAX_OVERLAP_CHARS:
                    # Берём только последнее предложение
                    overlap_text = prev_sentences[-1] if prev_sentences else ""
                    if len(overlap_text) > MAX_OVERLAP_CHARS:
                        # Обрезаем до лимита, ищем границу слова
                        overlap_text = overlap_text[-(MAX_OVERLAP_CHARS):]
                        space_pos = overlap_text.find(' ')
                        if space_pos > 0:
                            overlap_text = "..." + overlap_text[space_pos:]
                        overlap_sentences = [overlap_text]

                if overlap_text.strip():
                    current["chunk_text"] = overlap_text.strip() + "\n\n" + current["chunk_text"]
                    current["chunk_size"] = len(current["chunk_text"])
                    current["sentences_count"] += len(overlap_sentences)

            result.append(current)

        return result

    @staticmethod
    def _count_sentences(text: str) -> int:
        """Подсчитывает количество предложений в тексте (приблизительно)."""
        if not text:
            return 0
        # Считаем по концам предложений
        count = len(re.findall(r'[.!?]+\s', text))
        # Минимум 1 если текст не пустой
        return max(count, 1)


# ============================================================
# Старая версия (для rollback)
# ============================================================

class SemanticChunkerV1:
    """
    Старый семантический чанкер (v1). Оставлен для обратной совместимости.
    Разбивает по предложениям → эмбеддинги → percentile threshold.
    """

    def __init__(
        self,
        threshold_percentile: int = 60,
        min_chunk_size: int = 300,
        max_chunk_size: int = 2000,
        batch_size: int = 50,
    ):
        self.threshold_percentile = threshold_percentile
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.batch_size = batch_size

    async def chunk(
        self,
        text: str,
        list_boundaries: Optional[List[Dict]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        empty_stats = {
            "sentences_count": 0,
            "chunking_tokens": 0,
            "chunking_cost_usd": 0.0,
        }

        if not text or len(text.strip()) < self.min_chunk_size:
            chunks = [{
                "chunk_index": 0,
                "chunk_text": text.strip(),
                "chunk_size": len(text.strip()),
                "start_pos": 0,
                "end_pos": len(text),
                "sentences_count": 1,
            }] if text.strip() else []
            return chunks, {**empty_stats, "sentences_count": 1 if text.strip() else 0}

        sentences = SemanticChunkerV2._split_sentences(text)

        if len(sentences) <= 1:
            chunks = [{
                "chunk_index": 0,
                "chunk_text": text.strip(),
                "chunk_size": len(text.strip()),
                "start_pos": 0,
                "end_pos": len(text),
                "sentences_count": len(sentences),
            }]
            return chunks, {**empty_stats, "sentences_count": len(sentences)}

        if list_boundaries is None:
            list_boundaries = detect_list_boundaries(text)

        from src.services.documents.boundary_detector import (
            adjust_sentence_breakpoints_for_lists,
            get_heading_sentence_indices,
        )

        all_embeddings = []
        total_tokens = 0
        total_cost = 0.0
        for i in range(0, len(sentences), self.batch_size):
            batch = sentences[i:i + self.batch_size]
            batch_embeddings, tokens, cost = await get_embeddings_for_similarity_with_usage(
                texts=batch, output_dimensionality=768,
            )
            all_embeddings.extend(batch_embeddings)
            total_tokens += tokens
            total_cost += cost

        similarities = []
        for i in range(len(all_embeddings) - 1):
            sim = SemanticChunkerV2._cosine_similarity(all_embeddings[i], all_embeddings[i + 1])
            similarities.append(sim)

        if similarities:
            threshold = np.percentile(similarities, 100 - self.threshold_percentile)
            breakpoints = [i for i, sim in enumerate(similarities) if sim < threshold]
        else:
            breakpoints = []

        headings_detected = detect_headings(text)
        heading_indices = get_heading_sentence_indices(headings_detected, sentences)
        protected = set(heading_indices)
        breakpoints = [bp for bp in breakpoints if bp not in protected]
        breakpoints = adjust_sentence_breakpoints_for_lists(breakpoints, sentences, list_boundaries)

        # Формируем чанки
        breakpoints = sorted(set(breakpoints))
        if len(sentences) - 1 not in breakpoints:
            breakpoints.append(len(sentences) - 1)

        chunks = []
        chunk_index = 0
        start_sentence = 0
        current_pos = 0
        for bp in breakpoints:
            chunk_sentences = sentences[start_sentence:bp + 1]
            chunk_text = " ".join(chunk_sentences)
            start_pos = current_pos
            end_pos = start_pos + len(chunk_text)
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "chunk_size": len(chunk_text),
                "start_pos": start_pos,
                "end_pos": end_pos,
                "sentences_count": len(chunk_sentences),
            })
            chunk_index += 1
            start_sentence = bp + 1
            current_pos = end_pos + 1

        # Merge small
        if len(chunks) > 1:
            merged = []
            i = 0
            while i < len(chunks):
                current = chunks[i].copy()
                while current["chunk_size"] < self.min_chunk_size and i + 1 < len(chunks):
                    i += 1
                    nxt = chunks[i]
                    current["chunk_text"] += " " + nxt["chunk_text"]
                    current["chunk_size"] = len(current["chunk_text"])
                    current["end_pos"] = nxt["end_pos"]
                    current["sentences_count"] += nxt["sentences_count"]
                merged.append(current)
                i += 1
            for idx, c in enumerate(merged):
                c["chunk_index"] = idx
            chunks = merged

        # Split large
        final = []
        ci = 0
        for chunk in chunks:
            if chunk["chunk_size"] <= self.max_chunk_size:
                chunk["chunk_index"] = ci
                final.append(chunk)
                ci += 1
            else:
                sub = SemanticChunkerV2._split_sentences(chunk["chunk_text"])
                ct = ""
                cs = chunk["start_pos"]
                for s in sub:
                    if len(ct) + len(s) + 1 > self.max_chunk_size and ct:
                        final.append({
                            "chunk_index": ci, "chunk_text": ct.strip(),
                            "chunk_size": len(ct.strip()), "start_pos": cs,
                            "end_pos": cs + len(ct.strip()),
                            "sentences_count": ct.count(". ") + 1,
                        })
                        ci += 1
                        cs += len(ct)
                        ct = ""
                    ct += s + " "
                if ct.strip():
                    final.append({
                        "chunk_index": ci, "chunk_text": ct.strip(),
                        "chunk_size": len(ct.strip()), "start_pos": cs,
                        "end_pos": cs + len(ct.strip()),
                        "sentences_count": ct.count(". ") + 1,
                    })
                    ci += 1
        chunks = final

        stats = {
            "sentences_count": len(sentences),
            "chunking_tokens": total_tokens,
            "chunking_cost_usd": total_cost,
        }
        return chunks, stats


# ============================================================
# Синглтон и публичная функция-обёртка
# ============================================================

_chunker_v2_instance: Optional[SemanticChunkerV2] = None


def get_semantic_chunker(
    merge_threshold: float = 0.5,
    min_chunk_size: int = 300,
    max_chunk_size: int = 2000,
    overlap_sentences: int = 2,
    # Совместимость со старым API
    threshold_percentile: int = 60,
) -> SemanticChunkerV2:
    """Возвращает singleton instance SemanticChunkerV2."""
    global _chunker_v2_instance

    if _chunker_v2_instance is None:
        _chunker_v2_instance = SemanticChunkerV2(
            merge_threshold=merge_threshold,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            overlap_sentences=overlap_sentences,
        )

    return _chunker_v2_instance


async def chunk_text_semantic(
    text: str,
    list_boundaries: Optional[List[Dict]] = None,
    headings: Optional[List[Dict]] = None,
    merge_threshold: float = 0.5,
    min_chunk_size: int = 300,
    max_chunk_size: int = 2000,
    overlap_sentences: int = 2,
    # Совместимость со старым API
    threshold_percentile: int = 60,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Функция-обёртка для semantic chunking v3.

    Параметры:
        text: Текст для разбиения
        list_boundaries: Границы списков (из docx_parser или auto-detect)
        headings: Заголовки (из docx_parser или auto-detect)
        merge_threshold: Абсолютный порог similarity для слияния блоков (0.5 по умолчанию)
        min_chunk_size: Минимальный размер чанка (300 символов)
        max_chunk_size: Максимальный размер чанка (2000 символов)
        overlap_sentences: Количество предложений overlap (2 по умолчанию)

    Возвращает:
        Tuple[chunks, stats]
    """
    chunker = get_semantic_chunker(
        merge_threshold=merge_threshold,
        min_chunk_size=min_chunk_size,
        max_chunk_size=max_chunk_size,
        overlap_sentences=overlap_sentences,
    )

    return await chunker.chunk(text, list_boundaries, headings)
