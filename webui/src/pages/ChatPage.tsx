import { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Users, User, Search, RefreshCw, MessageSquare, ArrowLeft, ArrowDown, Wifi, WifiOff, Image as ImageIcon, X } from 'lucide-react'
import { api } from '@/utils/api'
import { useWebSocket, type WebSocketMessage } from '@/hooks/useWebSocket'
import { parseMessageContent } from '@/utils/messageParser'
import EmojiPicker from '@/components/EmojiPicker'
import { useToast } from '@/components/Toast'

interface Contact {
  id: string
  name: string
  avatar: string
  type: 'group' | 'private'
  lastMessage?: string
  lastMessageTime?: number  // Timestamp for sorting
  unread?: number
  member_count?: number
  max_member_count?: number
  remark?: string
}

interface Message {
  id: string
  timestamp: string
  message_id: string
  user_id: string
  message: string
  sender: {
    user_id?: string | number
    nickname?: string
    card?: string
    avatar?: string
    [key: string]: any
  }
  is_self: boolean
}

function fallbackAvatar(label: string, size = 40): string {
  const text = (label || '?').trim().slice(0, 2) || '?'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#dbeafe"/><stop offset="1" stop-color="#e2e8f0"/></linearGradient></defs><rect width="${size}" height="${size}" rx="${size / 2}" fill="url(#g)"/><text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" fill="#475569" font-family="sans-serif" font-size="${Math.max(12, Math.floor(size * 0.34))}" font-weight="700">${text}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function qqAvatar(userId?: string | number): string | null {
  const id = String(userId || '').trim()
  return id ? `https://q.qlogo.cn/headimg_dl?dst_uin=${id}&spec=640` : null
}

function messageAvatar(msg: Message, fallbackLabel: string): string {
  const senderUserId = msg.sender?.user_id
  const userId = msg.is_self ? (senderUserId || msg.user_id) : (msg.user_id || senderUserId)
  return msg.sender?.avatar || qqAvatar(userId) || fallbackAvatar(msg.is_self ? 'Bot' : fallbackLabel)
}

const TEXT_BUBBLE_CQ_TYPES = new Set(['text', 'at', 'reply', 'face', 'markdown'])

