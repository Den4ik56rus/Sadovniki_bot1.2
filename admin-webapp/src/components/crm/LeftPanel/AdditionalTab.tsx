// Additional Tab - Custom fields & notes
import type { CustomFieldValue, ClientNote } from '@/types'
import { CustomFieldsSection } from './CustomFieldsSection'
import styles from './AdditionalTab.module.css'

interface AdditionalTabProps {
  fields: CustomFieldValue[]
  notes: ClientNote[]
  clientId: number
  onFieldsChange: (fields: Record<number, unknown>) => void
}

export function AdditionalTab({
  fields,
  notes,
  clientId,
  onFieldsChange,
}: AdditionalTabProps) {
  return (
    <div className={styles.content}>
      {/* Custom fields */}
      <CustomFieldsSection
        fields={fields}
        clientId={clientId}
        onChange={onFieldsChange}
      />

      {/* UTM Section - placeholder for future */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>UTM-метки</h4>
        <div className={styles.utmGrid}>
          <div className={styles.utmField}>
            <span className={styles.utmLabel}>UTM Source</span>
            <span className={styles.utmValue}>-</span>
          </div>
          <div className={styles.utmField}>
            <span className={styles.utmLabel}>UTM Medium</span>
            <span className={styles.utmValue}>-</span>
          </div>
          <div className={styles.utmField}>
            <span className={styles.utmLabel}>UTM Campaign</span>
            <span className={styles.utmValue}>-</span>
          </div>
          <div className={styles.utmField}>
            <span className={styles.utmLabel}>UTM Content</span>
            <span className={styles.utmValue}>-</span>
          </div>
          <div className={styles.utmField}>
            <span className={styles.utmLabel}>UTM Term</span>
            <span className={styles.utmValue}>-</span>
          </div>
        </div>
      </div>

      {/* Notes section */}
      <div className={styles.section}>
        <h4 className={styles.sectionTitle}>Заметки о клиенте</h4>
        {notes.length > 0 ? (
          <div className={styles.notesList}>
            {notes.map((note) => (
              <div key={note.id} className={styles.noteItem}>
                <p className={styles.noteText}>{note.text}</p>
                <span className={styles.noteDate}>
                  {new Date(note.created_at).toLocaleDateString('ru-RU')}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.empty}>Нет заметок</p>
        )}
      </div>
    </div>
  )
}
