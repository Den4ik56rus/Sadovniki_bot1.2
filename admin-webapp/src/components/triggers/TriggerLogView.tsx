// TriggerLogView — execution log for a trigger

import { useEffect } from 'react'
import { useTriggerStore } from '@/store/triggerStore'
import type { AutomationTrigger, TriggerLogEntry } from '@/types'

const STATUS_LABELS: Record<TriggerLogEntry['status'], string> = {
  pending: 'Ожидание',
  sent: 'Выполнен',
  failed: 'Ошибка',
  skipped: 'Пропущен',
}

const STATUS_COLORS: Record<TriggerLogEntry['status'], string> = {
  pending: '#C2410C',
  sent: '#15803D',
  failed: '#B91C1C',
  skipped: '#6B7280',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

interface Props {
  trigger: AutomationTrigger
  onEdit: () => void
}

export function TriggerLogView({ trigger, onEdit }: Props) {
  const { triggerLog, fetchTriggerLog } = useTriggerStore()

  useEffect(() => {
    fetchTriggerLog(trigger.id)
  }, [trigger.id, fetchTriggerLog])

  return (
    <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)', padding: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {trigger.name}
          </h3>
          {trigger.description && (
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>
              {trigger.description}
            </p>
          )}
        </div>
        <button
          onClick={onEdit}
          style={{
            padding: '6px 14px',
            background: 'var(--accent-primary)',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Редактировать
        </button>
      </div>

      {/* Info summary */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <InfoChip label="Событие" value={trigger.event_type.replace('_', ' ')} />
        <InfoChip label="Действий" value={String(trigger.actions.length)} />
        {trigger.delay_minutes > 0 && (
          <InfoChip label="Задержка" value={`${trigger.delay_minutes} мин.`} />
        )}
        <InfoChip label="Статус" value={trigger.is_active ? 'Активен' : 'Выключен'} />
      </div>

      {/* Log table */}
      <div style={{ borderTop: '1px solid var(--border-default)', paddingTop: '12px' }}>
        <h4 style={{ margin: '0 0 10px 0', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Лог выполнений
        </h4>

        {triggerLog.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            Пока нет записей
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {triggerLog.map(entry => (
              <LogRow key={entry.id} entry={entry} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function InfoChip({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      padding: '4px 10px',
      background: 'var(--bg-primary)',
      border: '1px solid var(--border-default)',
      borderRadius: '6px',
      fontSize: '12px',
    }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}: </span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

function LogRow({ entry }: { entry: TriggerLogEntry }) {
  const userName = [entry.first_name, entry.last_name].filter(Boolean).join(' ') || entry.username || `#${entry.user_id}`

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '6px 10px',
      background: 'var(--bg-primary)',
      borderRadius: '6px',
      fontSize: '12px',
    }}>
      <span style={{
        padding: '2px 8px',
        borderRadius: '10px',
        fontWeight: 600,
        fontSize: '10px',
        color: 'white',
        background: STATUS_COLORS[entry.status],
        textTransform: 'uppercase',
        flexShrink: 0,
      }}>
        {STATUS_LABELS[entry.status]}
      </span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 500, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {userName}
      </span>
      <span style={{ color: 'var(--text-muted)', marginLeft: 'auto', flexShrink: 0 }}>
        {formatDate(entry.executed_at || entry.send_at)}
      </span>
      {entry.error_message && (
        <span style={{ color: '#B91C1C', fontSize: '11px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={entry.error_message}>
          {entry.error_message}
        </span>
      )}
    </div>
  )
}
