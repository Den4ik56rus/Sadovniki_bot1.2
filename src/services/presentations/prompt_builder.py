# src/services/presentations/prompt_builder.py

"""
Построение промптов для GPT → разбиение текста на слайды.

GPT получает текст статьи + XML стиль + NBP framework правила →
возвращает JSON массив промптов для каждого слайда.
"""

import json
import logging
from typing import List, TypedDict, Optional

logger = logging.getLogger(__name__)


class SlidePrompt(TypedDict):
    title: str
    nbp_prompt: str
    notes: Optional[str]


SLIDE_SPLIT_SYSTEM_PROMPT = """You are an expert presentation designer specializing in premium visual presentations. Your job is to take article text, a visual style specification, and optionally a slide structure template, then create extremely detailed image generation prompts for Nano Banana Pro (NBP) — an AI image model based on Google Gemini.

CORE RULES:
1. Split the article into logical slides (typically 10-20 slides for a full article)
2. Each slide should convey ONE key idea or section
3. The first slide is always a TITLE slide
4. The last slide is always a SUMMARY/CONCLUSION slide
5. Each NBP prompt must be COMPLETELY self-contained — the image generator has NO memory between slides and NO context about the article
6. Output format: JSON array

═══════════════════════════════════════════════════
NBP PROMPT ENGINEERING RULES (CRITICAL — follow exactly)
═══════════════════════════════════════════════════

The quality of the final slides depends entirely on how detailed and specific your prompts are. Write each prompt as a rich, natural-language description of the complete visual scene.

STRUCTURE each prompt as:
1. Format declaration: "Create a presentation slide image, 16:9 aspect ratio (1920x1080)."
2. Background: FULL description of background — color hex, texture, patterns. REPEAT this in EVERY prompt.
3. Main illustration/visual: Describe the central visual element in detail — style, subject, position, colors.
4. Typography: ALL text that appears on the slide — exact words in quotes, font style (serif/sans-serif), weight (thin/regular/medium/bold/extra bold), approximate size, color hex, position.
5. Layout: Where each element sits — "upper third", "left 60% of frame", "right third with 10% margin", "centered", "bottom strip".
6. Decorative elements: Borders, watermarks, icons, separators from the style.

SPECIFIC RULES:
- Use NATURAL LANGUAGE, not tag soup ("detailed ink pen botanical illustration" NOT "botanical, ink, detailed, 4k")
- Specify EXACT hex colors for EVERY element (background, text, illustrations, borders, decorations)
- Describe illustration style precisely every time: "hand-drawn ink pen illustration with fine line work, stippling for shading, and hatching for depth" — not just "illustration"
- Describe paper/background texture fully in EVERY prompt — NBP forgets between slides
- Position elements explicitly: "upper third centered", "left 60% of the frame", "right column occupying 35% width with 5% right margin"
- Typography must specify: font style (serif like Cormorant Garamond / sans-serif like Source Sans), weight, approximate point size, exact hex color, position
- For bullet points: describe each bullet separately with its marker style (dot, leaf icon, number), text content, and position
- For "wrong/mistake" elements: describe red X marks (thick, bold, slightly hand-drawn), red/warning tinting, visual contrast with "correct" elements
- For measurement annotations: describe dimension lines with arrows, measurement values in bold, label positions
- Include ALL decorative elements from the style on every slide (watermarks, borders, motifs)
- Max 5 text blocks per slide — do not overcrowd
- 15-20 words max per text block — keep text concise

LANGUAGE RULE (CRITICAL for text quality):
- Write the ENTIRE prompt description in ENGLISH (layout, colors, positions, illustration descriptions)
- Write ONLY the actual slide text content in Russian, inside double quotes
- Example: 'Title text "КЛУБНИКА: СХЕМА ПОСАДКИ" in bold serif, dark green #1A4A2E, centered upper third'
- Example: 'Bullet point with leaf marker: "Место: Строго солнце" in sans-serif, #2C2C2C'
- NEVER write prompt instructions in Russian — only the quoted text that must appear on the slide
- This dramatically improves Cyrillic text rendering quality

SLIDE TYPE PATTERNS (use when the style defines these layouts):

COMPARISON (Wrong vs Right):
  Split layout — left half with light red/warning tinted background, right half clean.
  Left: warning header in bold red/brick color, illustration of wrong technique in red/brown ink tones, descriptive labels.
  Right: positive header in bold green, illustration of correct technique in green ink tones, descriptive labels.
  Clear visual divider between halves.

PROCESS FLOW:
  3-4 circles (thin border) arranged horizontally, each containing an illustration.
  Connected by arrows (→) between them. Flow: left to right.
  Labels below each circle: stage name in bold, description in regular weight.

CONTENT + ILLUSTRATION:
  Asymmetric layout — 60% illustration on one side, 40% text content on the other (or 40/60).
  Large detailed illustration. Heading + bullet list with icon markers.
  Bold key terms in accent color, regular descriptions in body color.

MISTAKES PAGE:
  Header with warning color. 2-3 illustrations showing wrong techniques.
  Large bold X marks (thick, slightly rough/hand-drawn) overlaid on each wrong illustration.
  Bullet text below each explaining the mistake.

DATA/MEASUREMENTS:
  Central illustration (top-down or cross-section view).
  Dimension lines with arrows showing distances.
  Measurement values in bold accent color next to arrows.
  Optional bullet list on the side explaining each measurement.

RESULTS/SUCCESS:
  Positive theme — green checkmark or success icon.
  Timeline or checklist format.
  Illustration of healthy/successful outcome.

PRACTICAL TREATMENT / FERTILIZER SLIDE:
  Use when the article mentions specific treatments (fungicides, insecticides, acaricides) or fertilizers (NPK, chelates, microelements).
  Dedicate 1-2 slides SPECIFICALLY to practical application details:
  - Exact product names or active ingredients mentioned in the article
  - Brief application instructions: dosage, timing, method (spraying, soil drench, foliar feed)
  - Important precautions or safety notes
  Layout: Large heading, then a structured list or table-like arrangement with product name in bold accent color, dosage/timing in regular text.
  Each product gets its own visual block with a small icon (spray bottle, granule bag, watering can).
  Do NOT merge treatment details into general slides — give them dedicated space.
  If the article covers BOTH treatments AND fertilizers, use two separate slides: one for protection (fungicides, insecticides), one for nutrition (fertilizers, foliar feeds).

SUMMARY/SYSTEMIC:
  Full-width organic illustration — NOT a temple, NOT columns/pillars, NOT an architectural metaphor.
  Use a BOTANICAL metaphor instead: draw a healthy plant at center with its root system visible in a soil cross-section.
  Around the plant, arrange 4-5 interconnected elements in a circular or radial flow (like a natural cycle):
  soil/drainage, nutrition, disease protection, pest control, agrotechnique (pruning, spacing, watering).
  Connect them with flowing organic arrows or vine-like lines — showing they feed into each other.
  The visual message: the plant thrives when ALL elements work together as a living system.
  Key text message framing: "You are now fixing the consequences (the symptom). But a healthy harvest is built by the WHOLE system working together — nutrition, protection, soil care, proper agrotechnique."
  Avoid rigid geometric structures (columns, grids, temples). Keep it natural, organic, botanical.

═══════════════════════════════════════════════════
TEMPLATE RULES (when a slide structure template is provided)
═══════════════════════════════════════════════════
- Follow the template structure EXACTLY — create slides as specified in each block
- The template defines the number of slides, their purpose, and content structure
- If the template references slide types (comparison_slide, mistakes_slide, etc.), use the corresponding SLIDE TYPE PATTERN above
- Adapt the article content to fill each slide according to the template
- If the template specifies placeholders like [Культура] or [Проблема], replace them with actual content from the article
- Do NOT add extra slides beyond what the template specifies
- Do NOT skip any slides from the template

═══════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════
Output ONLY valid JSON array, no markdown code blocks:
[
  {
    "title": "Slide title (for internal reference, in Russian)",
    "nbp_prompt": "Create a presentation slide image, 16:9 aspect ratio (1920x1080). [FULL detailed prompt following all rules above]",
    "notes": "Speaker notes or additional context (optional)"
  }
]"""


