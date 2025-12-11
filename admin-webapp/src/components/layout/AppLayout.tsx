import { useUIStore } from '@/store'
import styles from './AppLayout.module.css'

interface AppLayoutProps {
  children: React.ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const { currentView, setView } = useUIStore()

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <h1 className={styles.logo}>Sadovniki Admin</h1>
        <nav className={styles.nav}>
          <button
            className={`${styles.navButton} ${currentView === 'users' ? styles.active : ''}`}
            onClick={() => setView('users')}
          >
            Пользователи
          </button>
          <button
            className={`${styles.navButton} ${currentView === 'live' ? styles.active : ''}`}
            onClick={() => setView('live')}
          >
            Live Feed
          </button>
          <button
            className={`${styles.navButton} ${currentView === 'stats' ? styles.active : ''}`}
            onClick={() => setView('stats')}
          >
            Статистика
          </button>
          <button
            className={`${styles.navButton} ${currentView === 'documents' ? styles.active : ''}`}
            onClick={() => setView('documents')}
          >
            Документы
          </button>
        </nav>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  )
}
