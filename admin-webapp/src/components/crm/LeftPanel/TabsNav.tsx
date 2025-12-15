// Tabs Navigation Component (i2crm style)
import styles from './TabsNav.module.css'

export type TabId = 'main' | 'additional' | 'billing'

interface Tab {
  id: TabId
  label: string
}

const TABS: Tab[] = [
  { id: 'main', label: 'Основное' },
  { id: 'additional', label: 'Дополнительно' },
  { id: 'billing', label: 'Счета' },
]

interface TabsNavProps {
  activeTab: TabId
  onChange: (tab: TabId) => void
}

export function TabsNav({ activeTab, onChange }: TabsNavProps) {
  return (
    <nav className={styles.tabs}>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`${styles.tab} ${activeTab === tab.id ? styles.active : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}
