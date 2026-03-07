# src/services/image_generator/prompt_optimizer.py

"""
Оптимизация промптов для генерации изображений через Nano Banana Pro.

ChatGPT 5.1 (medium reasoning) превращает русское описание + пресет → оптимизированный английский промпт
по правилам NBP (natural language, hex colors, specific positions, context).
"""

import logging
from typing import TypedDict

from src.services.llm.core_llm import create_chat_completion_with_usage

logger = logging.getLogger(__name__)

# Инструкции для каждого пресета
PRESET_INSTRUCTIONS = {
    "photo": (
        "Task type: Photorealistic Photography.\n"
        "Include: camera angle (eye-level, low angle, overhead), shot type (close-up, medium, wide), "
        "lighting conditions (golden hour, overcast, studio softbox, dramatic side light), "
        "depth of field description, material textures and surfaces, atmospheric details."
    ),
    "infographic": (
        "Task type: Infographic / Data Visualization.\n"
        "Include: chart/diagram types, icon style (flat, outlined, filled), color-coded sections with hex colors, "
        "readable text labels in quotes, structured grid layout, clean sans-serif typography, "
        "visual hierarchy with size and weight variation. Specify a Visual Style from: "
        "Paper Cutout, Isometric 3D, Blueprint/Schematic, Corporate Memphis/Flat Art, Dashboard, "
        "Da Vinci Notebook, Cyberpunk/Neon."
    ),
    "slide": (
        "Task type: Presentation Slide.\n"
        "Include: layout structure (title + content, split layout, bento grid, asymmetric), "
        "typography hierarchy (headline weight, body weight, sizes), color palette with hex codes, "
        "ample white/negative space, visual emphasis on key message. "
        "Quote any text exactly. Specify format as 16:9."
    ),
    "diagram": (
        "Task type: Technical Diagram / Flowchart.\n"
        "Include: connection types (arrows, dotted lines, solid lines), node shapes (rounded rectangles, circles), "
        "clear labels in quotes, visual hierarchy, logical flow direction (top-to-bottom or left-to-right), "
        "color coding with hex values for different categories, clean background."
    ),
    "illustration": (
        "Task type: Digital Illustration.\n"
        "Include: art style (flat vector, watercolor, hand-drawn, paper cutout, kawaii, pixel art, "
        "graphic novel, storybook), color palette with hex codes, line weight (thin, medium, bold), "
        "composition and focal point, background treatment."
    ),
    "product": (
        "Task type: Product / Commercial Photography.\n"
        "Include: surface/background (marble, wood, gradient, concrete), "
        "reflections and shadow style (hard, soft, dramatic), composition rule (rule of thirds, centered, diagonal), "
        "props if any, lighting setup (single spotlight, rim light, diffused), material finish (matte, glossy, brushed)."
    ),
    "edit": (
        "Task type: Photo Editing.\n"
        "The user is providing a reference image to edit. Describe the specific changes clearly:\n"
        "- What to add, remove, or modify\n"
        "- Use natural language: 'Remove [X], fill with [Y]' or 'Change lighting to [Z]'\n"
        "- Be precise about positions and colors (hex)\n"
        "- Keep instructions about the reference: 'Keep everything else exactly the same'"
    ),
    "free": (
        "Task type: Free-form Image Generation.\n"
        "Optimize the prompt for best image generation results. "
        "Add sensory details: textures, lighting, composition, atmosphere, mood. "
        "Use specific descriptions instead of vague terms."
    ),
}

# Описания пресетов для фронтенда
PRESET_DEFINITIONS = [
    {"key": "photo", "label": "Фото", "description": "Фотореалистичная съёмка", "requires_reference": False},
    {"key": "infographic", "label": "Инфографика", "description": "Визуализация данных, графики, иконки", "requires_reference": False},
    {"key": "slide", "label": "Слайд", "description": "Слайд презентации 16:9", "requires_reference": False},
    {"key": "diagram", "label": "Схема", "description": "Диаграммы, блок-схемы, флоучарты", "requires_reference": False},
    {"key": "illustration", "label": "Иллюстрация", "description": "Цифровая иллюстрация, арт", "requires_reference": False},
    {"key": "product", "label": "Продуктовое фото", "description": "Продуктовая/коммерческая съёмка", "requires_reference": False},
    {"key": "edit", "label": "Редактирование", "description": "Изменение загруженного фото", "requires_reference": True},
    {"key": "free", "label": "Свободный", "description": "Без пресета, общая оптимизация", "requires_reference": False},
]

