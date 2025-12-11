import { useEffect } from 'react'
import { useUsersStore, useUIStore, useCurrencyStore } from '@/store'
import { formatDistanceToNow } from 'date-fns'
import { ru } from 'date-fns/locale'
import styles from './UserList.module.css'

export function UserList() {
  const { users, isLoading, error, searchQuery, fetchUsers, setSearchQuery } = useUsersStore()
  const { selectedUserId, selectUser } = useUIStore()
  const { usdRate, fetchRate } = useCurrencyStore()

  useEffect(() => {
    fetchUsers()
    fetchRate()
  }, [fetchUsers, fetchRate])

  const toRub = (usd: number) => (usd * usdRate).toFixed(2)

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value
    setSearchQuery(query)
    fetchUsers(query)
  }

  if (error) {
    return <div className={styles.error}>Ошибка: {error}</div>
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Пользователи</h2>
        <input
          type="text"
          placeholder="Поиск по имени..."
          value={searchQuery}
          onChange={handleSearch}
          className={styles.search}
        />
      </div>

      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : (
        <div className={styles.list}>
          {users.map((user) => (
            <div
              key={user.id}
              className={`${styles.userCard} ${selectedUserId === user.id ? styles.selected : ''}`}
              onClick={() => selectUser(user.id)}
            >
              <div className={styles.userInfo}>
                <div className={styles.userName}>
                  {user.first_name || user.username || `User #${user.telegram_user_id}`}
                </div>
                {user.username && (
                  <div className={styles.userHandle}>@{user.username}</div>
                )}
              </div>
              <div className={styles.userStats}>
                <div className={styles.stat}>
                  <span className={styles.statValue}>{user.total_consultations}</span>
                  <span className={styles.statLabel}>консульт.</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statValue}>
                    {user.total_tokens.toLocaleString()}
                  </span>
                  <span className={styles.statLabel}>токенов</span>
                </div>
                <div className={styles.stat} title={`$${user.total_cost_usd.toFixed(4)}`}>
                  <span className={`${styles.statValue} ${styles.cost}`}>
                    {toRub(user.total_cost_usd)} ₽
                  </span>
                </div>
              </div>
              {user.last_consultation_at && (
                <div className={styles.lastActive}>
                  {formatDistanceToNow(new Date(user.last_consultation_at), {
                    addSuffix: true,
                    locale: ru,
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
