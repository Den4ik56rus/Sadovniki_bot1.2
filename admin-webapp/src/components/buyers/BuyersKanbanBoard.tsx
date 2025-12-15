// Kanban Board for Buyers (Покупатели)
// Based on CRM KanbanBoard with adaptations for buyers

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
import type { BuyerStatus, Buyer } from '@/types'
import { useBuyersStore, useCurrencyStore } from '@/store'
import { BuyerColumn } from './BuyerColumn'
import { BuyerCard } from './BuyerCard'
import { BuyerCardFull } from './BuyerCardFull'
import styles from '../crm/KanbanBoard.module.css'

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

export function BuyersKanbanBoard() {
  const {
    buyers,
    stats,
    selectedBuyerId,
    isLoading,
    error,
    isSettingsMode,
    columnConfigs,
    fetchBuyers,
    moveBuyer,
    selectBuyer,
    reorderColumns,
  } = useBuyersStore()

  // Track if we're dragging a column (for overlay)
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null)

  const { usdRate, fetchRate } = useCurrencyStore()

  const [activeBuyer, setActiveBuyer] = useState<Buyer | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Sensors for drag
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  // Custom collision detection: prioritize columns over buyer cards
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

  // Fetch data on mount
  useEffect(() => {
    fetchBuyers()
    fetchRate()
  }, [fetchBuyers, fetchRate])

  // Calculate total stats
  const totalBuyers = Object.values(stats).reduce((a, b) => (a ?? 0) + (b ?? 0), 0)
  const totalValue = Object.values(buyers)
    .flat()
    .reduce((sum, b) => sum + (b?.total_cost_usd ?? 0) * usdRate, 0)

  // Handle drag start
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event

    if (isSettingsMode && active.data.current?.type === 'column') {
      setActiveColumnId(active.id as string)
      return
    }

    const buyer = active.data.current?.buyer as Buyer | undefined
    if (buyer) {
      setActiveBuyer(buyer)
    }
  }

  // Handle drag end
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    setActiveBuyer(null)
    setActiveColumnId(null)

    if (!over) return

    // Handle column reordering (in settings mode)
    if (isSettingsMode) {
      const activeId = active.id as string
      const overId = over.id as string

      const isColumnDrag = columnConfigs.some(c => c.id === activeId)
      const isColumnTarget = columnConfigs.some(c => c.id === overId)

      if (isColumnDrag && isColumnTarget && activeId !== overId) {
        reorderColumns(activeId as BuyerStatus, overId as BuyerStatus)
        return
      }
    }

    // Handle buyer card drag (not in settings mode)
    if (!isSettingsMode) {
      const activeBuyerData = active.data.current?.buyer as Buyer | undefined
      if (!activeBuyerData) return

      let targetStatus: BuyerStatus | null = null

      if (over.data.current?.type === 'column') {
        targetStatus = over.data.current.status as BuyerStatus
      } else if (over.data.current?.type === 'buyer') {
        const overBuyer = over.data.current.buyer as Buyer
        targetStatus = overBuyer.status
      } else {
        const overId = over.id as string
        const isColumnId = columnConfigs.some(c => c.id === overId)
        if (isColumnId) {
          targetStatus = overId as BuyerStatus
        }
      }

      if (targetStatus && targetStatus !== activeBuyerData.status) {
        moveBuyer(activeBuyerData.id, activeBuyerData.status, targetStatus)
      }
    }
  }

  // Handle buyer click
  const handleBuyerClick = (buyerId: number) => {
    selectBuyer(buyerId)
  }

  // Close modal
  const handleCloseModal = () => {
    selectBuyer(null)
  }

  // Filter buyers by search query
  const filterBuyers = (buyerList: Buyer[]) => {
    if (!searchQuery.trim()) return buyerList
    const query = searchQuery.toLowerCase()
    return buyerList.filter(
      (b) =>
        b.username?.toLowerCase().includes(query) ||
        b.first_name?.toLowerCase().includes(query) ||
        b.last_name?.toLowerCase().includes(query) ||
        String(b.telegram_user_id).includes(query)
    )
  }

  if (isLoading && Object.values(buyers).every((b) => (b?.length ?? 0) === 0)) {
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
          <h2 className={styles.title}>ПОКУПАТЕЛИ</h2>
          <span className={styles.headerDivider}>|</span>
          <div className={styles.searchBox}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Поиск покупателя"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className={styles.headerRight}>
          <div className={styles.statsInfo}>
            <span className={styles.statItem}>
              {totalBuyers} покупателей: {totalValue.toFixed(0)} ₽
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
                <BuyerColumn
                  id={config.id}
                  buyers={filterBuyers(buyers[config.id] || [])}
                  count={stats[config.id] || 0}
                  totalValue={(buyers[config.id] || []).reduce((sum, b) => sum + b.total_cost_usd * usdRate, 0)}
                  onBuyerClick={handleBuyerClick}
                />
              </SortableColumnWrapper>
            ))}
          </div>
        </SortableContext>

        <DragOverlay>
          {activeBuyer && (
            <div className={styles.dragOverlay}>
              <BuyerCard
                buyer={activeBuyer}
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
                  <BuyerColumn
                    id={config.id}
                    buyers={filterBuyers(buyers[config.id] || [])}
                    count={stats[config.id] || 0}
                    totalValue={(buyers[config.id] || []).reduce((sum, b) => sum + b.total_cost_usd * usdRate, 0)}
                    onBuyerClick={() => {}}
                  />
                )
              })()}
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {selectedBuyerId && (
        <BuyerCardFull
          buyerId={selectedBuyerId}
          onClose={handleCloseModal}
        />
      )}
    </div>
  )
}
