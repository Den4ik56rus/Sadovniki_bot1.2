import { useRef, useCallback, useEffect } from 'react'

interface UseScrollPreservationOptions {
  enabled?: boolean
  autoScrollThreshold?: number  // px от низа для auto-scroll
}

/**
 * Хук для сохранения позиции прокрутки при обновлении контента.
 *
 * Логика:
 * - Если пользователь прокрутил вверх (читает старые сообщения) → позиция сохраняется
 * - Если пользователь внизу списка → автоматически прокручивается к новым элементам
 *
 * @example
 * ```tsx
 * const { containerRef, handleScroll } = useScrollPreservation({
 *   enabled: true,
 *   autoScrollThreshold: 100
 * })
 *
 * return (
 *   <div ref={containerRef} onScroll={handleScroll}>
 *     {items.map(item => <Item key={item.id} {...item} />)}
 *   </div>
 * )
 * ```
 */
export function useScrollPreservation({
  enabled = true,
  autoScrollThreshold = 100
}: UseScrollPreservationOptions = {}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wasNearBottomRef = useRef(true)

  const checkIfNearBottom = useCallback(() => {
    if (!containerRef.current) return false

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight

    return distanceFromBottom < autoScrollThreshold
  }, [autoScrollThreshold])

  const handleScroll = useCallback(() => {
    wasNearBottomRef.current = checkIfNearBottom()
  }, [checkIfNearBottom])

  const scrollToBottom = useCallback((smooth = true) => {
    if (!containerRef.current) return

    containerRef.current.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto'
    })
  }, [])

  // Auto-scroll when content updates IF user was near bottom
  useEffect(() => {
    if (enabled && wasNearBottomRef.current) {
      scrollToBottom()
    }
  })

  return {
    containerRef,
    handleScroll,
    scrollToBottom,
    isNearBottom: wasNearBottomRef.current
  }
}
