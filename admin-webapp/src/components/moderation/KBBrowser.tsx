import { useEffect, useState, useCallback } from 'react'
import { useModerationStore } from '@/store/moderationStore'
import type { KBEntry } from '@/types'
import styles from './KBBrowser.module.css'

export function KBBrowser() {
  const {
    kbItems, kbTotal, kbSearch, kbCategoryFilter, kbSubcategoryFilter,
    kbPage, isLoadingKB, kbCategories, kbSubcategories,
    fetchKBEntries, setKBSearch, setKBCategoryFilter, setKBSubcategoryFilter,
    fetchKBOptions, updateKBEntry,
  } = useModerationStore()

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<Partial<KBEntry>>({})
  const [searchInput, setSearchInput] = useState(kbSearch)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchKBEntries()
    fetchKBOptions()
  }, [fetchKBEntries, fetchKBOptions])

  const handleSearch = useCallback(() => {
    setKBSearch(searchInput)
    fetchKBEntries()
  }, [searchInput, setKBSearch, fetchKBEntries])

  const handleSearchKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const startEdit = (entry: KBEntry) => {
    setEditingId(entry.id)
    setEditForm({
      question: entry.question || '',
      answer: entry.answer,
      category: entry.category,
      subcategory: entry.subcategory || '',
      is_active: entry.is_active,
    })
  }

  const handleSaveEdit = async () => {
    if (editingId === null) return
    setSaving(true)
    const ok = await updateKBEntry(editingId, editForm)
    if (ok) setEditingId(null)
    setSaving(false)
  }

  const toggleActive = async (entry: KBEntry) => {
    await updateKBEntry(entry.id, { is_active: !entry.is_active })
  }

  const pageSize = 30
  const totalPages = Math.ceil(kbTotal / pageSize)

  return (
    <div className={styles.browser}>
      {/* Filters */}
      <div className={styles.filters}>
        <div className={styles.searchRow}>
          <input
            className={styles.searchInput}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleSearchKey}
            placeholder="Поиск по вопросу или ответу..."
          />
          <button className={styles.searchBtn} onClick={handleSearch}>
            Найти
          </button>
        </div>
        <div className={styles.filterRow}>
          <select
            className={styles.select}
            value={kbCategoryFilter || ''}
            onChange={(e) => setKBCategoryFilter(e.target.value || null)}
          >
            <option value="">Все категории</option>
            {kbCategories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            className={styles.select}
            value={kbSubcategoryFilter || ''}
            onChange={(e) => setKBSubcategoryFilter(e.target.value || null)}
          >
            <option value="">Все подкатегории</option>
            {kbSubcategories.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <span className={styles.totalCount}>
            {isLoadingKB ? '...' : `${kbTotal} записей`}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Категория</th>
              <th>Подкатегория</th>
              <th>Вопрос</th>
              <th>Ответ</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {kbItems.map((entry) => (
              editingId === entry.id ? (
                <tr key={entry.id} className={styles.editRow}>
                  <td>{entry.id}</td>
                  <td>
                    <input
                      className={styles.cellInput}
                      value={editForm.category || ''}
                      onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className={styles.cellInput}
                      value={editForm.subcategory || ''}
                      onChange={(e) => setEditForm({ ...editForm, subcategory: e.target.value })}
                    />
                  </td>
                  <td>
                    <textarea
                      className={styles.cellTextarea}
                      value={editForm.question || ''}
                      onChange={(e) => setEditForm({ ...editForm, question: e.target.value })}
                      rows={3}
                    />
                  </td>
                  <td>
                    <textarea
                      className={styles.cellTextarea}
                      value={editForm.answer || ''}
                      onChange={(e) => setEditForm({ ...editForm, answer: e.target.value })}
                      rows={3}
                    />
                  </td>
                  <td>
                    <label className={styles.toggleLabel}>
                      <input
                        type="checkbox"
                        checked={editForm.is_active ?? true}
                        onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                      />
                      Активна
                    </label>
                  </td>
                  <td>
                    <div className={styles.cellActions}>
                      <button className={styles.saveBtn} onClick={handleSaveEdit} disabled={saving}>
                        Сохранить
                      </button>
                      <button className={styles.cancelBtn} onClick={() => setEditingId(null)}>
                        Отмена
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={entry.id} className={!entry.is_active ? styles.inactive : ''}>
                  <td>{entry.id}</td>
                  <td>{entry.category}</td>
                  <td>{entry.subcategory || '—'}</td>
                  <td className={styles.truncated} title={entry.question || ''}>
                    {(entry.question || '—').slice(0, 60)}
                    {(entry.question || '').length > 60 ? '...' : ''}
                  </td>
                  <td className={styles.truncated} title={entry.answer}>
                    {entry.answer.slice(0, 80)}
                    {entry.answer.length > 80 ? '...' : ''}
                  </td>
                  <td>
                    <button
                      className={`${styles.statusToggle} ${entry.is_active ? styles.active : styles.inactiveBadge}`}
                      onClick={() => toggleActive(entry)}
                    >
                      {entry.is_active ? 'Активна' : 'Неактивна'}
                    </button>
                  </td>
                  <td>
                    <button className={styles.editRowBtn} onClick={() => startEdit(entry)}>
                      Изменить
                    </button>
                  </td>
                </tr>
              )
            ))}
          </tbody>
        </table>

        {!isLoadingKB && kbItems.length === 0 && (
          <div className={styles.empty}>Нет записей</div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            disabled={kbPage === 0}
            onClick={() => {
              useModerationStore.setState({ kbPage: kbPage - 1 })
              fetchKBEntries()
            }}
            className={styles.pageBtn}
          >
            &larr; Назад
          </button>
          <span className={styles.pageInfo}>
            {kbPage + 1} / {totalPages}
          </span>
          <button
            disabled={kbPage >= totalPages - 1}
            onClick={() => {
              useModerationStore.setState({ kbPage: kbPage + 1 })
              fetchKBEntries()
            }}
            className={styles.pageBtn}
          >
            Далее &rarr;
          </button>
        </div>
      )}
    </div>
  )
}
