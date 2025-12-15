// Kanban Board for CRM
import { useEffect, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from '@dnd-kit/core'
import type { FunnelStatus, CrmClient } from '@/types'
import { useCrmStore, useCurrencyStore } from '@/store'
import { KanbanColumn } from './KanbanColumn'
import { ClientCard } from './ClientCard'
import { ClientCardFull } from './ClientCardFull'
import styles from './KanbanBoard.module.css'

const COLUMNS: { id: FunnelStatus; title: string }[] = [
  { id: 'new', title: 'Новый' },
  { id: 'tried', title: 'Попробовал' },
  { id: 'trial_ended', title: 'Закончился триал' },
  { id: 'paid', title: 'Купил' },
]

export function KanbanBoard() {
  const {
    clients,
    stats,
    selectedClientId,
    isLoading,
    error,
    fetchClients,
    moveClient,
    selectClient,
  } = useCrmStore()

  const { fetchRate } = useCurrencyStore()

  const [activeClient, setActiveClient] = useState<CrmClient | null>(null)

  // Sensors for drag
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  // Fetch data on mount
  useEffect(() => {
    fetchClients()
    fetchRate()
  }, [fetchClients, fetchRate])

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event
    const client = active.data.current?.client as CrmClient | undefined
    if (client) {
      setActiveClient(client)
    }
  }

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    setActiveClient(null)

    if (!over) return

    const activeClient = active.data.current?.client as CrmClient | undefined
    if (!activeClient) return

    // Get target status
    let targetStatus: FunnelStatus | null = null

    if (over.data.current?.type === 'column') {
      targetStatus = over.data.current.status as FunnelStatus
    } else if (over.data.current?.type === 'client') {
      // Dropped on another client - find which column it belongs to
      const overClient = over.data.current.client as CrmClient
      targetStatus = overClient.status
    }

    if (targetStatus && targetStatus !== activeClient.status) {
      moveClient(activeClient.id, activeClient.status, targetStatus)
    }
  }

  // Handle client click
  const handleClientClick = (clientId: number) => {
    selectClient(clientId)
  }

  // Close modal
  const handleCloseModal = () => {
    selectClient(null)
  }

  if (isLoading && Object.values(clients).every((c) => c.length === 0)) {
    return (
      <div className={styles.loading}>
        Загрузка...
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.error}>
        Ошибка: {error}
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>CRM Воронка</h2>
        <div className={styles.stats}>
          Всего: {Object.values(stats).reduce((a, b) => a + b, 0)} клиентов
        </div>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className={styles.board}>
          {COLUMNS.map((column) => (
            <KanbanColumn
              key={column.id}
              id={column.id}
              title={column.title}
              clients={clients[column.id]}
              count={stats[column.id]}
              onClientClick={handleClientClick}
            />
          ))}
        </div>

        <DragOverlay>
          {activeClient && (
            <div className={styles.dragOverlay}>
              <ClientCard
                client={activeClient}
                onClick={() => {}}
              />
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {selectedClientId && (
        <ClientCardFull
          clientId={selectedClientId}
          onClose={handleCloseModal}
        />
      )}
    </div>
  )
}
