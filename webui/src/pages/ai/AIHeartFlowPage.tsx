import { useState, useEffect } from 'react'
import { Heart, Activity, Users, MessageSquare, TrendingUp, Loader2 } from 'lucide-react'

interface ChatMetrics {
  chat_id: string
  atmosphere: string
  topic_activity: number
  emotional_state: string
  emotion_intensity: number
  emotion_stability: number
  active_participants: number
  message_count: number
  reply_count: number
  reply_ratio: number
}

export default function AIHeartFlowPage() {
  const [loading, setLoading] = useState(false)
  const [chats, setChats] = useState<ChatMetrics[]>([])
  const [selectedChat, setSelectedChat] = useState<ChatMetrics | null>(null)

  useEffect(() => {
    loadChats()
    const interval = setInterval(loadChats, 5000) // Auto refresh every 5s
    return () => clearInterval(interval)
  }, [])

  const loadChats = async () => {
    try {
      const response = await fetch('/api/ai/heartflow/chats')
      const data = await response.json()
      setChats(data.chats || [])
    } catch (error) {
      console.error('Failed to load chats:', error)
    }
  }

  const loadChatDetails = async (chatId: string) => {
    setLoading(true)
    try {
      const response = await fetch(`/api/ai/heartflow/stats/${encodeURIComponent(chatId)}`)
      const data = await response.json()
      setSelectedChat({ chat_id: chatId, ...data })
    } catch (error) {
      console.error('Failed to load chat details:', error)
    } finally {
      setLoading(false)
    }
  }

  const getAtmosphereColor = (atmosphere: string) => {
    switch (atmosphere) {
      case 'silent': return 'bg-gray-100 text-gray-700'
      case 'calm': return 'bg-blue-100 text-blue-700'
      case 'active': return 'bg-green-100 text-green-700'
      case 'heated': return 'bg-orange-100 text-orange-700'
      case 'chaotic': return 'bg-red-100 text-red-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const getAtmosphereLabel = (atmosphere: string) => {
    const labels: Record<string, string> = {
      silent: '沉默',
      calm: '平静',
      active: '活跃',
      heated: '热烈',
      chaotic: '混乱'
    }
    return labels[atmosphere] || atmosphere
  }

  const getEmotionEmoji = (emotion: string) => {
    const emojis: Record<string, string> = {
      neutral: '😐',
      happy: '😊',
      excited: '🤩',
      sad: '😢',
      angry: '😠',
      confused: '😕',
      thoughtful: '🤔'
    }
    return emojis[emotion] || '😐'
  }

  const getEmotionLabel = (emotion: string) => {
    const labels: Record<string, string> = {
      neutral: '中立',
      happy: '开心',
      excited: '兴奋',
      sad: '悲伤',
      angry: '愤怒',
      confused: '困惑',
      thoughtful: '思考'
    }
    return labels[emotion] || emotion
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Heart className="w-7 h-7 text-red-500" />
          HeartFlow 对话流监控
        </h2>
        <button
          onClick={loadChats}
          className="px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          刷新
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-2">
          <Activity className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-800">
            <div className="font-medium mb-1">HeartFlow 对话流管理系统</div>
            <div>实时监控对话氛围、情感状态、参与度等指标，智能调节回复策略</div>
          </div>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm opacity-90">活跃对话</div>
            <MessageSquare className="w-5 h-5 opacity-75" />
          </div>
          <div className="text-3xl font-bold">{chats.length}</div>
        </div>

        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm opacity-90">总消息数</div>
            <Activity className="w-5 h-5 opacity-75" />
          </div>
          <div className="text-3xl font-bold">
            {chats.reduce((sum, chat) => sum + (chat.message_count || 0), 0)}
          </div>
        </div>

        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm opacity-90">总回复数</div>
            <MessageSquare className="w-5 h-5 opacity-75" />
          </div>
          <div className="text-3xl font-bold">
            {chats.reduce((sum, chat) => sum + (chat.reply_count || 0), 0)}
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg p-6 text-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm opacity-90">平均回复率</div>
            <TrendingUp className="w-5 h-5 opacity-75" />
          </div>
          <div className="text-3xl font-bold">
            {chats.length > 0
              ? (chats.reduce((sum, chat) => sum + (chat.reply_ratio || 0), 0) / chats.length * 100).toFixed(1)
              : 0}%
          </div>
        </div>
      </div>

      {/* Chat List */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">对话列表</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {chats.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              暂无活跃对话
            </div>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.chat_id}
                className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
                onClick={() => loadChatDetails(chat.chat_id)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium text-gray-900">{chat.chat_id}</div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-xs rounded-full ${getAtmosphereColor(chat.atmosphere)}`}>
                      {getAtmosphereLabel(chat.atmosphere)}
                    </span>
                    <span className="text-2xl">
                      {getEmotionEmoji(chat.emotional_state)}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
                  <div>
                    <div className="text-xs text-gray-500">活跃参与者</div>
                    <div className="font-medium">{chat.active_participants}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">消息数</div>
                    <div className="font-medium">{chat.message_count}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">回复率</div>
                    <div className="font-medium">{(chat.reply_ratio * 100).toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">话题活跃度</div>
                    <div className="font-medium">{(chat.topic_activity * 100).toFixed(0)}%</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Selected Chat Details */}
      {selectedChat && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-lg font-semibold">对话详情: {selectedChat.chat_id}</h3>
            <button
              onClick={() => setSelectedChat(null)}
              className="text-gray-500 hover:text-gray-700"
            >
              关闭
            </button>
          </div>
          
          {loading ? (
            <div className="px-6 py-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
            </div>
          ) : (
            <div className="p-6 space-y-6">
              {/* Atmosphere & Emotion */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-3">对话氛围</div>
                  <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-lg font-medium ${getAtmosphereColor(selectedChat.atmosphere)}`}>
                    <Activity className="w-5 h-5" />
                    {getAtmosphereLabel(selectedChat.atmosphere)}
                  </div>
                  <div className="mt-3 text-xs text-gray-600">
                    氛围等级反映对话的热度和节奏
                  </div>
                </div>

                <div>
                  <div className="text-sm font-medium text-gray-700 mb-3">情感状态</div>
                  <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-lg font-medium bg-purple-100 text-purple-700">
                    <span className="text-2xl">{getEmotionEmoji(selectedChat.emotional_state)}</span>
                    {getEmotionLabel(selectedChat.emotional_state)}
                  </div>
                  <div className="mt-3 space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">情感强度</span>
                      <span className="font-medium">{(selectedChat.emotion_intensity * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-purple-500 h-2 rounded-full transition-all"
                        style={{ width: `${selectedChat.emotion_intensity * 100}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs mt-2">
                      <span className="text-gray-600">情感稳定性</span>
                      <span className="font-medium">{(selectedChat.emotion_stability * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-500 h-2 rounded-full transition-all"
                        style={{ width: `${selectedChat.emotion_stability * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-4 h-4 text-blue-600" />
                    <div className="text-xs text-blue-600">活跃参与者</div>
                  </div>
                  <div className="text-2xl font-bold text-blue-900">{selectedChat.active_participants}</div>
                </div>

                <div className="bg-green-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare className="w-4 h-4 text-green-600" />
                    <div className="text-xs text-green-600">总消息数</div>
                  </div>
                  <div className="text-2xl font-bold text-green-900">{selectedChat.message_count}</div>
                </div>

                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Heart className="w-4 h-4 text-purple-600" />
                    <div className="text-xs text-purple-600">回复次数</div>
                  </div>
                  <div className="text-2xl font-bold text-purple-900">{selectedChat.reply_count}</div>
                </div>

                <div className="bg-orange-50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="w-4 h-4 text-orange-600" />
                    <div className="text-xs text-orange-600">回复率</div>
                  </div>
                  <div className="text-2xl font-bold text-orange-900">
                    {(selectedChat.reply_ratio * 100).toFixed(1)}%
                  </div>
                </div>
              </div>

              {/* Topic Activity */}
              <div>
                <div className="text-sm font-medium text-gray-700 mb-3">话题活跃度</div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-4 rounded-full transition-all flex items-center justify-end pr-2"
                    style={{ width: `${selectedChat.topic_activity * 100}%` }}
                  >
                    <span className="text-xs text-white font-medium">
                      {(selectedChat.topic_activity * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-600">
                  话题活跃度越高，说明当前话题受到的关注越多
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

