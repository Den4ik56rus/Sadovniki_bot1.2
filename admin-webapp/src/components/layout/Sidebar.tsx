// Sidebar Navigation Component - Narrow Icon Style with Dynamic Funnels
import { useEffect } from 'react'
import type { View } from '@/types'
import { useUIStore } from '@/store'
import { useFunnelStore } from '@/store/funnelStore'
import { useModerationStore } from '@/store/moderationStore'
import { navigate } from '@/router'
import styles from './Sidebar.module.css'

interface SubmenuItem {
  id: View | string
  label: string
}

interface MenuItem {
  id: View | 'deals-group' | 'lists-group' | 'stats-group'
  icon: React.ReactNode
  label: string
  badge?: number
  submenu?: SubmenuItem[]
  isDynamic?: boolean
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
  expenses: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="11" cy="11" r="9" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M11 6V16M8 9H14C14.5523 9 15 9.44772 15 10C15 10.5523 14.5523 11 14 11H8M8 11H14C14.5523 11 15 11.4477 15 12C15 12.5523 14.5523 13 14 13H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  moderation: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M11 2L3 6V11C3 15.42 6.42 19.61 11 20.5C15.58 19.61 19 15.42 19 11V6L11 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 11L10 13L14 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  triggers: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M13 2L5 12H11L9 20L17 10H11L13 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),
  articles: (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M6 2H14L18 6V20C18 20.5523 17.5523 21 17 21H5C4.44772 21 4 20.5523 4 20V3C4 2.44772 4.44772 2 5 2H6Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M14 2V6H18" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 10H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M8 14H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  plus: (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M7 1V13M1 7H13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
}

// Static menu items (without dynamic funnels)
const STATIC_MENU_ITEMS: MenuItem[] = [
  { id: 'dashboard', icon: Icons.dashboard, label: 'Рабочий стол' },
  {
    id: 'deals-group',
    icon: Icons.deals,
    label: 'Воронки',
    submenu: [], // Will be filled dynamically
    isDynamic: true,
  },
  { id: 'messages', icon: Icons.messages, label: 'Рассылки' },
  { id: 'triggers', icon: Icons.triggers, label: 'Триггеры' },
  { id: 'tasks', icon: Icons.tasks, label: 'Задачи' },
  { id: 'articles', icon: Icons.articles, label: 'Статьи' },
  { id: 'moderation', icon: Icons.moderation, label: 'Модерация' },
  {
    id: 'lists-group',
    icon: Icons.lists,
    label: 'Списки',
    submenu: [
      { id: 'payments', label: 'Платежи' },
      // { id: 'guides', label: 'Готовые решения' },  // временно скрыто
      { id: 'prompts', label: 'Промпты' },
      { id: 'prompt-preview', label: 'Превью промпта' },
      { id: 'rag-docs', label: 'RAG Документы' },
    ],
  },
  {
    id: 'stats-group',
    icon: Icons.stats,
    label: 'Аналитика',
    submenu: [
      { id: 'stats', label: 'Статистика' },
      { id: 'invite-links', label: 'Инвайт-ссылки' },
      { id: 'ab-test', label: 'A/B тест' },
    ],
  },
  { id: 'expenses', icon: Icons.expenses, label: 'Расходы' },
  { id: 'settings', icon: Icons.settings, label: 'Настройки' },
]

export function Sidebar() {
  const { currentView } = useUIStore()
  const { funnels, fetchFunnels } = useFunnelStore()
  const { pendingCount, fetchStats } = useModerationStore()

  // Fetch funnels and moderation stats on mount
  useEffect(() => {
    fetchFunnels()
    fetchStats()
  }, [fetchFunnels, fetchStats])

  // Inject moderation badge
  const menuItemsWithBadge: MenuItem[] = STATIC_MENU_ITEMS.map((item) => {
    if (item.id === 'moderation' && pendingCount > 0) {
      return { ...item, badge: pendingCount }
    }
    return item
  })

  // Build menu items with dynamic funnels
  const menuItems: MenuItem[] = menuItemsWithBadge.map((item) => {
    if (item.isDynamic && item.id === 'deals-group') {
      // Build submenu from funnels
      const submenu: SubmenuItem[] = funnels.map((funnel) => ({
        id: `funnel:${funnel.id}`,
        label: funnel.title,
      }))
      // Add "Create funnel" option
      submenu.push({
        id: 'create-funnel',
        label: '+ Новая воронка',
      })
      return { ...item, submenu }
    }
    return item
  })

  // Check if current view is in a submenu group
  const isSubmenuActive = (submenu?: SubmenuItem[]) => {
    if (!submenu) return false
    return submenu.some((sub) => {
      if (sub.id.startsWith('funnel:')) {
        const funnelId = sub.id.replace('funnel:', '')
        return currentView === 'crm' || currentView === 'buyers' || currentView === (`funnel:${funnelId}` as View)
      }
      return sub.id === currentView
    })
  }

  // Check if a specific submenu item is active
  const isSubmenuItemActive = (submenuId: string): boolean => {
    // For funnel items, check if it matches current funnel
    if (submenuId.startsWith('funnel:')) {
      const funnelId = submenuId.replace('funnel:', '')
      // Legacy CRM view
      if (currentView === 'crm' && funnelId === 'crm') return true
      // Legacy Buyers view
      if (currentView === 'buyers' && funnelId === 'buyers') return true
      // New unified funnel view
      return currentView === (`funnel:${funnelId}` as View)
    }
    return submenuId === currentView
  }

  // Handle submenu item click
  const handleSubmenuClick = (submenuId: string) => {
    if (submenuId === 'create-funnel') {
      // TODO: Open create funnel modal
      alert('Создание воронки будет доступно в следующей версии')
      return
    }

    if (submenuId.startsWith('funnel:')) {
      const funnelId = submenuId.replace('funnel:', '')
      const view = funnelId === 'crm' ? 'crm' : funnelId === 'buyers' ? 'buyers' : `funnel:${funnelId}`
      navigate({ view, funnelId })
      return
    }

    navigate({ view: submenuId })
  }

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
        {menuItems.map((item) => {
          // Item with submenu
          if (item.submenu && item.submenu.length > 0) {
            const isActive = isSubmenuActive(item.submenu)
            return (
              <div key={item.id} className={styles.navItemWithSubmenu}>
                <div
                  className={`${styles.navItem} ${isActive ? styles.active : ''}`}
                  title={item.label}
                >
                  <span className={styles.navIcon}>{item.icon}</span>
                  <span className={styles.navLabel}>{item.label}</span>
                </div>
                <div className={styles.submenu}>
                  {item.submenu.map((sub) => (
                    <button
                      key={sub.id}
                      className={`${styles.submenuItem} ${isSubmenuItemActive(sub.id) ? styles.active : ''} ${sub.id === 'create-funnel' ? styles.submenuCreate : ''}`}
                      onClick={() => handleSubmenuClick(sub.id)}
                    >
                      {sub.id === 'create-funnel' && <span className={styles.submenuIcon}>{Icons.plus}</span>}
                      {sub.label}
                    </button>
                  ))}
                </div>
              </div>
            )
          }

          // Regular item
          return (
            <button
              key={item.id}
              className={`${styles.navItem} ${currentView === item.id ? styles.active : ''}`}
              onClick={() => navigate({ view: item.id as string })}
              title={item.label}
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
              {item.badge !== undefined && item.badge > 0 && (
                <span className={styles.navBadge}>{item.badge > 99 ? '99+' : item.badge}</span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.statusDot} title="Подключено" />
      </div>
    </aside>
  )
}
