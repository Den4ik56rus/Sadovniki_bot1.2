import { AppLayout } from '@/components/layout/AppLayout'
import { UserList } from '@/components/users/UserList'
import { TopicTimeline } from '@/components/topics/TopicTimeline'
import { ConsultationView } from '@/components/consultation/ConsultationView'
import { LiveFeed } from '@/components/live/LiveFeed'
import { StatsPanel } from '@/components/stats/StatsPanel'
import { DocumentUpload } from '@/components/documents/DocumentUpload'
import { useUIStore } from '@/store'
import { useAutoRefresh, useRestoreState } from '@/hooks/useAutoRefresh'
import styles from './App.module.css'

function App() {
  const { currentView } = useUIStore()

  // Auto-refresh data and restore state on page reload
  useAutoRefresh()
  useRestoreState()

  return (
    <AppLayout>
      {currentView === 'users' && (
        <div className={styles.usersView}>
          <div className={styles.sidebar}>
            <UserList />
            <TopicTimeline />
          </div>
          <div className={styles.main}>
            <ConsultationView />
          </div>
        </div>
      )}

      {currentView === 'live' && <LiveFeed />}

      {currentView === 'stats' && <StatsPanel />}

      {currentView === 'documents' && <DocumentUpload />}
    </AppLayout>
  )
}

export default App
