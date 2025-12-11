import { useState } from 'react'
import styles from './CollapsibleSection.module.css'

interface CollapsibleSectionProps {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  badge?: string
}

export function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
  badge,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className={styles.section}>
      <button className={styles.header} onClick={() => setIsOpen(!isOpen)}>
        <span className={styles.chevron}>{isOpen ? '▼' : '▶'}</span>
        <span className={styles.title}>{title}</span>
        {badge && <span className={styles.badge}>{badge}</span>}
      </button>
      {isOpen && <div className={styles.content}>{children}</div>}
    </div>
  )
}
