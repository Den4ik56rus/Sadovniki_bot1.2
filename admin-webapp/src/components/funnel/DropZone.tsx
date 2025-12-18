// Drop zone component for drag actions (delete, transfer to buyers)
import { useDroppable } from '@dnd-kit/core'
import styles from './DropZone.module.css'

interface DropZoneProps {
  id: string
  label: string
  icon: string
  variant: 'danger' | 'success'
  isVisible: boolean
}

export function DropZone({ id, label, icon, variant, isVisible }: DropZoneProps) {
  const { isOver, setNodeRef } = useDroppable({
    id,
    data: {
      type: 'dropzone',
      action: id,
    },
  })

  if (!isVisible) return null

  return (
    <div
      ref={setNodeRef}
      className={`${styles.dropZone} ${styles[variant]} ${isOver ? styles.over : ''}`}
    >
      <span className={styles.icon}>{icon}</span>
      <span className={styles.label}>{label}</span>
    </div>
  )
}
