// Hook for auto-refreshing data
// NOTE: SSE used for live-feed, logs, documents, and funnels - no polling needed for those
// Polling remains only for users list, stats, and as SSE fallback for funnels

import { useEffect, useRef, useCallback } from 'react'
import {
  useUIStore,
  useUsersStore,
  useStatsStore,
  useDocumentsStore,
} from '@/store'
import { useFunnelStore } from '@/store/funnelStore'

// Refresh intervals in milliseconds
const REFRESH_INTERVALS = {
  users: 30000, // 30 seconds
  stats: 60000, // 1 minute
  documents: 10000, // 10 seconds (for fallback polling if SSE fails)
  funnelFallback: 30000, // 30 seconds — only when SSE disconnected
}

function isFunnelView(view: string): boolean {
  return view === 'crm' || view === 'buyers' || view.startsWith('funnel:')
}

export function useAutoRefresh() {
  const { currentView } = useUIStore()

  const { fetchUsers, searchQuery } = useUsersStore()
  const { fetchStats, period } = useStatsStore()
  const { fetchDocuments, pollProcessingDocuments, documents } = useDocumentsStore()

  // Track if component is mounted
  const isMounted = useRef(true)

  // Refresh users list
  const refreshUsers = useCallback(() => {
    if (currentView === 'users') {
      fetchUsers(searchQuery || undefined)
    }
  }, [currentView, fetchUsers, searchQuery])

  // Refresh stats
  const refreshStats = useCallback(() => {
    if (currentView === 'stats') {
      fetchStats(period)
    }
  }, [currentView, fetchStats, period])

  // Refresh documents (fallback polling if SSE fails)
  const refreshDocuments = useCallback(() => {
    if (currentView === 'documents') {
      // Check for processing documents
      const hasProcessing = documents.some(
        (d) => d.status === 'processing' || d.status === 'pending'
      )
      if (hasProcessing) {
        pollProcessingDocuments()
      } else {
        fetchDocuments()
      }
    }
  }, [currentView, documents, fetchDocuments, pollProcessingDocuments])

  // Fallback: refresh funnel only when SSE is disconnected
  const refreshFunnelFallback = useCallback(() => {
    const { currentFunnelId, sseConnected, smartRefresh } = useFunnelStore.getState()
    if (isFunnelView(currentView) && currentFunnelId && !sseConnected) {
      smartRefresh(currentFunnelId)
    }
  }, [currentView])

  // Set up intervals based on current view
  useEffect(() => {
    isMounted.current = true
    const intervals: NodeJS.Timeout[] = []

    if (currentView === 'users') {
      // Users refresh only (topics and logs now use SSE)
      intervals.push(setInterval(refreshUsers, REFRESH_INTERVALS.users))
    }

    if (currentView === 'stats') {
      intervals.push(setInterval(refreshStats, REFRESH_INTERVALS.stats))
    }

    if (currentView === 'documents') {
      intervals.push(setInterval(refreshDocuments, REFRESH_INTERVALS.documents))
    }

    // Funnel fallback polling — only active when SSE disconnected
    if (isFunnelView(currentView)) {
      intervals.push(setInterval(refreshFunnelFallback, REFRESH_INTERVALS.funnelFallback))
    }

    // Note: live-feed uses SSE, funnels use SSE with fallback polling

    return () => {
      isMounted.current = false
      intervals.forEach(clearInterval)
    }
  }, [
    currentView,
    refreshUsers,
    refreshStats,
    refreshDocuments,
    refreshFunnelFallback,
  ])
}

// Hook to restore state on mount (fetch data for persisted selections)
export function useRestoreState() {
  const { currentView } = useUIStore()
  const { fetchUsers, searchQuery } = useUsersStore()
  const { fetchStats, period } = useStatsStore()
  const { fetchDocuments } = useDocumentsStore()

  const hasRestored = useRef(false)

  useEffect(() => {
    if (hasRestored.current) return
    hasRestored.current = true

    // Restore data based on persisted state
    // Note: topics, logs, live-feed, and funnels will be loaded by their respective components via SSE
    switch (currentView) {
      case 'users':
        fetchUsers(searchQuery || undefined)
        break
      case 'stats':
        fetchStats(period)
        break
      case 'documents':
        fetchDocuments()
        break
      // 'live' view loads via SSE in LiveFeed component
      // Funnel views (crm/buyers/funnel:*) load via FunnelKanban component + SSE
    }
  }, [
    currentView,
    searchQuery,
    period,
    fetchUsers,
    fetchStats,
    fetchDocuments,
  ])
}
