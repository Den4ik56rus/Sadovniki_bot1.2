// Universal Kanban Board for any Funnel
import { useEffect, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  closestCorners,
  closestCenter,
  pointerWithin,
  rectIntersection,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type CollisionDetection,
} from '@dnd-kit/core'
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { useFunnelStore } from '@/store/funnelStore'
import { useCurrencyStore } from '@/store'
import { FunnelColumn } from './FunnelColumn'
import { FunnelClientCard } from './FunnelClientCard'
import { FunnelClientCardFull } from './FunnelClientCardFull'
import { DropZone } from './DropZone'
import type { FunnelClient } from '@/types'
import styles from './FunnelKanban.module.css'

// Sortable wrapper for column in settings mode
interface SortableColumnWrapperProps {
  id: string
  children: React.ReactNode
  disabled: boolean
}

function SortableColumnWrapper({ id, children, disabled }: SortableColumnWrapperProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id,
    disabled,
    data: {
      type: 'column',
      stageKey: id,
    },
  })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={!disabled ? styles.sortableColumn : undefined}
      {...attributes}
      {...listeners}
    >
      {children}
    </div>
  )
}

interface FunnelKanbanProps {
  funnelId: string
}

export function FunnelKanban({ funnelId }: FunnelKanbanProps) {
  const {
    stages,
    clients,
    stats,
    isLoadingClients,
    error,
    isSettingsMode,
    fetchStages,
    fetchClients,
    moveClient,
    reorderStages,
    removeClient,
    transferClient,
  } = useFunnelStore()

  const { usdRate, fetchRate } = useCurrencyStore()

  const [activeClient, setActiveClient] = useState<FunnelClient | null>(null)
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null)
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Sensors for drag
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  // Custom collision detection
  const customCollisionDetection: CollisionDetection = (args) => {
    const pointerCollisions = pointerWithin(args)
    const columnCollisions = pointerCollisions.filter((collision) => {
      const data = collision.data?.droppableContainer?.data?.current
      return data?.type === 'column'
    })

    if (columnCollisions.length > 0) {
      return columnCollisions
    }

    const rectCollisions = rectIntersection(args)
    const columnRectCollisions = rectCollisions.filter((collision) => {
      const data = collision.data?.droppableContainer?.data?.current
      return data?.type === 'column'
    })

    if (columnRectCollisions.length > 0) {
      return columnRectCollisions
    }

    return closestCorners(args)
  }

  // Fetch data on mount or funnel change
  useEffect(() => {
    fetchStages(funnelId)
    fetchClients(funnelId)
    fetchRate()
  }, [funnelId, fetchStages, fetchClients, fetchRate])

  // Calculate totals
  const totalClients = Object.values(stats).reduce((a, b) => (a ?? 0) + (b ?? 0), 0)
  const totalValue = Object.values(clients)
    .flat()
    .reduce((sum, c) => sum + (c?.total_cost_usd ?? 0) * usdRate, 0)

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event

    if (isSettingsMode && active.data.current?.type === 'column') {
      setActiveColumnId(active.id as string)
      return
    }

    const client = active.data.current?.client as FunnelClient | undefined
    if (client) {
      setActiveClient(client)
    }
  }

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    setActiveClient(null)
    setActiveColumnId(null)

    if (!over) return

    // Handle column reordering (in settings mode)
    if (isSettingsMode) {
      const activeId = active.id as string
      const overId = over.id as string

      const isColumnDrag = stages.some(s => s.stage_key === activeId)
      const isColumnTarget = stages.some(s => s.stage_key === overId)

      if (isColumnDrag && isColumnTarget && activeId !== overId) {
        const oldIndex = stages.findIndex(s => s.stage_key === activeId)
        const newIndex = stages.findIndex(s => s.stage_key === overId)

        if (oldIndex !== -1 && newIndex !== -1) {
          const newOrder = [...stages.map(s => s.stage_key)]
          const [removed] = newOrder.splice(oldIndex, 1)
          newOrder.splice(newIndex, 0, removed)
          reorderStages(funnelId, newOrder)
        }
        return
      }
    }

    // Handle client card drag
    if (!isSettingsMode) {
      const activeClientData = active.data.current?.client as FunnelClient | undefined
      if (!activeClientData) return

      // Handle drop zones (delete / transfer to buyers)
      if (over.data.current?.type === 'dropzone') {
        const action = over.data.current.action as string
        if (action === 'delete') {
          removeClient(activeClientData.id, activeClientData.status)
          return
        }
        if (action === 'transfer-buyers') {
          transferClient(activeClientData.id, 'buyers', 'pending_payment')
          return
        }
      }

      let targetStage: string | null = null

      if (over.data.current?.type === 'column') {
        targetStage = over.data.current.stageKey as string
      } else if (over.data.current?.type === 'client') {
        const overClient = over.data.current.client as FunnelClient
        targetStage = overClient.status
      } else {
        const overId = over.id as string
        const isStageKey = stages.some(s => s.stage_key === overId)
        if (isStageKey) {
          targetStage = overId
        }
      }

      if (targetStage && targetStage !== activeClientData.status) {
        moveClient(activeClientData.id, activeClientData.status, targetStage)
      }
    }
  }

  // Filter clients by search query
  const filterClients = (clientList: FunnelClient[]) => {
    if (!searchQuery.trim()) return clientList
    const query = searchQuery.toLowerCase()
    return clientList.filter(
      (c) =>
        c.username?.toLowerCase().includes(query) ||
        c.first_name?.toLowerCase().includes(query) ||
        c.last_name?.toLowerCase().includes(query) ||
        String(c.telegram_user_id).includes(query)
    )
  }

  if (isLoadingClients && Object.values(clients).every((c) => (c?.length ?? 0) === 0)) {
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
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.searchBox}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Поиск клиентов..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.headerRight}>
          <div className={styles.statsInfo}>
            <span className={styles.statItem}>
              {totalClients} клиентов: {totalValue.toFixed(0)} ₽
            </span>
          </div>
        </div>
      </div>

      {/* Kanban Board */}
      <DndContext
        sensors={sensors}
        collisionDetection={isSettingsMode ? closestCenter : customCollisionDetection}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={stages.map((s) => s.stage_key)}
          strategy={horizontalListSortingStrategy}
          disabled={!isSettingsMode}
        >
          <div className={styles.board}>
            {stages.map((stage) => (
              <SortableColumnWrapper
                key={stage.stage_key}
                id={stage.stage_key}
                disabled={!isSettingsMode}
              >
                <FunnelColumn
                  stageKey={stage.stage_key}
                  title={stage.title}
                  color={stage.color}
                  clients={filterClients(clients[stage.stage_key] || [])}
                  count={stats[stage.stage_key] || 0}
                  totalValue={(clients[stage.stage_key] || []).reduce((sum, c) => sum + c.total_cost_usd * usdRate, 0)}
                  onClientClick={(clientId) => setSelectedClientId(clientId)}
                />
              </SortableColumnWrapper>
            ))}
          </div>
        </SortableContext>

        {/* Drop Zones - appear when dragging a card (only in CRM funnel) */}
        {activeClient && !isSettingsMode && funnelId === 'crm' && (
          <div className={styles.dropZonesContainer}>
            <DropZone
              id="delete"
              label="Удалить"
              icon="🗑️"
              variant="danger"
              isVisible={true}
            />
            <DropZone
              id="transfer-buyers"
              label="Оплатил → Покупатели"
              icon="💰"
              variant="success"
              isVisible={true}
            />
          </div>
        )}

        <DragOverlay>
          {activeClient && (
            <div className={styles.dragOverlay}>
              <FunnelClientCard
                client={activeClient}
                onClick={() => {}}
              />
            </div>
          )}
          {activeColumnId && (
            <div className={styles.dragOverlay}>
              {(() => {
                const stage = stages.find((s) => s.stage_key === activeColumnId)
                if (!stage) return null
                return (
                  <FunnelColumn
                    stageKey={stage.stage_key}
                    title={stage.title}
                    color={stage.color}
                    clients={filterClients(clients[stage.stage_key] || [])}
                    count={stats[stage.stage_key] || 0}
                    totalValue={(clients[stage.stage_key] || []).reduce((sum, c) => sum + c.total_cost_usd * usdRate, 0)}
                    onClientClick={() => {}}
                  />
                )
              })()}
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {selectedClientId && (
        <FunnelClientCardFull
          clientId={selectedClientId}
          funnelId={funnelId}
          onClose={() => setSelectedClientId(null)}
        />
      )}
    </div>
  )
}
