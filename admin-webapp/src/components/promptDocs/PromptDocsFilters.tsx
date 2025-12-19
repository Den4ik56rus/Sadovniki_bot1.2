// Фильтры для промт-документов: Культура → Подкультура → Тип работ

import { usePromptDocumentStore } from '@/store/promptDocumentStore'
import styles from './PromptDocsFilters.module.css'

export function PromptDocsFilters() {
  const {
    cultures,
    subcultures,
    workTypes,
    filters,
    setFilters,
    clearFilters,
  } = usePromptDocumentStore()

  const hasFilters = filters.culture_id || filters.subculture_id || filters.work_type_id

  return (
    <div className={styles.filters}>
      {/* Culture filter */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Культура</label>
        <select
          className={styles.select}
          value={filters.culture_id || ''}
          onChange={(e) => setFilters({ culture_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Все культуры</option>
          {cultures.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Subculture filter (only if culture selected and has subcultures) */}
      {filters.culture_id && subcultures.length > 0 && (
        <div className={styles.filterGroup}>
          <label className={styles.label}>Подкультура</label>
          <select
            className={styles.select}
            value={filters.subculture_id || ''}
            onChange={(e) => setFilters({ subculture_id: e.target.value ? Number(e.target.value) : undefined })}
          >
            <option value="">Все подкультуры</option>
            {subcultures.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Work type filter */}
      <div className={styles.filterGroup}>
        <label className={styles.label}>Тип работ</label>
        <select
          className={styles.select}
          value={filters.work_type_id || ''}
          onChange={(e) => setFilters({ work_type_id: e.target.value ? Number(e.target.value) : undefined })}
        >
          <option value="">Все типы работ</option>
          {workTypes.map((w) => (
            <option key={w.id} value={w.id}>{w.name}</option>
          ))}
        </select>
      </div>

      {/* Clear filters button */}
      {hasFilters && (
        <button className={styles.clearBtn} onClick={clearFilters}>
          Сбросить фильтры
        </button>
      )}
    </div>
  )
}
