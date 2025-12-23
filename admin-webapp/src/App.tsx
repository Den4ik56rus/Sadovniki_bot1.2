import { AppLayout } from '@/components/layout/AppLayout'
import { UserList } from '@/components/users/UserList'
import { TopicTimeline } from '@/components/topics/TopicTimeline'
import { ConsultationView } from '@/components/consultation/ConsultationView'
import { LiveFeed } from '@/components/live/LiveFeed'
import { StatsPanel } from '@/components/stats/StatsPanel'
import { DocumentUpload } from '@/components/documents/DocumentUpload'
import { FunnelKanban } from '@/components/funnel/FunnelKanban'
import { Dashboard } from '@/components/pages/Dashboard'
import { PlaceholderPage } from '@/components/pages/PlaceholderPage'
import { ExpensesPage } from '@/components/expenses'
import { RagDocsPage } from '@/components/ragDocuments'
import { PromptsPage } from '@/components/prompts'
import { PaymentsList } from '@/components/payments/PaymentsList'
import { useUIStore } from '@/store'
import { useFunnelStore } from '@/store/funnelStore'
import { useAutoRefresh, useRestoreState } from '@/hooks/useAutoRefresh'
import styles from './App.module.css'

function App() {
  const { currentView } = useUIStore()
  const { currentFunnelId } = useFunnelStore()

  // Auto-refresh data and restore state on page reload
  useAutoRefresh()
  useRestoreState()

  // Determine if we're in a funnel view
  const isFunnelView = currentView === 'crm' || currentView === 'buyers' || currentView.startsWith('funnel:')

  return (
    <AppLayout>
      {/* Рабочий стол - Dashboard со статистикой */}
      {currentView === 'dashboard' && <Dashboard />}

      {/* Воронки - единый FunnelKanban для всех воронок (CRM, Покупатели, кастомные) */}
      {isFunnelView && currentFunnelId && <FunnelKanban funnelId={currentFunnelId} />}

      {/* Сообщения - заглушка */}
      {currentView === 'messages' && (
        <PlaceholderPage
          icon="💬"
          title="Сообщения"
          description="Раздел поддержки и сообщений находится в разработке"
        />
      )}

      {/* Задачи - заглушка */}
      {currentView === 'tasks' && (
        <PlaceholderPage
          icon="✅"
          title="Задачи"
          description="Управление задачами находится в разработке"
        />
      )}

      {/* Редактор промптов */}
      {currentView === 'prompts' && <PromptsPage />}

      {/* RAG Документы v2.0 — паспортизация чанков */}
      {currentView === 'rag-docs' && <RagDocsPage />}

      {/* Аналитика - существующий StatsPanel */}
      {currentView === 'stats' && <StatsPanel />}

      {/* Расходы */}
      {currentView === 'expenses' && <ExpensesPage />}

      {/* Списки - Платежи */}
      {currentView === 'payments' && <PaymentsList />}

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
