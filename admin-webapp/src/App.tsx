import { AppLayout } from '@/components/layout/AppLayout'
import { UserList } from '@/components/users/UserList'
import { TopicTimeline } from '@/components/topics/TopicTimeline'
import { ConsultationView } from '@/components/consultation/ConsultationView'
import { LiveFeed } from '@/components/live/LiveFeed'
import { StatsPanel } from '@/components/stats/StatsPanel'
import { DocumentUpload } from '@/components/documents/DocumentUpload'
import { KanbanBoard } from '@/components/crm/KanbanBoard'
import { BuyersKanbanBoard } from '@/components/buyers'
import { Dashboard } from '@/components/pages/Dashboard'
import { PlaceholderPage } from '@/components/pages/PlaceholderPage'
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
      {/* Рабочий стол - Dashboard со статистикой */}
      {currentView === 'dashboard' && <Dashboard />}

      {/* Сделки - CRM Kanban */}
      {currentView === 'crm' && <KanbanBoard />}

      {/* Сообщения - заглушка */}
      {currentView === 'messages' && (
        <PlaceholderPage
          icon="💬"
          title="Сообщения"
          description="Раздел поддержки и сообщений находится в разработке"
        />
      )}

      {/* Покупатели - Kanban Board */}
      {currentView === 'buyers' && <BuyersKanbanBoard />}

      {/* Задачи - заглушка */}
      {currentView === 'tasks' && (
        <PlaceholderPage
          icon="✅"
          title="Задачи"
          description="Управление задачами находится в разработке"
        />
      )}

      {/* Списки - заглушка */}
      {currentView === 'lists' && (
        <PlaceholderPage
          icon="📋"
          title="Списки"
          description="Раздел списков находится в разработке"
        />
      )}

      {/* Аналитика - существующий StatsPanel */}
      {currentView === 'stats' && <StatsPanel />}

      {/* Настройки - заглушка */}
      {currentView === 'settings' && (
        <PlaceholderPage
          icon="⚙️"
          title="Настройки"
          description="Настройки приложения находятся в разработке"
        />
      )}

      {/* Legacy views - для обратной совместимости */}
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

      {currentView === 'documents' && <DocumentUpload />}
    </AppLayout>
  )
}

export default App
