import { useState, useEffect, useCallback } from 'react'
import { api } from '@/services/api'
import type { SubscriptionPlan, TokenPackage } from '@/types'
import styles from './SettingsPage.module.css'

interface TaskConfig {
  model: string
  temperature: number | null
  reasoning_effort: string | null
  env_model: string
  env_temp: number | null
  label: string
}

interface LlmConfig {
  models: string[]
  tasks: Record<string, TaskConfig>
}

interface TaskState {
  model: string
  tempEnabled: boolean
  tempValue: number
  reasoning: string  // 'none' | 'low' | 'medium' | 'high'
  saved: boolean
}

const TASK_ORDER = ['consultation', 'classification', 'complexity', 'article', 'utility', 'guide'] as const

const REASONING_OPTIONS = [
  { value: 'none', label: 'Выкл' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]

export function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [ragEnabled, setRagEnabled] = useState(true)
  const [models, setModels] = useState<string[]>([])
  const [taskStates, setTaskStates] = useState<Record<string, TaskState>>({})
  const [taskLabels, setTaskLabels] = useState<Record<string, string>>({})
  const [envDefaults, setEnvDefaults] = useState<Record<string, { model: string; temp: number | null }>>({})
  const [saving, setSaving] = useState<Record<string, boolean>>({})

  // Pricing state
  const [plans, setPlans] = useState<SubscriptionPlan[]>([])
  const [packages, setPackages] = useState<TokenPackage[]>([])
  const [trialQuestions, setTrialQuestions] = useState(3)
  const [trialSaved, setTrialSaved] = useState(false)
  const [planEdits, setPlanEdits] = useState<Record<number, Partial<SubscriptionPlan>>>({})
  const [packageEdits, setPackageEdits] = useState<Record<number, Partial<TokenPackage>>>({})
  const [planSaving, setPlanSaving] = useState<Record<number, boolean>>({})
  const [packageSaving, setPackageSaving] = useState<Record<number, boolean>>({})
  const [planSaved, setPlanSaved] = useState<Record<number, boolean>>({})
  const [packageSaved, setPackageSaved] = useState<Record<number, boolean>>({})
  // Create new plan/package
  const [showNewPlan, setShowNewPlan] = useState(false)
  const [showNewPackage, setShowNewPackage] = useState(false)
  const [newPlan, setNewPlan] = useState({ name: '', price_rub: 0, tokens_included: 0, duration_days: 30 })
  const [newPackage, setNewPackage] = useState({ name: '', price_rub: 0, tokens_amount: 0 })
  const [creatingPlan, setCreatingPlan] = useState(false)
  const [creatingPackage, setCreatingPackage] = useState(false)

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [settingsRes, llmRes, plansRes, packagesRes] = await Promise.all([
        api.getSettings(),
        fetchLlmConfig(),
        api.getSubscriptionPlans(),
        api.getTokenPackages(),
      ])

      // RAG toggle
      const ragSetting = settingsRes.settings.find(s => s.key === 'rag_enabled')
      setRagEnabled(ragSetting?.value === 'true')

      // Trial questions
      const trialSetting = settingsRes.settings.find(s => s.key === 'trial_questions')
      if (trialSetting) setTrialQuestions(parseInt(trialSetting.value) || 3)

      // LLM config
      setModels(llmRes.models)

      const states: Record<string, TaskState> = {}
      const labels: Record<string, string> = {}
      const defaults: Record<string, { model: string; temp: number | null }> = {}

      for (const [task, config] of Object.entries(llmRes.tasks)) {
        states[task] = {
          model: config.model,
          tempEnabled: config.temperature !== null,
          tempValue: config.temperature ?? 0.4,
          reasoning: config.reasoning_effort || 'none',
          saved: false,
        }
        labels[task] = config.label
        defaults[task] = { model: config.env_model, temp: config.env_temp }
      }

      setTaskStates(states)
      setTaskLabels(labels)
      setEnvDefaults(defaults)

      // Pricing
      setPlans(plansRes.plans)
      setPackages(packagesRes.packages)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки настроек')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConfig()
  }, [loadConfig])

  const handleRagToggle = async () => {
    const newValue = !ragEnabled
    setRagEnabled(newValue)
    try {
      await api.updateSetting('rag_enabled', String(newValue))
    } catch {
      setRagEnabled(!newValue) // revert
    }
  }

  const updateTaskState = (task: string, update: Partial<TaskState>) => {
    setTaskStates(prev => ({
      ...prev,
      [task]: { ...prev[task], ...update, saved: false },
    }))
  }

  const saveTask = async (task: string) => {
    const state = taskStates[task]
    if (!state) return

    setSaving(prev => ({ ...prev, [task]: true }))
    try {
      await api.updateSetting(`model_${task}`, state.model)
      await api.updateSetting(
        `temp_${task}`,
        state.tempEnabled ? String(state.tempValue) : ''
      )
      await api.updateSetting(
        `reasoning_${task}`,
        state.reasoning
      )
      setTaskStates(prev => ({
        ...prev,
        [task]: { ...prev[task], saved: true },
      }))
      setTimeout(() => {
        setTaskStates(prev => ({
          ...prev,
          [task]: { ...prev[task], saved: false },
        }))
      }, 2000)
    } catch (e) {
      console.error(`Ошибка сохранения ${task}:`, e)
    } finally {
      setSaving(prev => ({ ...prev, [task]: false }))
    }
  }

  // =========================================================================
  // Pricing handlers
  // =========================================================================

  const saveTrialQuestions = async (value: number) => {
    setTrialQuestions(value)
    try {
      await api.updateSetting('trial_questions', String(value))
      setTrialSaved(true)
      setTimeout(() => setTrialSaved(false), 2000)
    } catch (e) {
      console.error('Ошибка сохранения trial_questions:', e)
    }
  }

  const getPlanValue = <K extends keyof SubscriptionPlan>(plan: SubscriptionPlan, key: K): SubscriptionPlan[K] => {
    const edit = planEdits[plan.id]
    if (edit && key in edit) return edit[key] as SubscriptionPlan[K]
    return plan[key]
  }

  const getPackageValue = <K extends keyof TokenPackage>(pkg: TokenPackage, key: K): TokenPackage[K] => {
    const edit = packageEdits[pkg.id]
    if (edit && key in edit) return edit[key] as TokenPackage[K]
    return pkg[key]
  }

  const updatePlanEdit = (planId: number, update: Partial<SubscriptionPlan>) => {
    setPlanEdits(prev => ({
      ...prev,
      [planId]: { ...prev[planId], ...update },
    }))
    setPlanSaved(prev => ({ ...prev, [planId]: false }))
  }

  const updatePackageEdit = (pkgId: number, update: Partial<TokenPackage>) => {
    setPackageEdits(prev => ({
      ...prev,
      [pkgId]: { ...prev[pkgId], ...update },
    }))
    setPackageSaved(prev => ({ ...prev, [pkgId]: false }))
  }

  const savePlan = async (planId: number) => {
    const edit = planEdits[planId]
    if (!edit || Object.keys(edit).length === 0) return

    setPlanSaving(prev => ({ ...prev, [planId]: true }))
    try {
      const result = await api.updateSubscriptionPlan(planId, edit)
      setPlans(prev => prev.map(p => p.id === planId ? result.plan : p))
      setPlanEdits(prev => {
        const next = { ...prev }
        delete next[planId]
        return next
      })
      setPlanSaved(prev => ({ ...prev, [planId]: true }))
      setTimeout(() => setPlanSaved(prev => ({ ...prev, [planId]: false })), 2000)
    } catch (e) {
      console.error(`Ошибка сохранения плана ${planId}:`, e)
    } finally {
      setPlanSaving(prev => ({ ...prev, [planId]: false }))
    }
  }

  const savePackage = async (pkgId: number) => {
    const edit = packageEdits[pkgId]
    if (!edit || Object.keys(edit).length === 0) return

    setPackageSaving(prev => ({ ...prev, [pkgId]: true }))
    try {
      const result = await api.updateTokenPackage(pkgId, edit)
      setPackages(prev => prev.map(p => p.id === pkgId ? result.package : p))
      setPackageEdits(prev => {
        const next = { ...prev }
        delete next[pkgId]
        return next
      })
      setPackageSaved(prev => ({ ...prev, [pkgId]: true }))
      setTimeout(() => setPackageSaved(prev => ({ ...prev, [pkgId]: false })), 2000)
    } catch (e) {
      console.error(`Ошибка сохранения пакета ${pkgId}:`, e)
    } finally {
      setPackageSaving(prev => ({ ...prev, [pkgId]: false }))
    }
  }

  const createPlan = async () => {
    if (!newPlan.name || !newPlan.price_rub || !newPlan.tokens_included) return
    setCreatingPlan(true)
    try {
      const result = await api.createSubscriptionPlan(newPlan)
      setPlans(prev => [...prev, result.plan])
      setNewPlan({ name: '', price_rub: 0, tokens_included: 0, duration_days: 30 })
      setShowNewPlan(false)
    } catch (e) {
      console.error('Ошибка создания плана:', e)
    } finally {
      setCreatingPlan(false)
    }
  }

  const createPackage = async () => {
    if (!newPackage.name || !newPackage.price_rub || !newPackage.tokens_amount) return
    setCreatingPackage(true)
    try {
      const result = await api.createTokenPackage(newPackage)
      setPackages(prev => [...prev, result.package])
      setNewPackage({ name: '', price_rub: 0, tokens_amount: 0 })
      setShowNewPackage(false)
    } catch (e) {
      console.error('Ошибка создания пакета:', e)
    } finally {
      setCreatingPackage(false)
    }
  }

  // =========================================================================
  // Render
  // =========================================================================

  if (loading) {
    return <div className={styles.loading}>Загрузка настроек...</div>
  }

  if (error) {
    return <div className={styles.error}>{error}</div>
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <span className={styles.headerIcon}>&#x2699;&#xFE0F;</span>
        <h1 className={styles.headerTitle}>Настройки</h1>
      </div>

      {/* RAG Toggle */}
      <div className={styles.toggleSection}>
        <div className={styles.toggleInfo}>
          <span className={styles.toggleLabel}>RAG-система</span>
          <span className={styles.toggleDescription}>
            Поиск по базе знаний для консультаций
          </span>
        </div>
        <label className={styles.switch}>
          <input
            type="checkbox"
            checked={ragEnabled}
            onChange={handleRagToggle}
          />
          <span className={styles.slider} />
        </label>
      </div>

      {/* LLM Section */}
      <h2 className={styles.sectionTitle}>Модели и Temperature</h2>

      <div className={styles.cardsGrid}>
        {TASK_ORDER.map(task => {
          const state = taskStates[task]
          if (!state) return null
          const env = envDefaults[task]
          const reasoningActive = state.reasoning !== 'none'

          return (
            <div key={task} className={styles.card}>
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>{taskLabels[task]}</span>
                <span className={state.saved ? styles.savedBadge : styles.savedBadgeHidden}>
                  Сохранено
                </span>
              </div>

              {/* Model Select */}
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Модель</label>
                <select
                  className={styles.select}
                  value={state.model}
                  onChange={e => updateTaskState(task, { model: e.target.value })}
                >
                  {models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                {env && (
                  <span className={styles.envHint}>
                    .env: {env.model}
                  </span>
                )}
              </div>

              {/* Reasoning Effort */}
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Reasoning</label>
                <div className={styles.reasoningRow}>
                  {REASONING_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      className={
                        state.reasoning === opt.value
                          ? styles.reasoningButtonActive
                          : styles.reasoningButton
                      }
                      onClick={() => updateTaskState(task, { reasoning: opt.value })}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {reasoningActive && (
                  <span className={styles.reasoningHint}>
                    Temperature отключается при активном reasoning
                  </span>
                )}
              </div>

              {/* Temperature */}
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Temperature</label>
                <div className={styles.tempRow}>
                  <label className={styles.tempCheckbox}>
                    <input
                      type="checkbox"
                      checked={state.tempEnabled}
                      disabled={reasoningActive}
                      onChange={e => updateTaskState(task, { tempEnabled: e.target.checked })}
                    />
                    Вкл
                  </label>
                  <div className={styles.sliderContainer}>
                    <input
                      type="range"
                      className={styles.rangeSlider}
                      min="0"
                      max="1"
                      step="0.1"
                      value={state.tempValue}
                      disabled={!state.tempEnabled || reasoningActive}
                      onChange={e => updateTaskState(task, { tempValue: parseFloat(e.target.value) })}
                    />
                    <span className={state.tempEnabled && !reasoningActive ? styles.tempValue : styles.tempValueDisabled}>
                      {state.tempEnabled && !reasoningActive ? state.tempValue.toFixed(1) : '—'}
                    </span>
                  </div>
                </div>
                {env && (
                  <span className={styles.envHint}>
                    .env: {env.temp !== null ? env.temp : 'отключено'}
                  </span>
                )}
              </div>

              {/* Save */}
              <button
                className={styles.saveButton}
                onClick={() => saveTask(task)}
                disabled={saving[task]}
              >
                {saving[task] ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )
        })}
      </div>

      {/* ================================================================= */}
      {/* PRICING SECTION */}
      {/* ================================================================= */}

      <h2 className={styles.sectionTitle}>Тарифы и цены</h2>

      {/* Trial Questions */}
      <div className={styles.trialRow}>
        <div className={styles.toggleInfo}>
          <span className={styles.toggleLabel}>Бесплатные токены</span>
          <span className={styles.toggleDescription}>
            Количество токенов для новых пользователей
          </span>
        </div>
        <div className={styles.inputRow}>
          <input
            type="number"
            className={styles.trialInput}
            value={trialQuestions}
            min={0}
            max={100}
            onChange={e => setTrialQuestions(parseInt(e.target.value) || 0)}
            onBlur={e => saveTrialQuestions(parseInt(e.target.value) || 0)}
          />
          <span className={trialSaved ? styles.savedBadge : styles.savedBadgeHidden}>
            Сохранено
          </span>
        </div>
      </div>

      {/* Token Packages */}
      <h3 className={styles.pricingSubtitle}>Разовые покупки</h3>
      <div className={styles.pricingList}>
        {packages.map(pkg => {
          const isActive = getPackageValue(pkg, 'is_active')
          return (
            <div
              key={pkg.id}
              className={isActive ? styles.pricingCard : styles.pricingCardInactive}
            >
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>
                  {getPackageValue(pkg, 'name') || pkg.name}
                </span>
                <div className={styles.inputRow}>
                  <span className={packageSaved[pkg.id] ? styles.savedBadge : styles.savedBadgeHidden}>
                    Сохранено
                  </span>
                  <label className={styles.switch}>
                    <input
                      type="checkbox"
                      checked={isActive as boolean}
                      onChange={e => updatePackageEdit(pkg.id, { is_active: e.target.checked })}
                    />
                    <span className={styles.slider} />
                  </label>
                </div>
              </div>

              <div className={styles.cardsGrid}>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Название</label>
                  <input
                    type="text"
                    className={styles.textInput}
                    value={getPackageValue(pkg, 'name') as string}
                    onChange={e => updatePackageEdit(pkg.id, { name: e.target.value })}
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Цена</label>
                  <div className={styles.inputRow}>
                    <input
                      type="number"
                      className={styles.numberInput}
                      value={getPackageValue(pkg, 'price_rub') as number}
                      min={0}
                      onChange={e => updatePackageEdit(pkg.id, { price_rub: parseFloat(e.target.value) || 0 })}
                    />
                    <span className={styles.inputSuffix}>&#8381;</span>
                  </div>
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Вопросов</label>
                  <input
                    type="number"
                    className={styles.numberInput}
                    value={getPackageValue(pkg, 'tokens_amount') as number}
                    min={1}
                    onChange={e => updatePackageEdit(pkg.id, { tokens_amount: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>

              <button
                className={styles.saveButton}
                onClick={() => savePackage(pkg.id)}
                disabled={packageSaving[pkg.id] || !packageEdits[pkg.id]}
              >
                {packageSaving[pkg.id] ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )
        })}

        {/* Create new package */}
        {showNewPackage ? (
          <div className={styles.pricingCard}>
            <span className={styles.cardTitle}>Новый пакет</span>
            <div className={styles.cardsGrid}>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Название</label>
                <input
                  type="text"
                  className={styles.textInput}
                  value={newPackage.name}
                  placeholder="Например: 10 токенов"
                  onChange={e => setNewPackage(p => ({ ...p, name: e.target.value }))}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Цена</label>
                <div className={styles.inputRow}>
                  <input
                    type="number"
                    className={styles.numberInput}
                    value={newPackage.price_rub || ''}
                    min={0}
                    placeholder="400"
                    onChange={e => setNewPackage(p => ({ ...p, price_rub: parseFloat(e.target.value) || 0 }))}
                  />
                  <span className={styles.inputSuffix}>&#8381;</span>
                </div>
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Вопросов</label>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={newPackage.tokens_amount || ''}
                  min={1}
                  placeholder="10"
                  onChange={e => setNewPackage(p => ({ ...p, tokens_amount: parseInt(e.target.value) || 0 }))}
                />
              </div>
            </div>
            <div className={styles.cardActions}>
              <button
                className={styles.reasoningButton}
                onClick={() => { setShowNewPackage(false); setNewPackage({ name: '', price_rub: 0, tokens_amount: 0 }) }}
              >
                Отмена
              </button>
              <button
                className={styles.saveButton}
                onClick={createPackage}
                disabled={creatingPackage || !newPackage.name || !newPackage.price_rub || !newPackage.tokens_amount}
              >
                {creatingPackage ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        ) : (
          <button className={styles.addButton} onClick={() => setShowNewPackage(true)}>
            + Добавить пакет
          </button>
        )}
      </div>

      {/* Subscription Plans */}
      <h3 className={styles.pricingSubtitle}>Подписки</h3>
      <div className={styles.pricingList}>
        {plans.map(plan => {
          const isActive = getPlanValue(plan, 'is_active')
          return (
            <div
              key={plan.id}
              className={isActive ? styles.pricingCard : styles.pricingCardInactive}
            >
              <div className={styles.cardHeader}>
                <span className={styles.cardTitle}>
                  {getPlanValue(plan, 'name') || plan.name}
                </span>
                <div className={styles.inputRow}>
                  <span className={planSaved[plan.id] ? styles.savedBadge : styles.savedBadgeHidden}>
                    Сохранено
                  </span>
                  <label className={styles.switch}>
                    <input
                      type="checkbox"
                      checked={isActive as boolean}
                      onChange={e => updatePlanEdit(plan.id, { is_active: e.target.checked })}
                    />
                    <span className={styles.slider} />
                  </label>
                </div>
              </div>

              <div className={styles.cardsGrid}>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Название</label>
                  <input
                    type="text"
                    className={styles.textInput}
                    value={getPlanValue(plan, 'name') as string}
                    onChange={e => updatePlanEdit(plan.id, { name: e.target.value })}
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Цена</label>
                  <div className={styles.inputRow}>
                    <input
                      type="number"
                      className={styles.numberInput}
                      value={getPlanValue(plan, 'price_rub') as number}
                      min={0}
                      onChange={e => updatePlanEdit(plan.id, { price_rub: parseFloat(e.target.value) || 0 })}
                    />
                    <span className={styles.inputSuffix}>&#8381;/мес</span>
                  </div>
                </div>
                <div className={styles.field}>
                  <label className={styles.fieldLabel}>Вопросов/мес</label>
                  <input
                    type="number"
                    className={styles.numberInput}
                    value={getPlanValue(plan, 'tokens_included') as number}
                    min={1}
                    onChange={e => updatePlanEdit(plan.id, { tokens_included: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>

              <button
                className={styles.saveButton}
                onClick={() => savePlan(plan.id)}
                disabled={planSaving[plan.id] || !planEdits[plan.id]}
              >
                {planSaving[plan.id] ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          )
        })}

        {/* Create new plan */}
        {showNewPlan ? (
          <div className={styles.pricingCard}>
            <span className={styles.cardTitle}>Новая подписка</span>
            <div className={styles.cardsGrid}>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Название</label>
                <input
                  type="text"
                  className={styles.textInput}
                  value={newPlan.name}
                  placeholder="Например: Про"
                  onChange={e => setNewPlan(p => ({ ...p, name: e.target.value }))}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Цена</label>
                <div className={styles.inputRow}>
                  <input
                    type="number"
                    className={styles.numberInput}
                    value={newPlan.price_rub || ''}
                    min={0}
                    placeholder="1000"
                    onChange={e => setNewPlan(p => ({ ...p, price_rub: parseFloat(e.target.value) || 0 }))}
                  />
                  <span className={styles.inputSuffix}>&#8381;/мес</span>
                </div>
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>Вопросов/мес</label>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={newPlan.tokens_included || ''}
                  min={1}
                  placeholder="50"
                  onChange={e => setNewPlan(p => ({ ...p, tokens_included: parseInt(e.target.value) || 0 }))}
                />
              </div>
            </div>
            <div className={styles.cardActions}>
              <button
                className={styles.reasoningButton}
                onClick={() => { setShowNewPlan(false); setNewPlan({ name: '', price_rub: 0, tokens_included: 0, duration_days: 30 }) }}
              >
                Отмена
              </button>
              <button
                className={styles.saveButton}
                onClick={createPlan}
                disabled={creatingPlan || !newPlan.name || !newPlan.price_rub || !newPlan.tokens_included}
              >
                {creatingPlan ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        ) : (
          <button className={styles.addButton} onClick={() => setShowNewPlan(true)}>
            + Добавить подписку
          </button>
        )}
      </div>
    </div>
  )
}

// Fetch LLM config from API
async function fetchLlmConfig(): Promise<LlmConfig> {
  const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'
  const response = await fetch(`${API_BASE}/settings/llm`, {
    headers: {
      'Content-Type': 'application/json',
      'ngrok-skip-browser-warning': 'true',
    },
  })
  if (!response.ok) {
    throw new Error(`Ошибка загрузки LLM конфигурации: ${response.status}`)
  }
  return response.json()
}
