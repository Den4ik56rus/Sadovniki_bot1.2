// Style Editor — modal for managing presentation styles (XML)
import { useState } from 'react'
import { api } from '@/services/api'
import type { PresentationStyle } from '@/types'
import css from './PresentationsPage.module.css'

interface Props {
  styles: PresentationStyle[]
  onClose: () => void
}

const STYLE_PRESETS: Record<string, { name: string; description: string; xml: string }> = {
  botanical_garden: {
    name: 'Ботанический сад (тёмная)',
    description: 'Тёмная тема с природными акцентами',
    xml: `<style version="1.0" name="Ботанический сад">
  <palette>
    <background>#1A2332</background>
    <primary>#4A7C59</primary>
    <secondary>#C75B5B</secondary>
    <text>#F5F0EB</text>
    <accent>#7CB68E</accent>
    <muted>#8B9DAF</muted>
  </palette>
  <typography>
    <heading font="Cormorant Garamond" weight="bold" size="48pt" color="#F5F0EB" />
    <subheading font="Source Sans 3" weight="600" size="28pt" color="#7CB68E" />
    <body font="Source Sans 3" weight="400" size="20pt" color="#F5F0EB" />
    <caption font="Source Sans 3" weight="300" size="14pt" color="#8B9DAF" />
  </typography>
  <layout aspect-ratio="16:9" width="1920" height="1080" margin="60" />
  <decoration>
    <background-pattern type="none" />
    <bullet type="circle" color="#7CB68E" />
  </decoration>
</style>`,
  },
  botanical_blueprint: {
    name: 'Botanical Blueprint',
    description: 'Премиальный стиль ботанического атласа — рисунки пером на миллиметровке',
    xml: `<style version="2.0" name="Botanical Blueprint">
  <description>
    Premium educational style inspired by 19th-century botanical scientific journals.
    Each slide looks like a page from a hand-illustrated botanical atlas on graph paper.
    This style is ideal for agricultural, gardening, and plant care presentations.
  </description>

  <background>
    Cream/ivory paper background (#FDFBF7) with subtle graph paper grid lines in light sage green (#D4E5D0 at 30% opacity).
    The grid should be very subtle — visible but not distracting, like engineering graph paper.
    Paper has a slight warm aged texture, like a premium botanical journal page.
    EVERY slide MUST have this exact same background — consistency is critical.
  </background>

  <palette>
    <primary>#1A4A2E — deep forest green. Use for: headers, main illustrations, positive/correct elements, dimension lines, borders</primary>
    <secondary>#8B3A3A — brick red. Use for: warnings, mistakes, "wrong" illustrations, X marks, error highlights, negative examples</secondary>
    <accent>#4A7C59 — medium green. Use for: subheadings, labels, annotations, secondary text, measurement values</accent>
    <text>#2C2C2C — near-black. Use for: body text, bullet points, descriptions</text>
    <background>#FDFBF7 — cream ivory. Main slide background</background>
    <grid>#D4E5D0 at 30% opacity — graph paper grid lines</grid>
    <warning-bg>#FDF2F2 — very light red tint. Background for "wrong/incorrect" sections</warning-bg>
    <success-bg>#F2FDF5 — very light green tint. Background for "correct" sections</success-bg>
  </palette>

  <typography>
    <heading>Elegant serif font (Cormorant Garamond or Playfair Display style), bold weight, ALL CAPS for main titles, dark green #1A4A2E, very large (48-60pt). Strong visual presence. Positioned in upper portion of slide.</heading>
    <subheading>Same serif font, medium weight, 28-36pt, dark green #1A4A2E. Sentence case. Often accompanied by a thin horizontal rule line below.</subheading>
    <body>Clean sans-serif font (Source Sans 3 or similar), regular weight, 18-22pt, dark #2C2C2C. Generous line spacing (1.5x). Clear and readable.</body>
    <labels>Sans-serif, bold, 16-20pt, medium green #4A7C59. Used for measurement annotations, diagram labels, figure captions.</labels>
    <warning-header>Serif, bold, brick red #8B3A3A, ALL CAPS. Used for "НЕПРАВИЛЬНО", "ОШИБКИ" section headers.</warning-header>
    <watermark>"Botanical Blueprint" text in small serif italic, top-right corner of every slide, light green #7A9B6E at 40% opacity.</watermark>
  </typography>

  <illustration_style>
    Hand-drawn botanical ink pen illustration style. This is the DEFINING feature of this style.
    CRITICAL RULES for every illustration:
    - Detailed fine line work with visible pen strokes, as if drawn with a 0.3mm technical pen
    - Stippling (dots) for light shading and hatching (parallel lines) for darker shading — NO smooth gradient fills
    - Scientific botanical accuracy: visible root systems, leaf vein patterns, crown/rosette detail, soil cross-sections, root hairs
    - Green ink (#1A4A2E) for all correct/positive/educational illustrations
    - Red/brown ink (#8B3A3A) for all incorrect/negative/warning illustrations
    - Tools (pruning shears, watering cans, shovels, rulers, string) drawn in the same ink sketch style
    - NO photographs, NO 3D renders, NO cartoon/kawaii style, NO flat vector art, NO digital gradients
    - Reference aesthetic: classic 19th-century botanical scientific illustrations from herbarium plates and field journals
    - Insects, fungi, diseases drawn with same scientific illustration approach
    - Cross-section views where relevant (soil layers, root depth, planting hole)
  </illustration_style>

  <slide_layouts>
    <title_slide>
      Large ALL CAPS serif title centered in upper third, dark green #1A4A2E.
      Subtitle below in smaller serif, medium weight.
      Two-panel comparison illustration in lower two-thirds: left panel with light red tint background showing wrong approach, right panel on clean cream showing correct approach.
      Decorative vine/leaf border element across the top of the slide.
    </title_slide>

    <comparison_slide>
      Split vertically in half with a thin vertical divider line.
      Left panel: light red background tint (#FDF2F2). "НЕПРАВИЛЬНО" header in bold red serif ALL CAPS. Ink illustration in red/brown tones showing the wrong technique. 2-3 text labels pointing out problems.
      Right panel: clean cream background (#FDFBF7). "ПРАВИЛЬНО" header in bold green serif ALL CAPS. Ink illustration in green tones showing the correct technique. 2-3 text labels highlighting benefits.
    </comparison_slide>

    <process_slide>
      3-4 circles (with thin dark green border) arranged horizontally across the middle of the slide.
      Each circle contains a detailed botanical ink illustration of that stage.
      Circles connected by arrows (→) in dark green.
      Below each circle: stage name in bold green serif, and brief description in regular sans-serif dark text.
      Flow direction: left to right. Title at top.
    </process_slide>

    <content_slide>
      Asymmetric layout — approximately 55% for detailed botanical illustration on one side, 45% for text content on the other.
      The illustration should be large and detailed, the centerpiece of the slide.
      Text side has: heading in bold green serif + bullet list.
      Bullet markers: small leaf (🌿) or berry icons, or bold green dots.
      Key terms in bold green #4A7C59, descriptions in regular dark #2C2C2C.
    </content_slide>

    <mistakes_slide>
      Header "ОШИБКИ [ТЕМА]" in brick red #8B3A3A bold serif ALL CAPS.
      Subheader "Чего нельзя делать" in lighter red.
      2-3 botanical illustrations showing wrong techniques, drawn in red/brown ink.
      Large bold X marks overlaid on each illustration — thick, slightly rough/hand-drawn style red X, not perfect geometric.
      Bullet text below each illustration explaining the specific mistake in dark sans-serif.
    </mistakes_slide>

    <measurements_slide>
      Central botanical illustration (top-down view or cross-section view showing planting layout/spacing).
      Dimension lines with double-headed arrows showing distances between elements.
      Measurement values displayed in bold green: "30 см", "60-90 см", etc.
      Optional bullet list on the right side explaining each measurement standard.
      A small scale reference element (like a shoe or hand for size comparison).
    </measurements_slide>

    <results_slide>
      Positive green theme throughout. Large green checkmark (✓) icon, hand-drawn style.
      Header "КОГДА ЖДАТЬ РЕЗУЛЬТАТ" in green serif.
      Timeline or checklist format with bullet points describing success signs.
      Illustration of a healthy, well-established planting at the side — thriving plants in neat rows.
    </results_slide>

    <summary_slide>
      Architectural illustration frame — classical temple/building structure drawn in green ink (columns, pediment, foundation).
      Key concept labels placed architecturally: foundation = base concept, pillars = supporting practices, roof/pediment = desired outcome.
      Central message about systemic/holistic approach.
      "Botanical Blueprint" watermark more prominent on this slide.
    </summary_slide>
  </slide_layouts>

  <decorative>
    - "Botanical Blueprint" watermark: small serif italic text in top-right corner of every slide, #7A9B6E at 40% opacity
    - Subtle vine/leaf border decoration on title and summary slides (thin green ink botanical border)
    - Small leaf or berry motifs as bullet point markers where appropriate
    - Thin green ruling lines (#4A7C59 at 30% opacity) to separate major sections within a slide
    - Classical ornamental frames (thin ink line borders with small leaf corner decorations) for key messages or callout boxes
    - Graph paper grid visible through all background areas
    - Small "©" or "NotebookLM" style mark replaced with custom brand watermark bottom-right
  </decorative>
</style>`,
  },
}

