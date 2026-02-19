// Hook: syncs browser URL ↔ Zustand stores (useUIStore + useFunnelStore)

import { useEffect, useCallback, useRef } from 'react'
import { matchRoute, navigate } from '@/router'
import { useUIStore } from '@/store'
import { useFunnelStore } from '@/store/funnelStore'
import type { View } from '@/types'

export function useRouter() {
  const setView = useUIStore((s) => s.setView)
  const setCurrentFunnel = useFunnelStore((s) => s.setCurrentFunnel)
  const isInitialized = useRef(false)

  /** Apply current URL to Zustand stores */
  const applyRoute = useCallback(() => {
    const match = matchRoute()
    setView(match.view as View)
    if (match.funnelId) {
      setCurrentFunnel(match.funnelId)
    }
  }, [setView, setCurrentFunnel])

  // On mount: read URL → set stores. Redirect `/` → `/dashboard`.
  useEffect(() => {
    if (isInitialized.current) return
    isInitialized.current = true

    // Redirect bare root to dashboard (replace, don't push)
    if (!window.location.pathname.endsWith('/dashboard')) {
      const match = matchRoute()
      if (match.view === 'dashboard') {
        navigate({ view: 'dashboard' }, { replace: true })
      }
    }

    // Always apply the current URL to stores
    applyRoute()
  }, [applyRoute])

  // Listen for popstate (browser back/forward + our navigate() calls)
  useEffect(() => {
    const handler = () => applyRoute()
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [applyRoute])
}
