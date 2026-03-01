// Main Tab - Basic client info, status fields, tags (no hero section)
import { useState } from 'react'
import type {
  CrmClientFull,
  ClientPriority,
  ClientTag,
} from '@/types'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
import { TagsSection } from './TagsSection'
import styles from './MainTab.module.css'

interface MainTabProps {
  client: CrmClientFull
  allTags: ClientTag[]
  isUpdating: boolean
  onPriorityChange: (priority: ClientPriority) => void
  onSourceChange: (source: string) => void
  onTagsChange: (tagIds: number[]) => void
  onFunnelVariantChange: (variant: 'A' | 'B') => void
  onQuizAnswersChange: (data: { culture?: string | null; region?: string | null; problem?: string | null }) => void
  onQuizReset: () => void
}

const PRIORITY_LABELS: Record<ClientPriority, string> = {
  low: 'Низкий',
  normal: 'Обычный',
  high: 'Высокий',
  vip: 'VIP',
}

const PRIORITY_COLORS: Record<ClientPriority, string> = {
  low: '#9CA3AF',
  normal: '#6B7280',
  high: '#F59E0B',
  vip: '#FFD700',
}

export function MainTab({
  client,
  allTags,
  isUpdating,
  onPriorityChange,
  onSourceChange,
  onTagsChange,
  onFunnelVariantChange,
  onQuizAnswersChange,
  onQuizReset,
}: MainTabProps) {
  const [editingQuiz, setEditingQuiz] = useState(false)
  const [quizCulture, setQuizCulture] = useState(client.quiz_culture ?? '')
  const [quizRegion, setQuizRegion] = useState(client.quiz_region ?? '')
  const [quizProblem, setQuizProblem] = useState(client.quiz_problem ?? '')

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'd MMM yyyy', { locale: ru })
    } catch {
      return '-'
    }
  }

  const handleSaveQuiz = () => {
    onQuizAnswersChange({
      culture: quizCulture || null,
      region: quizRegion || null,
      problem: quizProblem || null,
    })
    setEditingQuiz(false)
  }

  const handleCancelQuiz = () => {
    setQuizCulture(client.quiz_culture ?? '')
    setQuizRegion(client.quiz_region ?? '')
    setQuizProblem(client.quiz_problem ?? '')
    setEditingQuiz(false)
  }

  const currentVariant = client.funnel_variant ?? 'A'
  const quizDone = !!(client.quiz_culture || client.quiz_region || client.quiz_problem)

  return (
    <div className={styles.content}>
      {/* Base fields */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Основная информация</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Telegram ID</span>
          <span className={styles.fieldValue}>{client.telegram_user_id}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Регион</span>
          <span className={styles.fieldValue}>{client.region || '-'}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>С нами с</span>
          <span className={styles.fieldValue}>{formatDate(client.user_created_at)}</span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Последняя активность</span>
          <span className={styles.fieldValue}>{formatDate(client.last_consultation_at)}</span>
        </div>
      </div>

      {/* Status fields - without funnel selector */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Статус</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Приоритет</span>
          <select
            className={styles.select}
            value={client.priority}
            onChange={(e) => onPriorityChange(e.target.value as ClientPriority)}
            disabled={isUpdating}
            style={{ color: PRIORITY_COLORS[client.priority] }}
          >
            {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Источник</span>
          <input
            type="text"
            className={styles.input}
            value={client.source || ''}
            placeholder="Откуда пришёл"
            onChange={(e) => onSourceChange(e.target.value)}
            disabled={isUpdating}
          />
        </div>
      </div>

      {/* Funnel variant + quiz */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Воронка A/B</h4>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Тип воронки</span>
          <div className={styles.toggleGroup}>
            <button
              className={`${styles.toggleBtn} ${currentVariant === 'A' ? styles.toggleActive : ''}`}
              onClick={() => currentVariant !== 'A' && onFunnelVariantChange('A')}
              disabled={isUpdating}
            >
              A
            </button>
            <button
              className={`${styles.toggleBtn} ${currentVariant === 'B' ? styles.toggleActive : ''}`}
              onClick={() => currentVariant !== 'B' && onFunnelVariantChange('B')}
              disabled={isUpdating}
            >
              B
            </button>
          </div>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Квиз пройден</span>
          <span className={`${styles.quizBadge} ${quizDone ? styles.quizBadgeDone : styles.quizBadgeNo}`}>
            {quizDone ? 'Да' : 'Нет'}
          </span>
        </div>

        {/* Quiz answers block */}
        {currentVariant === 'B' && (
          <div className={styles.quizBlock}>
            {editingQuiz ? (
              <>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Культура</span>
                  <input
                    className={styles.input}
                    value={quizCulture}
                    onChange={(e) => setQuizCulture(e.target.value)}
                    placeholder="Не указано"
                  />
                </div>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Регион</span>
                  <input
                    className={styles.input}
                    value={quizRegion}
                    onChange={(e) => setQuizRegion(e.target.value)}
                    placeholder="Не указано"
                  />
                </div>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Проблема</span>
                  <input
                    className={styles.input}
                    value={quizProblem}
                    onChange={(e) => setQuizProblem(e.target.value)}
                    placeholder="Не указано"
                  />
                </div>
                <div className={styles.quizActions}>
                  <button className={styles.quizSaveBtn} onClick={handleSaveQuiz} disabled={isUpdating}>
                    Сохранить
                  </button>
                  <button className={styles.quizCancelBtn} onClick={handleCancelQuiz}>
                    Отмена
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Культура</span>
                  <span className={styles.quizValue}>{client.quiz_culture || '—'}</span>
                </div>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Регион</span>
                  <span className={styles.quizValue}>{client.quiz_region || '—'}</span>
                </div>
                <div className={styles.quizField}>
                  <span className={styles.quizLabel}>Проблема</span>
                  <span className={styles.quizValue}>{client.quiz_problem || '—'}</span>
                </div>
                <div className={styles.quizActions}>
                  <button className={styles.quizEditBtn} onClick={() => setEditingQuiz(true)}>
                    Редактировать
                  </button>
                  {quizDone && (
                    <button
                      className={styles.quizResetBtn}
                      onClick={onQuizReset}
                      disabled={isUpdating}
                      title="Удалить ответы — при следующем /start пользователь пройдёт квиз заново"
                    >
                      Сбросить
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Referral Program */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Реферальная программа</h4>

        {client.referrer && (
          <div className={styles.field}>
            <span className={styles.fieldLabel}>Приглашён</span>
            <span className={styles.fieldValue}>
              {client.referrer.first_name || client.referrer.username || `#${client.referrer.id}`}
            </span>
          </div>
        )}

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Реф. код</span>
          <span className={styles.fieldValue}>
            {client.referral_code
              ? <code className={styles.referralCode}>{client.referral_code}</code>
              : '-'}
          </span>
        </div>

        <div className={styles.field}>
          <span className={styles.fieldLabel}>Приглашено</span>
          <span className={styles.fieldValue}>{client.referrals_count ?? 0}</span>
        </div>
      </div>

      {/* Tags */}
      <TagsSection
        clientTags={client.tags}
        allTags={allTags}
        onChange={onTagsChange}
      />
    </div>
  )
}
