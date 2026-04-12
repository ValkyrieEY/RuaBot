import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Fingerprint,
  Globe2,
  Laptop,
  RefreshCw,
  Search,
  Shield,
  User,
  X,
} from 'lucide-react'
import { api } from '@/utils/api'

type AuditEvent = {
  event_type: string
  timestamp: string
  username?: string
  ip_address?: string
  resource?: string
  action?: string
  success?: boolean
  details?: Record<string, any>
}

type AuditFilter = 'all' | 'login' | 'operation' | 'failed'

const limit = 200
const recentMinutes = 24 * 60

const eventTypeLabel: Record<string, string> = {
  'auth.login': '登录成功',
  'auth.failed': '登录失败',
  'auth.logout': '退出登录',
  'webui.action': 'WebUI 操作',
  'config.changed': '配置变更',
  'plugin.loaded': '插件加载',
  'plugin.unloaded': '插件卸载',
  'plugin.enabled': '插件启用',
  'plugin.disabled': '插件停用',
  'plugin.configured': '插件配置',
  'access.denied': '访问拒绝',
}

const filters: Array<{ key: AuditFilter; label: string; icon: typeof Shield }> = [
  { key: 'all', label: '全部', icon: Shield },
  { key: 'login', label: '登录', icon: User },
  { key: 'operation', label: '操作', icon: Laptop },
  { key: 'failed', label: '失败', icon: AlertCircle },
]

const getEventLabel = (event: AuditEvent) => eventTypeLabel[event.event_type] || event.event_type

const getEventTime = (event: AuditEvent) => {
  const ts = event.timestamp ? new Date(event.timestamp).getTime() : 0
  return Number.isNaN(ts) ? 0 : ts
}

const getEventKey = (event: AuditEvent) => {
  return [
    event.event_type,
    event.timestamp,
    event.username || '',
    event.ip_address || '',
    event.resource || '',
    event.action || '',
    JSON.stringify(event.details || {}),
  ].join(':')
}

const mergeEvents = (base: AuditEvent[], incoming: AuditEvent[]) => {
  const byKey = new Map<string, AuditEvent>()
  base.forEach((event) => byKey.set(getEventKey(event), event))
  incoming.forEach((event) => byKey.set(getEventKey(event), event))
  return Array.from(byKey.values())
    .sort((a, b) => getEventTime(b) - getEventTime(a))
    .slice(0, limit)
}

const formatTime = (value?: string) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const getClient = (event: AuditEvent) => event.details?.client || {}

const getGeoText = (event: AuditEvent) => {
  const geo = event.details?.geo || {}
  const parts = [geo.continent, geo.country, geo.province, geo.city, geo.region, geo.carrier]
    .filter(Boolean)
    .filter((value, index, array) => array.indexOf(value) === index)
  const coords = [geo.latitude, geo.longitude].filter(Boolean).join(', ')
  if (parts.length && coords) return `${parts.join(' / ')} (${coords})`
  if (coords) return coords
  if (parts.length) return parts.join(' / ')
  return '未知位置'
}

const formatDetails = (event: AuditEvent) => {
  const details = event.details || {}
  if (event.action === 'send_message') {
    return `发送到 ${details.chat_type || '-'}:${details.chat_id || '-'}，内容：${details.message || ''}`
  }
  if (event.action === 'update_admin_username') {
    return `账号从 ${details.old_username || '-'} 改为 ${details.new_username || '-'}`
  }
  if (event.action === 'reset_admin_password') {
    return '重置管理员密码'
  }
  if (details.operation) {
    return `${details.operation}，状态码 ${details.status_code ?? '-'}`
  }
  if (details.reason) {
    return details.reason
  }
  if (event.resource || event.action) {
    return `${event.resource || 'webui'} / ${event.action || '-'}`
  }
  return JSON.stringify(details)
}

const getRowClasses = (event: AuditEvent) => {
  if (event.success === false) return 'border-l-4 border-l-red-500 bg-red-50 hover:bg-red-100/80'
  if (event.event_type.startsWith('auth.')) return 'border-l-4 border-l-blue-500 bg-blue-50 hover:bg-blue-100/80'
  if (event.event_type === 'webui.action' || event.event_type === 'config.changed') {
    return 'border-l-4 border-l-emerald-500 bg-emerald-50 hover:bg-emerald-100/80'
  }
  return 'border-l-4 border-l-transparent bg-white hover:bg-slate-50'
}

