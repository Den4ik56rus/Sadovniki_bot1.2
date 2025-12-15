// App Layout with Sidebar and Header - Clean Professional Style
import { useState } from 'react'
import { Sidebar } from './Sidebar'
import { useUIStore, useCrmStore, useBuyersStore } from '@/store'
import styles from './AppLayout.module.css'

interface AppLayoutProps {
  children: React.ReactNode
}

// Page titles mapping
const PAGE_TITLES: Record<string, { title: string; subtitle?: string }> = {
  dashboard: { title: 'Рабочий стол', subtitle: 'Обзор показателей' },
  crm: { title: 'Сделки', subtitle: 'Управление воронкой' },
  messages: { title: 'Сообщения', subtitle: 'Поддержка клиентов' },
  buyers: { title: 'Покупатели', subtitle: 'Активные подписчики' },
  tasks: { title: 'Задачи', subtitle: 'Управление задачами' },
  lists: { title: 'Списки', subtitle: 'Сегментация клиентов' },
  stats: { title: 'Аналитика', subtitle: 'Статистика и отчёты' },
  settings: { title: 'Настройки', subtitle: 'Конфигурация системы' },
}

export function AppLayout({ children }: AppLayoutProps) {
  const { currentView } = useUIStore()
  const { isSettingsMode: crmSettingsMode, toggleSettingsMode: toggleCrmSettings } = useCrmStore()
  const { isSettingsMode: buyersSettingsMode, toggleSettingsMode: toggleBuyersSettings } = useBuyersStore()
  const [searchQuery, setSearchQuery] = useState('')

  // Determine which settings mode and toggle to use based on current view
  const isSettingsMode = currentView === 'crm' ? crmSettingsMode : currentView === 'buyers' ? buyersSettingsMode : false
  const toggleSettingsMode = currentView === 'crm' ? toggleCrmSettings : currentView === 'buyers' ? toggleBuyersSettings : () => {}

  const pageInfo = PAGE_TITLES[currentView] || { title: 'Страница' }

  return (
    <div className={styles.layout}>
      <Sidebar />

      <div className={styles.mainArea}>
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.pageInfo}>
              <h1 className={styles.pageTitle}>{pageInfo.title}</h1>
              {pageInfo.subtitle && (
                <span className={styles.pageSubtitle}>{pageInfo.subtitle}</span>
              )}
            </div>
          </div>

          <div className={styles.headerCenter}>
            <div className={styles.searchWrapper}>
              <svg className={styles.searchIcon} width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M12 12L16 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Поиск клиентов, сделок..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <kbd className={styles.searchHotkey}>⌘K</kbd>
            </div>
          </div>

          <div className={styles.headerRight}>
            <button className={styles.headerButton} title="Уведомления">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M10 2C6.68629 2 4 4.68629 4 8V11L2.29289 12.7071C2.00689 12.9931 1.92134 13.4214 2.07612 13.7953C2.2309 14.1693 2.59554 14.4142 3 14.4142H17C17.4045 14.4142 17.7691 14.1693 17.9239 13.7953C18.0787 13.4214 17.9931 12.9931 17.7071 12.7071L16 11V8C16 4.68629 13.3137 2 10 2Z" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M8 14.5V15C8 16.1046 8.89543 17 10 17C11.1046 17 12 16.1046 12 15V14.5" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
              <span className={styles.notificationDot} />
            </button>

            {(currentView === 'crm' || currentView === 'buyers') && (
              <button
                className={`${styles.headerButton} ${isSettingsMode ? styles.headerButtonActive : ''}`}
                title={isSettingsMode ? 'Выйти из настроек' : 'Настройки воронки'}
                onClick={toggleSettingsMode}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M10 12.5C11.3807 12.5 12.5 11.3807 12.5 10C12.5 8.61929 11.3807 7.5 10 7.5C8.61929 7.5 7.5 8.61929 7.5 10C7.5 11.3807 8.61929 12.5 10 12.5Z" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M16.1667 10C16.1667 10.3517 16.1383 10.6967 16.0833 11.0333L17.8333 12.4167C17.9917 12.5417 18.0333 12.7667 17.9333 12.95L16.2667 15.8333C16.1583 16.0167 15.9417 16.0917 15.7417 16.0167L13.6917 15.2C13.1833 15.5917 12.6167 15.9167 12 16.1583L11.6917 18.3333C11.6583 18.5417 11.475 18.7083 11.25 18.7083H7.91667C7.69167 18.7083 7.50833 18.5417 7.475 18.3333L7.16667 16.1583C6.55 15.9167 5.98333 15.5917 5.475 15.2L3.425 16.0167C3.225 16.0917 3.00833 16.0167 2.9 15.8333L1.23333 12.95C1.13333 12.7667 1.175 12.5417 1.33333 12.4167L3.08333 11.0333C3.02833 10.6967 3 10.3517 3 10C3 9.64833 3.02833 9.30333 3.08333 8.96667L1.33333 7.58333C1.175 7.45833 1.13333 7.23333 1.23333 7.05L2.9 4.16667C3.00833 3.98333 3.225 3.90833 3.425 3.98333L5.475 4.8C5.98333 4.40833 6.55 4.08333 7.16667 3.84167L7.475 1.66667C7.50833 1.45833 7.69167 1.29167 7.91667 1.29167H11.25C11.475 1.29167 11.6583 1.45833 11.6917 1.66667L12 3.84167C12.6167 4.08333 13.1833 4.40833 13.6917 4.8L15.7417 3.98333C15.9417 3.90833 16.1583 3.98333 16.2667 4.16667L17.9333 7.05C18.0333 7.23333 17.9917 7.45833 17.8333 7.58333L16.0833 8.96667C16.1383 9.30333 16.1667 9.64833 16.1667 10Z" stroke="currentColor" strokeWidth="1.5"/>
                </svg>
              </button>
            )}

            <div className={styles.divider} />

            <button className={styles.addButton}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 3V13M3 8H13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <span>Новая сделка</span>
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  )
}
