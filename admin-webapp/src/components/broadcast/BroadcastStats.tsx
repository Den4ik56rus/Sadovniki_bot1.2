// Broadcast Stats — статистика кликов по кнопкам и ответов на опросы

import { useEffect, useState } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { StatUser } from '@/types'
import styles from './BroadcastStats.module.css'

interface Props {
  broadcastId: number
  runId?: number | null
  hasPoll: boolean
  hasButtons: boolean
}

export function BroadcastStats({ broadcastId, runId, hasPoll, hasButtons }: Props) {
  const { stats, statUsers, fetchStats, fetchStatUsers, fetchRunStats, fetchRunStatUsers } = useBroadcastStore()
  const [expandedSection, setExpandedSection] = useState<{
    type: 'button' | 'poll'
    key: string
  } | null>(null)

  useEffect(() => {
    if (runId) {
      fetchRunStats(broadcastId, runId)
    } else {
      fetchStats(broadcastId)
    }
  }, [broadcastId, runId, fetchStats, fetchRunStats])

  const handleBarClick = (type: 'button' | 'poll', key: string) => {
    if (expandedSection?.type === type && expandedSection?.key === key) {
      setExpandedSection(null)
      return
    }
    setExpandedSection({ type, key })
    if (runId) {
      fetchRunStatUsers(broadcastId, runId, type, key)
    } else {
      fetchStatUsers(broadcastId, type, key)
    }
  }

  if (!stats) return null

  const hasButtonStats = hasButtons && stats.button_clicks.length > 0
  const hasPollStats = hasPoll && stats.poll_answers.length > 0
  const nothingToShow = !hasButtonStats && !hasPollStats

  if (nothingToShow) return null

  return (
    <div className={styles.container}>
      <h4 className={styles.title}>Статистика ответов</h4>

      {/* Button click stats */}
      {hasButtonStats && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionLabel}>Кнопки-ответы</span>
            <span className={styles.sectionCount}>
              {stats.total_button_respondents} ответов
            </span>
          </div>
          <div className={styles.bars}>
            {stats.button_clicks.map((stat) => (
              <div key={stat.option_key} className={styles.barRow}>
                <button
                  className={styles.barClickable}
                  onClick={() => handleBarClick('button', stat.option_key)}
                >
                  <div className={styles.barHeader}>
                    <span className={styles.barLabel}>{stat.button_text}</span>
                    <span className={styles.barValue}>
                      {stat.click_count} ({stat.percentage}%)
                    </span>
                  </div>
                  <div className={styles.barTrack}>
                    <div
                      className={styles.barFill}
                      style={{ width: `${Math.max(stat.percentage, 2)}%` }}
                    />
                  </div>
                </button>
                {expandedSection?.type === 'button' && expandedSection?.key === stat.option_key && (
                  <UserList users={statUsers} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Poll answer stats */}
      {hasPollStats && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionLabel}>Опрос</span>
            <span className={styles.sectionCount}>
              {stats.total_poll_respondents} ответов
            </span>
          </div>
          <div className={styles.bars}>
            {stats.poll_answers.map((stat) => (
              <div key={stat.option_index} className={styles.barRow}>
                <button
                  className={styles.barClickable}
                  onClick={() => handleBarClick('poll', String(stat.option_index))}
                >
                  <div className={styles.barHeader}>
                    <span className={styles.barLabel}>{stat.option_text}</span>
                    <span className={styles.barValue}>
                      {stat.answer_count} ({stat.percentage}%)
                    </span>
                  </div>
                  <div className={styles.barTrack}>
                    <div
                      className={`${styles.barFill} ${styles.barFillPoll}`}
                      style={{ width: `${Math.max(stat.percentage, 2)}%` }}
                    />
                  </div>
                </button>
                {expandedSection?.type === 'poll' && expandedSection?.key === String(stat.option_index) && (
                  <UserList users={statUsers} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function UserList({ users }: { users: StatUser[] }) {
  if (users.length === 0) {
    return <div className={styles.userListEmpty}>Нет данных</div>
  }

  return (
    <div className={styles.userList}>
      {users.map((u) => (
        <div key={u.user_id} className={styles.userEntry}>
          <a
            className={styles.userRow}
            href={`#/funnel/crm/client/${u.user_id}`}
            onClick={(e) => {
              e.preventDefault()
              window.location.hash = `/funnel/crm/client/${u.user_id}`
            }}
          >
            <span className={styles.userName}>
              {u.first_name || u.username || `ID: ${u.user_id}`}
            </span>
            {u.username && (
              <span className={styles.userHandle}>@{u.username}</span>
            )}
          </a>
          {u.text_response && (
            <div className={styles.userResponse}>
              <span className={styles.responseIcon}>💬</span>
              <span className={styles.responseText}>{u.text_response}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
