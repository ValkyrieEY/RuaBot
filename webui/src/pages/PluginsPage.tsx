import { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/components/Toast'
import { api, type PluginInfo } from '@/utils/api'
import DynamicFormComponent from '@/components/DynamicForm/DynamicFormComponent'
import { 
  Play, 
  Square, 
  RotateCw, 
  Settings, 
  AlertCircle, 
  Upload,
  X,
  Save,
  CheckCircle,
  Trash2,
  Download
} from 'lucide-react'

interface PluginConfigModalProps {
  pluginName: string
  isOpen: boolean
  onClose: () => void
  onSave: (config: any) => void
}

function PluginConfigModal({ pluginName, isOpen, onClose, onSave }: PluginConfigModalProps) {
  const toast = useToast()
  const [config, setConfig] = useState<any>({})
  const [schema, setSchema] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saving, setSaving] = useState(false)
  const [priority, setPriority] = useState<number>(100)
  
  // 用于防止竞态条件
  const loadingRequestRef = useRef(0)

  useEffect(() => {
    if (isOpen && pluginName) {
      loadConfigData()
    }
  }, [isOpen, pluginName])

  const loadConfigData = async () => {
    const currentRequest = ++loadingRequestRef.current
    setLoading(true)
    setLoadError('')
    
    try {
      // 并行加载配置和插件信息
      const [schemaData, pluginData] = await Promise.allSettled([
        api.getPluginConfigSchema(pluginName),
        api.getPlugin(pluginName)
      ])
      
      // 只有最新的请求才更新状态
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // 处理配置schema
      if (schemaData.status === 'fulfilled') {
        setSchema(schemaData.value)
        const loadedConfig = schemaData.value.current_config || schemaData.value.default_config || {}
        setConfig(loadedConfig)
      } else {
        console.error('Failed to load config schema:', schemaData.reason)
        throw new Error('加载配置失败: ' + (schemaData.reason?.message || '未知错误'))
      }
      
      // 处理优先级
      if (pluginData.status === 'fulfilled') {
        const loadedPriority = pluginData.value?.system_data?.priority
        setPriority(loadedPriority !== undefined ? loadedPriority : 100)
      } else {
        console.error('Failed to load plugin info:', pluginData.reason)
        // 优先级加载失败不影响整体，使用默认值
        setPriority(100)
      }
    } catch (error: any) {
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load config data:', error)
      const errorMessage = error.response?.data?.detail || 
                          error.message || 
                          '加载插件配置失败'
      setLoadError(errorMessage)
    } finally {
      if (currentRequest === loadingRequestRef.current) {
        setLoading(false)
      }
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await api.updatePluginConfig(pluginName, config, priority)
      // Use returned config if available, otherwise use current config
      const updatedConfig = response?.config || config
      
      // Update local config state with returned config
      setConfig(updatedConfig)
      
      // Update priority from response if available
      if (response?.priority !== undefined) {
        setPriority(response.priority)
      }
      
      // Show success message
      toast.success('配置保存成功')
      
      // Notify parent but don't close modal
      onSave(updatedConfig)
      // Don't close modal automatically - let user close it manually
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Fixed Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 flex-shrink-0">
          <h2 className="text-xl font-bold text-gray-900">插件设置: {pluginName}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 错误显示 */}
          {loadError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium text-red-800 mb-1">加载配置失败</h4>
                  <p className="text-sm text-red-700 break-words">{loadError}</p>
                  <button
                    onClick={loadConfigData}
                    disabled={loading}
                    className="mt-3 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 rounded text-sm font-medium transition-colors inline-flex items-center gap-1.5"
                  >
                    <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    {loading ? '加载中...' : '重试'}
                  </button>
                </div>
              </div>
            </div>
          )}
          
          {/* Priority Setting */}
          {!loadError && (
            <div className="border-b border-gray-200 pb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                插件优先级
              </label>
              <div className="space-y-2">
                <input
                  type="number"
                  min="0"
                  max="1000"
                  value={priority}
                  onChange={(e) => setPriority(parseInt(e.target.value) || 100)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="100"
                />
                <p className="text-xs text-gray-500">
                  优先级越小，越早执行（默认：100）。用于控制事件上下文处理的顺序。
                </p>
              </div>
            </div>
          )}

          {/* Plugin Configuration */}
          {!loadError && (
            loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              </div>
            ) : schema && schema.config_schema ? (
              <DynamicFormComponent
                schema={schema.config_schema}
                initialValues={config}
                onSubmit={(values) => setConfig(values)}
              />
            ) : (
              <div className="text-center py-12 text-gray-500">
                此插件没有可配置项
              </div>
            )
          )}
        </div>
        
        {/* Fixed Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 flex-shrink-0">
          <button
            onClick={onClose}
            className="btn btn-secondary"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading || !!loadError}
            className="btn btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const handleUpload = async () => {
    if (!file) {
      setError('请选择文件')
      return
    }

    setUploading(true)
    setError('')
    setSuccess(false)

    try {
      await api.uploadPlugin(file)
      setSuccess(true)
      setTimeout(() => {
        onSuccess()
        onClose()
        setFile(null)
        setSuccess(false)
      }, 1500)
    } catch (err: any) {
      setError(err.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files && files.length > 0) {
      const droppedFile = files[0]
      if (droppedFile.name.endsWith('.zip')) {
        setFile(droppedFile)
        setError('')
      } else {
        setError('只支持 ZIP 文件')
      }
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            上传插件
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          {success ? (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span>上传成功！</span>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  选择或拖入 ZIP 文件
                </label>
                
                {/* Drag and Drop Zone */}
                <div
                  onDragEnter={handleDragEnter}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`
                    relative border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
                    ${isDragging 
                      ? 'border-primary-500 bg-primary-50' 
                      : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
                    }
                  `}
                  onClick={() => document.getElementById('file-upload')?.click()}
                >
                  <input
                    id="file-upload"
                    type="file"
                    accept=".zip"
                    onChange={(e) => {
                      const selectedFile = e.target.files?.[0]
                      if (selectedFile) {
                        setFile(selectedFile)
                        setError('')
                      }
                    }}
                    className="hidden"
                  />
                  
                  <Upload className={`w-12 h-12 mx-auto mb-3 ${isDragging ? 'text-primary-500' : 'text-gray-400'}`} />
                  
                  {file ? (
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-gray-900">{file.name}</p>
                      <p className="text-xs text-gray-500">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setFile(null)
                        }}
                        className="text-sm text-primary-600 hover:text-primary-700"
                      >
                        重新选择
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-sm text-gray-600">
                        {isDragging ? '松开鼠标上传文件' : '拖入文件或点击选择'}
                      </p>
                      <p className="text-xs text-gray-500">
                        支持 .zip 格式
                      </p>
                    </div>
                  )}
                </div>
              </div>
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
            </>
          )}
        </div>
        
        {!success && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <button
              onClick={onClose}
              className="btn btn-secondary"
              disabled={uploading}
            >
              取消
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || !file}
              className="btn btn-primary flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {uploading ? '上传中...' : '上传'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

