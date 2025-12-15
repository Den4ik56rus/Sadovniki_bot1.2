// Custom Fields Section Component
import { useState } from 'react'
import type { CustomFieldValue, CustomFieldType } from '@/types'
import { api } from '@/services/api'
import styles from './CustomFieldsSection.module.css'

interface CustomFieldsSectionProps {
  fields: CustomFieldValue[]
  clientId: number
  onChange: (fields: Record<number, unknown>) => void
}

export function CustomFieldsSection({ fields, clientId, onChange }: CustomFieldsSectionProps) {
  const [editingField, setEditingField] = useState<number | null>(null)
  const [editValue, setEditValue] = useState<unknown>(null)
  const [isAddingField, setIsAddingField] = useState(false)
  const [newFieldName, setNewFieldName] = useState('')
  const [newFieldType, setNewFieldType] = useState<CustomFieldType>('text')
  const [newFieldOptions, setNewFieldOptions] = useState('')

  const handleStartEdit = (field: CustomFieldValue) => {
    setEditingField(field.id)
    setEditValue(field.value)
  }

  const handleSave = (fieldId: number) => {
    onChange({ [fieldId]: editValue })
    setEditingField(null)
    setEditValue(null)
  }

  const handleCancel = () => {
    setEditingField(null)
    setEditValue(null)
  }

  const handleCreateField = async () => {
    if (!newFieldName.trim()) return

    try {
      const options = (newFieldType === 'select' || newFieldType === 'multiselect')
        ? newFieldOptions.split(',').map(o => o.trim()).filter(Boolean)
        : undefined

      await api.createCustomField({
        name: newFieldName.trim(),
        field_type: newFieldType,
        options,
      })

      setNewFieldName('')
      setNewFieldType('text')
      setNewFieldOptions('')
      setIsAddingField(false)

      // Trigger parent refresh
      onChange({})
    } catch (e) {
      console.error('Failed to create field:', e)
    }
  }

  const renderFieldValue = (field: CustomFieldValue) => {
    if (editingField === field.id) {
      return renderFieldEditor(field)
    }

    if (field.value === null || field.value === undefined) {
      return <span className={styles.emptyValue}>-</span>
    }

    switch (field.field_type) {
      case 'checkbox':
        return (
          <span className={`${styles.checkValue} ${field.value ? styles.checked : ''}`}>
            {field.value ? '✓' : '✗'}
          </span>
        )
      case 'multiselect':
        return (
          <div className={styles.multiselectValue}>
            {(field.value as string[]).map((v, i) => (
              <span key={i} className={styles.multiselectItem}>{v}</span>
            ))}
          </div>
        )
      default:
        return <span className={styles.fieldValue}>{String(field.value)}</span>
    }
  }

  const renderFieldEditor = (field: CustomFieldValue) => {
    switch (field.field_type) {
      case 'text':
        return (
          <input
            type="text"
            className={styles.input}
            value={editValue as string || ''}
            onChange={(e) => setEditValue(e.target.value)}
            autoFocus
          />
        )
      case 'number':
        return (
          <input
            type="number"
            className={styles.input}
            value={editValue as number || ''}
            onChange={(e) => setEditValue(e.target.valueAsNumber || null)}
            autoFocus
          />
        )
      case 'date':
        return (
          <input
            type="date"
            className={styles.input}
            value={editValue as string || ''}
            onChange={(e) => setEditValue(e.target.value)}
            autoFocus
          />
        )
      case 'checkbox':
        return (
          <input
            type="checkbox"
            className={styles.checkbox}
            checked={editValue as boolean || false}
            onChange={(e) => setEditValue(e.target.checked)}
          />
        )
      case 'select':
        return (
          <select
            className={styles.select}
            value={editValue as string || ''}
            onChange={(e) => setEditValue(e.target.value)}
            autoFocus
          >
            <option value="">Выбрать...</option>
            {field.options?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        )
      case 'multiselect':
        return (
          <div className={styles.multiselectEditor}>
            {field.options?.map((opt) => (
              <label key={opt} className={styles.multiselectOption}>
                <input
                  type="checkbox"
                  checked={(editValue as string[] || []).includes(opt)}
                  onChange={(e) => {
                    const current = editValue as string[] || []
                    if (e.target.checked) {
                      setEditValue([...current, opt])
                    } else {
                      setEditValue(current.filter(v => v !== opt))
                    }
                  }}
                />
                {opt}
              </label>
            ))}
          </div>
        )
      default:
        return null
    }
  }

  const FIELD_TYPE_LABELS: Record<CustomFieldType, string> = {
    text: 'Текст',
    number: 'Число',
    date: 'Дата',
    checkbox: 'Чекбокс',
    select: 'Выбор',
    multiselect: 'Мультивыбор',
  }

  return (
    <div className={styles.section}>
      <h4 className={styles.sectionTitle}>Дополнительные поля</h4>

      {fields.length > 0 ? (
        <div className={styles.fieldsList}>
          {fields.map(field => (
            <div key={field.id} className={styles.field}>
              <span className={styles.fieldLabel}>{field.name}</span>

              <div className={styles.fieldValueWrapper}>
                {renderFieldValue(field)}

                {editingField === field.id ? (
                  <div className={styles.editActions}>
                    <button
                      className={styles.saveBtn}
                      onClick={() => handleSave(field.id)}
                    >
                      ✓
                    </button>
                    <button
                      className={styles.cancelBtn}
                      onClick={handleCancel}
                    >
                      ✗
                    </button>
                  </div>
                ) : (
                  <button
                    className={styles.editBtn}
                    onClick={() => handleStartEdit(field)}
                  >
                    ✎
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className={styles.empty}>Нет дополнительных полей</p>
      )}

      {!isAddingField ? (
        <button
          className={styles.addFieldBtn}
          onClick={() => setIsAddingField(true)}
        >
          + Добавить поле
        </button>
      ) : (
        <div className={styles.addFieldForm}>
          <input
            type="text"
            className={styles.input}
            placeholder="Название поля"
            value={newFieldName}
            onChange={(e) => setNewFieldName(e.target.value)}
            autoFocus
          />

          <select
            className={styles.select}
            value={newFieldType}
            onChange={(e) => setNewFieldType(e.target.value as CustomFieldType)}
          >
            {Object.entries(FIELD_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>

          {(newFieldType === 'select' || newFieldType === 'multiselect') && (
            <input
              type="text"
              className={styles.input}
              placeholder="Опции через запятую"
              value={newFieldOptions}
              onChange={(e) => setNewFieldOptions(e.target.value)}
            />
          )}

          <div className={styles.formActions}>
            <button
              className={styles.createBtn}
              onClick={handleCreateField}
              disabled={!newFieldName.trim()}
            >
              Создать
            </button>
            <button
              className={styles.cancelFormBtn}
              onClick={() => {
                setIsAddingField(false)
                setNewFieldName('')
                setNewFieldType('text')
                setNewFieldOptions('')
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
