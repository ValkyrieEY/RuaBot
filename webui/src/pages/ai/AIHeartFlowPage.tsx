import { useState, useEffect } from 'react'
import { Heart, Activity, Users, MessageSquare, TrendingUp, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import axios from 'axios'

const getClient = () => {
  const token = localStorage.getItem('access_token')
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  })
}

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

const atmosphereConfig = {
  silent: { label: '沉默', color: 'gray', bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-300' },
  calm: { label: '平静', color: 'blue', bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-300' },
  active: { label: '活跃', color: 'green', bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-300' },
  heated: { label: '热烈', color: 'orange', bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300' },
  chaotic: { label: '混乱', color: 'red', bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300' }
}

const emotionConfig = {
  neutral: { label: '中立', emoji: '😐', color: 'gray' },
  happy: { label: '开心', emoji: '😊', color: 'green' },
  excited: { label: '兴奋', emoji: '🤩', color: 'yellow' },
  sad: { label: '悲伤', emoji: '😢', color: 'blue' },
  angry: { label: '愤怒', emoji: '😠', color: 'red' },
  confused: { label: '困惑', emoji: '😕', color: 'purple' },
  thoughtful: { label: '思考', emoji: '🤔', color: 'indigo' }
}

export default function AIHeartFlowPage() {
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [chats, setChats] = useState<ChatMetrics[]>([])
  const [selectedChat, setSelectedChat] = useState<ChatMetrics | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  useEffect(() => {
    loadChats()
    if (autoRefresh) {
      const interval = setInterval(loadChats, 5000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  const loadChats = async () => {
    try {
      const response = await getClient().get('/ai/heartflow/chats')
      setChats(response.data.chats || [])
    } catch (error) {
      console.error('Failed to load chats:', error)
    }
  }

  const loadChatDetails = async (chatId: string) => {
    setLoading(true)
    try {
      const response = await getClient().get(`/ai/heartflow/stats/${encodeURIComponent(chatId)}`)
      setSelectedChat({ chat_id: chatId, ...response.data })
    } catch (error) {
      console.error('Failed to load chat details:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadChats()
    setTimeout(() => setRefreshing(false), 500)
  }

  const totalMessages = chats.reduce((sum, chat) => sum + (chat.message_count || 0), 0)
  const totalReplies = chats.reduce((sum, chat) => sum + (chat.reply_count || 0), 0)
  const avgReplyRatio = chats.length > 0
    ? (chats.reduce((sum, chat) => sum + (chat.reply_ratio || 0), 0) / chats.length * 100)
    : 0
  const activeChats = chats.filter(c => c.atmosphere !== 'silent').length

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-pink-50 to-purple-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-3 bg-gradient-to-br from-red-500 to-pink-500 rounded-xl shadow-lg">
                <Heart className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-4xl font-bold bg-gradient-to-r from-red-600 to-pink-600 bg-clip-text text-transparent">
                  HeartFlow 对话流
                </h1>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-4 py-2 rounded-lg border-2 transition-all ${
                autoRefresh 
                  ? 'bg-green-50 border-green-500 text-green-700'
                  : 'bg-gray-50 border-gray-300 text-gray-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Sparkles className={`w-4 h-4 ${autoRefresh ? 'animate-pulse' : ''}`} />
                <span className="text-sm font-medium">
                  {autoRefresh ? '自动刷新' : '手动模式'}
                </span>
              </div>
            </button>
            
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-4 py-2 bg-white border-2 border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-5 h-5 text-gray-600 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-2xl shadow-lg border-2 border-purple-200 p-6 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <span className="text-3xl font-bold text-purple-600">{activeChats}</span>
          </div>
          <div className="text-sm font-medium text-gray-600">活跃对话</div>
          <div className="text-xs text-gray-500 mt-1">共 {chats.length} 个对话</div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border-2 border-green-200 p-6 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-gradient-to-br from-green-500 to-green-600 rounded-xl">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <span className="text-3xl font-bold text-green-600">{totalMessages}</span>
          </div>
          <div className="text-sm font-medium text-gray-600">总消息数</div>
          <div className="text-xs text-gray-500 mt-1">跨所有对话</div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border-2 border-blue-200 p-6 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl">
              <Heart className="w-6 h-6 text-white" />
            </div>
            <span className="text-3xl font-bold text-blue-600">{totalReplies}</span>
          </div>
          <div className="text-sm font-medium text-gray-600">AI 回复数</div>
          <div className="text-xs text-gray-500 mt-1">智能回复</div>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border-2 border-orange-200 p-6 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <span className="text-3xl font-bold text-orange-600">{avgReplyRatio.toFixed(1)}%</span>
          </div>
          <div className="text-sm font-medium text-gray-600">平均回复率</div>
          <div className="text-xs text-gray-500 mt-1">响应活跃度</div>
        </div>
      </div>

      {/* Chat List */}
      <div className="bg-white rounded-2xl shadow-xl border-2 border-gray-200 overflow-hidden">
        <div className="bg-gradient-to-r from-red-500 to-pink-500 px-6 py-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5" />
            对话列表
          </h2>
        </div>

        <div className="divide-y divide-gray-200">
          {chats.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="w-16 h-16 mx-auto mb-4 bg-gray-100 rounded-full flex items-center justify-center">
                <MessageSquare className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-500 text-lg">暂无活跃对话</p>
              <p className="text-gray-400 text-sm mt-2">当有新对话时，这里会显示相关信息</p>
            </div>
          ) : (
            chats.map((chat) => {
              const atmo = atmosphereConfig[chat.atmosphere as keyof typeof atmosphereConfig] || atmosphereConfig.calm
              const emo = emotionConfig[chat.emotional_state as keyof typeof emotionConfig] || emotionConfig.neutral

              return (
                <div
                  key={chat.chat_id}
                  className="px-6 py-5 hover:bg-gradient-to-r hover:from-purple-50 hover:to-pink-50 cursor-pointer transition-all group"
                  onClick={() => loadChatDetails(chat.chat_id)}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`text-4xl transition-transform group-hover:scale-125`}>
                        {emo.emoji}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-900 text-lg">{chat.chat_id}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${atmo.bg} ${atmo.text} border ${atmo.border}`}>
                            {atmo.label}
                          </span>
                          <span className="text-xs text-gray-500">
                            {emo.label} · 强度 {(chat.emotion_intensity * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                      <div className="text-xs text-gray-500 mb-1">活跃参与者</div>
                      <div className="text-lg font-bold text-gray-900">{chat.active_participants || 0}</div>
                    </div>
                    <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                      <div className="text-xs text-blue-600 mb-1">消息数</div>
                      <div className="text-lg font-bold text-blue-700">{chat.message_count || 0}</div>
                    </div>
                    <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                      <div className="text-xs text-green-600 mb-1">回复率</div>
                      <div className="text-lg font-bold text-green-700">{((chat.reply_ratio || 0) * 100).toFixed(1)}%</div>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-3 border border-purple-200">
                      <div className="text-xs text-purple-600 mb-1">话题活跃度</div>
                      <div className="text-lg font-bold text-purple-700">{((chat.topic_activity || 0) * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Selected Chat Details Modal */}
      {selectedChat && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-gradient-to-r from-red-500 to-pink-500 px-6 py-4 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">对话详情</h2>
              <button
                onClick={() => setSelectedChat(null)}
                className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg px-3 py-1 transition-colors"
              >
                关闭
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-8 h-8 animate-spin text-pink-500" />
              </div>
            ) : (
              <div className="p-6 space-y-6">
                <div>
                  <div className="text-sm font-medium text-gray-500 mb-2">对话 ID</div>
                  <div className="text-lg font-semibold text-gray-900 bg-gray-100 rounded-lg px-4 py-2">
                    {selectedChat.chat_id}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-500 mb-2">对话氛围</div>
                    <div className={`text-lg font-semibold rounded-lg px-4 py-2 border-2 ${
                      atmosphereConfig[selectedChat.atmosphere as keyof typeof atmosphereConfig]?.bg || 'bg-gray-100'
                    } ${
                      atmosphereConfig[selectedChat.atmosphere as keyof typeof atmosphereConfig]?.text || 'text-gray-700'
                    } ${
                      atmosphereConfig[selectedChat.atmosphere as keyof typeof atmosphereConfig]?.border || 'border-gray-300'
                    }`}>
                      {atmosphereConfig[selectedChat.atmosphere as keyof typeof atmosphereConfig]?.label || selectedChat.atmosphere}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-medium text-gray-500 mb-2">情感状态</div>
                    <div className="text-lg font-semibold bg-gray-100 rounded-lg px-4 py-2 flex items-center gap-2">
                      <span className="text-2xl">{emotionConfig[selectedChat.emotional_state as keyof typeof emotionConfig]?.emoji || '🤔'}</span>
                      <span>{emotionConfig[selectedChat.emotional_state as keyof typeof emotionConfig]?.label || selectedChat.emotional_state}</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm font-medium text-gray-500 mb-2">情绪强度</div>
                    <div className="bg-gray-100 rounded-lg px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-300 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all"
                            style={{ width: `${(selectedChat.emotion_intensity || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-bold">{((selectedChat.emotion_intensity || 0) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-medium text-gray-500 mb-2">情绪稳定性</div>
                    <div className="bg-gray-100 rounded-lg px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-300 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-green-500 to-emerald-500 transition-all"
                            style={{ width: `${(selectedChat.emotion_stability || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-sm font-bold">{((selectedChat.emotion_stability || 0) * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-blue-50 rounded-lg p-4 border-2 border-blue-200">
                    <div className="text-xs text-blue-600 mb-1">参与者</div>
                    <div className="text-2xl font-bold text-blue-700">{selectedChat.active_participants || 0}</div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 border-2 border-green-200">
                    <div className="text-xs text-green-600 mb-1">消息数</div>
                    <div className="text-2xl font-bold text-green-700">{selectedChat.message_count || 0}</div>
                  </div>
                  <div className="bg-purple-50 rounded-lg p-4 border-2 border-purple-200">
                    <div className="text-xs text-purple-600 mb-1">回复数</div>
                    <div className="text-2xl font-bold text-purple-700">{selectedChat.reply_count || 0}</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