const getFilterType = (event: AuditEvent): AuditFilter | 'other' => {
  if (event.event_type === 'auth.login' || event.event_type === 'auth.failed' || event.event_type === 'auth.logout') {
    return 'login'
  }
  if (event.event_type === 'webui.action' || event.event_type === 'config.changed' || event.event_type.startsWith('plugin.')) {
    return 'operation'
  }
  if (event.success === false) return 'failed'
  return 'other'
}

export default function SecurityPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<AuditFilter>('all')
  const [search, setSearch] = useState('')
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string>('')
  const eventsRef = useRef<AuditEvent[]>([])

  const loadEvents = async (replace = true) => {
    if (replace && eventsRef.current.length === 0) {
      setLoading(true)
    }

    try {
      const data = await api.getSecurityAuditEvents({ limit, recent_minutes: recentMinutes })
      const incoming = Array.isArray(data?.events) ? data.events : []
      setEvents((prev) => (replace ? mergeEvents([], incoming) : mergeEvents(prev, incoming)))
      setLastUpdated(new Date().toLocaleTimeString('zh-CN'))
    } catch (error) {
      console.error('Failed to load security audit events:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    eventsRef.current = events
  }, [events])

  useEffect(() => {
    void loadEvents()
    const interval = setInterval(() => {
      void loadEvents(false)
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const filteredEvents = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return events.filter((event) => {
      if (filter === 'failed' && event.success !== false) return false
      if (filter !== 'all' && filter !== 'failed' && getFilterType(event) !== filter) return false
      if (!keyword) return true
      const client = getClient(event)
      const browser = client.browser || {}
      const haystack = [
        event.event_type,
        event.username,
        event.ip_address,
        event.resource,
        event.action,
        client.fingerprint,
        browser.name,
        client.engine,
        client.os,
        getGeoText(event),
        formatDetails(event),
      ].join(' ').toLowerCase()
      return haystack.includes(keyword)
    })
  }, [events, filter, search])

  const counts: Record<AuditFilter, number> = {
    all: events.length,
    login: events.filter((event) => getFilterType(event) === 'login').length,
    operation: events.filter((event) => getFilterType(event) === 'operation').length,
    failed: events.filter((event) => event.success === false).length,
  }

  return (
    <div className="fixed top-16 left-0 right-0 bottom-0 md:left-64 flex bg-white overflow-hidden">
      <div className="flex w-full min-w-0 flex-col">
        <div className="h-16 shrink-0 border-b border-slate-200 bg-white px-4 md:px-6">
          <div className="flex h-full items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3 min-w-0">
                <h1 className="truncate text-lg font-semibold text-slate-900">权限审计</h1>
                <span className="hidden sm:inline text-sm text-slate-500">
                  最近 24 小时，最多 {limit} 条
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <span>自动刷新{lastUpdated ? ` · ${lastUpdated}` : ''}</span>
              </div>
              <button
                type="button"
                onClick={() => void loadEvents(true)}
                className="h-10 px-3 text-sm text-slate-600 hover:text-slate-900 transition-colors flex items-center gap-2"
                title="刷新"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">刷新</span>
              </button>
            </div>
          </div>
        </div>

        <div className="h-14 shrink-0 border-b border-slate-200 bg-white overflow-x-auto">
          <div className="flex h-full min-w-max items-stretch px-2 md:px-4">
            {filters.map((item) => {
              const Icon = item.icon
              const active = filter === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilter(item.key)}
                  className={`flex h-full items-center gap-2 border-b-2 px-4 text-sm font-medium transition-colors ${
                    active
                      ? 'border-primary-600 text-primary-700'
                      : 'border-transparent text-slate-500 hover:text-slate-900'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                  <span className={`${active ? 'text-primary-600' : 'text-slate-400'}`}>{counts[item.key]}</span>
                </button>
              )
            })}

            <div className="ml-auto flex h-full items-center px-2">
              <div className="relative w-64 max-w-[45vw]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="搜索账号、IP、操作..."
                  className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 min-h-0 bg-slate-100">
          {loading && events.length === 0 ? (
            <div className="flex h-full items-center justify-center px-6 text-slate-500">
              <div className="flex items-center gap-3 text-sm">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>正在载入权限审计</span>
              </div>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="flex h-full items-center justify-center px-6">
              <div className="max-w-md text-center">
                <Shield className="w-10 h-10 text-slate-300 mx-auto mb-4" />
                <div className="text-base font-medium text-slate-800">
                  {filter === 'all' ? '最近还没有审计记录' : '当前筛选下没有审计记录'}
                </div>
                <div className="mt-2 text-sm text-slate-500">
                  这里只展示最近 24 小时内最新的 {limit} 条登录与 WebUI 操作。
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full overflow-y-auto">
              <div className="min-h-full divide-y divide-slate-200 bg-white">
                {filteredEvents.map((event, index) => {
                  const client = getClient(event)
                  const browser = client.browser || {}
                  return (
                    <button
                      key={`${getEventKey(event)}:${index}`}
                      type="button"
                      onClick={() => setSelectedEvent(event)}
                      className={`w-full text-left px-4 py-0 transition-colors md:px-6 ${getRowClasses(event)}`}
                    >
                      <div className="flex h-16 w-full items-center gap-3 min-w-0">
                        <div className="flex w-24 shrink-0 items-center gap-2 text-xs font-medium text-slate-500 md:w-32">
                          {event.success === false ? <AlertCircle className="w-4 h-4" /> : <Shield className="w-4 h-4" />}
                          <span className="truncate">{getEventLabel(event)}</span>
                        </div>

                        <div className="hidden md:flex w-44 shrink-0 items-center gap-1 text-xs text-slate-500">
                          <Clock className="w-3.5 h-3.5" />
                          <span className="truncate">{formatTime(event.timestamp)}</span>
                        </div>

                        <div className="w-24 shrink-0 text-sm font-medium text-slate-900 truncate md:w-36">
                          {event.username || 'unknown'}
                        </div>

                        <div className="hidden sm:flex w-32 shrink-0 items-center gap-1 text-xs text-slate-500 md:w-48">
                          <Globe2 className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{event.ip_address || event.details?.ip || '未知 IP'}</span>
                        </div>

                        <div className="hidden lg:flex w-56 shrink-0 items-center gap-1 text-xs text-slate-500">
                          <Fingerprint className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">
                            {client.fingerprint || `${browser.name || 'Unknown'} / ${client.engine || 'Unknown'}`}
                          </span>
                        </div>

                        <div className="min-w-0 flex-1 text-sm text-slate-700 truncate">
                          {formatDetails(event)}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedEvent ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-slate-950/20 md:hidden"
            onClick={() => setSelectedEvent(null)}
            aria-label="关闭详情"
          />
          <div className="fixed right-0 top-16 bottom-0 z-40 w-full border-l border-slate-200 bg-white shadow-2xl md:w-[560px]">
            <div className="flex h-full flex-col min-w-0">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-4 md:px-6">
                <div className="min-w-0">
                  <div className="text-base font-semibold text-slate-900">{getEventLabel(selectedEvent)}</div>
                  <div className="mt-1 text-xs text-slate-500 truncate">
                    {formatTime(selectedEvent.timestamp)} · {selectedEvent.username || 'unknown'}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedEvent(null)}
                  className="ml-4 h-10 w-10 shrink-0 flex items-center justify-center text-slate-500 hover:text-slate-900"
                  aria-label="关闭详情"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
                <div className="grid gap-3 text-sm text-slate-700">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs font-medium text-slate-500">来源</div>
                    <div className="mt-1">{selectedEvent.resource || 'webui'} / {selectedEvent.action || '-'}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs font-medium text-slate-500">IP 与位置</div>
                    <div className="mt-1">{selectedEvent.ip_address || selectedEvent.details?.ip || '未知 IP'}</div>
                    <div className="mt-1 text-xs text-slate-500">{getGeoText(selectedEvent)}</div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs font-medium text-slate-500">浏览器 / 内核 / 系统</div>
                    <div className="mt-1">
                      {(() => {
                        const client = getClient(selectedEvent)
                        const browser = client.browser || {}
                        return `${browser.name || 'Unknown'} ${browser.version || ''} / ${client.engine || 'Unknown'} / ${client.os || 'Unknown'}`
                      })()}
                    </div>
                    <div className="mt-1 break-all font-mono text-xs text-slate-500">
                      {getClient(selectedEvent).fingerprint || '-'}
                    </div>
                  </div>
                </div>

                <div className="mt-6">
                  <div className="text-xs uppercase tracking-[0.18em] text-slate-500">详细信息</div>
                  <pre className="mt-3 whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                    {JSON.stringify(selectedEvent.details || {}, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
