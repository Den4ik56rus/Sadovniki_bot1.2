# src/services/presentations/presentation_service.py

"""
Оркестратор генерации презентаций.

Координирует:
1. GPT: текст → JSON промптов слайдов
2. NBP: промпт → PNG для каждого слайда
3. PDF: сборка PNG в PDF
4. SSE: прогресс генерации
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Callable, Awaitable

from src.services.db import presentation_repo
from src.services.db.article_repo import get_article_by_id
from src.services.llm.core_llm import (
    create_chat_completion_with_retry,
    calculate_cost,
)
from src.services.llm.article_llm import generate_article
from src.services.presentations.prompt_builder import (
    build_slide_split_prompt,
    parse_slide_prompts,
)
from src.services.presentations.slide_generator import (
    generate_slide_image,
    edit_slide_image,
    calculate_nbp_cost,
)
from src.services.presentations.pdf_builder import build_pdf
from src.data.funnel_b_problems import get_culture_label, get_problem_label, get_culture_russian

logger = logging.getLogger(__name__)

# Base directory for presentation files
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "presentations")


def _slide_image_path(presentation_id: int, slide_index: int, version: int) -> str:
    return os.path.join(DATA_DIR, str(presentation_id), f"slide_{slide_index}_v{version}.png")


def _pdf_path(presentation_id: int) -> str:
    return os.path.join(DATA_DIR, str(presentation_id), "presentation.pdf")


# Тип callback для SSE прогресса
ProgressCallback = Optional[Callable[[dict], Awaitable[None]]]


async def generate_presentation(
    presentation_id: int,
    on_progress: ProgressCallback = None,
) -> None:
    """
    Полный цикл генерации презентации.

    1. Загружает презентацию и стиль из БД
    2. GPT: текст + стиль → JSON промптов
    3. Сохраняет слайды в БД
    4. NBP: генерирует изображение для каждого слайда
    5. Собирает PDF
    6. Обновляет статус

    Args:
        presentation_id: ID презентации
        on_progress: callback для SSE прогресса
    """
    try:
        # Update status
        await presentation_repo.update_presentation(
            presentation_id, status="generating"
        )

        if on_progress:
            await on_progress({"type": "generation_started", "presentation_id": presentation_id})

        # 1. Load presentation + style
        pres = await presentation_repo.get_presentation_by_id(presentation_id)
        if not pres:
            raise ValueError(f"Презентация {presentation_id} не найдена")

        source_text = pres.get("source_text") or ""

        # STEP 0: Generate article if problem mode
        article_cost = 0.0
        if pres.get("generation_mode") == "problem":
            if on_progress:
                await on_progress({
                    "type": "article_generating",
                    "message": "Генерация статьи по проблеме...",
                })

            culture_key = pres.get("culture_key") or ""
            variety_key = pres.get("variety_key")
            problem_key = pres.get("problem_key") or ""

            topic = f"{get_culture_label(culture_key, variety_key)}: {get_problem_label(problem_key)}"
            culture_russian = get_culture_russian(culture_key)

            article_text, article_id = await generate_article(
                topic=topic,
                telegram_user_id=0,
                culture=culture_russian or None,
                use_scripts=True,
                skip_rag=False,
            )

            source_text = article_text

            # Get cost from saved article record
            article_record = await get_article_by_id(article_id)
            article_cost = float(article_record.get("cost_usd", 0)) if article_record else 0.0
            article_prompt_tokens = article_record.get("llm_prompt_tokens", 0) if article_record else 0
            article_completion_tokens = article_record.get("llm_completion_tokens", 0) if article_record else 0

            await presentation_repo.update_presentation(
                presentation_id,
                source_text=source_text,
                article_cost_usd=article_cost,
                article_prompt_tokens=article_prompt_tokens,
                article_completion_tokens=article_completion_tokens,
            )

            if on_progress:
                await on_progress({
                    "type": "article_completed",
                    "message": "Статья сгенерирована",
                    "article_cost_usd": article_cost,
                    "article_length": len(source_text),
                })

            logger.info(f"[presentation_service] Статья сгенерирована: {len(source_text)} символов, cost=${article_cost:.4f}")

        style_xml = None
        if pres["style_id"]:
            style = await presentation_repo.get_style_by_id(pres["style_id"])
            if style:
                style_xml = style["style_xml"]

        template_text = None
        # В problem mode шаблон не используется — GPT сам решает структуру
        if pres.get("generation_mode") != "problem" and pres.get("template_id"):
            template = await presentation_repo.get_template_by_id(pres["template_id"])
            if template:
                template_text = template["template_text"]

        # Extra instructions for systemic closing slide (problem mode only)
        extra_instructions = None
        if pres.get("generation_mode") == "problem":
            extra_instructions = _build_systemic_slide_instruction(pres)

        # 2. GPT: split text into slides
        custom_system_prompt = pres.get("custom_system_prompt") or None
        messages = build_slide_split_prompt(source_text, style_xml, template_text, extra_instructions, custom_system_prompt)

        if on_progress:
            await on_progress({"type": "text_processing", "message": "GPT разбивает текст на слайды..."})

        llm_result = await create_chat_completion_with_retry(
            messages=messages,
            model=pres.get("llm_model"),
            reasoning_effort=pres.get("reasoning_effort"),
            max_attempts=3,
            base_delay=5.0,
        )

        all_slide_prompts = parse_slide_prompts(llm_result["content"])
        text_cost = calculate_cost(
            llm_result["model"],
            llm_result["prompt_tokens"],
            llm_result["completion_tokens"],
        )

        # Test mode: generate only one slide
        test_slide_index = pres.get("test_slide_index")
        if test_slide_index is not None:
            if 0 <= test_slide_index < len(all_slide_prompts):
                slide_prompts = [all_slide_prompts[test_slide_index]]
                logger.info(f"[presentation_service] Тестовый режим: только слайд {test_slide_index}")
            else:
                # Fallback: first slide
                slide_prompts = [all_slide_prompts[0]]
                test_slide_index = 0
                logger.warning(f"[presentation_service] test_slide_index вне диапазона, используем слайд 0")
        else:
            slide_prompts = all_slide_prompts

        # Image model override
        image_model = pres.get("image_model") or None

        # Update text costs
        await presentation_repo.update_presentation(
            presentation_id,
            text_prompt_tokens=llm_result["prompt_tokens"],
            text_completion_tokens=llm_result["completion_tokens"],
            text_cost_usd=text_cost,
            slide_count=len(slide_prompts),
        )

        if on_progress:
            await on_progress({
                "type": "slides_planned",
                "slide_count": len(slide_prompts),
                "text_cost_usd": text_cost,
            })

        # 3. Save all slides to DB first
        slide_tasks = []  # (index, slide_id, version_id, output_path, nbp_prompt)
        for i, sp in enumerate(slide_prompts):
            slide_id = await presentation_repo.create_slide(
                presentation_id=presentation_id,
                slide_index=i,
                slide_title=sp["title"],
                slide_prompt=sp["nbp_prompt"],
                slide_notes=sp.get("notes"),
            )
            output_path = _slide_image_path(presentation_id, i, 1)
            version_id = await presentation_repo.create_slide_version(
                slide_id=slide_id,
                version_number=1,
                nbp_prompt=sp["nbp_prompt"],
            )
            slide_tasks.append((i, slide_id, version_id, output_path, sp))

        # 4. Generate images in parallel (batches of NBP_CONCURRENCY)
        # Vertex AI free trial: ~10 RPM — batch of 2 + pause between batches
        NBP_CONCURRENCY = 2
        BATCH_PAUSE = 5  # секунд между батчами (rate limit protection)
        total_image_input = 0
        total_image_output = 0
        total_image_cost = 0.0
        image_paths_map = {}  # index → path

        async def _gen_one(i, slide_id, version_id, output_path, sp):
            """Generate one slide image, return result or None on failure."""
            await presentation_repo.update_slide_version(version_id, status="generating")
            if on_progress:
                await on_progress({
                    "type": "slide_generating",
                    "slide_index": i,
                    "slide_count": len(slide_prompts),
                    "slide_title": sp["title"],
                })
            try:
                gen_kwargs = {"prompt": sp["nbp_prompt"], "output_path": output_path}
                if image_model:
                    gen_kwargs["model"] = image_model
                result = await generate_slide_image(**gen_kwargs)
                await presentation_repo.update_slide_version(
                    version_id,
                    status="completed",
                    image_path=result["image_path"],
                    nbp_input_tokens=result["input_tokens"],
                    nbp_output_tokens=result["output_tokens"],
                    nbp_cost_usd=result["cost_usd"],
                )
                return i, slide_id, version_id, result
            except Exception as e:
                logger.error(f"[presentation_service] Ошибка генерации слайда {i}: {e}")
                await presentation_repo.update_slide_version(
                    version_id, status="failed", error_message=str(e),
                )
                if on_progress:
                    await on_progress({"type": "slide_failed", "slide_index": i, "error": str(e)})
                return i, slide_id, version_id, None

        # Process in batches with pause between them (rate limit)
        for batch_start in range(0, len(slide_tasks), NBP_CONCURRENCY):
            if batch_start > 0:
                await asyncio.sleep(BATCH_PAUSE)
            batch = slide_tasks[batch_start:batch_start + NBP_CONCURRENCY]
            coros = [_gen_one(i, sid, vid, opath, sp) for i, sid, vid, opath, sp in batch]
            results = await asyncio.gather(*coros)

            for idx, sid, vid, result in results:
                if result:
                    total_image_input += result["input_tokens"]
                    total_image_output += result["output_tokens"]
                    total_image_cost += result["cost_usd"]
                    image_paths_map[idx] = result["image_path"]
                    if on_progress:
                        await on_progress({
                            "type": "slide_completed",
                            "slide_index": idx,
                            "slide_count": len(slide_prompts),
                            "slide_cost_usd": result["cost_usd"],
                            "total_image_cost_usd": total_image_cost,
                            "version_id": vid,
                            "slide_id": sid,
                            "slide_title": slide_prompts[idx]["title"],
                        })

        # Collect paths in order
        image_paths = [image_paths_map[i] for i in sorted(image_paths_map)]

        # 4. Update image costs
        total_cost = article_cost + text_cost + total_image_cost
        await presentation_repo.update_presentation(
            presentation_id,
            image_input_tokens=total_image_input,
            image_output_tokens=total_image_output,
            image_cost_usd=total_image_cost,
            total_cost_usd=total_cost,
        )

        # 5. Build PDF
        if image_paths:
            if on_progress:
                await on_progress({"type": "building_pdf"})

            pdf_output = _pdf_path(presentation_id)
            await build_pdf(image_paths, pdf_output)

            await presentation_repo.update_presentation(
                presentation_id,
                pdf_path=pdf_output,
                status="completed",
            )
        else:
            await presentation_repo.update_presentation(
                presentation_id,
                status="failed",
                error_message="Ни один слайд не был сгенерирован",
            )

        if on_progress:
            await on_progress({
                "type": "generation_completed",
                "presentation_id": presentation_id,
                "slide_count": len(slide_prompts),
                "total_cost_usd": total_cost,
            })

        logger.info(
            f"[presentation_service] Презентация {presentation_id} завершена: "
            f"{len(slide_prompts)} слайдов, cost=${total_cost:.4f}"
        )

    except Exception as e:
        logger.error(f"[presentation_service] Ошибка генерации презентации {presentation_id}: {e}", exc_info=True)
        await presentation_repo.update_presentation(
            presentation_id,
            status="failed",
            error_message=str(e),
        )
        if on_progress:
            await on_progress({
                "type": "generation_failed",
                "presentation_id": presentation_id,
                "error": str(e),
            })


async def edit_slide(
    slide_id: int,
    instruction: str,
    on_progress: ProgressCallback = None,
) -> dict:
    """
    Редактирует слайд: создаёт новую версию с правками.

    Args:
        slide_id: ID слайда
        instruction: Инструкция по правке
        on_progress: callback для SSE

    Returns:
        dict с данными новой версии
    """
    slide = await presentation_repo.get_slide_by_id(slide_id)
    if not slide:
        raise ValueError(f"Слайд {slide_id} не найден")

    # Get latest version to find current image
    latest = await presentation_repo.get_latest_version(slide_id)
    if not latest or not latest.get("image_path"):
        raise ValueError(f"У слайда {slide_id} нет изображения для редактирования")

    # Get next version number
    next_ver = await presentation_repo.get_next_version_number(slide_id)

    # Create version record
    output_path = _slide_image_path(
        slide["presentation_id"],
        slide["slide_index"],
        next_ver,
    )

    # Build edit prompt: original prompt + edit instruction
    edit_prompt = f"{slide['slide_prompt']}\n\nEDIT: {instruction}"

    version_id = await presentation_repo.create_slide_version(
        slide_id=slide_id,
        version_number=next_ver,
        nbp_prompt=edit_prompt,
        edit_instruction=instruction,
    )

    try:
        await presentation_repo.update_slide_version(version_id, status="generating")

        result = await edit_slide_image(
            image_path=latest["image_path"],
            instruction=instruction,
            output_path=output_path,
        )

        await presentation_repo.update_slide_version(
            version_id,
            status="completed",
            image_path=result["image_path"],
            nbp_input_tokens=result["input_tokens"],
            nbp_output_tokens=result["output_tokens"],
            nbp_cost_usd=result["cost_usd"],
        )

        # Update presentation image costs
        pres = await presentation_repo.get_presentation_by_id(slide["presentation_id"])
        if pres:
            new_image_cost = float(pres["image_cost_usd"]) + result["cost_usd"]
            new_total = float(pres.get("article_cost_usd") or 0) + float(pres["text_cost_usd"]) + new_image_cost
            await presentation_repo.update_presentation(
                slide["presentation_id"],
                image_input_tokens=int(pres["image_input_tokens"]) + result["input_tokens"],
                image_output_tokens=int(pres["image_output_tokens"]) + result["output_tokens"],
                image_cost_usd=new_image_cost,
                total_cost_usd=new_total,
            )

        version = await presentation_repo.get_version_by_id(version_id)
        return version

    except Exception as e:
        logger.error(f"[presentation_service] Ошибка редактирования слайда {slide_id}: {e}")
        await presentation_repo.update_slide_version(
            version_id,
            status="failed",
            error_message=str(e),
        )
        raise


async def rebuild_pdf(presentation_id: int) -> str:
    """
    Пересобирает PDF из текущих (latest) версий слайдов.

    Returns:
        Путь к PDF файлу
    """
    slides = await presentation_repo.get_slides_by_presentation(presentation_id)
    if not slides:
        raise ValueError(f"У презентации {presentation_id} нет слайдов")

    image_paths = []
    for slide in slides:
        latest = await presentation_repo.get_latest_version(slide["id"])
        if latest and latest.get("image_path") and Path(latest["image_path"]).exists():
            image_paths.append(latest["image_path"])

    if not image_paths:
        raise ValueError("Нет изображений для сборки PDF")

    pdf_output = _pdf_path(presentation_id)
    await build_pdf(image_paths, pdf_output)

    await presentation_repo.update_presentation(
        presentation_id, pdf_path=pdf_output
    )

    return pdf_output


def _build_systemic_slide_instruction(pres: dict) -> str:
    """Инструкция для GPT: завершающий слайд о системном подходе."""
    culture_key = pres.get("culture_key") or ""
    variety_key = pres.get("variety_key")
    problem_key = pres.get("problem_key") or ""

    culture_label = get_culture_label(culture_key, variety_key)
    problem_label = get_problem_label(problem_key)

    return (
        f"\n\nIMPORTANT — FINAL SLIDE REQUIREMENT:\n"
        f"The LAST slide MUST be a 'systemic thinking' slide. "
        f"The core message: right now you are dealing with the CONSEQUENCES — '{problem_label}'. "
        f"But healthy {culture_label} and a good harvest are built by an entire SYSTEM working together: "
        f"soil preparation, balanced nutrition, timely disease protection, pest control, and proper agrotechnique "
        f"(spacing, watering, pruning). When one element breaks, the symptoms appear elsewhere. "
        f"Use the SUMMARY/SYSTEMIC slide type pattern — a botanical/organic metaphor with a healthy plant "
        f"at center and interconnected care elements flowing around it. "
        f"Do NOT use columns, pillars, temples, or rigid architectural metaphors. "
        f"Make the illustration feel natural, like a living ecosystem diagram.\n\n"
        f"ALSO IMPORTANT — PRACTICAL TREATMENT/FERTILIZER SLIDES:\n"
        f"If the article mentions specific treatments (fungicides, insecticides, acaricides) or "
        f"fertilizers/nutrients, you MUST dedicate 1-2 slides specifically to practical application details. "
        f"Use the PRACTICAL TREATMENT / FERTILIZER SLIDE type pattern. "
        f"List exact product names, dosages, timing, and brief instructions. "
        f"Do not bury these details inside general informational slides."
    )
