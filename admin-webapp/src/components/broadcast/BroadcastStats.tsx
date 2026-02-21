// Broadcast Stats — статистика кликов по кнопкам и ответов на опросы

import { useEffect, useState } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import type { StatUser } from '@/types'
import styles from './BroadcastStats.module.css'

interface Props {
  broadcastId: number
  isAnonymousPoll: boolean
  hasPoll: boolean
  hasButtons: boolean
}

export function BroadcastStats({ broadcastId, isAnonymousPoll, hasPoll, hasButtons }: Props) {
  const { stats, statUsers, fetchStats, fetchStatUsers } = useBroadcastStore()
  const [expandedSection, setExpandedSection] = useState<{
    type: 'button' | 'poll'
    key: string
  } | null>(null)

  useEffect(() => {
    fetchStats(broadcastId)
  }, [broadcastId, fetchStats])

  const handleBarClick = (type: 'button' | 'poll', key: string) => {
    if (expandedSection?.type === type && expandedSection?.key === key) {
      setExpandedSection(null)
      return
    }
    setExpandedSection({ type, key })
    fetchStatUsers(broadcastId, type, key)
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
          {isAnonymousPoll && (
            <div className={styles.warning}>
              Анонимный опрос — ответы по пользователям не отслеживаются
            </div>
          )}
          <div className={styles.bars}>
            {stats.poll_answers.map((stat) => (
              <div key={stat.option_index} className={styles.barRow}>
                <button
                  className={styles.barClickable}
                  onClick={() => !isAnonymousPoll && handleBarClick('poll', String(stat.option_index))}
                  disabled={isAnonymousPoll}
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
                {!isAnonymousPoll && expandedSection?.type === 'poll' && expandedSection?.key === String(stat.option_index) && (
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
        <a
          key={u.user_id}
          className={styles.userRow}
          href={`#/funnel/crm/client/${u.user_id}`}
          onClick={(e) => {
            e.preventDefault()
            // Навигация через hash
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
      ))}
    </div>
  )
}
