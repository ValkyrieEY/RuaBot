import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bell,
  Clock,
  MessageSquare,
  RefreshCw,
  User,
  UserPlus,
  Users,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'
import { api, type MessageLog } from '@/utils/api'
import { useWebSocket, type WebSocketMessage } from '@/hooks/useWebSocket'

type MessageFilter = 'all' | 'message' | 'notice' | 'request'

export default function MessageLogPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<MessageLog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<MessageFilter>('all')
  const [selectedMessage, setSelectedMessage] = useState<MessageLog | null>(null)
  const messagesRef = useRef<MessageLog[]>([])
  const limit = 300

  const getEventKey = (msg: MessageLog) => {
    return (
      msg.id ||
      `${(msg as any).event_type || ''}:${(msg as any).message_id || ''}:${msg.time || (msg as any).timestamp || ''}:${msg.raw_message || msg.message || ''}`
    )
  }

  const getEventTime = (msg: MessageLog) => {
    const raw = msg.time || (msg as any).timestamp
    const ts = raw ? new Date(raw).getTime() : 0
    return Number.isNaN(ts) ? 0 : ts
  }

  const mergeMessageLists = (base: MessageLog[], incoming: MessageLog[], nextLimit: number) => {
    const byKey = new Map<string, MessageLog>()

    const upsert = (msg: MessageLog) => {
      byKey.set(getEventKey(msg), msg)
    }

    base.forEach(upsert)
    incoming.forEach(upsert)

    return Array.from(byKey.values())
      .sort((a, b) => getEventTime(b) - getEventTime(a))
      .slice(0, nextLimit)
  }

  const loadMessages = async (replace = true) => {
    if (replace && messagesRef.current.length === 0) {
      setLoading(true)
    }

    try {
      const data = await api.getSessionMessageLog(limit)
      setMessages((prev) => (replace ? mergeMessageLists([], data, limit) : mergeMessageLists(prev, data, limit)))
    } catch (error) {
      console.error('Failed to load session messages:', error)
    } finally {
      setLoading(false)
    }
  }

  const compensateMissedMessages = async () => {
    await loadMessages(false)
  }

  const { isConnected } = useWebSocket({
    onMessage: (wsMessage: WebSocketMessage) => {
      if (!['message', 'notice', 'request'].includes(wsMessage.type)) {
        return
      }
      setMessages((prev) => mergeMessageLists(prev, [wsMessage as MessageLog], limit))
    },
    onConnected: () => {
      console.log('[MessageLog] WebSocket connected')
      compensateMissedMessages()
    },
    onDisconnected: () => {
      console.log('[MessageLog] WebSocket disconnected')
    }
  })

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    loadMessages()

    let interval: ReturnType<typeof setInterval> | null = null
    if (!isConnected) {
      interval = setInterval(() => {
        compensateMissedMessages()
      }, 5000)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isConnected])

  const formatTime = (timestamp: string | undefined) => {
    if (!timestamp) return '--'
    try {
      const date = new Date(timestamp)
      if (Number.isNaN(date.getTime())) {
        return timestamp
      }
      return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return timestamp || '--'
    }
  }

  const filteredMessages = messages.filter((msg) => {
    if (filter === 'all') return true
    return ((msg as any).event_type || 'message') === filter
  })

  const counts = {
    all: messages.length,
    message: messages.filter((msg) => ((msg as any).event_type || 'message') === 'message').length,
    notice: messages.filter((msg) => (msg as any).event_type === 'notice').length,
    request: messages.filter((msg) => (msg as any).event_type === 'request').length,
  }

  const filters: Array<{
    key: MessageFilter
    label: string
    icon: typeof MessageSquare
  }> = [
    { key: 'all', label: t('common.all'), icon: MessageSquare },
    { key: 'message', label: t('messages.message'), icon: MessageSquare },
    { key: 'notice', label: t('messages.notice'), icon: Bell },
    { key: 'request', label: t('messages.request'), icon: UserPlus },
  ]

  const getEventLabel = (msg: MessageLog) => {
    const eventType = (msg as any).event_type || 'message'
    if (eventType === 'notice') return t('messages.systemNotice')
    if (eventType === 'request') return t('messages.requestEvent')

    const isSelf = Boolean((msg as any).is_self)
    if (msg.message_type === 'group') {
      return isSelf ? '机器人群消息' : (msg.sender?.nickname || `用户 ${msg.user_id}`)
    }
    return isSelf ? '机器人私聊消息' : (msg.sender?.nickname || `用户 ${msg.user_id}`)
  }

  const getMetaLabel = (msg: MessageLog) => {
    const eventType = (msg as any).event_type || 'message'
    if (eventType !== 'message') {
      return msg.group_id ? `群 ${msg.group_id}` : '系统事件'
    }

    if (msg.message_type === 'group' && msg.group_id) {
      return `群 ${msg.group_id}`
    }

    const isSelf = Boolean((msg as any).is_self)
    const privateId = isSelf ? (msg as any).target_id || msg.user_id : msg.user_id
    return privateId ? `私聊 ${privateId}` : '私聊'
  }

  const renderTypeIcon = (msg: MessageLog) => {
    const eventType = (msg as any).event_type || 'message'
    if (eventType === 'notice') return <Bell className="w-4 h-4" />
    if (eventType === 'request') return <UserPlus className="w-4 h-4" />
    return msg.message_type === 'group' ? <Users className="w-4 h-4" /> : <User className="w-4 h-4" />
  }

  const getRowClasses = (msg: MessageLog) => {
    const eventType = (msg as any).event_type || 'message'
    const isSelf = Boolean((msg as any).is_self)

    if (eventType === 'notice') return 'border-l-4 border-l-blue-500 bg-blue-50 hover:bg-blue-100/80'
    if (eventType === 'request') return 'border-l-4 border-l-yellow-500 bg-yellow-50 hover:bg-yellow-100/80'
    if (isSelf) return 'border-l-4 border-l-emerald-500 bg-emerald-50 hover:bg-emerald-100/80'
    return 'border-l-4 border-l-transparent bg-white hover:bg-slate-50'
  }

  const getPreviewText = (msg: MessageLog) => {
    return String(msg.message || msg.raw_message || '[空消息]')
      .replace(/\s+/g, ' ')
      .trim()
  }

  const getViewerTitle = (msg: MessageLog) => {
    const eventType = (msg as any).event_type || 'message'
    if (eventType === 'notice') return '通知详情'
    if (eventType === 'request') return '请求详情'
    return '消息详情'
  }

  return (
    <div className="fixed top-16 left-0 right-0 bottom-0 md:left-64 flex bg-white overflow-hidden">
      <div className="flex w-full min-w-0 flex-col">
        <div className="h-16 shrink-0 border-b border-slate-200 bg-white px-4 md:px-6">
          <div className="flex h-full items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3 min-w-0">
                <h1 className="truncate text-lg font-semibold text-slate-900">{t('messages.title')}</h1>
                <span className="hidden sm:inline text-sm text-slate-500">仅显示本次启动后的消息</span>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <div className="hidden sm:flex items-center gap-2 text-sm text-slate-500">
                {isConnected ? (
                  <>
                    <Wifi className="w-4 h-4 text-emerald-500" />
                    <span>{t('messages.realtime')}</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-4 h-4 text-amber-500" />
                    <span>{t('messages.polling')}</span>
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={() => loadMessages(true)}
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
          </div>
        </div>

        <div className="flex-1 min-h-0 bg-slate-100">
          {loading && messages.length === 0 ? (
            <div className="flex h-full items-center justify-center px-6 text-slate-500">
              <div className="flex items-center gap-3 text-sm">
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>正在载入本次启动消息</span>
              </div>
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="flex h-full items-center justify-center px-6">
              <div className="max-w-md text-center">
                <MessageSquare className="w-10 h-10 text-slate-300 mx-auto mb-4" />
                <div className="text-base font-medium text-slate-800">
                  {filter === 'all' ? '本次启动还没有消息' : '当前筛选下没有消息'}
                </div>
                <div className="mt-2 text-sm text-slate-500">
                  历史消息仍然保留在消息发送页面，这里只展示当前启动期间的新消息流。
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full overflow-y-auto">
              <div className="min-h-full divide-y divide-slate-200 bg-white">
                {filteredMessages.map((msg, index) => (
                  <button
                    key={msg.id || `${getEventKey(msg)}:${index}`}
                    type="button"
                    onClick={() => setSelectedMessage(msg)}
                    className={`w-full text-left px-4 py-0 transition-colors md:px-6 ${getRowClasses(msg)}`}
                  >
                    <div className="flex h-16 w-full items-center gap-3 min-w-0">
                      <div className="flex w-24 shrink-0 items-center gap-2 text-xs font-medium text-slate-500 md:w-32">
                        {renderTypeIcon(msg)}
                        <span className="truncate">
                          {((msg as any).event_type || 'message') === 'notice' ? t('messages.notice') : ((msg as any).event_type || 'message') === 'request' ? t('messages.request') : t('messages.message')}
                        </span>
                      </div>

                      <div className="hidden md:flex w-44 shrink-0 items-center gap-1 text-xs text-slate-500">
                        <Clock className="w-3.5 h-3.5" />
                        <span className="truncate">{formatTime(msg.time || msg.timestamp)}</span>
                      </div>

                      <div className="w-28 shrink-0 text-sm font-medium text-slate-900 truncate md:w-44">
                        {getEventLabel(msg)}
                      </div>

                      <div className="hidden sm:flex w-28 shrink-0 items-center gap-1 text-xs text-slate-500 md:w-40">
                        {msg.message_type === 'group' ? <Users className="w-3.5 h-3.5 shrink-0" /> : <User className="w-3.5 h-3.5 shrink-0" />}
                        <span className="truncate">{getMetaLabel(msg)}</span>
                      </div>

                      <div className="min-w-0 flex-1 text-sm text-slate-700 truncate">
                        {getPreviewText(msg)}
                      </div>

                      {(msg as any).is_self ? (
                        <div className="hidden lg:block shrink-0 text-xs font-medium text-emerald-600">机器人发送</div>
                      ) : null}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {selectedMessage ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-slate-950/20 md:hidden"
            onClick={() => setSelectedMessage(null)}
            aria-label="关闭详情"
          />
          <div className="fixed right-0 top-16 bottom-0 z-40 w-full border-l border-slate-200 bg-white shadow-2xl md:w-[520px]">
            <div className="flex h-full flex-col min-w-0">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-4 md:px-6">
                <div className="min-w-0">
                  <div className="text-base font-semibold text-slate-900">{getViewerTitle(selectedMessage)}</div>
                  <div className="mt-1 text-xs text-slate-500 truncate">
                    {formatTime(selectedMessage.time || selectedMessage.timestamp)} · {getMetaLabel(selectedMessage)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedMessage(null)}
                  className="ml-4 h-10 w-10 shrink-0 flex items-center justify-center text-slate-500 hover:text-slate-900"
                  aria-label="关闭详情"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                  {renderTypeIcon(selectedMessage)}
                  <span>{getEventLabel(selectedMessage)}</span>
                </div>
                <div className="mt-3 text-sm text-slate-500">
                  {getMetaLabel(selectedMessage)}
                </div>
                <pre className="mt-6 whitespace-pre-wrap break-words text-[14px] leading-7 text-slate-800">
                  {selectedMessage.message || selectedMessage.raw_message || '[空消息]'}
                </pre>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
