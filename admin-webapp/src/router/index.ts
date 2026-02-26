// Lightweight SPA router — syncs URL ↔ Zustand stores
// No dependencies. Uses browser History API.

// All simple (non-funnel) views
const SIMPLE_VIEWS = new Set([
  'dashboard', 'messages', 'tasks', 'payments', 'prompts',
  'prompt-preview', 'rag-docs', 'stats', 'invite-links',
  'expenses', 'guides', 'settings', 'users', 'live', 'documents',
  'moderation', 'ab-test',
])

export interface RouteMatch {
  view: string
  funnelId?: string
  clientId?: number
  topicId?: number
  searchQuery?: string
  /** Arbitrary query params (for filters, pagination, etc.) */
  params?: Record<string, string>
}

/** Returns Vite base path (e.g. '/' in dev, '/Sadovniki_bot1.2/' in prod) */
export function getBasePath(): string {
  return import.meta.env.BASE_URL || '/'
}

/** Strips base path from current pathname, returns app-relative path */
export function getAppPath(): string {
  const base = getBasePath().replace(/\/$/, '')
  let path = window.location.pathname
  if (base && path.startsWith(base)) {
    path = path.slice(base.length)
  }
  if (!path.startsWith('/')) path = '/' + path
  return path
}

/** Read a single query param from current URL */
export function getParam(key: string): string | null {
  return new URLSearchParams(window.location.search).get(key)
}

/** Read all query params from current URL */
export function getParams(): Record<string, string> {
  const result: Record<string, string> = {}
  new URLSearchParams(window.location.search).forEach((v, k) => {
    result[k] = v
  })
  return result
}

/** Update query params on current URL without changing the path (replaceState) */
export function setParams(params: Record<string, string | undefined | null>) {
  const url = new URL(window.location.href)
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === '') {
      url.searchParams.delete(k)
    } else {
      url.searchParams.set(k, v)
    }
  }
  const newUrl = url.pathname + url.search
  if (window.location.pathname + window.location.search !== newUrl) {
    window.history.replaceState(null, '', newUrl)
  }
}

/** Parse an app-relative path into a RouteMatch */
export function matchRoute(appPath?: string): RouteMatch {
  const path = appPath ?? getAppPath()
  const searchParams = new URLSearchParams(window.location.search)

  // Strip leading/trailing slashes, split into segments
  const segments = path.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean)

  // /funnel/:funnelId[/client/:clientId[/topic/:topicId]]
  if (segments[0] === 'funnel' && segments[1]) {
    const funnelId = decodeURIComponent(segments[1])
    // Map funnelId to view name (legacy compat)
    let view: string
    if (funnelId === 'crm') view = 'crm'
    else if (funnelId === 'buyers') view = 'buyers'
    else view = `funnel:${funnelId}`

    const match: RouteMatch = { view, funnelId }

    // /funnel/:funnelId/client/:clientId[/topic/:topicId]
    if (segments[2] === 'client' && segments[3]) {
      const id = parseInt(segments[3], 10)
      if (!isNaN(id)) match.clientId = id

      // /funnel/:funnelId/client/:clientId/topic/:topicId
      if (segments[4] === 'topic' && segments[5]) {
        const tid = parseInt(segments[5], 10)
        if (!isNaN(tid)) match.topicId = tid
      }
    }

    const search = searchParams.get('search')
    if (search) match.searchQuery = search

    return match
  }

  // Simple views: /dashboard, /stats, /settings, etc.
  if (segments[0] && SIMPLE_VIEWS.has(segments[0])) {
    return { view: segments[0] }
  }

  // Fallback: unknown path → dashboard
  return { view: 'dashboard' }
}

/** Build an app-relative path from a RouteMatch */
export function buildPath(match: RouteMatch): string {
  // Funnel views
  if (match.funnelId) {
    let path = `/funnel/${encodeURIComponent(match.funnelId)}`
    if (match.clientId) {
      path += `/client/${match.clientId}`
      if (match.topicId) {
        path += `/topic/${match.topicId}`
      }
    }
    // Build query string from searchQuery + params
    const qp = new URLSearchParams()
    if (match.searchQuery) qp.set('search', match.searchQuery)
    if (match.params) {
      for (const [k, v] of Object.entries(match.params)) {
        if (v) qp.set(k, v)
      }
    }
    const qs = qp.toString()
    if (qs) path += `?${qs}`
    return path
  }

  // Simple views
  const viewName = match.view.startsWith('funnel:')
    ? match.view
    : match.view

  let path = `/${viewName}`

  // Append params as query string
  if (match.params) {
    const qp = new URLSearchParams()
    for (const [k, v] of Object.entries(match.params)) {
      if (v) qp.set(k, v)
    }
    const qs = qp.toString()
    if (qs) path += `?${qs}`
  }

  return path
}

/** Navigate to a route — updates URL and dispatches popstate for listeners */
export function navigate(match: RouteMatch, options?: { replace?: boolean }) {
  const base = getBasePath().replace(/\/$/, '')
  const appPath = buildPath(match)
  const fullPath = base + appPath

  // Avoid pushing duplicate entries
  if (window.location.pathname + window.location.search === fullPath) {
    return
  }

  if (options?.replace) {
    window.history.replaceState(null, '', fullPath)
  } else {
    window.history.pushState(null, '', fullPath)
  }

  // Dispatch popstate so useRouter picks up the change
  window.dispatchEvent(new PopStateEvent('popstate'))
}
