import { useEffect, useMemo, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useToast } from '@/components/Toast'
import { api, type MarketplacePlugin, type PluginInfo } from '@/utils/api'
import DynamicFormComponent from '@/components/DynamicForm/DynamicFormComponent'
import { 
  RotateCw, 
  Settings, 
  AlertCircle, 
  Upload,
  X,
  Save,
  Trash2,
  Download,
  Github,
  BookOpen,
  RefreshCcw,
  Package,
  Search,
  ExternalLink,
  Loader2
} from 'lucide-react'

interface PluginUpdateInfo {
  marketplacePlugin: MarketplacePlugin
  repository: string
  currentVersion: string
  latestVersion: string
}

interface PluginConfigModalProps {
  pluginName: string
  isOpen: boolean
  onClose: () => void
  onSave: (config: any) => void
}

function collectUploadedFileKeys(value: any): string[] {
  const keys = new Set<string>()

  const walk = (current: any) => {
    if (Array.isArray(current)) {
      current.forEach(walk)
      return
    }
    if (current && typeof current === 'object') {
      Object.values(current).forEach(walk)
      return
    }
    if (typeof current === 'string' && current.startsWith('plugin_config_')) {
      keys.add(current)
    }
  }

  walk(value)
  return [...keys]
}

function PluginConfigModal({ pluginName, isOpen, onClose, onSave }: PluginConfigModalProps) {
  const { t } = useTranslation()
  const toast = useToast()
  const [config, setConfig] = useState<any>({})
  const [schema, setSchema] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [saving, setSaving] = useState(false)
  const [priority, setPriority] = useState<number>(100)
  
  // 
  const loadingRequestRef = useRef(0)
  const pendingUploadKeysRef = useRef<Set<string>>(new Set())

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
      // 
      const [schemaData, pluginData] = await Promise.allSettled([
        api.getPluginConfigSchema(pluginName),
        api.getPlugin(pluginName)
      ])
      
      // 
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // schema
      if (schemaData.status === 'fulfilled') {
        setSchema(schemaData.value)
        const loadedConfig = schemaData.value.current_config || schemaData.value.default_config || {}
        setConfig(loadedConfig)
        pendingUploadKeysRef.current.clear()
      } else {
        console.error('Failed to load config schema:', schemaData.reason)
        throw new Error(t('plugins.configLoadErrorTitle') + ': ' + (schemaData.reason?.message || ''))
      }
      
      // 
      if (pluginData.status === 'fulfilled') {
        const loadedPriority = pluginData.value?.system_data?.priority
        setPriority(loadedPriority !== undefined ? loadedPriority : 100)
      } else {
        console.error('Failed to load plugin info:', pluginData.reason)
        // 
        setPriority(100)
      }
    } catch (error: any) {
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load config data:', error)
      const errorMessage = error.response?.data?.detail || 
                          error.message || 
                          t('plugins.configLoadErrorTitle')
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
      const persistedKeys = new Set(collectUploadedFileKeys(updatedConfig))
      pendingUploadKeysRef.current.forEach((key) => {
        if (persistedKeys.has(key)) {
          pendingUploadKeysRef.current.delete(key)
        }
      })
      
      // Update priority from response if available
      if (response?.priority !== undefined) {
        setPriority(response.priority)
      }
      
      // Show success message
      toast.success(t('plugins.configSaveSuccess'))
      
      // Notify parent but don't close modal
      onSave(updatedConfig)
      // Don't close modal automatically - let user close it manually
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('common.error'))
    } finally {
      setSaving(false)
    }
  }

  const handleClose = async () => {
    const pendingKeys = [...pendingUploadKeysRef.current]
    pendingUploadKeysRef.current.clear()

    if (pendingKeys.length > 0) {
      await Promise.allSettled(
        pendingKeys.map((fileKey) => api.deletePluginConfigFile(pluginName, fileKey)),
      )
    }

    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col">
        {/* Fixed Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 flex-shrink-0">
          <h2 className="text-xl font-bold text-gray-900">{t('plugins.pluginConfigTitle', { name: pluginName })}</h2>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/*  */}
          {loadError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium text-red-800 mb-1">{t('plugins.configLoadErrorTitle')}</h4>
                  <p className="text-sm text-red-700 break-words">{loadError}</p>
                  <button
                    onClick={loadConfigData}
                    disabled={loading}
                    className="mt-3 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 rounded text-sm font-medium transition-colors inline-flex items-center gap-1.5"
                  >
                    <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    {loading ? t('common.loading') : t('plugins.retryLoad')}
                  </button>
                </div>
              </div>
            </div>
          )}
          
          {/* Priority Setting */}
          {!loadError && (
            <div className="border-b border-gray-200 pb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {t('plugins.interceptorPriority')}
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
                  {t('plugins.interceptorPriorityHint')}
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
                pluginName={pluginName}
                schema={schema.config_schema}
                initialValues={config}
                onSubmit={(values) => setConfig(values)}
                onFileUploaded={(fileKey) => pendingUploadKeysRef.current.add(fileKey)}
              />
            ) : (
              <div className="text-center py-12 text-gray-500">
                {t('plugins.noConfigSchema')}
              </div>
            )
          )}
        </div>
        
        {/* Fixed Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 flex-shrink-0">
          <button
            onClick={handleClose}
            className="btn btn-secondary"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading || !!loadError}
            className="btn btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? t('common.loading') : t('common.save')}
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
  const { t } = useTranslation()
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  const handleUpload = async () => {
    if (!file) {
      toast.warning(t('plugins.uploadZipLabel'))
      return
    }

    setUploading(true)

    try {
      await api.uploadPlugin(file)
      toast.success(t('plugins.uploadSuccessMsg'))
      onSuccess()
      onClose()
      setFile(null)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('common.error'))
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
      } else {
        toast.warning(t('plugins.invalidZip'))
      }
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            {t('plugins.uploadZipTitle')}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('plugins.uploadZipLabel')}
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
                    {t('plugins.removeFile')}
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-sm text-gray-600">
                    {isDragging ? t('plugins.dragDropZip') : t('plugins.dragDropZip')}
                  </p>
                  <p className="text-xs text-gray-500">
                    {t('plugins.zipOnlyHint')}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="btn btn-secondary"
            disabled={uploading}
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || !file}
            className="btn btn-primary flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            {uploading ? t('common.loading') : t('plugins.uploadPlugin')}
          </button>
        </div>
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
  const { t } = useTranslation()
  const toast = useToast()
  const [repoUrl, setRepoUrl] = useState('')
  const [installing, setInstalling] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const [installLogs, setInstallLogs] = useState<string[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)
  const installFinishedRef = useRef(false)

  useEffect(() => {
    // Cleanup EventSource on unmount or close
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [])

  const handleInstall = async () => {
    if (!repoUrl.trim()) {
      toast.warning(t('plugins.githubUrlRequired'))
      return
    }

    setInstalling(true)
    installFinishedRef.current = false
    setProgress(0)
    setProgressMessage('')
    setInstallLogs([])

    try {
      // Start installation and get task_id
      const response = await api.installPluginFromGitHub(repoUrl.trim())
      const taskId = response.task_id

      // Connect to SSE endpoint for progress updates
      const eventSource = new EventSource(api.getPluginProgressUrl(taskId))
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.status === 'completed') {
            installFinishedRef.current = true
            setProgress(100)
            setProgressMessage('Update OK')
            setInstallLogs(Array.isArray(data.logs) ? data.logs : [])
            setInstalling(false)
            toast.success(t('plugins.uploadSuccessMsg'))
            eventSource.close()
            eventSourceRef.current = null
            setTimeout(() => {
              onSuccess()
              onClose()
              setRepoUrl('')
              setProgress(0)
              setProgressMessage('')
            }, 500)
          } else if (data.status === 'failed') {
            installFinishedRef.current = true
            setInstallLogs(Array.isArray(data.logs) ? data.logs : [])
            toast.error(data.message || 'Update failed')
            setInstalling(false)
            eventSource.close()
            eventSourceRef.current = null
          } else {
            setProgress(data.progress || 0)
            setProgressMessage(data.message || '')
            setInstallLogs(Array.isArray(data.logs) ? data.logs : [])
          }
        } catch (err) {
          console.error('Failed to parse progress data:', err)
        }
      }

      eventSource.onerror = (err) => {
        console.error('EventSource error:', err)
        eventSource.close()
        eventSourceRef.current = null
        if (!installFinishedRef.current) {
          toast.error('Connection interrupted')
          setInstalling(false)
        }
      }
    } catch (err: any) {
      installFinishedRef.current = true
      toast.error(err.response?.data?.detail || t('common.error'))
      setInstalling(false)
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }

  const handleClose = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setInstalling(false)
    setProgress(0)
    setProgressMessage('')
    setInstallLogs([])
    installFinishedRef.current = false
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            {t('plugins.githubInstallTitle')}
          </h2>
          <button
            onClick={handleClose}
            disabled={installing}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('plugins.githubRepoLabel')}
            </label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder={t('plugins.githubRepoPlaceholder')}
              className="input w-full"
              disabled={installing}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !installing) {
                  handleInstall()
                }
              }}
            />
            <p className="text-xs text-gray-500 mt-2">
              {t('plugins.githubRepoHelp')}
            </p>
          </div>
          
          {installing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-700 truncate">{progressMessage || t('plugins.installingGithub')}</span>
                <span className="text-gray-500 flex-shrink-0">{progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="h-64 overflow-y-auto rounded-lg bg-gray-950 p-3">
                <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-gray-100">
                  {installLogs.length > 0 ? installLogs.join('\n') : progressMessage}
                </pre>
              </div>
            </div>
          )}
        </div>
        
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
          <button
            onClick={handleClose}
            disabled={installing}
            className="btn btn-secondary"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleInstall}
            disabled={installing || !repoUrl.trim()}
            className="btn btn-primary flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            {installing ? t('plugins.installingGithub') : t('plugins.installFromGithub')}
          </button>
        </div>
      </div>
    </div>
  )
}

function getMarketplacePluginId(plugin: MarketplacePlugin) {
  const value = plugin.id || plugin.slug || plugin.name || plugin.repository || plugin.github || plugin.githubUrl || plugin.repo_url
  return String(value || 'plugin')
}

function getMarketplacePluginName(plugin: MarketplacePlugin) {
  return plugin.name || plugin.displayName || plugin.id || 'Plugin'
}

function getMarketplaceRepository(plugin: MarketplacePlugin) {
  return (
    plugin.repository ||
    plugin.github ||
    plugin.githubUrl ||
    plugin.repo_url ||
    plugin.repositoryUrl ||
    plugin.github_url ||
    ''
  )
}

function getMarketplaceLogo(plugin: MarketplacePlugin) {
  return plugin.logo || plugin.logoUrl || plugin.icon || ''
}

function getMarketplaceReadme(plugin: MarketplacePlugin) {
  const value =
    plugin.readme ||
    plugin.readmeContent ||
    plugin.readme_content ||
    plugin.README ||
    plugin.documentationContent ||
    plugin.documentation_content ||
    plugin.system_data?.readme ||
    plugin.systemData?.readme ||
    ''

  if (typeof value === 'string') return value
  if (value == null) return ''
  return JSON.stringify(value, null, 2)
}

function getMarketplaceReadmeFilename(plugin: MarketplacePlugin) {
  return (
    plugin.readmeFilename ||
    plugin.readme_filename ||
    plugin.documentationFilename ||
    plugin.documentation_filename ||
    'README.md'
  )
}

function getMarketplaceTags(plugin: MarketplacePlugin): string[] {
  const tags = plugin.tags || plugin.manifest?.tags || []
  return Array.isArray(tags) ? tags.map((tag) => String(tag)).filter(Boolean) : []
}

function getMarketplaceDownloads(plugin: MarketplacePlugin): number {
  const value = plugin.downloads ?? plugin.downloadCount ?? plugin.download_count ?? plugin.stats?.downloads
  const count = Number(value)
  return Number.isFinite(count) && count >= 0 ? count : 0
}

function needsMarketplaceDetail(plugin: MarketplacePlugin) {
  return getMarketplaceTags(plugin).length === 0 || plugin.downloads === undefined || plugin.rating === undefined || plugin.category === undefined
}

function formatMarketplaceUpdatedAt(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString()
}

function normalizePluginKey(value?: string) {
  return String(value || '').trim().toLowerCase()
}

function normalizeRepositoryKey(value?: string) {
  const repo = String(value || '')
    .trim()
    .replace(/^git\+/i, '')
    .replace(/^https?:\/\/github\.com\//i, '')
    .replace(/^git@github\.com:/i, '')
    .replace(/\.git$/i, '')
    .replace(/\/+$/g, '')

  const parts = repo.split('/').filter(Boolean)
  return parts.length >= 2 ? `${parts[0]}/${parts[1]}`.toLowerCase() : repo.toLowerCase()
}

function compareVersions(latest?: string, current?: string) {
  const latestValue = String(latest || '').trim().replace(/^v/i, '')
  const currentValue = String(current || '').trim().replace(/^v/i, '')

  if (!latestValue || !currentValue || latestValue === currentValue) {
    return 0
  }

  const tokenize = (value: string) =>
    value
      .split(/[._+-]/)
      .flatMap((part) => part.match(/\d+|[a-zA-Z]+/g) || [])
      .map((part) => (/^\d+$/.test(part) ? Number(part) : part.toLowerCase()))

  const latestParts = tokenize(latestValue)
  const currentParts = tokenize(currentValue)
  const maxLength = Math.max(latestParts.length, currentParts.length)

  for (let index = 0; index < maxLength; index += 1) {
    const left = latestParts[index] ?? 0
    const right = currentParts[index] ?? 0

    if (left === right) continue

    if (typeof left === 'number' && typeof right === 'number') {
      return left > right ? 1 : -1
    }

    if (typeof left === 'number') {
      return left === 0 ? 1 : 1
    }

    if (typeof right === 'number') {
      return right === 0 ? -1 : -1
    }

    return String(left).localeCompare(String(right), undefined, { numeric: true })
  }

  return latestValue.localeCompare(currentValue, undefined, { numeric: true })
}

function findMarketplacePluginForLocalPlugin(plugin: PluginInfo, marketplacePlugins: MarketplacePlugin[]) {
  const pluginName = normalizePluginKey(getPluginDisplayName(plugin))
  const rawPluginName = normalizePluginKey(plugin.name)
  const repository = normalizeRepositoryKey(plugin.metadata?.repository || plugin.metadata?.homepage)

  return marketplacePlugins.find((marketplacePlugin) => {
    const marketplaceName = normalizePluginKey(getMarketplacePluginName(marketplacePlugin))
    const marketplaceId = normalizePluginKey(marketplacePlugin.id)
    const marketplaceRepo = normalizeRepositoryKey(getMarketplaceRepository(marketplacePlugin))

    return (
      (pluginName && pluginName === marketplaceName) ||
      (rawPluginName && rawPluginName === marketplaceName) ||
      (rawPluginName && rawPluginName === marketplaceId) ||
      (repository && marketplaceRepo && repository === marketplaceRepo)
    )
  })
}

function MarketplaceLogo({ plugin }: { plugin: MarketplacePlugin }) {
  const name = getMarketplacePluginName(plugin)
  const logo = getMarketplaceLogo(plugin)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [logo])

  return (
    <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-xl border border-gray-200 bg-gray-50 flex items-center justify-center">
      {logo && !failed ? (
        <img
          src={logo}
          alt={`${name} logo`}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="text-xl font-bold text-gray-500">
          {name.trim().charAt(0).toUpperCase() || 'P'}
        </span>
      )}
    </div>
  )
}

interface PluginMarketplaceModalProps {
  isOpen: boolean
  onClose: () => void
  onInstallSuccess: () => void | Promise<void>
}

function PluginMarketplaceModal({ isOpen, onClose, onInstallSuccess }: PluginMarketplaceModalProps) {
  const { t } = useTranslation()
  const toast = useToast()
  const [plugins, setPlugins] = useState<MarketplacePlugin[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [loadingReadmeId, setLoadingReadmeId] = useState<string | null>(null)
  const [readmeModal, setReadmeModal] = useState<{
    title: string
    filename: string
    content: string
  } | null>(null)
  const [progress, setProgress] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const eventSourceRef = useRef<EventSource | null>(null)
  const installSettledRef = useRef(false)

  const closeProgressStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }

  useEffect(() => {
    if (isOpen) {
      loadMarketplacePlugins()
    } else {
      closeProgressStream()
      setInstallingId(null)
      setLoadingReadmeId(null)
      setReadmeModal(null)
      setProgress(0)
      setProgressMessage('')
    }

    return () => {
      closeProgressStream()
    }
  }, [isOpen])

  const loadMarketplacePlugins = async () => {
    setLoading(true)
    setError('')

    try {
      const list = await api.getMarketplacePlugins()
      setPlugins(list)
      const enriched = await Promise.all(
        list.map(async (plugin) => {
          if (!needsMarketplaceDetail(plugin)) return plugin
          try {
            const detail = await api.getMarketplacePlugin(getMarketplacePluginId(plugin))
            return { ...plugin, ...detail }
          } catch (err) {
            console.warn('Failed to enrich marketplace plugin:', plugin.id || plugin.name, err)
            return plugin
          }
        })
      )
      setPlugins(enriched)
    } catch (err: any) {
      console.error('Failed to load marketplace plugins:', err)
      const message = err.response?.data?.detail || err.message || t('plugins.marketplaceLoadFailed')
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleShowMarketplaceReadme = async (plugin: MarketplacePlugin) => {
    const id = getMarketplacePluginId(plugin)
    setLoadingReadmeId(id)

    try {
      let targetPlugin = plugin
      let content = getMarketplaceReadme(targetPlugin)

      if (!content.trim() && id) {
        const detailPlugin = await api.getMarketplacePlugin(id)
        targetPlugin = { ...targetPlugin, ...detailPlugin }
        content = getMarketplaceReadme(targetPlugin)
      }

      if (!content.trim()) {
        throw new Error(t('plugins.readmeLoadFailed'))
      }

      setReadmeModal({
        title: getMarketplacePluginName(targetPlugin),
        filename: getMarketplaceReadmeFilename(targetPlugin),
        content,
      })
    } catch (err: any) {
      toast.error(err.response?.data?.detail || err.message || t('plugins.readmeLoadFailed'))
    } finally {
      setLoadingReadmeId(null)
    }
  }

  const waitForInstallProgress = (taskId: string) => {
    return new Promise<void>((resolve, reject) => {
      const eventSource = new EventSource(api.getPluginProgressUrl(taskId))
      eventSourceRef.current = eventSource
      installSettledRef.current = false

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.status === 'completed') {
            installSettledRef.current = true
            setProgress(100)
            setProgressMessage(data.message || t('plugins.marketplaceInstallComplete'))
            closeProgressStream()
            resolve()
            return
          }

          if (data.status === 'failed') {
            installSettledRef.current = true
            closeProgressStream()
            reject(new Error(data.message || t('plugins.marketplaceInstallFailed')))
            return
          }

          setProgress(data.progress || 0)
          setProgressMessage(data.message || '')
        } catch (err) {
          console.error('Failed to parse marketplace install progress:', err)
        }
      }

      eventSource.onerror = () => {
        closeProgressStream()
        if (!installSettledRef.current) {
          reject(new Error(t('plugins.marketplaceInstallConnectionLost')))
        }
      }
    })
  }

  const handleInstall = async (plugin: MarketplacePlugin) => {
    const id = getMarketplacePluginId(plugin)
    setInstallingId(id)
    setProgress(0)
    setProgressMessage(t('plugins.marketplacePreparingInstall'))

    try {
      let targetPlugin = plugin
      let repository = getMarketplaceRepository(targetPlugin)

      if (!repository && id) {
        targetPlugin = await api.getMarketplacePlugin(id)
        repository = getMarketplaceRepository(targetPlugin)
      }

      if (!repository) {
        throw new Error(t('plugins.marketplaceRepositoryMissing'))
      }

      const response = await api.installPluginFromGitHub(repository)

      if (response?.task_id) {
        await waitForInstallProgress(response.task_id)
      }

      try {
        const recordedPlugin = await api.recordMarketplaceDownload(id)
        if (recordedPlugin) {
          setPlugins((current) =>
            current.map((item) => (getMarketplacePluginId(item) === id ? { ...item, ...recordedPlugin } : item))
          )
        }
      } catch (recordErr) {
        console.warn('Failed to record marketplace download:', id, recordErr)
      }

      toast.success(t('plugins.marketplaceInstallSuccess'))
      await onInstallSuccess()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || err.message || t('plugins.marketplaceInstallFailed'))
    } finally {
      closeProgressStream()
      setInstallingId(null)
      setProgress(0)
      setProgressMessage('')
    }
  }

  const visiblePlugins = plugins.filter((plugin) => {
    const keyword = query.trim().toLowerCase()
    if (!keyword) return true

    return [
      getMarketplacePluginName(plugin),
      plugin.author,
      plugin.description,
      getMarketplaceRepository(plugin),
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword))
  })

  if (!isOpen) return null

  return (
    <>
    <div className="fixed inset-0 z-50 bg-black/50 p-3 sm:p-5 lg:p-8 flex items-center justify-center">
      <div className="flex h-[86vh] w-[94vw] max-w-[1760px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <div className="flex flex-col gap-4 border-b border-gray-200 p-4 sm:p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-gray-950 sm:text-2xl">{t('plugins.pluginMarketplace')}</h2>
            <p className="mt-1 text-sm text-gray-500">{t('plugins.marketplaceDescription')}</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative min-w-0 sm:w-72">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t('plugins.marketplaceSearchPlaceholder')}
                className="input h-10 pl-9"
              />
            </div>
            <button
              onClick={loadMarketplacePlugins}
              disabled={loading || !!installingId}
              className="btn btn-secondary inline-flex items-center justify-center gap-2 whitespace-nowrap"
            >
              <RotateCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              {t('common.refresh')}
            </button>
            <button
              onClick={onClose}
              disabled={!!installingId}
              className="btn btn-secondary inline-flex items-center justify-center gap-2 whitespace-nowrap"
            >
              <X className="h-4 w-4" />
              {t('common.close')}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-5">
          {loading && plugins.length === 0 ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : error && plugins.length === 0 ? (
            <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6 text-center">
              <AlertCircle className="mx-auto mb-3 h-10 w-10 text-red-500" />
              <h3 className="text-base font-semibold text-red-900">{t('plugins.marketplaceLoadFailed')}</h3>
              <p className="mt-2 break-words text-sm text-red-700">{error}</p>
              <button
                onClick={loadMarketplacePlugins}
                className="btn btn-primary mt-4 inline-flex items-center gap-2"
              >
                <RotateCw className="h-4 w-4" />
                {t('common.retry')}
              </button>
            </div>
          ) : visiblePlugins.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-10 text-center text-gray-500">
              {t('plugins.marketplaceEmpty')}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {visiblePlugins.map((plugin) => {
                const id = getMarketplacePluginId(plugin)
                const name = getMarketplacePluginName(plugin)
                const repository = getMarketplaceRepository(plugin)
                const isInstalling = installingId === id
                const isReadmeLoading = loadingReadmeId === id
                const tags = getMarketplaceTags(plugin).slice(0, 4)
                const updatedAt = formatMarketplaceUpdatedAt(plugin.updatedAt || plugin.lastUpdated || plugin.createdAt)
                const downloads = getMarketplaceDownloads(plugin)

                return (
                  <div key={id} className="flex min-h-[230px] flex-col gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-3 min-w-0">
                      <MarketplaceLogo plugin={plugin} />
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate text-lg font-bold text-gray-950">{name}</h3>
                        <div className="mt-1 flex min-w-0 items-center gap-2 text-sm text-gray-500">
                          {plugin.version && <span className="whitespace-nowrap">v{plugin.version}</span>}
                          {plugin.version && plugin.author && <span className="text-gray-300">•</span>}
                          {plugin.author && <span className="truncate">{plugin.author}</span>}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span>{downloads} 下载</span>
                      {updatedAt && (
                        <>
                          <span className="text-gray-300">•</span>
                          <span>更新 {updatedAt}</span>
                        </>
                      )}
                    </div>

                    <p className="min-h-[48px] text-sm leading-6 text-gray-600 line-clamp-2" title={plugin.description || ''}>
                      {plugin.description || t('plugins.noDescription')}
                    </p>

                    <div className="h-[28px] overflow-hidden">
                      {tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {tags.map((tag) => (
                            <span key={tag} className="rounded bg-primary-50 px-2 py-1 text-xs text-primary-700">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-gray-400">暂无标签</div>
                      )}
                    </div>

                    {isInstalling && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span className="truncate">{progressMessage || t('plugins.installingGithub')}</span>
                          <span className="flex-shrink-0">{progress}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-gray-200">
                            <div className="h-full rounded-full bg-primary-600 transition-all" style={{ width: `${progress}%` }} />
                        </div>
                      </div>
                    )}

                    <div className="mt-auto flex items-center justify-between gap-3">
                      {repository ? (
                        <a
                          href={repository}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-700 transition-colors hover:bg-gray-200"
                          title={t('plugins.openRepository')}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      ) : (
                        <span className="h-10 w-10" />
                      )}
                      <button
                        onClick={() => handleShowMarketplaceReadme(plugin)}
                        disabled={!!installingId || !!loadingReadmeId}
                        className="btn btn-secondary inline-flex items-center justify-center gap-2 whitespace-nowrap"
                        title={t('plugins.showReadme')}
                      >
                        {isReadmeLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <BookOpen className="h-4 w-4" />
                        )}
                        README
                      </button>
                      <button
                        onClick={() => handleInstall(plugin)}
                        disabled={!!installingId || !!loadingReadmeId}
                        className="btn btn-primary inline-flex flex-1 items-center justify-center gap-2"
                      >
                        {isInstalling ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="h-4 w-4" />
                        )}
                        {isInstalling ? t('plugins.installingGithub') : t('plugins.marketplaceInstall')}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
    <PluginReadmeModal
      isOpen={readmeModal !== null}
      title={readmeModal?.title || ''}
      filename={readmeModal?.filename || ''}
      content={readmeModal?.content || ''}
      onClose={() => setReadmeModal(null)}
    />
    </>
  )
}

function getPluginDisplayName(plugin: PluginInfo) {
  return plugin.metadata?.name || plugin.name
}

function getPluginLogoSource(plugin: PluginInfo) {
  const logo = plugin.metadata?.logo?.trim()
  if (!logo) return ''

  if (/^(https?:)?\/\//i.test(logo) || /^(data:image\/|blob:)/i.test(logo)) {
    return logo
  }

  return api.getPluginLogoUrl(plugin.name)
}

function PluginLogo({ plugin }: { plugin: PluginInfo }) {
  const displayName = getPluginDisplayName(plugin)
  const logoSrc = getPluginLogoSource(plugin)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [logoSrc])

  const initial = displayName.trim().charAt(0).toUpperCase() || 'P'

  return (
    <div className="w-16 h-16 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center flex-shrink-0">
      {logoSrc && !failed ? (
        <img
          src={logoSrc}
          alt={`${displayName} logo`}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="text-xl font-bold text-gray-500">{initial}</span>
      )}
    </div>
  )
}

function PluginEnableSwitch({
  enabled,
  disabled,
  onToggle,
}: {
  enabled: boolean
  disabled: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation()

  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={onToggle}
      title={enabled ? t('plugins.disable') : t('plugins.enable')}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
        enabled ? 'bg-primary-600' : 'bg-gray-200'
      }`}
    >
      <span
        className={`absolute left-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
          enabled ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )
}

const pluginIconButtonBase =
  'h-9 w-9 rounded-lg transition-colors flex flex-none items-center justify-center disabled:opacity-45 disabled:cursor-not-allowed'
const pluginIconButtonSecondary =
  `${pluginIconButtonBase} bg-gray-100 text-gray-700 hover:bg-gray-200`
const pluginIconButtonWarning =
  `${pluginIconButtonBase} bg-yellow-50 text-yellow-700 hover:bg-yellow-100`
const pluginIconButtonDanger =
  `${pluginIconButtonBase} bg-red-50 text-red-600 hover:bg-red-100`

interface PluginReadmeModalProps {
  isOpen: boolean
  title: string
  filename: string
  content: string
  onClose: () => void
}

interface PluginActionProgressState {
  pluginName: string
  action: string
  status: string
  progress: number
  message: string
  logs: string[]
}

function PluginActionProgressModal({
  state,
  onClose,
}: {
  state: PluginActionProgressState | null
  onClose: () => void
}) {
  const { t } = useTranslation()

  if (!state) return null

  const isRunning = !['completed', 'failed'].includes(state.status)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl h-[620px] max-h-[86vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-200 flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900 truncate">
              {state.pluginName}
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              {state.action} · {state.status}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isRunning}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 h-[104px] flex-shrink-0">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-700 truncate">{state.message || t('common.loading')}</span>
            <span className="text-gray-500 flex-shrink-0">{state.progress}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-gray-200">
            <div
              className={`h-full rounded-full transition-all ${state.status === 'failed' ? 'bg-red-500' : 'bg-primary-600'}`}
              style={{ width: `${state.progress}%` }}
            />
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto border-y border-gray-200 bg-gray-950 p-4">
          <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-gray-100">
            {state.logs.length > 0 ? state.logs.join('\n') : state.message}
          </pre>
        </div>

        <div className="flex items-center justify-end gap-3 p-5 flex-shrink-0">
          <button
            onClick={onClose}
            disabled={isRunning}
            className="btn btn-secondary"
          >
            {isRunning ? t('common.loading') : t('common.close')}
          </button>
        </div>
      </div>
    </div>
  )
}

function PluginReadmeModal({ isOpen, title, filename, content, onClose }: PluginReadmeModalProps) {
  const { t } = useTranslation()

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[86vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-200 flex-shrink-0">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900 truncate">{title}</h2>
            <p className="text-xs text-gray-500 mt-1">{filename}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-gray-700 font-sans">{content}</pre>
        </div>
        <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-200 flex-shrink-0">
          <button
            onClick={onClose}
            className="btn btn-secondary"
          >
            {t('common.close')}
          </button>
        </div>
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
  const [showMarketplaceModal, setShowMarketplaceModal] = useState(false)
  const [marketplacePlugins, setMarketplacePlugins] = useState<MarketplacePlugin[]>([])
  const [configPlugin, setConfigPlugin] = useState<string | null>(null)
  const [readmeModal, setReadmeModal] = useState<{
    title: string
    filename: string
    content: string
  } | null>(null)
  const [actionProgress, setActionProgress] = useState<PluginActionProgressState | null>(null)
  
  // 
  const loadingRequestRef = useRef(0)
  const actionProgressEventSourceRef = useRef<EventSource | null>(null)
  const actionProgressSettledRef = useRef(false)

  useEffect(() => {
    const loadInitialData = async () => {
      await Promise.allSettled([
        loadPlugins(),
        loadMarketplacePluginsForUpdates(),
      ])
      setInitialLoading(false)
    }
    loadInitialData()

    return () => {
      if (actionProgressEventSourceRef.current) {
        actionProgressEventSourceRef.current.close()
        actionProgressEventSourceRef.current = null
      }
    }
  }, [])

  const pluginUpdates = useMemo(() => {
    const updates: Record<string, PluginUpdateInfo> = {}

    plugins.forEach((plugin) => {
      const marketplacePlugin = findMarketplacePluginForLocalPlugin(plugin, marketplacePlugins)
      if (!marketplacePlugin) return

      const latestVersion = marketplacePlugin.version || ''
      const currentVersion = plugin.metadata?.version || plugin.version || ''
      const repository = getMarketplaceRepository(marketplacePlugin)

      if (!repository || compareVersions(latestVersion, currentVersion) <= 0) {
        return
      }

      updates[plugin.name] = {
        marketplacePlugin,
        repository,
        currentVersion,
        latestVersion,
      }
    })

    return updates
  }, [plugins, marketplacePlugins])

  const loadPlugins = async () => {
    const currentRequest = ++loadingRequestRef.current
    
    try {
      setLoading(true)
      setLoadError('') // 
      
      const data = await api.getPlugins()
      
      // 
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // 
      if (!Array.isArray(data)) {
        throw new Error('Invalid plugins data received')
      }
      
      console.log('Loaded plugins:', data)
      setPlugins(data)
    } catch (error: any) {
      // 
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load plugins:', error)
      const errorMessage = error.response?.data?.detail || 
                          error.message || 
                          t('plugins.loadPluginsFailed')
      setLoadError(errorMessage)
      toast.error(errorMessage)
    } finally {
      // 
      if (currentRequest === loadingRequestRef.current) {
        setLoading(false)
      }
    }
  }

  const loadMarketplacePluginsForUpdates = async () => {
    try {
      const list = await api.getMarketplacePlugins()
      setMarketplacePlugins(list)
    } catch (error) {
      console.warn('Failed to load marketplace plugins for update check:', error)
    }
  }

  const refreshPluginsAndUpdates = async () => {
    await Promise.allSettled([
      loadPlugins(),
      loadMarketplacePluginsForUpdates(),
    ])
  }

  const closeActionProgressStream = () => {
    if (actionProgressEventSourceRef.current) {
      actionProgressEventSourceRef.current.close()
      actionProgressEventSourceRef.current = null
    }
  }

  const waitForActionProgress = (taskId: string, pluginName: string, action: string) => {
    return new Promise<void>((resolve, reject) => {
      closeActionProgressStream()
      actionProgressSettledRef.current = false

      const eventSource = new EventSource(api.getPluginProgressUrl(taskId))
      actionProgressEventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const nextState: PluginActionProgressState = {
            pluginName,
            action,
            status: data.status || 'running',
            progress: data.progress || 0,
            message: data.message || '',
            logs: Array.isArray(data.logs) ? data.logs : [],
          }
          if (nextState.logs.length > 0 || nextState.status === 'failed' || actionProgress) {
            setActionProgress(nextState)
          }

          if (data.status === 'completed') {
            actionProgressSettledRef.current = true
            closeActionProgressStream()
            resolve()
          } else if (data.status === 'failed') {
            actionProgressSettledRef.current = true
            closeActionProgressStream()
            reject(new Error(data.message || t('plugins.actionFailed')))
          } else if (data.status === 'not_found') {
            actionProgressSettledRef.current = true
            closeActionProgressStream()
            reject(new Error(t('plugins.actionFailed')))
          }
        } catch (err) {
          console.error('Failed to parse plugin action progress:', err)
        }
      }

      eventSource.onerror = () => {
        closeActionProgressStream()
        if (!actionProgressSettledRef.current) {
          reject(new Error('Connection interrupted'))
        }
      }
    })
  }

  const handleAction = async (pluginName: string, action: string) => {
    setActionLoading(pluginName)
    setActionProgress(null)
    try {
      if (['enable', 'load', 'reload'].includes(action)) {
        const response = await api.pluginActionWithProgress(pluginName, action)
        if (response?.task_id) {
          await waitForActionProgress(response.task_id, pluginName, action)
        } else {
          await api.pluginAction(pluginName, action)
        }
      } else {
        await api.pluginAction(pluginName, action)
      }
      await loadPlugins() // Reload plugins after action
      
      // Show success toast based on action
      const actionMessages: Record<string, string> = {
        enable: t('plugins.enableSuccess'),
        disable: t('plugins.disableSuccess'),
        load: t('plugins.enableSuccess'),
        unload: t('plugins.disableSuccess'),
        reload: t('plugins.reloadSuccess'),
      }
      toast.success(actionMessages[action] || t('common.success'))
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || t('plugins.actionFailed')
      toast.error(errorMsg)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (pluginName: string) => {
    if (!confirm(t('plugins.deleteConfirm', { name: pluginName }))) {
      return
    }
    
    setActionLoading(pluginName)
    try {
      await api.deletePlugin(pluginName)
      await loadPlugins() // Reload plugins after deletion
      toast.success(t('plugins.pluginDeleted'))
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || t('plugins.deleteFailed')
      toast.error(errorMsg)
    } finally {
      setActionLoading(null)
    }
  }

  const handleShowReadme = async (plugin: PluginInfo) => {
    setActionLoading(plugin.name)
    try {
      const readme = await api.getPluginReadme(plugin.name)
      setReadmeModal({
        title: getPluginDisplayName(plugin),
        filename: readme.filename,
        content: readme.content,
      })
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('plugins.readmeLoadFailed'))
    } finally {
      setActionLoading(null)
    }
  }

  const handleRefreshMetadata = async (pluginName: string) => {
    setActionLoading(pluginName)
    try {
      await api.refreshPluginMetadata(pluginName)
      await loadPlugins()
      toast.success(t('plugins.metadataRefreshSuccess'))
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('plugins.metadataRefreshFailed'))
    } finally {
      setActionLoading(null)
    }
  }

  const handleUpdatePlugin = async (plugin: PluginInfo, updateInfo: PluginUpdateInfo) => {
    setActionLoading(plugin.name)

    try {
      await api.installPluginFromGitHub(updateInfo.repository)
      if (plugin.enabled) {
        try {
          await api.reloadPlugin(plugin.name)
        } catch (reloadError) {
          console.warn('Plugin updated but reload failed:', reloadError)
        }
      }
      await Promise.allSettled([
        loadPlugins(),
        loadMarketplacePluginsForUpdates(),
      ])
      toast.success(
        t('plugins.updateSuccess', {
          name: getPluginDisplayName(plugin),
          version: updateInfo.latestVersion,
        }),
      )
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('plugins.updateFailed'))
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

  // 
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
            {t('plugins.loadPluginsFailed')}
          </h3>
          <p className="text-sm text-gray-600 mb-4">{loadError}</p>
          <button
            onClick={loadPlugins}
            disabled={loading}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors inline-flex items-center gap-2"
          >
            <RotateCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? t('common.loading') : t('common.retry')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden pt-28 sm:pt-14">
      <div className="fixed left-0 right-0 top-16 z-30 border-b border-gray-100 bg-white/95 px-4 py-4 backdrop-blur md:left-64 sm:px-6 lg:px-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-shrink">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('plugins.title')}</h1>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          <button
            onClick={() => setShowGitHubModal(true)}
            className="btn btn-secondary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <Github className="w-4 h-4" />
            <span className="hidden xl:inline">{t('plugins.githubDirectInstall')}</span>
            <span className="xl:hidden">GitHub</span>
          </button>
          <button
            onClick={() => setShowMarketplaceModal(true)}
            className="btn btn-primary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <Package className="w-4 h-4" />
            <span className="hidden lg:inline">{t('plugins.pluginMarketplace')}</span>
            <span className="lg:hidden">{t('plugins.marketplaceShort')}</span>
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn btn-secondary flex items-center gap-1.5 text-sm px-3 py-2 whitespace-nowrap"
          >
            <Upload className="w-4 h-4" />
            <span className="hidden lg:inline">{t('plugins.uploadPlugin')}</span>
            <span className="lg:hidden">{t('common.upload')}</span>
          </button>
          <button
            onClick={refreshPluginsAndUpdates}
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
          <div className="flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={() => setShowMarketplaceModal(true)}
              className="btn btn-primary flex items-center gap-2"
            >
              <Package className="w-4 h-4" />
              {t('plugins.pluginMarketplace')}
            </button>
            <button
              onClick={() => setShowGitHubModal(true)}
              className="btn btn-secondary flex items-center gap-2"
            >
              <Github className="w-4 h-4" />
              GitHub
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {plugins.map((plugin) => {
            const displayName = getPluginDisplayName(plugin)
            const version = plugin.metadata?.version || plugin.version
            const author = plugin.metadata?.author || plugin.author
            const description = plugin.metadata?.description || plugin.description
            const repositoryUrl = plugin.metadata?.repository || plugin.metadata?.homepage
            const updateInfo = pluginUpdates[plugin.name]

            return (
              <div key={plugin.name} className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col h-full overflow-hidden gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <PluginLogo plugin={plugin} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3 min-w-0">
                      <h3 className="font-bold text-gray-950 text-lg leading-6 truncate">
                        {displayName}
                      </h3>
                      <PluginEnableSwitch
                        enabled={plugin.enabled}
                        disabled={actionLoading === plugin.name || loading}
                        onToggle={() => handleAction(plugin.name, plugin.enabled ? 'disable' : 'enable')}
                      />
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-sm text-gray-500 min-w-0">
                      {version && <span className="whitespace-nowrap">v{version}</span>}
                      {version && author && <span className="text-gray-300">•</span>}
                      {author && <span className="truncate">{author}</span>}
                    </div>
                  </div>
                </div>

                <div className="min-h-[44px]">
                  {description ? (
                    <p
                      className="text-sm leading-5 text-gray-600 line-clamp-2 break-words"
                      title={description}
                    >
                      {description}
                    </p>
                  ) : (
                    <p className="text-sm leading-5 text-gray-400">
                      {t('plugins.noDescription')}
                    </p>
                  )}
                  {(plugin as any).adapter && (
                    <div className="text-xs text-gray-500 mt-2 truncate">
                      {t('plugins.adapter')}: <span className="font-medium">{(plugin as any).adapter}</span>
                    </div>
                  )}
                </div>

                <div className="mt-auto flex flex-wrap items-center gap-2">
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                    {repositoryUrl ? (
                      <a
                        href={repositoryUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={pluginIconButtonSecondary}
                        title={t('plugins.openRepository')}
                      >
                        <Github className="w-4 h-4" />
                      </a>
                    ) : (
                      <button
                        disabled
                        className={pluginIconButtonSecondary}
                        title={t('plugins.repositoryUnavailable')}
                      >
                        <Github className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => handleShowReadme(plugin)}
                      disabled={actionLoading === plugin.name || loading}
                      className={pluginIconButtonSecondary}
                      title={t('plugins.showReadme')}
                    >
                      <BookOpen className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setConfigPlugin(plugin.name)}
                      disabled={loading}
                      className={pluginIconButtonSecondary}
                      title={t('plugins.configure')}
                    >
                      <Settings className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleRefreshMetadata(plugin.name)}
                      disabled={actionLoading === plugin.name || loading}
                      className={pluginIconButtonSecondary}
                      title={t('plugins.refreshMetadata')}
                    >
                      <RotateCw className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="ml-auto flex flex-none flex-wrap items-center justify-end gap-2">
                    {plugin.enabled === true ? (
                      <button
                        onClick={() => handleAction(plugin.name, 'reload')}
                        disabled={actionLoading === plugin.name || loading}
                        className={pluginIconButtonWarning}
                        title={t('plugins.reload')}
                      >
                        <RefreshCcw className="w-4 h-4" />
                      </button>
                    ) : null}
                    {updateInfo ? (
                      <button
                        onClick={() => handleUpdatePlugin(plugin, updateInfo)}
                        disabled={actionLoading === plugin.name || loading}
                        className={pluginIconButtonWarning}
                        title={t('plugins.updateAvailable', {
                          current: updateInfo.currentVersion,
                          latest: updateInfo.latestVersion,
                        })}
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    ) : null}
                    <button
                      onClick={() => handleDelete(plugin.name)}
                      disabled={actionLoading === plugin.name || loading}
                      className={pluginIconButtonDanger}
                      title={t('plugins.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
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

      <PluginMarketplaceModal
        isOpen={showMarketplaceModal}
        onClose={() => setShowMarketplaceModal(false)}
        onInstallSuccess={async () => {
          await Promise.allSettled([
            loadPlugins(),
            loadMarketplacePluginsForUpdates(),
          ])
        }}
      />

      <PluginConfigModal
        pluginName={configPlugin || ''}
        isOpen={configPlugin !== null}
        onClose={() => setConfigPlugin(null)}
        onSave={loadPlugins}
      />

      <PluginReadmeModal
        isOpen={readmeModal !== null}
        title={readmeModal?.title || ''}
        filename={readmeModal?.filename || ''}
        content={readmeModal?.content || ''}
        onClose={() => setReadmeModal(null)}
      />

      <PluginActionProgressModal
        state={actionProgress}
        onClose={() => setActionProgress(null)}
      />
    </div>
  )
}
