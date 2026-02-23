import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type MessageLog } from '@/utils/api'
import { MessageSquare, User, Users, Clock, RefreshCw, Bell, UserPlus, Wifi, WifiOff } from 'lucide-react'
import { useWebSocket, type WebSocketMessage } from '@/hooks/useWebSocket'

export default function MessageLogPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<MessageLog[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [filter, setFilter] = useState<'all' | 'message' | 'notice' | 'request'>('all')

  // WebSocket for real-time updates
  const { isConnected } = useWebSocket({
    onMessage: (wsMessage: WebSocketMessage) => {
      // Add new message to the top of the list
      setMessages((prev) => {
        // Check if message already exists (by id)
        if (prev.some((m) => m.id === wsMessage.id)) {
          return prev
        }
        // Add new message and maintain limit
        const newMessages = [wsMessage as MessageLog, ...prev]
        return newMessages.slice(0, limit)
      })
    },
    onConnected: () => {
      console.log('[MessageLog] WebSocket connected')
    },
    onDisconnected: () => {
      console.log('[MessageLog] WebSocket disconnected')
    }
  })

  useEffect(() => {
    loadMessages()
    // Still use polling as fallback, but with longer interval (30 seconds)
    let interval: ReturnType<typeof setInterval> | null = null
    if (autoRefresh && !isConnected) {
      interval = setInterval(loadMessages, 30000) // Fallback polling every 30 seconds when WebSocket disconnected
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [limit, autoRefresh, isConnected])

  const loadMessages = async (showRefreshing = false) => {
    if (showRefreshing) {
      setRefreshing(true)
    } else if (messages.length === 0) {
      setLoading(true)
    }
    try {
      const data = await api.getMessageLog(limit)
      setMessages(data)
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const formatTime = (timestamp: string | undefined) => {
    if (!timestamp) return 'Invalid Date'
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) {
        return timestamp
      }
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return timestamp || 'Invalid Date'
    }
  }

  // Filter messages based on selected filter
  const filteredMessages = messages.filter((msg) => {
    if (filter === 'all') return true
    const eventType = (msg as any).event_type || 'message'
    return eventType === filter
  })

  if (loading && messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col space-y-6 max-w-full overflow-x-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-shrink">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('messages.title')}</h1>
            {/* WebSocket Status Indicator */}
            <div className="flex items-center gap-1.5 text-xs">
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-500" />
                  <span className="text-green-600 font-medium">{t('messages.realtime')}</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-orange-500" />
                  <span className="text-orange-600 font-medium">{t('messages.polling')}</span>
                </>
              )}
            </div>
          </div>
          <p className="text-gray-500 text-sm mt-1">
            {t('messages.description')} {isConnected ? ` (${t('messages.realtimePush')})` : ` (${t('messages.pollingRefresh')})`}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <label className="flex items-center gap-1 text-xs text-gray-600 cursor-pointer whitespace-nowrap">
            <span className="hidden md:inline">{t('common.auto')}</span>
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              style={{ backgroundColor: autoRefresh ? '#3b82f6' : '#d1d5db' }}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  autoRefresh ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="input py-1.5 text-xs w-[80px]"
          >
            <option value={50}>50条</option>
            <option value={100}>100条</option>
            <option value={200}>200条</option>
            <option value={500}>500条</option>
          </select>
          <button
            onClick={() => loadMessages(true)}
            disabled={refreshing}
            className="btn btn-secondary flex items-center justify-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap text-xs px-2 py-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{t('common.refresh')}</span>
          </button>
        </div>
      </div>

      {/* Filter Buttons */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            filter === 'all'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          {t('common.all')} ({messages.length})
        </button>
        <button
          onClick={() => setFilter('message')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
            filter === 'message'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          {t('messages.message')} ({messages.filter(m => !(m as any).is_system).length})
        </button>
        <button
          onClick={() => setFilter('notice')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
            filter === 'notice'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <Bell className="w-4 h-4" />
          {t('messages.notice')} ({messages.filter(m => (m as any).event_type === 'notice').length})
        </button>
        <button
          onClick={() => setFilter('request')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
            filter === 'request'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          <UserPlus className="w-4 h-4" />
          {t('messages.request')} ({messages.filter(m => (m as any).event_type === 'request').length})
        </button>
      </div>

      {/* Messages */}
      <div className="space-y-3">
        {filteredMessages.length === 0 ? (
          <div className="card text-center py-12">
            <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {filter === 'all' ? t('messages.noEvents') : filter === 'message' ? t('messages.noMessages') : filter === 'notice' ? t('messages.noNotices') : t('messages.noRequests')}
            </h3>
            <p className="text-gray-500">
              {filter === 'all' ? t('messages.noEventsDesc') : filter === 'message' ? t('messages.noMessagesDesc') : filter === 'notice' ? t('messages.noNoticesDesc') : t('messages.noRequestsDesc')}
            </p>
          </div>
        ) : (
          filteredMessages.map((msg, index) => {
            const isSystem = (msg as any).is_system || (msg as any).event_type === 'notice' || (msg as any).event_type === 'request'
            const eventType = (msg as any).event_type || 'message'
            
            // System notification style
            if (isSystem) {
              return (
                <div
                  key={msg.id || index}
                  className="card hover:shadow-md transition-shadow bg-gradient-to-r from-yellow-50 to-orange-50 border-l-4 border-yellow-400"
                >
                  <div className="flex items-start gap-4">
                    {/* System Icon */}
                    <div className="flex-shrink-0">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center text-white">
                        {eventType === 'request' ? (
                          <UserPlus className="w-6 h-6" />
                        ) : (
                          <Bell className="w-6 h-6" />
                        )}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <span className="font-medium text-orange-900">
                          {eventType === 'notice' ? t('messages.systemNotice') : eventType === 'request' ? t('messages.requestEvent') : t('messages.systemMessage')}
                        </span>
                        {msg.group_id && (
                          <div className="flex items-center gap-1 text-xs text-orange-700 bg-orange-100 px-2 py-1 rounded">
                            <Users className="w-3 h-3" />
                            <span>{t('messages.group')} {msg.group_id}</span>
                          </div>
                        )}
                        <div className="flex items-center gap-1 text-xs text-orange-700">
                          <Clock className="w-3 h-3" />
                          <span>{formatTime(msg.time || msg.timestamp)}</span>
                        </div>
                      </div>
                      <p className="text-orange-900 font-medium break-words whitespace-pre-wrap">
                        {msg.message || msg.raw_message}
                      </p>
                    </div>
                  </div>
                </div>
              )
            }

            // Normal message style
            const isSelf = (msg as any).is_self || false
            // For private messages: if self-sent, show target_id; if received, show user_id
            // For group messages: always show user_id (sender)
            const displayUserId = msg.message_type === 'private' && isSelf 
              ? (msg as any).target_id || msg.user_id 
              : msg.user_id
            
            return (
              <div
                key={msg.id || index}
                className={`card hover:shadow-md transition-shadow ${
                  isSelf ? 'bg-gradient-to-r from-blue-50 to-primary-50 border-l-4 border-primary-400' : ''
                }`}
              >
                <div className="flex items-start gap-4">
                  {/* Avatar */}
                  <div className="flex-shrink-0">
                    {displayUserId ? (
                      <img
                        src={`https://q.qlogo.cn/headimg_dl?dst_uin=${displayUserId}&spec=640`}
                        alt={msg.sender?.nickname || `User ${displayUserId}`}
                        className="w-12 h-12 rounded-full object-cover"
                        onError={(e) => {
                          // Fallback to gradient avatar if image fails
                          const target = e.currentTarget as HTMLImageElement
                          target.style.display = 'none'
                          const parent = target.parentElement
                          if (parent) {
                            const fallback = document.createElement('div')
                            fallback.className = `w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                              isSelf 
                                ? 'bg-gradient-to-br from-primary-500 to-primary-600' 
                                : 'bg-gradient-to-br from-blue-400 to-purple-600'
                            }`
                            fallback.textContent = msg.sender?.nickname?.[0]?.toUpperCase() || 'U'
                            parent.appendChild(fallback)
                          }
                        }}
                      />
                    ) : (
                      <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                        isSelf 
                          ? 'bg-gradient-to-br from-primary-500 to-primary-600' 
                          : 'bg-gradient-to-br from-blue-400 to-purple-600'
                      }`}>
                        {msg.sender?.nickname?.[0]?.toUpperCase() || 'U'}
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`font-medium ${isSelf ? 'text-primary-900' : 'text-gray-900'}`}>
                        {msg.sender?.nickname || `User ${displayUserId}`}
                        {displayUserId && (
                          <span className="ml-2 text-xs text-gray-500">({displayUserId})</span>
                        )}
                        {isSelf && <span className="ml-2 text-xs text-primary-600">{t('messages.me')}</span>}
                      </span>
                      {msg.message_type === 'group' ? (
                        <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${
                          isSelf ? 'text-primary-700 bg-primary-100' : 'text-gray-500 bg-blue-50'
                        }`}>
                          <Users className="w-3 h-3" />
                          <span>{t('messages.group')} {msg.group_id}</span>
                        </div>
                      ) : (
                        <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${
                          isSelf ? 'text-primary-700 bg-primary-100' : 'text-gray-500 bg-purple-50'
                        }`}>
                          <User className="w-3 h-3" />
                          <span>{t('messages.private')}</span>
                          {msg.message_type === 'private' && displayUserId && (
                            <span className="ml-1">{displayUserId}</span>
                          )}
                        </div>
                      )}
                      <div className={`flex items-center gap-1 text-xs ${
                        isSelf ? 'text-primary-700' : 'text-gray-500'
                      }`}>
                        <Clock className="w-3 h-3" />
                        <span>{formatTime(msg.time || msg.timestamp)}</span>
                      </div>
                    </div>
                    <p className={`break-words whitespace-pre-wrap ${
                      isSelf ? 'text-primary-900 font-medium' : 'text-gray-700'
                    }`}>
                      {msg.message || msg.raw_message}
                    </p>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
