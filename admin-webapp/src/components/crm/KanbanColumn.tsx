// Kanban Column Component
import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { CrmClient, FunnelStatus } from '@/types'
import { ClientCard } from './ClientCard'
import styles from './KanbanColumn.module.css'

interface KanbanColumnProps {
  id: FunnelStatus
  title: string
  clients: CrmClient[]
  count: number
  onClientClick: (clientId: number) => void
}

const COLUMN_COLORS: Record<FunnelStatus, string> = {
  new: '#58a6ff',      // blue
  tried: '#a371f7',    // purple
  trial_ended: '#d29922', // yellow
  paid: '#3fb950',     // green
}

export function KanbanColumn({ id, title, clients, count, onClientClick }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: {
      type: 'column',
      status: id,
    },
  })

  const clientIds = clients.map((c) => c.id)

  return (
    <div
      ref={setNodeRef}
      className={`${styles.column} ${isOver ? styles.columnOver : ''}`}
    >
      <div className={styles.header}>
        <div
          className={styles.indicator}
          style={{ backgroundColor: COLUMN_COLORS[id] }}
        />
        <h3 className={styles.title}>{title}</h3>
        <span className={styles.count}>{count}</span>
      </div>

      <div className={styles.content}>
        <SortableContext items={clientIds} strategy={verticalListSortingStrategy}>
          {clients.map((client) => (
            <ClientCard
              key={client.id}
              client={client}
              onClick={() => onClientClick(client.id)}
            />
          ))}
        </SortableContext>

        {clients.length === 0 && (
          <div className={styles.empty}>
            Нет клиентов
          </div>
        )}
      </div>
    </div>
  )
}