interface GitHubInstallModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function GitHubInstallModal({ isOpen, onClose, onSuccess }: GitHubInstallModalProps) {
  const [repoUrl, setRepoUrl] = useState('')
  const [installing, setInstalling] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleInstall = async () => {
    if (!repoUrl.trim()) {
      setError('请输入 GitHub 仓库地址')
      return
    }

    setInstalling(true)
    setError('')
    setSuccess(false)

    try {
      await api.installPluginFromGitHub(repoUrl.trim())
      setSuccess(true)
      setTimeout(() => {
        onSuccess()
        onClose()
        setRepoUrl('')
        setSuccess(false)
      }, 1500)
    } catch (err: any) {
      setError(err.response?.data?.detail || '安装失败')
    } finally {
      setInstalling(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            从 GitHub 安装插件
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          {success ? (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span>安装成功！</span>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  GitHub 仓库地址
                </label>
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="owner/repo 或 https://github.com/owner/repo"
                  className="input w-full"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !installing) {
                      handleInstall()
                    }
                  }}
                />
                <p className="text-xs text-gray-500 mt-2">
                  支持格式：owner/repo 或完整的 GitHub URL
                </p>
              </div>
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
            </>
          )}
        </div>
        
        {!success && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <button
              onClick={onClose}
              disabled={installing}
              className="btn btn-secondary"
            >
              取消
            </button>
            <button
              onClick={handleInstall}
              disabled={installing || !repoUrl.trim()}
              className="btn btn-primary flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              {installing ? '安装中...' : '安装'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function PluginsPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showGitHubModal, setShowGitHubModal] = useState(false)
  const [configPlugin, setConfigPlugin] = useState<string | null>(null)
  
  // 用于防止竞态条件
  const loadingRequestRef = useRef(0)

  useEffect(() => {
    const loadInitialData = async () => {
      await loadPlugins()
      setInitialLoading(false)
    }
    loadInitialData()
  }, [])

  const loadPlugins = async () => {
    const currentRequest = ++loadingRequestRef.current
    
    try {
      setLoading(true)
      setLoadError('') // 清除之前的错误
      
      const data = await api.getPlugins()
      
      // 只有最新的请求才更新状态
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // 验证数据
      if (!Array.isArray(data)) {
        throw new Error('Invalid plugins data received')
      }
      
      console.log('Loaded plugins:', data)
      setPlugins(data)
    } catch (error: any) {
      // 只有最新的请求才更新错误状态
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load plugins:', error)
      const errorMessage = error.response?.data?.detail || 
                          error.message || 
                          '加载插件列表失败'
      setLoadError(errorMessage)
      toast.error(errorMessage)
    } finally {
      // 只有最新的请求才更新加载状态
      if (currentRequest === loadingRequestRef.current) {
        setLoading(false)
      }
    }
  }

  const handleAction = async (pluginName: string, action: string) => {
    setActionLoading(pluginName)
    try {
      await api.pluginAction(pluginName, action)
      await loadPlugins() // Reload plugins after action
      
      // Show success toast based on action
      const actionMessages = {
        enable: `插件 "${pluginName}" 已启用`,
        disable: `插件 "${pluginName}" 已停用`,
        load: `插件 "${pluginName}" 已启用`,
        unload: `插件 "${pluginName}" 已停用`,
        reload: `插件 "${pluginName}" 已重载`
      }
      toast.success(actionMessages[action as keyof typeof actionMessages] || `操作成功`)
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || t('plugins.actionFailed')
      toast.error(errorMsg)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (pluginName: string) => {
    if (!confirm(`确定要删除插件 "${pluginName}" 吗？此操作将删除插件数据库记录和文件目录，无法恢复！`)) {
      return
    }
    
    setActionLoading(pluginName)
    try {
      await api.deletePlugin(pluginName)
      await loadPlugins() // Reload plugins after deletion
      toast.success(`插件 "${pluginName}" 已成功删除`)
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '删除插件失败'
      toast.error(errorMsg)
    } finally {
      setActionLoading(null)
    }
  }

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  // 加载失败显示
  if (loadError && plugins.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="min-w-0 flex-shrink">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('plugins.title')}</h1>
            <p className="text-gray-500 text-sm mt-1">{t('plugins.description')}</p>
          </div>
        </div>
        
        <div className="card text-center py-12">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            加载插件失败
          </h3>
          <p className="text-sm text-gray-600 mb-4">{loadError}</p>
          <button
            onClick={loadPlugins}
            disabled={loading}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors inline-flex items-center gap-2"
          >
            <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? '加载中...' : t('common.retry') || '重试'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-shrink">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('plugins.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('plugins.description')}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          <button
            onClick={() => setShowGitHubModal(true)}
            className="btn btn-secondary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <Download className="w-4 h-4" />
            <span className="hidden xl:inline">GitHub 安装</span>
            <span className="xl:hidden">GitHub</span>
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn btn-primary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <Upload className="w-4 h-4" />
            <span className="hidden lg:inline">{t('plugins.uploadPlugin')}</span>
            <span className="lg:hidden">{t('common.upload')}</span>
          </button>
          <button
            onClick={loadPlugins}
            className="btn btn-secondary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <RotateCw className="w-4 h-4" />
            <span className="hidden lg:inline">{t('common.refresh')}</span>
          </button>
        </div>
      </div>

      {plugins.length === 0 ? (
        <div className="card text-center py-12">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
            <AlertCircle className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {t('plugins.noPlugins')}
          </h3>
          <p className="text-gray-500 mb-4">{t('plugins.noPluginsDescription')}</p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn btn-primary flex items-center gap-2 mx-auto"
          >
            <Upload className="w-4 h-4" />
            {t('plugins.uploadPlugin')}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plugins.map((plugin) => (
            <div key={plugin.name} className="card flex flex-col h-full overflow-hidden">
              <div className="flex items-start justify-between mb-4 min-w-0">
                <div className="flex-1 min-h-[80px] min-w-0">
                  <h3 className="font-semibold text-gray-900 mb-1 truncate">{plugin.name}</h3>
                  {(plugin.metadata?.description || plugin.description) && (
                    <p className="text-sm text-gray-600 mb-2 line-clamp-2 break-words">
                      {plugin.metadata?.description || plugin.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
                    {(plugin.metadata?.version || plugin.version) && (
                      <span className="whitespace-nowrap">v{plugin.metadata?.version || plugin.version}</span>
                    )}
                    {(plugin.metadata?.author || plugin.author) && (
                      <>
                        {(plugin.metadata?.version || plugin.version) && <span>•</span>}
                        <span className="truncate">{plugin.metadata?.author || plugin.author}</span>
                      </>
                    )}
                  </div>
                  {(plugin as any).adapter && (
                    <div className="text-xs text-gray-500 mt-1 truncate">
                      {t('plugins.adapter')}: <span className="font-medium">{(plugin as any).adapter}</span>
                    </div>
                  )}
                </div>
                <div
                  className={`px-2 py-1 rounded text-xs font-medium flex-shrink-0 h-fit ml-2 ${
                    plugin.enabled
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {plugin.enabled ? t('common.enabled') : t('common.disabled')}
                </div>
              </div>

              <div className="space-y-2 mt-auto">
                {/* 主操作按钮行 */}
                <div className="flex gap-2">
                  {plugin.enabled === true ? (
                    <>
                      <button
                        onClick={() => handleAction(plugin.name, 'reload')}
                        disabled={actionLoading === plugin.name || loading}
                        className="btn btn-secondary flex-1 flex items-center justify-center gap-1.5 text-sm whitespace-nowrap"
                      >
                        <RotateCw className="w-4 h-4" />
                        {t('plugins.reload')}
                      </button>
                      <button
                        onClick={() => handleAction(plugin.name, 'disable')}
                        disabled={actionLoading === plugin.name || loading}
                        className="btn btn-secondary flex-1 flex items-center justify-center gap-1.5 text-sm whitespace-nowrap"
                      >
                        <Square className="w-4 h-4" />
                        {t('plugins.disable')}
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => handleAction(plugin.name, 'enable')}
                      disabled={actionLoading === plugin.name || loading}
                      className="btn btn-primary flex-1 flex items-center justify-center gap-1.5 text-sm whitespace-nowrap"
                    >
                      <Play className="w-4 h-4" />
                      {t('plugins.enable')}
                    </button>
                  )}
                </div>
                {/* 次要操作按钮行 */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setConfigPlugin(plugin.name)}
                    disabled={loading}
                    className="btn btn-secondary flex-1 flex items-center justify-center gap-1.5 text-sm whitespace-nowrap"
                    title="配置"
                  >
                    <Settings className="w-4 h-4" />
                    <span>配置</span>
                  </button>
                  <button
                    onClick={() => handleDelete(plugin.name)}
                    disabled={actionLoading === plugin.name || loading}
                    className="btn btn-danger flex-1 flex items-center justify-center gap-1.5 text-sm whitespace-nowrap"
                    title="删除插件"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>删除</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onSuccess={loadPlugins}
      />

      <GitHubInstallModal
        isOpen={showGitHubModal}
        onClose={() => setShowGitHubModal(false)}
        onSuccess={loadPlugins}
      />

      <PluginConfigModal
        pluginName={configPlugin || ''}
        isOpen={configPlugin !== null}
        onClose={() => setConfigPlugin(null)}
        onSave={loadPlugins}
      />
    </div>
  )
}
