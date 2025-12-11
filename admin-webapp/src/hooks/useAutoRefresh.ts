// Hook for auto-refreshing data
// NOTE: SSE used for live-feed, logs, and documents - no polling needed for those
// Polling remains only for users list and stats

import { useEffect, useRef, useCallback } from 'react'
import {
  useUIStore,
  useUsersStore,
  useStatsStore,
  useDocumentsStore,
} from '@/store'

// Refresh intervals in milliseconds
const REFRESH_INTERVALS = {
  users: 30000, // 30 seconds
  stats: 60000, // 1 minute
  documents: 10000, // 10 seconds (for fallback polling if SSE fails)
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

    // Note: live-feed now uses SSE, no polling needed

    return () => {
      isMounted.current = false
      intervals.forEach(clearInterval)
    }
  }, [
    currentView,
    refreshUsers,
    refreshStats,
    refreshDocuments,
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
    // Note: topics, logs, and live-feed will be loaded by their respective components via SSE
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
