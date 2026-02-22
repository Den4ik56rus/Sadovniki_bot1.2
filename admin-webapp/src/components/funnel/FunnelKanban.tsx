// Universal Kanban Board for any Funnel
import { useEffect, useState, useCallback, useRef } from 'react'
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
import { useCurrencyStore, useUIStore } from '@/store'
import { useSSE } from '@/hooks/useSSE'
import { api } from '@/services/api'
import { navigate as routerNavigate, matchRoute } from '@/router'
import { FunnelColumn } from './FunnelColumn'
import { FunnelClientCard } from './FunnelClientCard'
import { FunnelClientCardFull } from './FunnelClientCardFull'
import { DropZone } from './DropZone'
import type { FunnelClient, FunnelSortOption } from '@/types'
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
    selectedInviteLinkId,
    setInviteLinkFilter,
    sortOption,
    setSortOption,
    fetchStages,
    fetchClients,
    moveClient,
    reorderStages,
    removeClient,
    transferClient,
    smartRefresh,
    removeClientLocally,
    setSseConnected,
  } = useFunnelStore()

  const { usdRate, fetchRate } = useCurrencyStore()

  const { currentView, globalSearchQuery } = useUIStore()

  // Invite link filter — загружаем список ссылок для дропдауна
  const [inviteLinks, setInviteLinks] = useState<Array<{ id: number; name: string }>>([])
  const inviteLinksLoaded = useRef(false)
  useEffect(() => {
    if (!inviteLinksLoaded.current) {
      inviteLinksLoaded.current = true
      api.getInviteLinks().then((res) => {
        setInviteLinks(res.links.map((l) => ({ id: l.id, name: l.name })))
      }).catch(() => {})
    }
  }, [])

  const [activeClient, setActiveClient] = useState<FunnelClient | null>(null)
  const [activeColumnId, setActiveColumnId] = useState<string | null>(null)

  // Read initial state from URL
  const [selectedClientId, setSelectedClientIdRaw] = useState<number | null>(() => {
    const match = matchRoute()
    return match.clientId ?? null
  })

  // Wrappers that sync state to URL
  const setSelectedClientId = useCallback((clientId: number | null) => {
    setSelectedClientIdRaw(clientId)
    if (clientId) {
      routerNavigate({ view: currentView, funnelId, clientId })
    } else {
      routerNavigate({ view: currentView, funnelId }, { replace: true })
    }
  }, [currentView, funnelId])

  // Self-echo suppression: отслеживаем собственные действия чтобы не дублировать SSE
  const recentActions = useRef<Map<string, number>>(new Map())

  const trackAction = useCallback((userId: number, action: string) => {
    const key = `${userId}-${action}`
    recentActions.current.set(key, Date.now())
    // Чистим старые записи
    setTimeout(() => recentActions.current.delete(key), 3000)
  }, [])

  const isOwnAction = useCallback((userId: number, action: string) => {
    const key = `${userId}-${action}`
    const ts = recentActions.current.get(key)
    return ts !== undefined && Date.now() - ts < 3000
  }, [])

  // SSE подписка для real-time обновлений воронки
  const handleFunnelSSE = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        if (event.type === 'heartbeat') return

        switch (event.type) {
          case 'client_moved':
            if (!isOwnAction(data.user_id, 'move')) {
              smartRefresh(funnelId)
            }
            break
          case 'client_removed':
            if (!isOwnAction(data.user_id, 'remove')) {
              removeClientLocally(data.user_id)
            }
            break
          case 'client_added':
          case 'consultation_logged':
            smartRefresh(funnelId)
            break
        }
      } catch (err) {
        console.error('[FunnelKanban] SSE parse error:', err)
      }
    },
    [funnelId, smartRefresh, removeClientLocally, isOwnAction]
  )

  const { isConnected: sseConnected } = useSSE({
    endpoint: api.sse.funnelEvents(funnelId),
    onMessage: handleFunnelSSE,
    enabled: true,
    eventTypes: ['client_moved', 'client_removed', 'client_added', 'consultation_logged', 'heartbeat'],
  })

  useEffect(() => {
    setSseConnected(sseConnected)
  }, [sseConnected, setSseConnected])

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
          trackAction(activeClientData.id, 'remove')
          removeClient(activeClientData.id, activeClientData.status)
          return
        }
        if (action === 'transfer-buyers') {
          trackAction(activeClientData.id, 'remove')
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
        trackAction(activeClientData.id, 'move')
        moveClient(activeClientData.id, activeClientData.status, targetStage)
      }
    }
  }

  // Filter clients by search query
  const filterClients = (clientList: FunnelClient[]) => {
    if (!globalSearchQuery.trim()) return clientList
    const query = globalSearchQuery.toLowerCase()
    return clientList.filter(
      (c) =>
        c.username?.toLowerCase().includes(query) ||
        c.first_name?.toLowerCase().includes(query) ||
        c.last_name?.toLowerCase().includes(query) ||
        String(c.telegram_user_id).includes(query)
    )
  }

  // Sort clients by selected option
  const sortClients = (clientList: FunnelClient[]): FunnelClient[] => {
    const sorted = [...clientList]
    switch (sortOption) {
      case 'last_activity_desc':
        return sorted.sort((a, b) => {
          const aDate = a.last_consultation_at ? new Date(a.last_consultation_at).getTime() : 0
          const bDate = b.last_consultation_at ? new Date(b.last_consultation_at).getTime() : 0
          if (bDate !== aDate) return bDate - aDate
          const aEntered = a.entered_at ? new Date(a.entered_at).getTime() : 0
          const bEntered = b.entered_at ? new Date(b.entered_at).getTime() : 0
          return bEntered - aEntered
        })
      case 'last_activity_asc':
        return sorted.sort((a, b) => {
          const aDate = a.last_consultation_at ? new Date(a.last_consultation_at).getTime() : Infinity
          const bDate = b.last_consultation_at ? new Date(b.last_consultation_at).getTime() : Infinity
          return aDate - bDate
        })
      case 'entered_desc':
        return sorted.sort((a, b) => {
          const aDate = a.entered_at ? new Date(a.entered_at).getTime() : 0
          const bDate = b.entered_at ? new Date(b.entered_at).getTime() : 0
          return bDate - aDate
        })
      case 'entered_asc':
        return sorted.sort((a, b) => {
          const aDate = a.entered_at ? new Date(a.entered_at).getTime() : Infinity
          const bDate = b.entered_at ? new Date(b.entered_at).getTime() : Infinity
          return aDate - bDate
        })
      case 'cost_desc':
        return sorted.sort((a, b) => (b.total_cost_usd ?? 0) - (a.total_cost_usd ?? 0))
      case 'cost_asc':
        return sorted.sort((a, b) => (a.total_cost_usd ?? 0) - (b.total_cost_usd ?? 0))
      default:
        return sorted
    }
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
      {/* Фильтр и сортировка */}
      <div className={styles.filterBar}>
        <label className={styles.filterLabel}>Сортировка:</label>
        <select
          className={styles.filterSelect}
          value={sortOption}
          onChange={(e) => setSortOption(e.target.value as FunnelSortOption)}
        >
          <option value="last_activity_desc">По активности (новые)</option>
          <option value="last_activity_asc">По активности (старые)</option>
          <option value="entered_desc">По дате входа (новые)</option>
          <option value="entered_asc">По дате входа (старые)</option>
          <option value="cost_desc">По стоимости (дороже)</option>
          <option value="cost_asc">По стоимости (дешевле)</option>
        </select>

        {inviteLinks.length > 0 && (
          <>
            <span className={styles.filterDivider}>|</span>
            <label className={styles.filterLabel}>Кампания:</label>
            <select
              className={styles.filterSelect}
              value={selectedInviteLinkId ?? ''}
              onChange={(e) => setInviteLinkFilter(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Все клиенты</option>
              {inviteLinks.map((link) => (
                <option key={link.id} value={link.id}>{link.name}</option>
              ))}
            </select>
            {selectedInviteLinkId !== null && (
              <button className={styles.filterClear} onClick={() => setInviteLinkFilter(null)}>
                ✕ Сбросить
              </button>
            )}
          </>
        )}
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
                  clients={sortClients(filterClients(clients[stage.stage_key] || []))}
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
                    clients={sortClients(filterClients(clients[stage.stage_key] || []))}
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
