# src/services/documents/semantic_chunker.py

"""
Semantic Chunker для разбиения текста на смысловые блоки.

Использует Google Gemini Embeddings для определения семантических границ:
1. Разбивает текст на предложения
2. Получает embeddings для каждого предложения
3. Вычисляет cosine similarity между соседними предложениями
4. Находит точки разрыва там, где similarity падает ниже порога
5. Группирует предложения в чанки
6. Защищает списки от разрыва

Преимущества перед fixed-size chunking:
- +70% улучшение качества retrieval (по исследованиям 2025)
- Сохранение смысловой целостности
- Адаптивный размер чанков
"""

import re
import numpy as np
from typing import List, Dict, Optional, Any, Tuple

from src.services.llm.gemini_embeddings import get_embeddings_for_similarity_with_usage
from src.services.documents.boundary_detector import (
    adjust_sentence_breakpoints_for_lists,
    detect_list_boundaries,
    detect_headings,
    get_heading_sentence_indices,
)


class SemanticChunker:
    """
    Semantic chunker на основе Gemini Embeddings.
    """

    def __init__(
        self,
        threshold_percentile: int = 60,
        min_chunk_size: int = 300,
        max_chunk_size: int = 2000,
        batch_size: int = 50,
    ):
        """
        Параметры:
            threshold_percentile: Процентиль для определения порога разрыва.
                Выше = меньше разрывов = более крупные чанки.
                60 — хороший баланс для сохранения контекста.
            min_chunk_size: Минимальный размер чанка в символах.
                300 — предотвращает чанки из 1-2 предложений.
            max_chunk_size: Максимальный размер чанка в символах.
            batch_size: Размер батча для Gemini API.
        """
        self.threshold_percentile = threshold_percentile
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.batch_size = batch_size

    async def chunk(
        self,
        text: str,
        list_boundaries: Optional[List[Dict]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Разбивает текст на семантические чанки.

        Параметры:
            text: Текст для разбиения
            list_boundaries: Границы списков (из docx_parser или boundary_detector)

        Возвращает:
            Tuple[chunks, stats]:
            - chunks: Список чанков
            - stats: Статистика chunking (sentences_count, tokens, cost_usd)
        """
        # Статистика по умолчанию (для коротких текстов без API вызовов)
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

        # 1. Разбиваем на предложения
        sentences = self._split_sentences(text)

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

        # 2. Если списки не переданы, детектируем их
        if list_boundaries is None:
            list_boundaries = detect_list_boundaries(text)

        # 3. Получаем embeddings для всех предложений (с подсчётом стоимости)
        embeddings, chunking_tokens, chunking_cost = await self._get_sentence_embeddings(sentences)

        # 4. Вычисляем similarity между соседними предложениями
        similarities = self._compute_similarities(embeddings)

        # 5. Находим точки разрыва
        breakpoints = self._find_breakpoints(similarities)

        # 6. Детектируем заголовки и защищаем их от отрыва от контента
        headings = detect_headings(text)
        heading_indices = get_heading_sentence_indices(headings, sentences)

        # Убираем breakpoints сразу после заголовков (чтобы заголовок не отрывался)
        protected_breakpoints = set(heading_indices)
        breakpoints = [bp for bp in breakpoints if bp not in protected_breakpoints]

        # 7. Корректируем breakpoints с учётом списков
        breakpoints = adjust_sentence_breakpoints_for_lists(
            breakpoints, sentences, list_boundaries
        )

        # 8. Формируем чанки
        chunks = self._create_chunks(sentences, breakpoints, text)

        # 9. Пост-обработка: объединяем слишком мелкие чанки
        chunks = self._merge_small_chunks(chunks)

        # 10. Пост-обработка: разбиваем слишком большие чанки
        chunks = self._split_large_chunks(chunks)

        # Статистика chunking
        stats = {
            "sentences_count": len(sentences),
            "chunking_tokens": chunking_tokens,
            "chunking_cost_usd": chunking_cost,
        }

        return chunks, stats

    def _split_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения.

        Учитывает:
        - Русские и английские точки, вопросительные и восклицательные знаки
        - Сокращения (т.е., т.п., и др.)
        - Числа с точками (1.5, 2.0)
        """
        # Защищаем сокращения
        text = re.sub(r'\bт\.е\.', 'Т_Е_', text)
        text = re.sub(r'\bт\.п\.', 'Т_П_', text)
        text = re.sub(r'\bт\.д\.', 'Т_Д_', text)
        text = re.sub(r'\bт\.к\.', 'Т_К_', text)
        text = re.sub(r'\bи др\.', 'И_ДР_', text)
        text = re.sub(r'\bи пр\.', 'И_ПР_', text)
        text = re.sub(r'\bг\.', 'Г_', text)  # год
        text = re.sub(r'\bмл\.', 'МЛ_', text)  # младший
        text = re.sub(r'\bст\.', 'СТ_', text)  # старший
        text = re.sub(r'\bв\.', 'В_', text)  # век

        # Защищаем числа с точками
        text = re.sub(r'(\d)\.(\d)', r'\1_DOT_\2', text)

        # Разбиваем по предложениям
        # Точка/!/? + пробел + заглавная буква
        sentences = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])', text)

        # Восстанавливаем сокращения
        sentences = [
            s.replace('Т_Е_', 'т.е.')
             .replace('Т_П_', 'т.п.')
             .replace('Т_Д_', 'т.д.')
             .replace('Т_К_', 'т.к.')
             .replace('И_ДР_', 'и др.')
             .replace('И_ПР_', 'и пр.')
             .replace('Г_', 'г.')
             .replace('МЛ_', 'мл.')
             .replace('СТ_', 'ст.')
             .replace('В_', 'в.')
             .replace('_DOT_', '.')
            for s in sentences
        ]

        # Фильтруем пустые
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    async def _get_sentence_embeddings(
        self,
        sentences: List[str],
    ) -> Tuple[List[List[float]], int, float]:
        """
        Получает embeddings для предложений через Gemini API.

        Обрабатывает батчами для оптимизации.

        Возвращает:
            Tuple[embeddings, total_tokens, total_cost_usd]
        """
        all_embeddings = []
        total_tokens = 0
        total_cost = 0.0

        for i in range(0, len(sentences), self.batch_size):
            batch = sentences[i:i + self.batch_size]
            batch_embeddings, tokens, cost = await get_embeddings_for_similarity_with_usage(
                texts=batch,
                output_dimensionality=768,  # Меньше для скорости
            )
            all_embeddings.extend(batch_embeddings)
            total_tokens += tokens
            total_cost += cost

        return all_embeddings, total_tokens, total_cost

    def _compute_similarities(
        self,
        embeddings: List[List[float]],
    ) -> List[float]:
        """
        Вычисляет cosine similarity между соседними предложениями.
        """
        similarities = []

        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        return similarities

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Вычисляет косинусное сходство между двумя векторами."""
        a_arr = np.array(a)
        b_arr = np.array(b)

        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _find_breakpoints(self, similarities: List[float]) -> List[int]:
        """
        Находит точки разрыва на основе падения similarity.

        Использует percentile для определения порога.
        """
        if not similarities:
            return []

        # Порог: similarity ниже этого значения = точка разрыва
        threshold = np.percentile(similarities, 100 - self.threshold_percentile)

        breakpoints = [
            i for i, sim in enumerate(similarities)
            if sim < threshold
        ]

        return breakpoints

    def _create_chunks(
        self,
        sentences: List[str],
        breakpoints: List[int],
        original_text: str,
    ) -> List[Dict[str, Any]]:
        """
        Формирует чанки из предложений по точкам разрыва.
        """
        chunks = []
        chunk_index = 0

        # Добавляем конец как последнюю точку разрыва
        breakpoints = sorted(set(breakpoints))
        if len(sentences) - 1 not in breakpoints:
            breakpoints.append(len(sentences) - 1)

        start_sentence = 0
        current_pos = 0

        for bp in breakpoints:
            # Собираем предложения от start_sentence до bp включительно
            chunk_sentences = sentences[start_sentence:bp + 1]
            chunk_text = " ".join(chunk_sentences)

            # Находим позицию в оригинальном тексте
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
            current_pos = end_pos + 1  # +1 для пробела между чанками

        return chunks

    def _merge_small_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Объединяет слишком маленькие чанки с соседними.
        """
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0

        while i < len(chunks):
            current = chunks[i].copy()

            # Если чанк слишком маленький, объединяем со следующим
            while (current["chunk_size"] < self.min_chunk_size and
                   i + 1 < len(chunks)):
                i += 1
                next_chunk = chunks[i]
                current["chunk_text"] += " " + next_chunk["chunk_text"]
                current["chunk_size"] = len(current["chunk_text"])
                current["end_pos"] = next_chunk["end_pos"]
                current["sentences_count"] += next_chunk["sentences_count"]

            merged.append(current)
            i += 1

        # Пересчитываем индексы
        for idx, chunk in enumerate(merged):
            chunk["chunk_index"] = idx

        return merged

    def _split_large_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Разбивает слишком большие чанки.

        Если чанк превышает max_chunk_size, разбиваем его по предложениям.
        """
        result = []
        chunk_index = 0

        for chunk in chunks:
            if chunk["chunk_size"] <= self.max_chunk_size:
                chunk["chunk_index"] = chunk_index
                result.append(chunk)
                chunk_index += 1
            else:
                # Разбиваем большой чанк
                text = chunk["chunk_text"]
                sub_sentences = self._split_sentences(text)

                current_text = ""
                current_start = chunk["start_pos"]

                for sentence in sub_sentences:
                    if len(current_text) + len(sentence) + 1 > self.max_chunk_size:
                        if current_text:
                            result.append({
                                "chunk_index": chunk_index,
                                "chunk_text": current_text.strip(),
                                "chunk_size": len(current_text.strip()),
                                "start_pos": current_start,
                                "end_pos": current_start + len(current_text.strip()),
                                "sentences_count": current_text.count(". ") + 1,
                            })
                            chunk_index += 1
                            current_start += len(current_text)
                            current_text = ""

                    current_text += sentence + " "

                if current_text.strip():
                    result.append({
                        "chunk_index": chunk_index,
                        "chunk_text": current_text.strip(),
                        "chunk_size": len(current_text.strip()),
                        "start_pos": current_start,
                        "end_pos": current_start + len(current_text.strip()),
                        "sentences_count": current_text.count(". ") + 1,
                    })
                    chunk_index += 1

        return result


# Синглтон для переиспользования
_chunker_instance: Optional[SemanticChunker] = None


def get_semantic_chunker(
    threshold_percentile: int = 60,
    min_chunk_size: int = 300,
    max_chunk_size: int = 2000,
) -> SemanticChunker:
    """
    Возвращает singleton instance SemanticChunker.
    """
    global _chunker_instance

    if _chunker_instance is None:
        _chunker_instance = SemanticChunker(
            threshold_percentile=threshold_percentile,
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
        )

    return _chunker_instance


async def chunk_text_semantic(
    text: str,
    list_boundaries: Optional[List[Dict]] = None,
    threshold_percentile: int = 60,
    min_chunk_size: int = 300,
    max_chunk_size: int = 2000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Функция-обёртка для semantic chunking.

    Для совместимости с текущим интерфейсом chunker.py.

    Возвращает:
        Tuple[chunks, stats]:
        - chunks: Список чанков
        - stats: Статистика (sentences_count, chunking_tokens, chunking_cost_usd)
    """
    chunker = get_semantic_chunker(
        threshold_percentile=threshold_percentile,
        min_chunk_size=min_chunk_size,
        max_chunk_size=max_chunk_size,
    )

    return await chunker.chunk(text, list_boundaries)
