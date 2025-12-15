// Sidebar Navigation Component - Narrow Icon Style (i2crm inspired)
import type { View } from '@/types'
import { useUIStore } from '@/store'
import styles from './Sidebar.module.css'

interface MenuItem {
  id: View
  icon: React.ReactNode
  label: string
  badge?: number
}

// SVG Icons
const Icons = {
  dashboard: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="12" y="2" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="2" y="12" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="12" y="12" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  deals: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 6C3 4.89543 3.89543 4 5 4H17C18.1046 4 19 4.89543 19 6V16C19 17.1046 18.1046 18 17 18H5C3.89543 18 3 17.1046 3 16V6Z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 4V18" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M14 4V18" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  messages: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 4H18C19.1046 4 20 4.89543 20 6V14C20 15.1046 19.1046 16 18 16H6L2 19V6C2 4.89543 2.89543 4 4 4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M7 9H15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M7 12H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  buyers: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="11" cy="7" r="3.5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M4 19C4 15.6863 7.13401 13 11 13C14.866 13 18 15.6863 18 19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  tasks: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 11L10 14L15 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  lists: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M7 5H19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M7 11H19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M7 17H19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="3.5" cy="5" r="1.5" fill="currentColor"/>
      <circle cx="3.5" cy="11" r="1.5" fill="currentColor"/>
      <circle cx="3.5" cy="17" r="1.5" fill="currentColor"/>
    </svg>
  ),
  stats: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 19V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M8 19V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M13 19V11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M18 19V3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  settings: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="11" cy="11" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M11 2V4M11 18V20M20 11H18M4 11H2M17.07 4.93L15.66 6.34M6.34 15.66L4.93 17.07M17.07 17.07L15.66 15.66M6.34 6.34L4.93 4.93" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
}

const MENU_ITEMS: MenuItem[] = [
  { id: 'dashboard', icon: Icons.dashboard, label: 'Рабочий стол' },
  { id: 'crm', icon: Icons.deals, label: 'Сделки' },
  { id: 'messages', icon: Icons.messages, label: 'Сообщения' },
  { id: 'buyers', icon: Icons.buyers, label: 'Покупатели' },
  { id: 'tasks', icon: Icons.tasks, label: 'Задачи' },
  { id: 'lists', icon: Icons.lists, label: 'Списки' },
  { id: 'stats', icon: Icons.stats, label: 'Аналитика' },
  { id: 'settings', icon: Icons.settings, label: 'Настройки' },
]

export function Sidebar() {
  const { currentView, setView } = useUIStore()

  return (
    <aside className={styles.sidebar}>
      {/* Logo */}
      <div className={styles.logo}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="14" fill="var(--accent-primary)" fillOpacity="0.15"/>
          <path d="M16 7C16 7 11 12 11 16C11 19 13 22 16 24C19 22 21 19 21 16C21 12 16 7 16 7Z" fill="var(--accent-primary)" stroke="var(--accent-primary)" strokeWidth="1.5" strokeLinejoin="round"/>
          <path d="M16 11V18" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
          <path d="M14 14L16 12L18 14" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {MENU_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`${styles.navItem} ${currentView === item.id ? styles.active : ''}`}
            onClick={() => setView(item.id)}
            title={item.label}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            <span className={styles.navLabel}>{item.label}</span>
            {item.badge !== undefined && item.badge > 0 && (
              <span className={styles.navBadge}>{item.badge > 99 ? '99+' : item.badge}</span>
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.statusDot} title="Подключено" />
      </div>
    </aside>
  )
}