const DEFAULT_STYLE_XML = STYLE_PRESETS.botanical_garden.xml

export function StyleEditor({ styles: stylesList, onClose }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [styleXml, setStyleXml] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleNew = () => {
    setEditingId(null)
    setName('')
    setDescription('')
    setStyleXml(DEFAULT_STYLE_XML)
  }

  const handleLoadPreset = (presetKey: string) => {
    const preset = STYLE_PRESETS[presetKey]
    if (!preset) return
    setName(preset.name)
    setDescription(preset.description)
    setStyleXml(preset.xml)
  }

  const handleEdit = (style: PresentationStyle) => {
    setEditingId(style.id)
    setName(style.name)
    setDescription(style.description || '')
    setStyleXml(style.style_xml)
  }

  const handleSave = async () => {
    if (!name.trim() || !styleXml.trim()) return
    setIsSaving(true)
    setError(null)

    try {
      if (editingId) {
        await api.updatePresentationStyle(editingId, {
          name: name.trim(),
          description: description.trim() || undefined,
          style_xml: styleXml.trim(),
        })
      } else {
        await api.createPresentationStyle({
          name: name.trim(),
          description: description.trim() || undefined,
          style_xml: styleXml.trim(),
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка сохранения')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить стиль?')) return
    try {
      await api.deletePresentationStyle(id)
      onClose()
    } catch (err) {
      console.error('Failed to delete style:', err)
    }
  }

  // Parse palette from XML for preview
  const paletteColors = (() => {
    const colors: Record<string, string> = {}
    const regex = /<(\w+)>(#[0-9A-Fa-f]{6})<\/\1>/g
    let match
    while ((match = regex.exec(styleXml)) !== null) {
      colors[match[1]] = match[2]
    }
    return colors
  })()

  return (
    <div className={css.modalOverlay} onClick={onClose}>
      <div className={css.modalContent} onClick={e => e.stopPropagation()}>
        <div className={css.modalHeader}>
          <h3>Стили презентаций</h3>
          <button className={css.modalClose} onClick={onClose}>&times;</button>
        </div>

        <div className={css.styleEditorLayout}>
          {/* Left: list of styles */}
          <div className={css.styleList}>
            <button className={css.styleListAdd} onClick={handleNew}>
              + Новый стиль
            </button>
            {stylesList.map(s => (
              <div
                key={s.id}
                className={`${css.styleListItem} ${editingId === s.id ? css.styleListItemActive : ''}`}
              >
                <button className={css.styleListName} onClick={() => handleEdit(s)}>
                  {s.name}
                </button>
                <button className={css.styleListDelete} onClick={() => handleDelete(s.id)}>
                  &times;
                </button>
              </div>
            ))}
            {stylesList.length === 0 && (
              <div className={css.empty}>Стилей нет</div>
            )}
          </div>

          {/* Right: editor */}
          <div className={css.styleForm}>
            {/* Presets */}
            <div className={css.field}>
              <label className={css.label}>Загрузить пресет</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {Object.entries(STYLE_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    className={css.styleListAdd}
                    onClick={() => handleLoadPreset(key)}
                    title={preset.description}
                    style={{ fontSize: '12px', padding: '4px 10px' }}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>

            <div className={css.field}>
              <label className={css.label}>Название</label>
              <input
                className={css.textInput}
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Ботанический сад"
              />
            </div>

            <div className={css.field}>
              <label className={css.label}>Описание</label>
              <input
                className={css.textInput}
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Тёмная тема с природными акцентами"
              />
            </div>

            <div className={css.field}>
              <label className={css.label}>XML стиль</label>
              <textarea
                className={css.textarea}
                value={styleXml}
                onChange={e => setStyleXml(e.target.value)}
                rows={15}
              />
            </div>

            {/* Palette preview */}
            {Object.keys(paletteColors).length > 0 && (
              <div className={css.palettePreview}>
                {Object.entries(paletteColors).map(([name, color]) => (
                  <div key={name} className={css.paletteItem}>
                    <div
                      className={css.paletteColor}
                      style={{ backgroundColor: color }}
                    />
                    <span className={css.paletteName}>{name}</span>
                    <span className={css.paletteHex}>{color}</span>
                  </div>
                ))}
              </div>
            )}

            {error && <div className={css.error}>{error}</div>}

            <button
              className={css.generateButton}
              onClick={handleSave}
              disabled={isSaving || !name.trim() || !styleXml.trim()}
            >
              {isSaving ? 'Сохранение...' : editingId ? 'Обновить' : 'Создать'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
