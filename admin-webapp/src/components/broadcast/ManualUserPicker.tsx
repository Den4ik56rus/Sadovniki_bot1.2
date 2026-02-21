// Manual User Picker — ручной выбор пользователей для рассылки

import { useEffect, useState, useMemo } from 'react'
import { useBroadcastStore } from '@/store/broadcastStore'
import styles from './ManualUserPicker.module.css'

interface Props {
  selectedIds: number[]
  onSelectedChange: (ids: number[]) => void
}

export function ManualUserPicker({ selectedIds, onSelectedChange }: Props) {
  const { users, fetchUsers } = useBroadcastStore()
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (users.length === 0) {
      fetchUsers()
    }
  }, [users.length, fetchUsers])

  const filteredUsers = useMemo(() => {
    if (!search.trim()) return users
    const q = search.toLowerCase()
    return users.filter((u) =>
      (u.username && u.username.toLowerCase().includes(q)) ||
      (u.first_name && u.first_name.toLowerCase().includes(q)) ||
      (u.last_name && u.last_name.toLowerCase().includes(q)) ||
      String(u.telegram_user_id).includes(q)
    )
  }, [users, search])

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const toggleUser = (userId: number) => {
    if (selectedSet.has(userId)) {
      onSelectedChange(selectedIds.filter((id) => id !== userId))
    } else {
      onSelectedChange([...selectedIds, userId])
    }
  }

  const selectAll = () => {
    const allIds = filteredUsers.map((u) => u.id)
    const merged = new Set([...selectedIds, ...allIds])
    onSelectedChange(Array.from(merged))
  }

  const deselectAll = () => {
    const filteredSet = new Set(filteredUsers.map((u) => u.id))
    onSelectedChange(selectedIds.filter((id) => !filteredSet.has(id)))
  }

  const displayName = (user: { username: string | null; first_name: string | null; last_name: string | null }) => {
    if (user.first_name || user.last_name) {
      return `${user.first_name || ''} ${user.last_name || ''}`.trim()
    }
    return user.username || 'Без имени'
  }

  return (
    <div className={styles.container}>
      {/* Search */}
      <input
        className={styles.search}
        type="text"
        placeholder="Поиск по имени или username..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarButtons}>
          <button className={styles.toolbarBtn} onClick={selectAll}>
            Выбрать всех
          </button>
          <button className={styles.toolbarBtn} onClick={deselectAll}>
            Снять все
          </button>
        </div>
        <span className={styles.selectedCount}>
          Выбрано: {selectedIds.length}
        </span>
      </div>

      {/* User list */}
      <div className={styles.list}>
        {filteredUsers.length === 0 ? (
          <div className={styles.emptyList}>
            {users.length === 0 ? 'Загрузка пользователей...' : 'Ничего не найдено'}
          </div>
        ) : (
          filteredUsers.map((user) => (
            <label key={user.id} className={styles.userRow}>
              <input
                type="checkbox"
                checked={selectedSet.has(user.id)}
                onChange={() => toggleUser(user.id)}
              />
              <span className={styles.userName}>{displayName(user)}</span>
              {user.username && (
                <span className={styles.userHandle}>@{user.username}</span>
              )}
            </label>
          ))
        )}
      </div>
    </div>
  )
}