function shouldUseTextBubble(message: string): boolean {
  if (!message || !message.includes('[CQ:')) return true

  const matches = Array.from(message.matchAll(/\[CQ:([a-zA-Z0-9_]+)/g))
  if (matches.length === 0) return true

  return matches.every((match) => TEXT_BUBBLE_CQ_TYPES.has(match[1].toLowerCase()))
}

export default function ChatPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [contacts, setContacts] = useState<Contact[]>([])
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<'all' | 'group' | 'private'>('all')
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({}) // Track unread messages
  const [lastCheckedTime, setLastCheckedTime] = useState<number>(Date.now()) // Track when we last checked messages
  const viewedChatsRef = useRef<Set<string>>(new Set()) // Track which chats have been viewed
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showMembersModal, setShowMembersModal] = useState(false)
  const [groupMembers, setGroupMembers] = useState<any[]>([])
  const [loadingMembers, setLoadingMembers] = useState(false)
  const [isChatAtBottom, setIsChatAtBottom] = useState(true)
  const [mentionNameMap, setMentionNameMap] = useState<Record<string, string>>({})
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageContainerRef = useRef<HTMLDivElement>(null)
  const prevMessagesLengthRef = useRef(0)
  const shouldStickChatBottomRef = useRef(true)

  // WebSocket for real-time message updates
  const { isConnected } = useWebSocket({
    onMessage: (wsMessage: WebSocketMessage) => {
      // Skip system messages
      if (wsMessage.is_system) return

      // Update messages if this message belongs to the currently selected chat
      if (selectedContact) {
        let isForCurrentChat = false
        
        // Group message matching
        if (wsMessage.message_type === 'group' && selectedContact.type === 'group') {
          isForCurrentChat = String(wsMessage.group_id || '') === String(selectedContact.id)
        }
        // Private message matching
        else if (wsMessage.message_type === 'private' && selectedContact.type === 'private') {
          // For self-sent messages, check if target_id matches the selected contact
          // For received messages, check if user_id matches the selected contact
          if (wsMessage.is_self && wsMessage.target_id) {
            // Bot sent to this contact - match by target_id
            isForCurrentChat = String(wsMessage.target_id) === String(selectedContact.id)
          } else {
            // Message from contact - match by sender ID
            isForCurrentChat = String(wsMessage.user_id || '') === String(selectedContact.id)
          }
        }

        if (isForCurrentChat) {
          setMessages((prev) => {
            // Check if message already exists
            if (prev.some((m) => m.message_id === wsMessage.message_id)) {
              return prev
            }
            // Add new message
            return [
              ...prev,
              {
                id: wsMessage.id,
                timestamp: wsMessage.timestamp,
                message_id: wsMessage.message_id || wsMessage.id,
                user_id: wsMessage.user_id || '',
                message: wsMessage.message || wsMessage.raw_message || '',
                sender: wsMessage.sender || {},
                is_self: wsMessage.is_self || false
              }
            ]
          })
        }
      }

      // Update unread counts if message is not for current chat and not self
      if (!wsMessage.is_self) {
        const contactKey = wsMessage.message_type === 'group'
          ? `group-${wsMessage.group_id}`
          : `private-${wsMessage.user_id}`

        // Don't count as unread if this contact is currently selected
        if (selectedContact) {
          const selectedKey = `${selectedContact.type}-${selectedContact.id}`
          if (contactKey === selectedKey) return
        }

        // Skip if this chat has been viewed
        if (viewedChatsRef.current.has(contactKey)) return

        // Increment unread count
        setUnreadCounts((prev) => ({
          ...prev,
          [contactKey]: (prev[contactKey] || 0) + 1
        }))
      }
    }
  })

  // Load contacts on mount
  useEffect(() => {
    loadContacts()
  }, [])

  // Poll for new messages and update unread counts
  useEffect(() => {
    const checkNewMessages = async () => {
      try {
        const allMessages = await api.getMessageLog(50)
        
        // Only count messages that are newer than last check time
        const newMessagesOnly = allMessages.filter((msg: any) => {
          const msgTime = new Date(msg.timestamp || msg.time).getTime()
          return msgTime > lastCheckedTime
        })
        
        // Count NEW unread messages for each contact (since last check)
        const newUnreadCounts: Record<string, number> = {}
        
        newMessagesOnly.forEach((msg: any) => {
          // Skip system messages and self messages
          if (msg.is_system || msg.is_self) return
          
          const contactKey = msg.message_type === 'group' 
            ? `group-${msg.group_id}` 
            : `private-${msg.user_id}`
          
          // Skip if this chat has been viewed
          if (viewedChatsRef.current.has(contactKey)) return
          
          // Don't count as unread if this contact is currently selected
          if (selectedContact) {
            const selectedKey = `${selectedContact.type}-${selectedContact.id}`
            if (contactKey === selectedKey) return
          }
          
          newUnreadCounts[contactKey] = (newUnreadCounts[contactKey] || 0) + 1
        })
        
        // Merge with existing unread counts (add new messages to existing counts)
        setUnreadCounts(prev => {
          const merged = { ...prev }
          Object.keys(newUnreadCounts).forEach(key => {
            merged[key] = (merged[key] || 0) + newUnreadCounts[key]
          })
          return merged
        })
        
        // Update last checked time
        setLastCheckedTime(Date.now())
        
        // Update contacts with last message time
        setContacts(prevContacts => {
          const updatedContacts = prevContacts.map(contact => {
            const contactKey = `${contact.type}-${contact.id}`
            const contactMessages = allMessages.filter((msg: any) => {
              if (msg.message_type === 'group' && contact.type === 'group') {
                return msg.group_id === contact.id
              } else if (msg.message_type === 'private' && contact.type === 'private') {
                return msg.user_id === contact.id
              }
              return false
            })
            
            if (contactMessages.length > 0) {
              const lastMsg = contactMessages[0] // Already sorted by newest first
              return {
                ...contact,
                lastMessageTime: new Date(lastMsg.timestamp).getTime(),
                lastMessage: lastMsg.message?.substring(0, 30),
                unread: newUnreadCounts[contactKey] || 0
              }
            }
            return contact
          })
          
          // Sort by last message time (newest first)
          return updatedContacts.sort((a, b) => {
            const timeA = a.lastMessageTime || 0
            const timeB = b.lastMessageTime || 0
            return timeB - timeA
          })
        })
      } catch (error) {
        console.error('Failed to check new messages:', error)
      }
    }
    
    // Check immediately and adjust interval based on WebSocket status
    checkNewMessages()
    // Use longer interval when WebSocket is connected (30s vs 5s)
    const checkInterval = isConnected ? 30000 : 5000
    const interval = setInterval(checkNewMessages, checkInterval)
    
    return () => clearInterval(interval)
  }, [selectedContact, isConnected])

  // Load messages when contact is selected
  useEffect(() => {
    if (selectedContact) {
      shouldStickChatBottomRef.current = true
      setIsChatAtBottom(true)
      prevMessagesLengthRef.current = 0
      loadMessages(selectedContact, true)
      // Auto refresh messages - use longer interval when WebSocket is connected
      const refreshInterval = isConnected ? 30000 : 5000 // 30s with WebSocket, 5s without
      const interval = setInterval(() => {
        loadMessages(selectedContact, false)
      }, refreshInterval)
      return () => clearInterval(interval)
    }
  }, [selectedContact, isConnected])

  useEffect(() => {
    let cancelled = false
    setMentionNameMap({})

    if (!selectedContact || selectedContact.type !== 'group') {
      return () => {
        cancelled = true
      }
    }

    api.getGroupMembers(selectedContact.id)
      .then((data) => {
        if (cancelled) return
        const nextMap: Record<string, string> = {}
        for (const member of data.members || []) {
          const userId = String(member.user_id || member.uin || member.id || '').trim()
          const displayName = String(member.card || member.nickname || member.remark || member.name || '').trim()
          if (userId && displayName) {
            nextMap[userId] = displayName
          }
        }
        setMentionNameMap(nextMap)
      })
      .catch((error) => {
        if (!cancelled) {
          console.warn('Failed to load group mention names:', error)
        }
      })

    return () => {
      cancelled = true
    }
  }, [selectedContact?.id, selectedContact?.type])

  // Keep the chat pinned only when the user is already near the bottom.
  useEffect(() => {
    const previousLength = prevMessagesLengthRef.current
    if (messages.length > 0 && previousLength === 0) {
      requestAnimationFrame(() => scrollToBottom('instant'))
    } else if (messages.length > previousLength && shouldStickChatBottomRef.current) {
      requestAnimationFrame(() => scrollToBottom('smooth'))
    }
    prevMessagesLengthRef.current = messages.length
  }, [messages])

  const scrollToBottom = (behavior: 'smooth' | 'instant' = 'smooth') => {
    const container = messageContainerRef.current
    if (!container) return

    container.scrollTo({
      top: container.scrollHeight,
      behavior: behavior === 'instant' ? 'auto' : behavior,
    })
    shouldStickChatBottomRef.current = true
    setIsChatAtBottom(true)
  }

  const updateChatScrollState = () => {
    const container = messageContainerRef.current
    if (!container) return

    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= 80
    shouldStickChatBottomRef.current = nearBottom
    setIsChatAtBottom(nearBottom)
  }

  const loadContacts = async () => {
    setLoading(true)
    try {
      const data = await api.getChatContacts()
      const allContacts: Contact[] = [
        ...data.groups.map((g: any) => ({
          id: g.id,
          name: g.name,
          avatar: g.avatar,
          type: 'group' as const,
          member_count: g.member_count,
          max_member_count: g.max_member_count
        })),
        ...data.friends.map((f: any) => ({
          id: f.id,
          name: f.name,
          avatar: f.avatar,
          type: 'private' as const,
          remark: f.remark
        }))
      ]
      setContacts(allContacts)
    } catch (error) {
      console.error('Failed to load contacts:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMessages = async (contact: Contact, showLoading = true) => {
    if (showLoading) setLoading(true)
    try {
      const data = await api.getChatHistory(contact.type, contact.id, 50)
      setMessages(data)
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !selectedContact || sending) return

    setSending(true)
    const messageText = inputMessage.trim()
    try {
      const result = await api.sendChatMessage({
        type: selectedContact.type,
        id: selectedContact.id,
        message: messageText
      })
      
      console.log('Message sent successfully:', result)
      
      setInputMessage('')
      
      // Wait a bit for EventBus to process, then refresh to show the sent message
      setTimeout(() => {
        loadMessages(selectedContact, false)
      }, 300)
    } catch (error: any) {
      console.error('Send message error:', error)
      toast.error(error.response?.data?.detail || '发送失败')
    } finally {
      setSending(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleEmojiSelect = (emoji: string) => {
    setInputMessage((prev) => prev + emoji)
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !selectedContact) return

    // 检查文件类型
    if (!file.type.startsWith('image/')) {
      toast.warning('请选择图片文件')
      return
    }

    // 检查文件大小（最大10MB）
    if (file.size > 10 * 1024 * 1024) {
      toast.warning('图片大小不能超过10MB')
      return
    }

    setSending(true)
    try {
      // 方案1: 尝试使用 file:/// 协议（本地文件路径）
      // 大多数 OneBot 实现支持本地文件路径
      const reader = new FileReader()
      reader.onload = async (event) => {
        try {
          const base64 = event.target?.result as string
          
          // 直接使用 base64，不通过 buildCQCode（避免编码问题）
          const imageMessage = `[CQ:image,file=${base64}]`
          
          console.log('Sending image message:', imageMessage.substring(0, 100) + '...')
          
          // 发送消息
          await api.sendChatMessage({
            type: selectedContact.type,
            id: selectedContact.id,
            message: imageMessage
          })
          
          console.log('Image sent successfully')
          
          // 刷新消息列表
          setTimeout(() => {
            loadMessages(selectedContact, false)
          }, 300)
        } catch (error: any) {
          console.error('Send image error:', error)
          const errorMsg = error.response?.data?.detail || error.message || '发送图片失败'
          toast.error(`发送图片失败: ${errorMsg}`)
        } finally {
          setSending(false)
          if (fileInputRef.current) {
            fileInputRef.current.value = ''
          }
        }
      }
      reader.onerror = () => {
        setSending(false)
        toast.error('读取图片失败')
      }
      reader.readAsDataURL(file)
    } catch (error) {
      setSending(false)
      toast.error('发送图片失败')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  const filteredContacts = contacts.filter(contact => {
    const matchesSearch = contact.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === 'all' || contact.type === filterType
    return matchesSearch && matchesType
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    if (diff < 60000) return t('chat.justNow')
    if (diff < 3600000) return t('chat.minutesAgo', { count: Math.floor(diff / 60000) })
    if (diff < 86400000) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return date.toLocaleDateString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  if (loading && contacts.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="fixed top-16 left-0 md:left-64 right-0 bottom-0 flex bg-gray-50 overflow-hidden">
      {/* Contact List Sidebar - Hidden on mobile when chat is selected */}
      <div className={`w-full md:w-80 bg-white md:border-r border-gray-200 flex flex-col ${
        selectedContact ? 'hidden md:flex' : 'flex'
      }`}>
        {/* Search and Filter */}
        <div className="p-3 md:p-4 border-b border-gray-200">
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder={t('chat.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm md:text-base"
            />
          </div>
          <div className="flex gap-1 md:gap-2 flex-wrap">
            <button
              onClick={() => setFilterType('all')}
              className={`flex-1 px-2 md:px-3 py-1.5 text-xs md:text-sm rounded-lg transition-colors ${
                filterType === 'all'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {t('chat.all')}
            </button>
            <button
              onClick={() => setFilterType('group')}
              className={`flex-1 px-2 md:px-3 py-1.5 text-xs md:text-sm rounded-lg transition-colors flex items-center justify-center gap-1 ${
                filterType === 'group'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Users className="w-3 h-3 md:w-3.5 md:h-3.5" />
              <span className="hidden sm:inline">{t('chat.group')}</span>
            </button>
            <button
              onClick={() => setFilterType('private')}
              className={`flex-1 px-2 md:px-3 py-1.5 text-xs md:text-sm rounded-lg transition-colors flex items-center justify-center gap-1 ${
                filterType === 'private'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <User className="w-3 h-3 md:w-3.5 md:h-3.5" />
              <span className="hidden sm:inline">{t('chat.private')}</span>
            </button>
            <button
              onClick={loadContacts}
              className="px-2 md:px-3 py-1.5 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
              title={t('common.refresh')}
            >
              <RefreshCw className="w-3 h-3 md:w-3.5 md:h-3.5" />
            </button>
          </div>
        </div>

        {/* Contact List */}
        <div className="flex-1 overflow-y-auto">
          {filteredContacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <MessageSquare className="w-12 h-12 mb-2" />
              <p className="text-sm">{t('chat.noChats')}</p>
            </div>
          ) : (
            filteredContacts.map((contact) => {
              const contactKey = `${contact.type}-${contact.id}`
              const unreadCount = unreadCounts[contactKey] || 0
              
              return (
                <div
                  key={contactKey}
                  onClick={() => {
                    setSelectedContact(contact)
                    // Mark this chat as viewed
                    viewedChatsRef.current.add(contactKey)
                    // Clear unread count for this contact
                    setUnreadCounts(prev => {
                      const newCounts = { ...prev }
                      delete newCounts[contactKey]
                      return newCounts
                    })
                  }}
                  className={`flex items-center gap-3 p-3 md:p-4 cursor-pointer border-b border-gray-100 hover:bg-gray-50 active:bg-gray-100 transition-colors ${
                    selectedContact?.id === contact.id && selectedContact?.type === contact.type
                      ? 'bg-primary-50'
                      : ''
                  }`}
                >
                  {/* Avatar with unread badge */}
                  <div className="relative flex-shrink-0">
                    <img
                      src={contact.avatar}
                      alt={contact.name}
                      className="w-12 h-12 rounded-full object-cover"
                      onError={(e) => {
                        e.currentTarget.src = fallbackAvatar(contact.name, 48)
                      }}
                    />
                    {unreadCount > 0 && (
                      <div className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1 shadow-lg">
                        {unreadCount > 99 ? '99+' : unreadCount}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="font-medium text-gray-900 truncate">{contact.name}</h3>
                      {contact.type === 'group' && (
                        <Users className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      )}
                    </div>
                    {contact.lastMessage ? (
                      <p className="text-xs text-gray-500 truncate">{contact.lastMessage}</p>
                    ) : contact.type === 'group' && contact.member_count ? (
                      <p className="text-xs text-gray-500">
                        {t('chat.memberCount', { count: contact.member_count })} · {contact.id}
                      </p>
                    ) : contact.type === 'group' ? (
                      <p className="text-xs text-gray-500">群号: {contact.id}</p>
                    ) : contact.remark ? (
                      <p className="text-xs text-gray-500 truncate">{contact.remark}</p>
                    ) : (
                      <p className="text-xs text-gray-500">ID: {contact.id}</p>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Chat Area - Full screen on mobile when contact selected */}
      <div className={`flex-1 flex flex-col ${
        selectedContact ? 'flex w-full' : 'hidden md:flex'
      }`}>
        {selectedContact ? (
          <>
            {/* Chat Header */}
            <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* Back button - Mobile only */}
                <button
                  onClick={() => setSelectedContact(null)}
                  className="md:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                  title={t('common.cancel')}
                >
                  <ArrowLeft className="w-5 h-5 text-gray-600" />
                </button>
                <img
                  src={selectedContact.avatar}
                  alt={selectedContact.name}
                  className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                  onError={(e) => {
                    e.currentTarget.src = fallbackAvatar(selectedContact.name, 40)
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="font-semibold text-gray-900 truncate">{selectedContact.name}</h2>
                    {/* WebSocket Status Indicator */}
                    {isConnected ? (
                      <span title={t('dashboard.online')} className="flex-shrink-0">
                        <Wifi className="w-3.5 h-3.5 text-green-500" />
                      </span>
                    ) : (
                      <span title={t('dashboard.offline')} className="flex-shrink-0">
                        <WifiOff className="w-3.5 h-3.5 text-orange-500" />
                      </span>
                    )}
                  </div>
                  {selectedContact.type === 'group' ? (
                    <p className="text-xs text-gray-500">
                      {selectedContact.member_count && `${t('chat.members', { count: selectedContact.member_count })} · `}
                      {selectedContact.id}
                    </p>
                  ) : (
                    <p className="text-xs text-gray-500">{selectedContact.id}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedContact.type === 'group' && (
                  <button
                    onClick={async () => {
                      setShowMembersModal(true)
                      setLoadingMembers(true)
                      try {
                        const data = await api.getGroupMembers(selectedContact.id)
                        const members = data.members || []
                        // 按角色排序：群主 > 管理员 > 普通成员
                        const sortedMembers = members.sort((a, b) => {
                          const roleOrder = { 'owner': 0, 'admin': 1, 'member': 2 }
                          const aOrder = roleOrder[a.role as keyof typeof roleOrder] ?? 3
                          const bOrder = roleOrder[b.role as keyof typeof roleOrder] ?? 3
                          return aOrder - bOrder
                        })
                        setGroupMembers(sortedMembers)
                      } catch (error) {
                        console.error('Failed to load group members:', error)
                        toast.error('加载群成员列表失败')
                      } finally {
                        setLoadingMembers(false)
                      }
                    }}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                    title="查看群成员"
                  >
                    <Users className="w-5 h-5 text-gray-600" />
                  </button>
                )}
                <button
                  onClick={() => loadMessages(selectedContact)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                  title={t('common.refresh')}
                >
                  <RefreshCw className="w-5 h-5 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="relative flex-1 min-h-0 bg-gray-50">
              <div
                ref={messageContainerRef}
                onScroll={updateChatScrollState}
                className="h-full overflow-y-auto p-3 md:p-6 space-y-3 md:space-y-4"
              >
                {messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <p>{t('chat.noMessages')}</p>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const senderName = msg.sender?.card || msg.sender?.nickname || `用户${msg.user_id}`
                    const isGroup = selectedContact.type === 'group'
                    const avatarSrc = messageAvatar(msg, senderName)
                    const useTextBubble = shouldUseTextBubble(msg.message)
                    const renderedMessage = parseMessageContent(
                      msg.message,
                      useTextBubble ? msg.is_self : false,
                      { atNames: mentionNameMap }
                    )
                    
                    return (
                      <div key={msg.id} className={`flex gap-2 md:gap-3 ${msg.is_self ? 'flex-row-reverse' : ''}`}>
                        <img
                          src={avatarSrc}
                          alt={senderName}
                          className="w-8 h-8 md:w-10 md:h-10 rounded-full object-cover flex-shrink-0"
                          onError={(e) => {
                            e.currentTarget.src = fallbackAvatar(msg.is_self ? 'Bot' : senderName, 40)
                          }}
                        />
                        <div className={`flex-1 min-w-0 ${msg.is_self ? 'flex flex-col items-end' : ''}`}>
                          {isGroup && !msg.is_self && (
                            <p className="text-xs text-gray-500 mb-1 truncate">
                              {senderName}
                              <span className="text-gray-400 ml-1">({msg.user_id})</span>
                            </p>
                          )}
                          <div
                            className={`inline-block max-w-[85%] md:max-w-xl text-sm md:text-base ${
                              useTextBubble
                                ? `px-3 md:px-4 py-2 rounded-lg ${
                                    msg.is_self
                                      ? 'bg-primary-600 text-white'
                                      : 'bg-white text-gray-900 border border-gray-200'
                                  }`
                                : 'text-gray-900'
                            }`}
                          >
                            <div className="whitespace-pre-wrap break-words">
                              {renderedMessage}
                            </div>
                          </div>
                          <p className="text-xs text-gray-400 mt-1">
                            {formatTime(msg.timestamp)}
                          </p>
                        </div>
                      </div>
                    )
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {!isChatAtBottom && messages.length > 0 ? (
                <button
                  type="button"
                  onClick={() => scrollToBottom('smooth')}
                  className="absolute bottom-4 right-4 z-10 flex items-center gap-2 rounded-lg border border-gray-200 bg-white/95 px-3 py-2 text-xs font-medium text-gray-700 shadow-lg transition-colors hover:bg-gray-50"
                >
                  <ArrowDown className="h-4 w-4" />
                  返回底部
                </button>
              ) : null}
            </div>

            {/* Input Area */}
            <div className="bg-white border-t border-gray-200 p-3 md:p-4">
              <div className="flex gap-2 md:gap-3">
                <div className="flex flex-col gap-2">
                  {/* 图片上传按钮 */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={sending}
                    className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title={t('chat.selectImage')}
                  >
                    <ImageIcon className="w-5 h-5" />
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    className="hidden"
                  />
                  
                  {/* 表情选择器 */}
                  <EmojiPicker onSelectEmoji={handleEmojiSelect} />
                </div>
                
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={t('chat.inputPlaceholder')}
                  className="flex-1 px-3 md:px-4 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm md:text-base"
                  rows={2}
                  disabled={sending}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || sending}
                  className="px-3 md:px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1 md:gap-2 h-fit min-w-[60px] md:min-w-[80px]"
                >
                  <Send className="w-4 h-4 md:w-5 md:h-5" />
                  <span className="hidden sm:inline">{sending ? t('chat.sending') : t('chat.sendMessage')}</span>
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2 hidden md:block">
                {t('chat.enterToSend')}
              </p>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <MessageSquare className="w-16 h-16 mx-auto mb-4" />
              <p className="text-lg">{t('chat.selectChat')}</p>
              <p className="text-sm mt-2">{t('chat.selectChatDesc')}</p>
            </div>
          </div>
        )}
      </div>

      {/* Group Members Modal */}
      {showMembersModal && selectedContact && selectedContact.type === 'group' && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-900">群成员列表 - {selectedContact.name}</h2>
              <button
                onClick={() => {
                  setShowMembersModal(false)
                  setGroupMembers([])
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {loadingMembers ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                </div>
              ) : groupMembers.length === 0 ? (
                <div className="text-center py-12 text-gray-500">暂无成员</div>
              ) : (
                <div className="space-y-2">
                  {groupMembers.map((member) => (
                    <div
                      key={member.user_id}
                      className="flex items-center gap-3 p-3 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <img
                        src={`https://q.qlogo.cn/headimg_dl?dst_uin=${member.user_id}&spec=640`}
                        alt={member.nickname || member.card || `用户${member.user_id}`}
                        className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                        onError={(e) => {
                          e.currentTarget.src = fallbackAvatar(member.card || member.nickname || `用户${member.user_id}`, 40)
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 truncate">
                            {member.card || member.nickname || `用户${member.user_id}`}
                          </span>
                          {member.role === 'owner' && (
                            <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">群主</span>
                          )}
                          {member.role === 'admin' && (
                            <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">管理员</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                          <span>{member.user_id}</span>
                          {member.nickname && member.card && member.nickname !== member.card && (
                            <>
                              <span>·</span>
                              <span className="truncate">{member.nickname}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Footer */}
            <div className="flex items-center justify-between p-6 border-t border-gray-200 flex-shrink-0">
              <span className="text-sm text-gray-500">共 {groupMembers.length} 名成员</span>
              <button
                onClick={() => {
                  setShowMembersModal(false)
                  setGroupMembers([])
                }}
                className="btn btn-secondary"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
