import { useState, useEffect, useRef } from 'react'
import {
  ArrowLeft,
  Plus,
  Trash2,
  Edit,
  Send,
  Trash,
  FlaskConical,
  User,
  Users,
  MessageSquare,
  Bot,
  Loader2,
  X,
  Terminal,
  Code2,
  FileText,
  Folder,
  FolderOpen,
  File,
  Play,
  Save,
  RefreshCw,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import { api } from '@/utils/api'
import { useToast } from '@/components/Toast'
import { useTranslation } from 'react-i18next'

interface Sandbox {
  uuid: string
  name: string
  description: string | null
  enabled: boolean
  mock_user_id: string
  mock_user_nickname: string
  mock_group_id: string | null
  mock_group_name: string | null
  auto_reply: boolean
  record_messages: boolean
  use_plugins: boolean
  use_ai: boolean
  ai_model_uuid: string | null
  ai_preset_uuid: string | null
  message_count: number
  last_activity: string | null
  created_at: string
  updated_at: string
}

interface SandboxMessage {
  id: number
  sandbox_uuid: string
  message_type: string
  direction: string
  user_id: string
  user_nickname: string | null
  group_id: string | null
  content: string
  processed_by_plugins: boolean
  processed_by_ai: boolean
  plugin_responses: any[]
  ai_response: string | null
  has_error: boolean
  error_message: string | null
  created_at: string
}

interface LLMModel {
  uuid: string
  name: string
  description: string | null
  provider: string
  model_name: string
}

interface AIPreset {
  uuid: string
  name: string
  description: string | null
  system_prompt: string
}

interface FileEntry {
  name: string
  path: string
  type: 'file' | 'directory'
  size: number
  modified: number
}

type TabType = 'chat' | 'shell' | 'python' | 'files'

export default function SandboxPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [sandboxes, setSandboxes] = useState<Sandbox[]>([])
  const [selectedSandbox, setSelectedSandbox] = useState<Sandbox | null>(null)
  const [messages, setMessages] = useState<SandboxMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [messageInput, setMessageInput] = useState('')
  const [messageType, setMessageType] = useState<'private' | 'group'>('private')
  const [models] = useState<LLMModel[]>([])
  const [presets] = useState<AIPreset[]>([])
  const [activeTab, setActiveTab] = useState<TabType>('chat')
  
  // Confirm dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean
    title: string
    message: string
    onConfirm: () => void
  }>({
    open: false,
    title: '',
    message: '',
    onConfirm: () => {},
  })
  
  // Prompt dialog state
  const [promptDialog, setPromptDialog] = useState<{
    open: boolean
    title: string
    placeholder: string
    defaultValue: string
    onConfirm: (value: string) => void
  }>({
    open: false,
    title: '',
    placeholder: '',
    defaultValue: '',
    onConfirm: () => {},
  })
  const [promptValue, setPromptValue] = useState('')
  
  // Shell state
  const [shellCommand, setShellCommand] = useState('')
  const [shellOutput, setShellOutput] = useState<Array<{type: 'command' | 'output' | 'error', content: string}>>([])
  const [shellLoading, setShellLoading] = useState(false)
  
  // Python state
  const [pythonCode, setPythonCode] = useState('')
  const [pythonOutput, setPythonOutput] = useState<Array<{type: 'output' | 'error', content: string}>>([])
  const [pythonLoading, setPythonLoading] = useState(false)
  const [kernelId] = useState(() => `kernel_${Date.now()}`)
  
  // File system state
  const [currentPath, setCurrentPath] = useState('.')
  const [files, setFiles] = useState<FileEntry[]>([])
  const [filesLoading, setFilesLoading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<FileEntry | null>(null)
  const [fileContent, setFileContent] = useState('')
  const [fileEditing, setFileEditing] = useState(false)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const shellEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Form state for create/edit
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    mock_user_id: '',
    mock_user_nickname: '',
    mock_group_id: '',
    mock_group_name: '',
    use_plugins: true,
    use_ai: true,
    ai_model_uuid: '',
    ai_preset_uuid: '',
  })

  useEffect(() => {
    loadSandboxes()
  }, [])

  useEffect(() => {
    if (selectedSandbox) {
      loadMessages(selectedSandbox.uuid)
      connectWebSocket(selectedSandbox.uuid)
      if (activeTab === 'files') {
        loadFiles()
      }
    } else {
      disconnectWebSocket()
    }

    return () => {
      disconnectWebSocket()
    }
  }, [selectedSandbox])

  useEffect(() => {
    if (activeTab === 'files' && selectedSandbox) {
      loadFiles()
    }
  }, [activeTab, currentPath, selectedSandbox])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    scrollShellToBottom()
  }, [shellOutput])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const scrollShellToBottom = () => {
    shellEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const loadSandboxes = async () => {
    try {
      const response = await api.get('/sandbox/list')
      if (response.ok) {
        setSandboxes(response.sandboxes)
      }
    } catch (error) {
      console.error('Failed to load sandboxes:', error)
    }
  }

  const loadMessages = async (sandboxUuid: string) => {
    try {
      const response = await api.get(`/sandbox/${sandboxUuid}/messages`, {
        params: { limit: 100 },
      })
      if (response.ok) {
        setMessages(response.messages.reverse())
      }
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const loadFiles = async () => {
    if (!selectedSandbox) return
    
    setFilesLoading(true)
    try {
      const response = await api.get(`/sandbox/${selectedSandbox.uuid}/files`, {
        params: { path: currentPath, show_hidden: false },
      })
      if (response.ok && response.result.success) {
        setFiles(response.result.entries || [])
      }
    } catch (error) {
      console.error('Failed to load files:', error)
    } finally {
      setFilesLoading(false)
    }
  }

  const connectWebSocket = (sandboxUuid: string) => {
    disconnectWebSocket()

    const token = localStorage.getItem('access_token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/sandbox/${sandboxUuid}/ws?token=${token}`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'message') {
        setMessages((prev) => [...prev, data.data])
      } else if (data.type === 'connected') {
        console.log('Connected to sandbox:', data.sandbox.name)
      } else if (data.type === 'error') {
        console.error('WebSocket error:', data.message)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
    }

    wsRef.current = ws
  }

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  const handleCreateSandbox = async () => {
    try {
      setLoading(true)
      const response = await api.post('/sandbox/create', formData)
      if (response.ok) {
        await loadSandboxes()
        setCreateDialogOpen(false)
        resetForm()
        toast.success(t('sandbox.toastCreated'))
      }
    } catch (error: any) {
      console.error('Failed to create sandbox:', error)
      toast.error(error.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateSandbox = async () => {
    if (!selectedSandbox) return

    try {
      setLoading(true)
      const response = await api.post(
        `/sandbox/${selectedSandbox.uuid}/update`,
        formData
      )
      if (response.ok) {
        await loadSandboxes()
        setSelectedSandbox(response.sandbox)
        setEditDialogOpen(false)
        toast.success(t('sandbox.toastUpdated'))
      }
    } catch (error: any) {
      console.error('Failed to update sandbox:', error)
      toast.error(error.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteSandbox = async (sandboxUuid: string) => {
    setConfirmDialog({
      open: true,
      title: t('sandbox.deleteConfirmTitle'),
      message: t('sandbox.deleteConfirmMessage'),
      onConfirm: async () => {
        try {
          const response = await api.delete(`/sandbox/${sandboxUuid}`)
          if (response.ok) {
            await loadSandboxes()
            if (selectedSandbox?.uuid === sandboxUuid) {
              setSelectedSandbox(null)
              setMessages([])
            }
            toast.success(t('sandbox.toastDeleted'))
          }
        } catch (error: any) {
          console.error('Failed to delete sandbox:', error)
          toast.error(error.response?.data?.detail || t('common.error'))
        }
        setConfirmDialog({ ...confirmDialog, open: false })
      },
    })
  }

  const handleSendMessage = async () => {
    if (!selectedSandbox || !messageInput.trim()) return

    try {
      setLoading(true)
      const response = await api.post(`/sandbox/${selectedSandbox.uuid}/send`, {
        message: messageInput,
        message_type: messageType,
      })

      if (response.ok) {
        setMessageInput('')
      }
    } catch (error: any) {
      console.error('Failed to send message:', error)
      toast.error(error.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleClearMessages = async () => {
    if (!selectedSandbox) return
    
    setConfirmDialog({
      open: true,
      title: t('sandbox.clearMessagesTitle'),
      message: t('sandbox.clearMessagesMessage'),
      onConfirm: async () => {
        try {
          const response = await api.delete(`/sandbox/${selectedSandbox.uuid}/messages`)
          if (response.ok) {
            setMessages([])
            await loadSandboxes()
            toast.success(t('sandbox.toastMessagesCleared'))
          }
        } catch (error: any) {
          console.error('Failed to clear messages:', error)
          toast.error(error.response?.data?.detail || t('common.error'))
        }
        setConfirmDialog({ ...confirmDialog, open: false })
      },
    })
  }

  const handleExecuteShell = async () => {
    if (!selectedSandbox || !shellCommand.trim()) return

    setShellLoading(true)
    setShellOutput(prev => [...prev, { type: 'command', content: `$ ${shellCommand}` }])

    try {
      const response = await api.post(`/sandbox/${selectedSandbox.uuid}/shell`, {
        command: shellCommand,
        timeout: 30,
      })

      if (response.ok && response.result) {
        const result = response.result
        if (result.stdout) {
          setShellOutput(prev => [...prev, { type: 'output', content: result.stdout }])
        }
        if (result.stderr) {
          setShellOutput(prev => [...prev, { type: 'error', content: result.stderr }])
        }
        if (!result.success) {
          setShellOutput(prev => [...prev, { type: 'error', content: t('sandbox.exitCode', { code: result.exit_code }) }])
        }
      }
      
      setShellCommand('')
    } catch (error: any) {
      console.error('Failed to execute shell command:', error)
      setShellOutput(prev => [...prev, { type: 'error', content: error.message || '' }])
      toast.error(t('sandbox.shellFailed'))
    } finally {
      setShellLoading(false)
    }
  }

  const handleExecutePython = async () => {
    if (!selectedSandbox || !pythonCode.trim()) return

    setPythonLoading(true)

    try {
      const response = await api.post(`/sandbox/${selectedSandbox.uuid}/python`, {
        code: pythonCode,
        kernel_id: kernelId,
        timeout: 30,
      })

      if (response.ok && response.result) {
        const result = response.result
        
        setPythonOutput(prev => [
          ...prev,
          {
            type: 'output',
            content: result.output || result.data?.output?.text || t('sandbox.emptyOutput')
          }
        ])
        
        if (result.error) {
          setPythonOutput(prev => [...prev, { type: 'error', content: result.error }])
        }
      }
    } catch (error: any) {
      console.error('Failed to execute Python code:', error)
      setPythonOutput(prev => [...prev, { type: 'error', content: error.message || '' }])
      toast.error(t('sandbox.pythonFailed'))
    } finally {
      setPythonLoading(false)
    }
  }

  const handleFileClick = async (file: FileEntry) => {
    if (file.type === 'directory') {
      // Navigate into directory - normalize path
      const normalizedPath = file.path.replace(/\\/g, '/')
      setCurrentPath(normalizedPath)
      setSelectedFile(null)
      setFileContent('')
    } else {
      // Read file content
      setSelectedFile(file)
      setFilesLoading(true)
      try {
        const normalizedPath = file.path.replace(/\\/g, '/')
        const response = await api.get(`/sandbox/${selectedSandbox!.uuid}/files/read`, {
          params: { path: normalizedPath },
        })
        if (response.ok && response.result.success) {
          setFileContent(response.result.content)
          setFileEditing(false)
        } else {
          toast.error(`${t('sandbox.readFailed')}: ${response.result?.error || ''}`)
        }
      } catch (error: any) {
        console.error('Failed to read file:', error)
        toast.error(`${t('sandbox.readFailed')}: ${error.message || ''}`)
      } finally {
        setFilesLoading(false)
      }
    }
  }

  const handleSaveFile = async () => {
    if (!selectedSandbox || !selectedFile) return

    setFilesLoading(true)
    try {
      const normalizedPath = selectedFile.path.replace(/\\/g, '/')
      const response = await api.post(`/sandbox/${selectedSandbox.uuid}/files/write`, {
        path: normalizedPath,
        content: fileContent,
      })
      if (response.ok && response.result.success) {
        toast.success(t('sandbox.toastFileSaved'))
        setFileEditing(false)
        await loadFiles()
      } else {
        toast.error(`${t('sandbox.saveFailed')}: ${response.result?.error || ''}`)
      }
    } catch (error: any) {
      console.error('Failed to save file:', error)
      toast.error(error.response?.data?.detail || t('common.error'))
    } finally {
      setFilesLoading(false)
    }
  }

  const handleDeleteFile = async (file: FileEntry) => {
    if (!selectedSandbox) return
    
    setConfirmDialog({
      open: true,
      title: t('sandbox.deleteFileTitle'),
      message: t('sandbox.deleteFileMessage', { name: file.name }),
      onConfirm: async () => {
        try {
          const normalizedPath = file.path.replace(/\\/g, '/')
          const response = await api.delete(`/sandbox/${selectedSandbox.uuid}/files`, {
            params: { path: normalizedPath },
          })
          if (response.ok && response.result.success) {
            await loadFiles()
            if (selectedFile?.path === file.path) {
              setSelectedFile(null)
              setFileContent('')
            }
            toast.success(t('sandbox.toastFileDeleted'))
          } else {
            toast.error(`${t('sandbox.saveFailed')}: ${response.result?.error || ''}`)
          }
        } catch (error: any) {
          console.error('Failed to delete file:', error)
          toast.error(error.response?.data?.detail || t('common.error'))
        }
        setConfirmDialog({ ...confirmDialog, open: false })
      },
    })
  }

  const handleCreateDirectory = async () => {
    if (!selectedSandbox) return
    
    setPromptValue('')
    setPromptDialog({
      open: true,
      title: t('sandbox.mkdirTitle'),
      placeholder: t('sandbox.mkdirPlaceholder'),
      defaultValue: '',
      onConfirm: async (dirName: string) => {
        if (!dirName.trim()) {
          toast.warning(t('sandbox.toastNameRequired'))
          return
        }

        setFilesLoading(true)
        try {
          const newPath = currentPath === '.' ? dirName.trim() : `${currentPath}/${dirName.trim()}`
          const response = await api.post(`/sandbox/${selectedSandbox.uuid}/files/mkdir`, {
            path: newPath,
          })
          if (response.ok && response.result.success) {
            await loadFiles()
            toast.success(t('sandbox.toastDirCreated'))
          } else {
            toast.error(`${t('sandbox.saveFailed')}: ${response.result?.error || ''}`)
          }
        } catch (error: any) {
          console.error('Failed to create directory:', error)
          toast.error(error.response?.data?.detail || t('common.error'))
        } finally {
          setFilesLoading(false)
          setPromptDialog({ ...promptDialog, open: false })
        }
      },
    })
  }

  const handleCreateFile = async () => {
    if (!selectedSandbox) return
    
    setPromptValue('')
    setPromptDialog({
      open: true,
      title: t('sandbox.newFileTitle'),
      placeholder: t('sandbox.newFilePlaceholder'),
      defaultValue: '',
      onConfirm: async (fileName: string) => {
        if (!fileName.trim()) {
          toast.warning(t('sandbox.toastNameRequired'))
          return
        }

        setFilesLoading(true)
        try {
          const newPath = currentPath === '.' ? fileName.trim() : `${currentPath}/${fileName.trim()}`
          const response = await api.post(`/sandbox/${selectedSandbox.uuid}/files/write`, {
            path: newPath,
            content: '# \n',
          })
          if (response.ok && response.result.success) {
            await loadFiles()
            toast.success(t('sandbox.toastFileCreated'))
          } else {
            toast.error(`${t('sandbox.saveFailed')}: ${response.result?.error || ''}`)
          }
        } catch (error: any) {
          console.error('Failed to create file:', error)
          toast.error(error.response?.data?.detail || t('common.error'))
        } finally {
          setFilesLoading(false)
          setPromptDialog({ ...promptDialog, open: false })
        }
      },
    })
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      mock_user_id: '',
      mock_user_nickname: '',
      mock_group_id: '',
      mock_group_name: '',
      use_plugins: true,
      use_ai: true,
      ai_model_uuid: '',
      ai_preset_uuid: '',
    })
  }

  const openEditDialog = (sandbox: Sandbox) => {
    setFormData({
      name: sandbox.name,
      description: sandbox.description || '',
      mock_user_id: sandbox.mock_user_id,
      mock_user_nickname: sandbox.mock_user_nickname,
      mock_group_id: sandbox.mock_group_id || '',
      mock_group_name: sandbox.mock_group_name || '',
      use_plugins: sandbox.use_plugins,
      use_ai: sandbox.use_ai,
      ai_model_uuid: sandbox.ai_model_uuid || '',
      ai_preset_uuid: sandbox.ai_preset_uuid || '',
    })
    setEditDialogOpen(true)
  }

  const renderMessage = (message: SandboxMessage) => {
    const isInbound = message.direction === 'inbound'
    const isOutbound = message.direction === 'outbound'

    return (
      <div
        key={message.id}
        className={`flex ${isOutbound ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-lg p-3 ${
            isOutbound
              ? 'bg-primary-600 text-white'
              : 'bg-white text-gray-900 border border-gray-200'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            {isInbound ? (
              <User className="w-4 h-4" />
            ) : (
              <Bot className="w-4 h-4" />
            )}
            <span className="text-sm font-semibold">
              {message.user_nickname || message.user_id}
            </span>
            {message.message_type === 'group' && (
              <span className={`text-xs px-2 py-0.5 rounded ${
                isOutbound ? 'bg-white bg-opacity-20' : 'bg-gray-100'
              }`}>
                <Users className="w-3 h-3 inline mr-1" />
                {message.group_id}
              </span>
            )}
          </div>

          <p className="text-sm mb-2 whitespace-pre-wrap">{message.content}</p>

          {message.has_error && (
            <div className="mb-1">
              <span className={`text-xs px-2 py-0.5 rounded ${
                isOutbound ? 'bg-red-500 bg-opacity-30' : 'bg-red-100 text-red-700'
              }`}>
                {t('sandbox.processingError')}
              </span>
            </div>
          )}

          {message.has_error && message.error_message && (
            <div className={`mt-2 p-2 rounded text-xs ${
              isOutbound ? 'bg-red-500 bg-opacity-20' : 'bg-red-100 text-red-800'
            }`}>
              {message.error_message}
            </div>
          )}

          <div className={`text-xs mt-1 ${isOutbound ? 'opacity-70' : 'text-gray-500'}`}>
            {new Date(message.created_at).toLocaleString()}
          </div>
        </div>
      </div>
    )
  }

  const renderChatTab = () => (
    <>
      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-500">{t('sandbox.chatEmpty')}</p>
          </div>
        ) : (
          <>
            {messages.map(renderMessage)}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex flex-col gap-2 mb-2 sm:flex-row">
          <select
            value={messageType}
            onChange={(e) => setMessageType(e.target.value as 'private' | 'group')}
            className="px-3 py-1 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="private">{t('sandbox.privateChat')}</option>
            <option value="group">{t('sandbox.groupChat')}</option>
          </select>
          <button
            onClick={handleClearMessages}
            className="flex items-center gap-1 px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <Trash className="w-4 h-4" />
            {t('sandbox.clearChat')}
          </button>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="flex-1 relative">
            <MessageSquare className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
            <textarea
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              placeholder={t('sandbox.messagePlaceholder')}
              rows={2}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendMessage()
                }
              }}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={loading || !messageInput.trim()}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors sm:w-auto"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
            {t('sandbox.send')}
          </button>
        </div>
      </div>
    </>
  )

  const renderShellTab = () => (
    <>
      <div className="flex-1 overflow-y-auto p-4 bg-gray-900 text-gray-100 font-mono text-sm">
        {shellOutput.length === 0 ? (
          <div className="text-gray-400 space-y-2">
            <p>{t('sandbox.shellIntro')}</p>
            <p className="text-xs text-gray-500">
              {t('sandbox.shellExamples')}{' '}
              <span className="text-green-400">pwd</span>{' '}
              <span className="text-green-400">ls</span>{' '}
              <span className="text-green-400">echo &quot;Hello&quot;</span>
            </p>
          </div>
        ) : (
          <>
            {shellOutput.map((item, idx) => (
              <div key={idx} className="mb-2">
                {item.type === 'command' && (
                  <div className="text-green-400 font-semibold">{item.content}</div>
                )}
                {item.type === 'output' && (
                  <pre className="whitespace-pre-wrap text-gray-300">{item.content}</pre>
                )}
                {item.type === 'error' && (
                  <pre className="whitespace-pre-wrap text-red-400">{item.content}</pre>
                )}
              </div>
            ))}
            <div ref={shellEndRef} />
          </>
        )}
      </div>

      <div className="p-4 border-t border-gray-700 bg-gray-900">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="flex-1 relative">
            <Terminal className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              type="text"
              value={shellCommand}
              onChange={(e) => setShellCommand(e.target.value)}
              placeholder={t('sandbox.shellPlaceholder')}
              className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 text-gray-100 placeholder-gray-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  handleExecuteShell()
                }
              }}
              disabled={shellLoading}
            />
          </div>
          <button
            onClick={handleExecuteShell}
            disabled={shellLoading || !shellCommand.trim()}
            className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors sm:w-auto"
          >
            {shellLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Play className="w-5 h-5" />
            )}
            {t('sandbox.shellRun')}
          </button>
          <button
            onClick={() => setShellOutput([])}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors sm:w-auto"
          >
            {t('sandbox.shellClear')}
          </button>
        </div>
      </div>
    </>
  )

  const renderPythonTab = () => (
    <>
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
          <div className="flex-1 min-h-0 flex flex-col border-b border-gray-200 lg:border-b-0 lg:border-r">
            <div className="p-2 bg-gray-100 border-b border-gray-200 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">{t('sandbox.pythonEditor')}</span>
              <div className="flex flex-wrap gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setPythonCode(`# Sample
import os
import sys

print("Python:", sys.version)
print("cwd:", os.getcwd())
print("list:", os.listdir("."))

result = sum(range(1, 11))
print(f"1-10 sum: {result}")
`)}
                  className="text-xs text-gray-600 hover:text-gray-900 px-2 py-1 border border-gray-300 rounded"
                >
                  {t('sandbox.pythonInsertTemplate')}
                </button>
                <button
                  type="button"
                  onClick={handleExecutePython}
                  disabled={pythonLoading || !pythonCode.trim()}
                  className="flex items-center gap-1 px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {pythonLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {t('sandbox.pythonRun')} {t('sandbox.pythonRunHint')}
                </button>
              </div>
            </div>
            <textarea
              value={pythonCode}
              onChange={(e) => setPythonCode(e.target.value)}
              placeholder={t('sandbox.pythonPlaceholder')}
              className="flex-1 min-h-[240px] lg:min-h-0 p-4 font-mono text-sm resize-none focus:outline-none border-none"
              disabled={pythonLoading}
              onKeyDown={(e) => {
                if (e.ctrlKey && e.key === 'Enter') {
                  e.preventDefault()
                  handleExecutePython()
                }
              }}
            />
          </div>
          
          <div className="flex-1 min-h-0 flex flex-col bg-gray-50">
            <div className="p-2 bg-gray-100 border-b border-gray-200 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">{t('sandbox.pythonOutput')}</span>
              <button
                type="button"
                onClick={() => setPythonOutput([])}
                className="text-sm text-gray-600 hover:text-gray-900 px-2 py-1 border border-gray-300 rounded"
              >
                {t('sandbox.pythonClearOutput')}
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 font-mono text-sm">
              {pythonOutput.length === 0 ? (
                <div className="text-gray-500">
                  <p className="mb-2">{t('sandbox.pythonEmpty')}</p>
                  <p className="text-xs">{t('sandbox.pythonShortcutHint')}</p>
                </div>
              ) : (
                <>
                  {pythonOutput.map((item, idx) => (
                    <div key={idx} className="mb-2">
                      {item.type === 'output' && (
                        <pre className="whitespace-pre-wrap text-gray-900">{item.content}</pre>
                      )}
                      {item.type === 'error' && (
                        <pre className="whitespace-pre-wrap text-red-600">{item.content}</pre>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )

  const renderFilesTab = () => (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Help Banner */}
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-3">
        <div className="flex items-start gap-3">
          <FileText className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-blue-900 mb-2">{t('sandbox.filesHelpTitle')}</p>
            <div className="text-xs text-blue-800 space-y-1">
              <p>• {t('sandbox.filesHelp1')}</p>
              <p>• {t('sandbox.filesHelp2')}</p>
              <p>• {t('sandbox.filesHelp3')}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        <div className={`${selectedFile ? 'hidden md:flex' : 'flex'} w-full md:w-80 md:shrink-0 border-r border-gray-200 flex-col bg-white min-h-0`}>
          <div className="p-3 border-b border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Folder className="w-5 h-5 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">{t('sandbox.fileListTitle')}</span>
              </div>
              <button
                type="button"
                onClick={loadFiles}
                className="p-1 hover:bg-gray-100 rounded"
                title={t('sandbox.refreshList')}
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleCreateFile}
                className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                {t('sandbox.newFile')}
              </button>
              <button
                type="button"
                onClick={handleCreateDirectory}
                className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
              >
                <Folder className="w-4 h-4" />
                {t('sandbox.newFolder')}
              </button>
            </div>
          </div>

        <div className="p-2 border-b border-gray-200">
          <div className="flex items-center gap-1 text-sm min-w-0">
            <button
              type="button"
              onClick={() => setCurrentPath('.')}
              className={`hover:text-primary-600 transition-colors ${
                currentPath === '.' ? 'text-primary-600 font-medium' : 'text-gray-600'
              }`}
            >
              {t('sandbox.root')}
            </button>
            {currentPath !== '.' && (
              <>
                <ChevronRight className="w-4 h-4 text-gray-400" />
                <span className="text-gray-900 font-medium truncate">{currentPath}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {filesLoading && files.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : files.length === 0 ? (
            <div className="text-center text-gray-500 text-sm mt-8 space-y-2">
              <p>{t('sandbox.folderEmpty')}</p>
              <p className="text-xs">{t('sandbox.folderEmptyHint')}</p>
            </div>
          ) : (
            <div className="space-y-1">
              {currentPath !== '.' && (
                <button
                  onClick={() => {
                    const parts = currentPath.split('/').filter(p => p)
                    const parentPath = parts.slice(0, -1).join('/') || '.'
                    setCurrentPath(parentPath)
                    setSelectedFile(null)
                    setFileContent('')
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded transition-colors text-left"
                >
                  <FolderOpen className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-600">..</span>
                </button>
              )}
              
              {files.map((file) => (
                <div
                  key={file.path}
                  className={`group flex items-center gap-2 px-2 py-1.5 hover:bg-gray-100 rounded transition-colors cursor-pointer ${
                    selectedFile?.path === file.path ? 'bg-primary-50' : ''
                  }`}
                >
                  <div
                    className="flex-1 flex items-center gap-2 min-w-0"
                    onClick={() => handleFileClick(file)}
                  >
                    {file.type === 'directory' ? (
                      <Folder className="w-4 h-4 text-yellow-600 flex-shrink-0" />
                    ) : (
                      <File className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-900 truncate">{file.name}</div>
                      {file.type === 'file' && (
                        <div className="text-xs text-gray-500">
                          {(file.size / 1024).toFixed(2)} KB
                        </div>
                      )}
                    </div>
                  </div>
                  {file.type === 'file' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteFile(file)
                      }}
                      className="p-1 hover:bg-red-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                      title={t('sandbox.deleteFile')}
                    >
                      <Trash2 className="w-3 h-3 text-red-500" />
                    </button>
                  )}
                  {file.type === 'directory' && (
                    <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

        <div className={`${selectedFile ? 'flex' : 'hidden md:flex'} flex-1 min-w-0 min-h-0 flex-col bg-white`}>
          {selectedFile ? (
            <>
              <div className="p-3 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedFile(null)}
                    className="md:hidden p-1 -ml-1 hover:bg-gray-100 rounded"
                    aria-label="返回文件列表"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </button>
                  <FileText className="w-5 h-5 text-gray-600" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{selectedFile.name}</div>
                    <div className="text-xs text-gray-500 truncate">{selectedFile.path}</div>
                  </div>
                </div>
                <div className="flex gap-2 shrink-0">
                  {fileEditing ? (
                    <>
                      <button
                        onClick={handleSaveFile}
                        disabled={filesLoading}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50 transition-colors"
                      >
                        <Save className="w-4 h-4" />
                        {t('common.save')}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setFileEditing(false)
                          handleFileClick(selectedFile)
                        }}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                      >
                        {t('sandbox.cancelEdit')}
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setFileEditing(true)}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                      {t('sandbox.edit')}
                    </button>
                  )}
                </div>
              </div>
              <div className="flex-1 overflow-hidden">
                {fileEditing ? (
                  <textarea
                    value={fileContent}
                    onChange={(e) => setFileContent(e.target.value)}
                    className="w-full h-full p-4 font-mono text-sm resize-none focus:outline-none border-none"
                    placeholder={t('sandbox.filePlaceholder')}
                  />
                ) : (
                  <pre className="w-full h-full p-4 overflow-auto font-mono text-sm text-gray-900 whitespace-pre-wrap">
                    {fileContent || t('sandbox.emptyOutput')}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center max-w-md">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p className="text-lg mb-2">{t('sandbox.noFileSelected')}</p>
                <p className="text-sm text-gray-500">{t('sandbox.noFileSelectedHint')}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <div className="fixed top-16 left-0 md:left-64 right-0 bottom-0 flex bg-gray-50 overflow-hidden">
      {/* Sandbox List Sidebar */}
      <div className={`${selectedSandbox ? 'hidden md:flex' : 'flex'} w-full md:w-80 md:shrink-0 bg-white border-r border-gray-200 flex-col min-h-0`}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">{t('sandbox.pageTitle')}</h2>
          </div>
          <button
            type="button"
            onClick={() => {
              resetForm()
              setCreateDialogOpen(true)
            }}
            className="p-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            title={t('sandbox.newSandboxTooltip')}
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          {sandboxes.map((sandbox) => (
            <div
              key={sandbox.uuid}
              className={`p-3 border-b border-gray-100 cursor-pointer transition-colors ${
                selectedSandbox?.uuid === sandbox.uuid
                  ? 'bg-primary-50 border-l-4 border-l-primary-600'
                  : 'hover:bg-gray-50'
              }`}
              onClick={() => setSelectedSandbox(sandbox)}
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-gray-900">{sandbox.name}</h3>
                <div className="flex gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedSandbox(sandbox)
                      openEditDialog(sandbox)
                    }}
                    className="p-1 hover:bg-gray-200 rounded"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSandbox(sandbox.uuid)
                    }}
                    className="p-1 hover:bg-red-100 rounded"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
              <div className="text-sm text-gray-600 space-y-1">
                <div>
                  {t('sandbox.mockUser')}: {sandbox.mock_user_nickname} ({sandbox.mock_user_id})
                </div>
                {sandbox.mock_group_id && (
                  <div>
                    {t('sandbox.mockGroup')}: {sandbox.mock_group_name || sandbox.mock_group_id}
                  </div>
                )}
                <div>
                  {t('sandbox.messages')}: {sandbox.message_count}
                </div>
                <div className="flex gap-2 mt-2">
                  {sandbox.use_plugins && (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                      {t('sandbox.badgePlugins')}
                    </span>
                  )}
                  {sandbox.use_ai && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                      AI
                    </span>
                  )}
                  {!sandbox.enabled && (
                    <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                      {t('sandbox.badgeDisabled')}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Area */}
      <div className={`${selectedSandbox ? 'flex' : 'hidden md:flex'} flex-1 min-w-0 flex-col`}>
        {selectedSandbox ? (
          <>
            {/* Header */}
            <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  type="button"
                  onClick={() => setSelectedSandbox(null)}
                  className="md:hidden p-1 -ml-1 hover:bg-gray-100 rounded"
                  aria-label="返回沙箱列表"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
                <FlaskConical className="w-6 h-6 text-primary-600" />
                <div className="min-w-0">
                  <h2 className="font-semibold text-gray-900 truncate">{selectedSandbox.name}</h2>
                  <p className="text-xs text-gray-500 truncate">
                    {selectedSandbox.description || ''}
                  </p>
                </div>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="bg-white border-b border-gray-200 flex overflow-x-auto px-2 md:px-6">
              <button
                type="button"
                onClick={() => setActiveTab('chat')}
                className={`shrink-0 flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === 'chat'
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                <MessageSquare className="w-5 h-5" />
                {t('sandbox.tabChat')}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('shell')}
                className={`shrink-0 flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === 'shell'
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                <Terminal className="w-5 h-5" />
                {t('sandbox.tabShell')}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('python')}
                className={`shrink-0 flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === 'python'
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                <Code2 className="w-5 h-5" />
                {t('sandbox.tabPython')}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('files')}
                className={`shrink-0 flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                  activeTab === 'files'
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                <FileText className="w-5 h-5" />
                {t('sandbox.tabFiles')}
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
              {activeTab === 'chat' && renderChatTab()}
              {activeTab === 'shell' && renderShellTab()}
              {activeTab === 'python' && renderPythonTab()}
              {activeTab === 'files' && renderFilesTab()}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <FlaskConical className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-xl">{t('sandbox.selectSandboxTitle')}</p>
              <p className="text-sm mt-2">{t('sandbox.selectSandboxHint')}</p>
            </div>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {createDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold">{t('sandbox.createTitle')}</h2>
              <button
                type="button"
                onClick={() => setCreateDialogOpen(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.name')} *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.description')}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('sandbox.mockUserId')} *</label>
                  <input
                    type="text"
                    value={formData.mock_user_id}
                    onChange={(e) => setFormData({ ...formData, mock_user_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">{t('sandbox.mockUserNickname')}</label>
                  <input
                    type="text"
                    value={formData.mock_user_nickname}
                    onChange={(e) => setFormData({ ...formData, mock_user_nickname: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">{t('sandbox.mockGroupId')}</label>
                  <input
                    type="text"
                    value={formData.mock_group_id}
                    onChange={(e) => setFormData({ ...formData, mock_group_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">{t('sandbox.mockGroupName')}</label>
                  <input
                    type="text"
                    value={formData.mock_group_name}
                    onChange={(e) => setFormData({ ...formData, mock_group_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.aiModel')}</label>
                <select
                  value={formData.ai_model_uuid}
                  onChange={(e) => setFormData({ ...formData, ai_model_uuid: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('sandbox.selectModel')}</option>
                  {models.map((model) => (
                    <option key={model.uuid} value={model.uuid}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.aiPreset')}</label>
                <select
                  value={formData.ai_preset_uuid}
                  onChange={(e) => setFormData({ ...formData, ai_preset_uuid: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('sandbox.selectPreset')}</option>
                  {presets.map((preset) => (
                    <option key={preset.uuid} value={preset.uuid}>
                      {preset.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.use_plugins}
                    onChange={(e) => setFormData({ ...formData, use_plugins: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('sandbox.usePlugins')}</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.use_ai}
                    onChange={(e) => setFormData({ ...formData, use_ai: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('sandbox.useAi')}</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                type="button"
                onClick={() => setCreateDialogOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={handleCreateSandbox}
                disabled={loading}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? t('common.loading') : t('sandbox.create')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Dialog */}
      {editDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold">{t('sandbox.editTitle')}</h2>
              <button
                type="button"
                onClick={() => setEditDialogOpen(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.name')} *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.description')}</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.aiModel')}</label>
                <select
                  value={formData.ai_model_uuid}
                  onChange={(e) => setFormData({ ...formData, ai_model_uuid: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('sandbox.selectModel')}</option>
                  {models.map((model) => (
                    <option key={model.uuid} value={model.uuid}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">{t('sandbox.aiPreset')}</label>
                <select
                  value={formData.ai_preset_uuid}
                  onChange={(e) => setFormData({ ...formData, ai_preset_uuid: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">{t('sandbox.selectPreset')}</option>
                  {presets.map((preset) => (
                    <option key={preset.uuid} value={preset.uuid}>
                      {preset.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.use_plugins}
                    onChange={(e) => setFormData({ ...formData, use_plugins: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('sandbox.usePlugins')}</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.use_ai}
                    onChange={(e) => setFormData({ ...formData, use_ai: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span className="text-sm">{t('sandbox.useAi')}</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                type="button"
                onClick={() => setEditDialogOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={handleUpdateSandbox}
                disabled={loading}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? t('sandbox.saving') : t('sandbox.save')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Dialog */}
      {confirmDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertCircle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-bold text-gray-900">{confirmDialog.title}</h3>
            </div>
            <p className="text-gray-600 mb-6">{confirmDialog.message}</p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDialog({ ...confirmDialog, open: false })}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {t('sandbox.cancel')}
              </button>
              <button
                type="button"
                onClick={confirmDialog.onConfirm}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                {t('sandbox.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Dialog */}
      {promptDialog.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 mb-4">{promptDialog.title}</h3>
            <input
              type="text"
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder={promptDialog.placeholder}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 mb-4"
              onKeyPress={(e) => {
                if (e.key === 'Enter' && promptValue.trim()) {
                  promptDialog.onConfirm(promptValue)
                  setPromptValue('')
                }
              }}
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setPromptDialog({ ...promptDialog, open: false })
                  setPromptValue('')
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                {t('sandbox.cancel')}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (promptValue.trim()) {
                    promptDialog.onConfirm(promptValue)
                    setPromptValue('')
                  }
                }}
                disabled={!promptValue.trim()}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {t('sandbox.promptOk')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
