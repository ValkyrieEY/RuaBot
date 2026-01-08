import { useEffect, useState, useRef } from 'react'
import { Send, Users, User, Search, RefreshCw, MessageSquare, ArrowLeft } from 'lucide-react'
import { api } from '@/utils/api'

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
    [key: string]: any
  }
  is_self: boolean
}

export default function ChatPage() {
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
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageContainerRef = useRef<HTMLDivElement>(null)
  const prevMessagesLengthRef = useRef(0)

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
    
    // Check immediately and then every 3 seconds
    checkNewMessages()
    const interval = setInterval(checkNewMessages, 3000)
    
    return () => clearInterval(interval)
  }, [selectedContact])

  // Load messages when contact is selected
  useEffect(() => {
    if (selectedContact) {
      loadMessages(selectedContact, true) // Initial load with scroll
      prevMessagesLengthRef.current = 0 // Reset counter
      // Auto refresh messages every 2 seconds
      const interval = setInterval(() => {
        loadMessages(selectedContact, false) // Refresh without forced scroll
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [selectedContact])

  // Scroll to bottom when NEW messages arrive (not when switching contacts)
  useEffect(() => {
    if (messages.length > prevMessagesLengthRef.current && prevMessagesLengthRef.current > 0) {
      // Only scroll if there are new messages (length increased)
      scrollToBottom('smooth')
    } else if (messages.length > 0 && prevMessagesLengthRef.current === 0) {
      // Initial load - scroll instantly
      scrollToBottom('instant')
    }
    prevMessagesLengthRef.current = messages.length
  }, [messages])

  const scrollToBottom = (behavior: 'smooth' | 'instant' = 'smooth') => {
    if (behavior === 'instant') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
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
      alert(error.response?.data?.detail || '发送失败')
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

  const filteredContacts = contacts.filter(contact => {
    const matchesSearch = contact.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === 'all' || contact.type === filterType
    return matchesSearch && matchesType
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  if (loading && contacts.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-gray-50 overflow-hidden">
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
              placeholder="搜索聊天..."
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
              全部
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
              <span className="hidden sm:inline">群聊</span>
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
              <span className="hidden sm:inline">私聊</span>
            </button>
            <button
              onClick={loadContacts}
              className="px-2 md:px-3 py-1.5 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
              title="刷新"
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
              <p className="text-sm">暂无聊天</p>
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
                        e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="48" height="48"%3E%3Crect width="48" height="48" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="16"%3E%3C/text%3E%3C/svg%3E'
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
                        {contact.member_count} 人
                      </p>
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
                  title="返回"
                >
                  <ArrowLeft className="w-5 h-5 text-gray-600" />
                </button>
                <img
                  src={selectedContact.avatar}
                  alt={selectedContact.name}
                  className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold text-gray-900 truncate">{selectedContact.name}</h2>
                  {selectedContact.type === 'group' && selectedContact.member_count && (
                    <p className="text-xs text-gray-500">{selectedContact.member_count} 名成员</p>
                  )}
                </div>
              </div>
              <button
                onClick={() => loadMessages(selectedContact)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                title="刷新消息"
              >
                <RefreshCw className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            {/* Messages */}
            <div ref={messageContainerRef} className="flex-1 overflow-y-auto p-3 md:p-6 space-y-3 md:space-y-4 bg-gray-50">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-400">
                  <p>暂无消息</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const senderName = msg.sender?.card || msg.sender?.nickname || `用户${msg.user_id}`
                  const isGroup = selectedContact.type === 'group'
                  
                  return (
                    <div key={msg.id} className={`flex gap-2 md:gap-3 ${msg.is_self ? 'flex-row-reverse' : ''}`}>
                      <img
                        src={`http://q.qlogo.cn/headimg_dl?dst_uin=${msg.user_id}&spec=640`}
                        alt={senderName}
                        className="w-8 h-8 md:w-10 md:h-10 rounded-full object-cover flex-shrink-0"
                        onError={(e) => {
                          e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="40" height="40"%3E%3Crect width="40" height="40" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="14"%3E%3C/text%3E%3C/svg%3E'
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
                          className={`inline-block max-w-[85%] md:max-w-xl px-3 md:px-4 py-2 rounded-lg text-sm md:text-base ${
                            msg.is_self
                              ? 'bg-primary-600 text-white'
                              : 'bg-white text-gray-900 border border-gray-200'
                          }`}
                        >
                          <p className="whitespace-pre-wrap break-words">{msg.message}</p>
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

            {/* Input Area */}
            <div className="bg-white border-t border-gray-200 p-3 md:p-4">
              <div className="flex gap-2 md:gap-3">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="输入消息..."
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
                  <span className="hidden sm:inline">{sending ? '发送中' : '发送'}</span>
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2 hidden md:block">
                Enter 发送，Shift+Enter 换行
              </p>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <MessageSquare className="w-16 h-16 mx-auto mb-4" />
              <p className="text-lg">选择一个聊天开始对话</p>
              <p className="text-sm mt-2">点击左侧联系人或群组</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

