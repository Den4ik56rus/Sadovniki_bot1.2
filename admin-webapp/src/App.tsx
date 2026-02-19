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
import { PromptPreviewPage } from '@/components/promptPreview'
import { PaymentsList } from '@/components/payments/PaymentsList'
import { SettingsPage } from '@/components/settings'
import { InviteLinksPage } from '@/components/inviteLinks'
import { GuidesPage } from '@/components/guides'
import { useUIStore } from '@/store'
import { useFunnelStore } from '@/store/funnelStore'
import { useAutoRefresh, useRestoreState } from '@/hooks/useAutoRefresh'
import { useRouter } from '@/hooks/useRouter'
import styles from './App.module.css'

function App() {
  const { currentView } = useUIStore()
  const { currentFunnelId } = useFunnelStore()

  // Sync URL ↔ Zustand stores (must be before useRestoreState)
  useRouter()

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

      {/* Превью собранного промпта */}
      {currentView === 'prompt-preview' && <PromptPreviewPage />}

      {/* RAG Документы v2.0 — паспортизация чанков */}
      {currentView === 'rag-docs' && <RagDocsPage />}

      {/* Аналитика - существующий StatsPanel */}
      {currentView === 'stats' && <StatsPanel />}

      {/* Инвайт-ссылки - отслеживание кампаний */}
      {currentView === 'invite-links' && <InviteLinksPage />}

      {/* Расходы */}
      {currentView === 'expenses' && <ExpensesPage />}

      {/* Списки - Платежи */}
      {currentView === 'payments' && <PaymentsList />}

      {/* Готовые решения — PDF-гайды */}
      {currentView === 'guides' && <GuidesPage />}

      {/* Настройки — модели, temperature, RAG */}
      {currentView === 'settings' && <SettingsPage />}

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