SYSTEM_PROMPT = """\
You are an expert prompt engineer for Nano Banana Pro (NBP) — a "thinking" image generation model built on Gemini's reasoning engine.

Your task: Transform the user's Russian description into an optimized English prompt for NBP image generation.

## NBP Golden Rules (MUST follow):

1. **Natural language, not tags.** Write flowing narrative descriptions.
   ❌ "cool, modern, 4k, realistic"
   ✅ "A cinematic wide shot of a futuristic sports car speeding through a rainy Tokyo street at night."

2. **Be specific.** Use hex colors (#0d3d2d not "dark green"), exact positions ("right third, bleeding off edge"), material details ("brushed steel with matte finish").

3. **Provide context.** Tell NBP the purpose — "for a professional cookbook", "for executive strategy deck", "for children's educational app". This shapes the model's decisions.

4. **Quote text exactly.** Any text to render must be in quotes with weight, color, size, and position specified.

5. **No lens parameters.** NBP ignores f-stop, focal length, ISO. Instead describe the visual effect you want.

## Prompt Template:
```
Create a [TYPE] for [CONTEXT].

Background: [Description with hex colors]. [Atmospheric effects].

[HERO ELEMENT]:
[Detailed description — position, lighting, angle]

Typography (if any):
Line 1: "[TEXT]" in [weight], [color], [size], [position]

Mood: [Emotional descriptor]
Format: [ASPECT RATIO]
```

## LANGUAGE RULE (CRITICAL for Cyrillic text quality):
- Write the ENTIRE prompt description in ENGLISH (layout, colors, positions, lighting, composition, style)
- Write ONLY the actual text content that must appear ON the image in Russian, inside double quotes
- Example: 'Title text "КЛУБНИКА: СХЕМА ПОСАДКИ" in bold serif, dark green #1A4A2E, centered upper third'
- Example: 'Label: "Место посадки" in sans-serif, #2C2C2C, below the diagram'
- NEVER write prompt instructions in Russian — only the quoted text that must visually render on the image
- This dramatically improves Cyrillic text rendering quality

## Your rules:
- Output ONLY the optimized English prompt, nothing else
- Keep prompts Standard mode (1-2 paragraphs) unless the description is very complex
- Preserve all specific details from user's description (names, numbers, colors, text)
- ALL Russian text from user's description that should appear on the image MUST be kept in Russian inside double quotes — never translate it to English
- Add visual details the user didn't specify but that improve the result
- Always include Format/aspect ratio (default 1:1 unless context suggests otherwise)
"""


class PromptOptimizationResult(TypedDict):
    optimized_prompt: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


async def optimize_prompt(
    user_description: str,
    preset: str,
    has_reference_image: bool = False,
) -> PromptOptimizationResult:
    """
    Оптимизирует пользовательское описание в NBP-промпт через ChatGPT 5.1 (medium reasoning).

    Args:
        user_description: Описание на русском языке
        preset: Ключ пресета (photo, infographic, slide, etc.)
        has_reference_image: Есть ли загруженный референс

    Returns:
        PromptOptimizationResult с оптимизированным промптом и статистикой
    """
    preset_instruction = PRESET_INSTRUCTIONS.get(preset, PRESET_INSTRUCTIONS["free"])

    user_message = f"Preset: {preset_instruction}\n\n"
    if has_reference_image:
        user_message += "Note: The user has uploaded a reference image that will be sent alongside this prompt to the image model.\n\n"
    user_message += f"User's description (Russian):\n{user_description}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    result = await create_chat_completion_with_usage(
        messages=messages,
        model="chatgpt-5.1",
        reasoning_effort="medium",
    )

    # Стоимость chatgpt-5.1: $2.00/1M input, $8.00/1M output
    cost = (result["prompt_tokens"] / 1_000_000) * 2.00 + (result["completion_tokens"] / 1_000_000) * 8.0

    logger.info(
        f"[prompt_optimizer] Промпт оптимизирован: preset={preset}, "
        f"tokens={result['prompt_tokens']}+{result['completion_tokens']}, cost=${cost:.4f}"
    )

    return {
        "optimized_prompt": result["content"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "cost_usd": cost,
    }
