import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type MessageLog } from '@/utils/api'
import { MessageSquare, User, Users, Clock, RefreshCw, Bell, UserPlus } from 'lucide-react'

export default function MessageLogPage() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<MessageLog[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [limit, setLimit] = useState(100)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [filter, setFilter] = useState<'all' | 'message' | 'notice' | 'request'>('all')

  useEffect(() => {
    loadMessages()
    let interval: ReturnType<typeof setInterval> | null = null
    if (autoRefresh) {
      interval = setInterval(loadMessages, 5000) // Auto-refresh every 5 seconds
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [limit, autoRefresh])

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
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('messages.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">查看消息、通知和请求事件</p>
        </div>
        <div className="flex items-center gap-2 sm:gap-4 flex-nowrap flex-shrink-0">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer whitespace-nowrap">
            <span>自动刷新</span>
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 flex-shrink-0"
              style={{ backgroundColor: autoRefresh ? '#3b82f6' : '#d1d5db' }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  autoRefresh ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="input py-2 text-sm min-w-[120px]"
          >
            <option value={50}>最近 50 条</option>
            <option value={100}>最近 100 条</option>
            <option value={200}>最近 200 条</option>
            <option value={500}>最近 500 条</option>
          </select>
          <button
            onClick={() => loadMessages(true)}
            disabled={refreshing}
            className="btn btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>刷新</span>
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
          全部 ({messages.length})
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
          消息 ({messages.filter(m => !(m as any).is_system).length})
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
          通知 ({messages.filter(m => (m as any).event_type === 'notice').length})
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
          请求 ({messages.filter(m => (m as any).event_type === 'request').length})
        </button>
      </div>

      {/* Messages */}
      <div className="space-y-3">
        {filteredMessages.length === 0 ? (
          <div className="card text-center py-12">
            <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">暂无{filter === 'all' ? '事件' : filter === 'message' ? '消息' : filter === 'notice' ? '通知' : '请求'}</h3>
            <p className="text-gray-500">当前没有接收到{filter === 'all' ? '任何事件' : filter === 'message' ? '任何消息' : filter === 'notice' ? '任何通知' : '任何请求'}</p>
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
                          {eventType === 'notice' ? '系统通知' : eventType === 'request' ? '请求事件' : '系统消息'}
                        </span>
                        {msg.group_id && (
                          <div className="flex items-center gap-1 text-xs text-orange-700 bg-orange-100 px-2 py-1 rounded">
                            <Users className="w-3 h-3" />
                            <span>群 {msg.group_id}</span>
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
            
            return (
              <div
                key={msg.id || index}
                className={`card hover:shadow-md transition-shadow ${
                  isSelf ? 'bg-gradient-to-r from-green-50 to-blue-50 border-l-4 border-green-400' : ''
                }`}
              >
                <div className="flex items-start gap-4">
                  {/* Avatar */}
                  <div className="flex-shrink-0">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                      isSelf 
                        ? 'bg-gradient-to-br from-green-400 to-blue-500' 
                        : 'bg-gradient-to-br from-blue-400 to-purple-600'
                    }`}>
                      {msg.sender?.nickname?.[0]?.toUpperCase() || 'U'}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`font-medium ${isSelf ? 'text-green-900' : 'text-gray-900'}`}>
                        {msg.sender?.nickname || `User ${msg.user_id}`}
                        {isSelf && <span className="ml-2 text-xs text-green-600">(我)</span>}
                      </span>
                      {msg.message_type === 'group' ? (
                        <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${
                          isSelf ? 'text-green-700 bg-green-100' : 'text-gray-500 bg-blue-50'
                        }`}>
                          <Users className="w-3 h-3" />
                          <span>群 {msg.group_id}</span>
                        </div>
                      ) : (
                        <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded ${
                          isSelf ? 'text-green-700 bg-green-100' : 'text-gray-500 bg-purple-50'
                        }`}>
                          <User className="w-3 h-3" />
                          <span>私聊</span>
                        </div>
                      )}
                      <div className={`flex items-center gap-1 text-xs ${
                        isSelf ? 'text-green-700' : 'text-gray-500'
                      }`}>
                        <Clock className="w-3 h-3" />
                        <span>{formatTime(msg.time || msg.timestamp)}</span>
                      </div>
                    </div>
                    <p className={`break-words whitespace-pre-wrap ${
                      isSelf ? 'text-green-900 font-medium' : 'text-gray-700'
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
