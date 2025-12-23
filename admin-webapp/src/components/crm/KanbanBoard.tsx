// Kanban Board for CRM
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
import type { FunnelStatus, CrmClient } from '@/types'
import { useCrmStore, useCurrencyStore } from '@/store'
import { KanbanColumn } from './KanbanColumn'
import { ClientCard } from './ClientCard'
import { ClientCardFull } from './ClientCardFull'
import { DropZone } from '../funnel/DropZone'
import { api } from '@/services/api'
import styles from './KanbanBoard.module.css'

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
      status: id,
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

export function KanbanBoard() {
  const {
    clients,
    stats,
    selectedClientId,
    isLoading,
    error,
    isSettingsMode,
    columnConfigs,
    fetchClients,
    moveClient,
    selectClient,
    reorderColumns,
  } = useCrmStore()

  // Track if we're dragging a column (for overlay)
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null)

  const { usdRate, fetchRate } = useCurrencyStore()

  const [activeClient, setActiveClient] = useState<CrmClient | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Sensors for drag
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  // Custom collision detection: prioritize columns over client cards
  const customCollisionDetection: CollisionDetection = (args) => {
    // First check pointer intersection with columns
    const pointerCollisions = pointerWithin(args)

    // Filter to only column droppables (not client cards)
    const columnCollisions = pointerCollisions.filter((collision) => {
      const data = collision.data?.droppableContainer?.data?.current
      return data?.type === 'column'
    })

    // If we found a column, use it
    if (columnCollisions.length > 0) {
      return columnCollisions
    }

    // Fall back to rect intersection for columns
    const rectCollisions = rectIntersection(args)
    const columnRectCollisions = rectCollisions.filter((collision) => {
      const data = collision.data?.droppableContainer?.data?.current
      return data?.type === 'column'
    })

    if (columnRectCollisions.length > 0) {
      return columnRectCollisions
    }

    // If no columns found, use closestCorners for client cards
    return closestCorners(args)
  }

  // Fetch data on mount
  useEffect(() => {
    fetchClients()
    fetchRate()
  }, [fetchClients, fetchRate])

  // Calculate total stats
  const totalClients = Object.values(stats).reduce((a, b) => (a ?? 0) + (b ?? 0), 0)
  const totalValue = Object.values(clients)
    .flat()
    .reduce((sum, c) => sum + (c?.total_cost_usd ?? 0) * usdRate, 0)

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event

    // Check if dragging a column (in settings mode)
    if (isSettingsMode && active.data.current?.type === 'column') {
      setActiveColumnId(active.id as string)
      return
    }

    // Dragging a client card
    const client = active.data.current?.client as CrmClient | undefined
    if (client) {
      setActiveClient(client)
    }
  }

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    // Reset active states
    setActiveClient(null)
    setActiveColumnId(null)

    if (!over) return

    // Handle column reordering (in settings mode)
    if (isSettingsMode) {
      const activeId = active.id as string
      const overId = over.id as string

      // Check if this is a column being dragged (column IDs are in columnConfigs)
      const isColumnDrag = columnConfigs.some(c => c.id === activeId)
      const isColumnTarget = columnConfigs.some(c => c.id === overId)

      if (isColumnDrag && isColumnTarget && activeId !== overId) {
        reorderColumns(activeId as FunnelStatus, overId as FunnelStatus)
        return
      }
    }

    // Handle client card drag (not in settings mode)
    if (!isSettingsMode) {
      const activeClientData = active.data.current?.client as CrmClient | undefined
      if (!activeClientData) return

      // Handle drop zones (delete / transfer to buyers)
      if (over.data.current?.type === 'dropzone') {
        const action = over.data.current.action as string
        if (action === 'delete') {
          handleDeleteClient(activeClientData.id, activeClientData.status)
          return
        }
        if (action === 'transfer-buyers') {
          handleTransferToBuyers(activeClientData.id, activeClientData.status)
          return
        }
      }

      // Get target status
      let targetStatus: FunnelStatus | null = null

      if (over.data.current?.type === 'column') {
        targetStatus = over.data.current.status as FunnelStatus
      } else if (over.data.current?.type === 'client') {
        // Dropped on another client - find which column it belongs to
        const overClient = over.data.current.client as CrmClient
        targetStatus = overClient.status
      } else {
        // Fallback: check if over.id matches a column ID
        const overId = over.id as string
        const isColumnId = columnConfigs.some(c => c.id === overId)
        if (isColumnId) {
          targetStatus = overId as FunnelStatus
        }
      }

      if (targetStatus && targetStatus !== activeClientData.status) {
        moveClient(activeClientData.id, activeClientData.status, targetStatus)
      }
    }
  }

  // Handle delete client from CRM
  const handleDeleteClient = async (clientId: number, _fromStatus: FunnelStatus) => {
    try {
      await api.removeClientFromFunnel('crm', clientId)
      // Refetch clients to update UI
      fetchClients()
    } catch (error) {
      console.error('Failed to delete client:', error)
    }
  }

  // Handle transfer client to Buyers funnel
  const handleTransferToBuyers = async (clientId: number, _fromStatus: FunnelStatus) => {
    try {
      await api.transferClient('crm', clientId, 'buyers', 'pending_payment')
      // Refetch clients to update UI
      fetchClients()
    } catch (error) {
      console.error('Failed to transfer client to buyers:', error)
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

  // Filter clients by search query
  const filterClients = (clientList: CrmClient[]) => {
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

  if (isLoading && Object.values(clients).every((c) => (c?.length ?? 0) === 0)) {
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
          <h2 className={styles.title}>SADOVNIKI</h2>
          <span className={styles.headerDivider}>|</span>
          <div className={styles.searchBox}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Поиск и фильтр"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.headerRight}>
          <div className={styles.statsInfo}>
            <span className={styles.statItem}>
              {totalClients} сделок: {totalValue.toFixed(0)} ₽
            </span>
          </div>
          <button className={styles.headerButton}>
            <span>⚙️</span>
            Настроить
          </button>
          <button className={`${styles.headerButton} ${styles.primary}`}>
            <span>+</span>
            Новая сделка
          </button>
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
          items={columnConfigs.map((c) => c.id)}
          strategy={horizontalListSortingStrategy}
          disabled={!isSettingsMode}
        >
          <div className={styles.board}>
            {columnConfigs.map((config) => (
              <SortableColumnWrapper
                key={config.id}
                id={config.id}
                disabled={!isSettingsMode}
              >
                <KanbanColumn
                  id={config.id}
                  clients={filterClients(clients[config.id] || [])}
                  count={stats[config.id] || 0}
                  totalValue={(clients[config.id] || []).reduce((sum, c) => sum + c.total_cost_usd * usdRate, 0)}
                  onClientClick={handleClientClick}
                />
              </SortableColumnWrapper>
            ))}
          </div>
        </SortableContext>

        {/* Drop Zones - appear when dragging a card */}
        {activeClient && !isSettingsMode && (
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
              <ClientCard
                client={activeClient}
                onClick={() => {}}
              />
            </div>
          )}
          {activeColumnId && (
            <div className={styles.dragOverlay}>
              {(() => {
                const config = columnConfigs.find((c) => c.id === activeColumnId)
                if (!config) return null
                return (
                  <KanbanColumn
                    id={config.id}
                    clients={filterClients(clients[config.id] || [])}
                    count={stats[config.id] || 0}
                    totalValue={(clients[config.id] || []).reduce((sum, c) => sum + c.total_cost_usd * usdRate, 0)}
                    onClientClick={() => {}}
                  />
                )
              })()}
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