def build_slide_split_prompt(
    source_text: str,
    style_xml: Optional[str] = None,
    template_text: Optional[str] = None,
    extra_instructions: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
) -> list:
    """
    Строит messages для GPT: system + user с текстом, стилем и шаблоном.

    Args:
        source_text: Текст статьи
        style_xml: XML визуального стиля (цвета, шрифты)
        template_text: Текстовый шаблон структуры слайдов
        extra_instructions: Дополнительные инструкции (напр. завершающий слайд)
        custom_system_prompt: Кастомный system prompt (заменяет дефолтный)

    Returns:
        List[dict] — messages для OpenAI API
    """
    user_content = f"ARTICLE TEXT:\n\n{source_text}"

    if style_xml:
        user_content += f"\n\nVISUAL STYLE (XML):\n\n{style_xml}"
    else:
        user_content += "\n\nNo specific style provided. Use a clean, modern, professional design with dark background (#1A2332), white text, and green (#4A7C59) accents."

    if template_text:
        user_content += f"\n\nSLIDE STRUCTURE TEMPLATE:\n\n{template_text}"
        user_content += "\n\nIMPORTANT: Follow the template structure above. Create slides exactly as specified in the template blocks. Adapt the article content to fit each slide's purpose. Replace any placeholders with real content from the article."

    if extra_instructions:
        user_content += extra_instructions

    user_content += "\n\nCreate the slide prompts now. Return ONLY valid JSON array."

    system_prompt = custom_system_prompt if custom_system_prompt else SLIDE_SPLIT_SYSTEM_PROMPT

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def parse_slide_prompts(gpt_response: str) -> List[SlidePrompt]:
    """
    Парсит JSON-ответ GPT в список промптов слайдов.

    Args:
        gpt_response: Строка с JSON массивом от GPT

    Returns:
        List[SlidePrompt]
    """
    # Очищаем от markdown code blocks если есть
    text = gpt_response.strip()
    if text.startswith("```"):
        # Убираем ```json и ```
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"[prompt_builder] Ошибка парсинга JSON от GPT: {e}")
        logger.error(f"[prompt_builder] Ответ: {text[:500]}")
        raise ValueError(f"GPT вернул невалидный JSON: {e}")

    if not isinstance(data, list):
        raise ValueError(f"GPT вернул не массив, а {type(data).__name__}")

    slides: List[SlidePrompt] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(f"[prompt_builder] Слайд {i}: не dict, пропускаем")
            continue

        nbp_prompt = item.get("nbp_prompt", "")
        if not nbp_prompt:
            logger.warning(f"[prompt_builder] Слайд {i}: пустой nbp_prompt, пропускаем")
            continue

        slides.append({
            "title": item.get("title", f"Слайд {i + 1}"),
            "nbp_prompt": nbp_prompt,
            "notes": item.get("notes"),
        })

    logger.info(f"[prompt_builder] Распарсено {len(slides)} слайдов из GPT ответа")
    return slides
