import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import {
  Server,
  Download,
  Play,
  Square,
  Terminal,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  RefreshCw,
  Settings,
  Code,
  FolderOpen,
  Plus,
  Trash2,
  Copy,
  Check,
  X,
  ChevronRight,
  Home
} from 'lucide-react'

interface SystemInfo {
  platform: string
  system: string
  release: string
  machine: string
  python: string
  is_admin: boolean
  has_sudo: boolean
  commands: {
    curl: boolean
    wget: boolean
    bash: boolean
    docker: boolean
    powershell: boolean
  }
}

interface NapCatStatus {
  running: boolean
  install_path: string
}

interface InstallProgress {
  job_id: string
  platform: string
  status: string
  percent: number
  message: string
  script: string
  logs: string[]
  created_at: number
}

interface NapCatConfig {
  ok: boolean
  installer_base: string
  bases: string[]
  custom_bases: string[]
  recommended_bases: string[]
}

interface DockerContainerInfo {
  name: string
  image: string
  status: string
  running: boolean
  is_napcat: boolean
}

// 
function PathBrowser({ 
  onSelect, 
  onClose,
  initialPath = ''
}: { 
  onSelect: (path: string) => void
  onClose: () => void
  initialPath?: string
}) {
  const { t } = useTranslation()
  const [currentPath, setCurrentPath] = useState(initialPath || '')
  const [inputPath, setInputPath] = useState(currentPath)
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadDirectory(currentPath)
  }, [])

  useEffect(() => {
    setInputPath(currentPath)
  }, [currentPath])

  const loadDirectory = async (path: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listDirectory({ path })
      if (data.ok) {
        setItems(data.items || [])
        setCurrentPath(data.path)
      } else {
        setError(data.error || t('napcat.permissionDenied'))
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const handleItemClick = (item: any) => {
    if (item.is_dir) {
      loadDirectory(item.path)
    }
  }

  const handleGoUp = () => {
    const parentItem = items.find(item => item.is_parent)
    if (parentItem) {
      loadDirectory(parentItem.path)
    }
  }

  const handleGoHome = () => {
    // Let backend decide root listing by platform to avoid client-side path mismatch.
    loadDirectory('')
  }

  const handleInputConfirm = () => {
    if (inputPath) {
      loadDirectory(inputPath)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">{t('napcat.selectFolder')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-4 border-b border-gray-200">
          <div className="flex gap-2 mb-3">
            <button
              onClick={handleGoUp}
              className="btn btn-secondary btn-sm"
              title={t('napcat.parentFolder')}
              disabled={!items.some(item => item.is_parent)}
            >
              <ChevronRight className="w-4 h-4 rotate-180" />
            </button>
            <button
              onClick={handleGoHome}
              className="btn btn-secondary btn-sm"
              title={t('napcat.home')}
            >
              <Home className="w-4 h-4" />
            </button>
            <button
              onClick={() => loadDirectory(currentPath)}
              className="btn btn-secondary btn-sm"
              title={t('common.refresh')}
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex gap-2">
            <input
              type="text"
              value={inputPath}
              onChange={(e) => setInputPath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleInputConfirm()}
              className="input flex-1 text-sm font-mono"
              placeholder={t('napcat.enterPath')}
            />
            <button onClick={handleInputConfirm} className="btn btn-primary btn-sm">
              {t('common.confirm')}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm mb-3">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              {t('napcat.noItems')}
            </div>
          ) : (
            <div className="space-y-1">
              {items.map((item, index) => (
                <button
                  key={index}
                  onClick={() => handleItemClick(item)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    item.is_dir
                      ? 'hover:bg-primary-50 cursor-pointer'
                      : 'opacity-50 cursor-not-allowed'
                  }`}
                  disabled={!item.is_dir}
                >
                  {item.is_parent ? (
                    <ChevronRight className="w-5 h-5 text-gray-400 rotate-180 flex-shrink-0" />
                  ) : item.is_dir ? (
                    <FolderOpen className="w-5 h-5 text-primary-600 flex-shrink-0" />
                  ) : (
                    <div className="w-5 h-5 flex-shrink-0" />
                  )}
                  <span className="text-sm font-medium text-gray-900 truncate flex-1">
                    {item.name}
                  </span>
                  {item.is_dir && !item.is_parent && (
                    <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-between items-center gap-2 p-4 border-t border-gray-200">
          <div className="text-sm text-gray-600 truncate flex-1">
            {currentPath || t('napcat.selectFolder')}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              {t('common.cancel')}
            </button>
            <button 
              onClick={() => onSelect(currentPath)} 
              className="btn btn-primary"
              disabled={!currentPath}
            >
              {t('napcat.selectThis')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function DockerContainerPicker({
  onSelect,
  onClose
}: {
  onSelect: (containerName: string) => void
  onClose: () => void
}) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [containers, setContainers] = useState<DockerContainerInfo[]>([])

  useEffect(() => {
    const loadContainers = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await api.listNapCatDockerContainers()
        if (data.ok) {
          setContainers(data.containers || [])
        } else {
          setError(data.error || t('common.error'))
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || t('common.error'))
      } finally {
        setLoading(false)
      }
    }
    loadContainers()
  }, [])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">{t('napcat.selectDockerContainer')}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
              {error}
            </div>
          ) : containers.length === 0 ? (
            <div className="text-center py-10 text-gray-500">{t('napcat.noDockerContainers')}</div>
          ) : (
            <div className="space-y-2">
              {containers.map((item) => (
                <button
                  key={item.name}
                  onClick={() => onSelect(item.name)}
                  className="w-full text-left border border-gray-200 rounded-lg p-3 hover:bg-primary-50 hover:border-primary-300 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900">{item.name}</span>
                    <span className={`text-xs px-2 py-1 rounded ${item.running ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
                      {item.running ? t('napcat.running') : t('napcat.stopped')}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600 mt-1 truncate">{item.image}</div>
                  <div className="text-xs text-gray-500 mt-1 truncate">{item.status}</div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-200 flex justify-end">
          <button onClick={onClose} className="btn btn-secondary">
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function NapCatPage() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [status, setStatus] = useState<NapCatStatus | null>(null)
  const [config, setConfig] = useState<NapCatConfig | null>(null)
  const [installing, setInstalling] = useState(false)
  const [installProgress, setInstallProgress] = useState<InstallProgress | null>(null)
  const [runtimeLogs, setRuntimeLogs] = useState<string[]>([])
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showScript, setShowScript] = useState(false)
  const [scriptPreview, setScriptPreview] = useState('')
  const [copiedScript, setCopiedScript] = useState(false)
  const [showPathBrowser, setShowPathBrowser] = useState(false)
  const [showDockerPicker, setShowDockerPicker] = useState(false)
  const [showSudoPasswordDialog, setShowSudoPasswordDialog] = useState(false)
  const [sudoPassword, setSudoPassword] = useState('')
  
  // 
  const [selectedPlatform, setSelectedPlatform] = useState('auto')
  const [useAutoPath, setUseAutoPath] = useState(true)
  const [installPath, setInstallPath] = useState('')
  const [selectedInstallerBase, setSelectedInstallerBase] = useState('')
  const [newCustomBase, setNewCustomBase] = useState('')
  
  // Docker 
  const [dockerQQ, setDockerQQ] = useState('')
  const [dockerMode, setDockerMode] = useState('ws')
  const [dockerProxy, setDockerProxy] = useState('')
  
  const deployLogsEndRef = useRef<HTMLDivElement>(null)
  const runtimeLogsEndRef = useRef<HTMLDivElement>(null)
  const deployLogsContainerRef = useRef<HTMLDivElement>(null)
  const runtimeLogsContainerRef = useRef<HTMLDivElement>(null)
  const progressIntervalRef = useRef<number | null>(null)
  const logsIntervalRef = useRef<number | null>(null)

  useEffect(() => {
    loadData()
    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
      if (logsIntervalRef.current) clearInterval(logsIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    if (autoRefresh && status?.running) {
      startLogsPolling()
    } else {
      if (logsIntervalRef.current) {
        clearInterval(logsIntervalRef.current)
        logsIntervalRef.current = null
      }
    }
  }, [autoRefresh, status?.running])

  useEffect(() => {
    // 
    if (deployLogsContainerRef.current && installProgress?.logs.length) {
      const el = deployLogsContainerRef.current
      el.scrollTop = el.scrollHeight
    }
  }, [installProgress?.logs])

  useEffect(() => {
    // 
    if (autoRefresh && runtimeLogsContainerRef.current && runtimeLogs.length) {
      const el = runtimeLogsContainerRef.current
      el.scrollTop = el.scrollHeight
    }
  }, [runtimeLogs, autoRefresh])

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [sysInfo, napStatus, napConfig] = await Promise.all([
        api.getNapCatSystemInfo(),
        api.getNapCatStatus(),
        api.getNapCatConfig()
      ])
      setSystemInfo(sysInfo)
      setStatus(napStatus)
      setConfig(napConfig)
      setSelectedInstallerBase(napConfig.installer_base || '')
      if (napStatus.install_path) {
        setInstallPath(napStatus.install_path)
        setUseAutoPath(false)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  const startLogsPolling = async () => {
    if (logsIntervalRef.current) return
    
    const fetchLogs = async () => {
      try {
        const data = await api.getNapCatLogs()
        setRuntimeLogs(data.logs || [])
      } catch (err) {
        console.error('Failed to fetch logs:', err)
      }
    }
    
    // Load logs immediately when starting
    await fetchLogs()
    logsIntervalRef.current = window.setInterval(fetchLogs, 2000)
  }

  const handleGenerateScript = async () => {
    setError('')
    setScriptPreview('')
    
    //  Docker 
    if (selectedPlatform === 'docker') {
      if (!dockerQQ || !dockerQQ.match(/^\d+$/)) {
        setError('Docker 模式需要提供有效的 QQ 号')
        return
      }
    }

    try {
      const payload: any = {
        platform: selectedPlatform,
        action: 'script'
      }
      
      // Docker 
      if (selectedPlatform === 'docker') {
        payload.docker = true
        payload.qq = dockerQQ
        payload.mode = dockerMode
        if (dockerProxy) payload.proxy = parseInt(dockerProxy)
      } else {
        //  Docker 
        if (!useAutoPath && installPath) payload.path = installPath
      }
      
      const data = await api.deployNapCat(payload)
      setScriptPreview(data.script || '')
      setShowScript(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.scriptGenerateFailed'))
    }
  }

  const handleInstall = async () => {
    setInstalling(true)
    setError('')
    setSuccess('')
    setInstallProgress(null)

    //  Docker 
    if (selectedPlatform === 'docker') {
      if (!dockerQQ || !dockerQQ.match(/^\d+$/)) {
        setError('Docker 模式需要提供有效的 QQ 号')
        setInstalling(false)
        return
      }
    }

    try {
      const payload: any = {
        platform: selectedPlatform,
        action: 'auto'
      }
      
      // Docker 
      if (selectedPlatform === 'docker') {
        payload.docker = true
        payload.qq = dockerQQ
        payload.mode = dockerMode
        if (dockerProxy) payload.proxy = parseInt(dockerProxy)
      } else {
        //  Docker 
        if (!useAutoPath && installPath) payload.path = installPath
      }

      const data = await api.deployNapCat(payload)

      if (data.downgraded) {
        setScriptPreview(data.script || '')
        setShowScript(true)
        setError(t('napcat.sudoNotAvailable'))
        setInstalling(false)
        return
      }

      if (data.job_id) {
        setInstallProgress({
          job_id: data.job_id,
          platform: data.platform,
          status: 'queued',
          percent: 0,
          message: t('napcat.queued'),
          script: data.script || '',
          logs: [],
          created_at: Date.now()
        })
        startProgressPolling(data.job_id)
      } else {
        setError(t('napcat.noJobId'))
        setInstalling(false)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.installFailed'))
      setInstalling(false)
    }
  }

  const startProgressPolling = (jobId: string) => {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)

    const checkProgress = async () => {
      try {
        const data = await api.getNapCatProgress(jobId)
        setInstallProgress(data)

        if (data.status === 'done') {
          setSuccess(t('napcat.installSuccess'))
          setInstalling(false)
          if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
          // Reload data to get the auto-saved install_path
          await loadData()
          // Show success message with path info if available
          const logs = data.logs || []
          const savedPathLog = logs.find((log: string) => log.includes('[auto_saved] install_path'))
          if (savedPathLog) {
            const pathMatch = savedPathLog.match(/install_path = (.+)/)
            if (pathMatch) {
              setSuccess(`${t('napcat.installSuccess')} - ${t('napcat.pathAutoSaved')}: ${pathMatch[1]}`)
            }
          }
        } else if (data.status === 'error' || data.status === 'canceled') {
          setError(data.message || t('napcat.installFailed'))
          setInstalling(false)
          if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
        }
      } catch (err: any) {
        console.error('Failed to check progress:', err)
      }
    }

    checkProgress()
    progressIntervalRef.current = window.setInterval(checkProgress, 1000)
  }

  const handleCancelInstall = async () => {
    if (!installProgress?.job_id) return

    try {
      await api.cancelNapCatInstall({ job_id: installProgress.job_id })
      setInstalling(false)
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
      setInstallProgress(null)
      setSuccess(t('napcat.installCanceled'))
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.cancelFailed'))
    }
  }

  const handleStart = async () => {
    setError('')
    setSuccess('')
    try {
      await api.startNapCat()
      setSuccess(t('napcat.startSuccess'))
      setTimeout(() => loadData(), 1000)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.startFailed'))
    }
  }

  const handleStop = async () => {
    setError('')
    setSuccess('')
    try {
      await api.stopNapCat()
      setSuccess(t('napcat.stopSuccess'))
      setTimeout(() => loadData(), 1000)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.stopFailed'))
    }
  }

  const handleOpenWebUI = async () => {
    try {
      const data = await api.getNapCatWebUIInfo()
      if (data.ok && data.url) {
        window.open(data.url, '_blank')
      } else {
        setError(data.error || t('napcat.webUINotAvailable'))
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.webUIFailed'))
    }
  }

  const handlePathSelect = (path: string) => {
    setInstallPath(path)
    setShowPathBrowser(false)
  }

  const handleDockerContainerSelect = (containerName: string) => {
    setInstallPath(`docker://${containerName}`)
    setShowDockerPicker(false)
  }

  const handleSaveInstallerBase = async () => {
    try {
      await api.updateNapCatConfig({ installer_base: selectedInstallerBase })
      setSuccess(t('napcat.configSaved'))
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.configSaveFailed'))
    }
  }

  const handleAddCustomBase = async () => {
    if (!newCustomBase.trim()) return
    try {
      await api.updateNapCatConfig({ installer_base: newCustomBase.trim() })
      setNewCustomBase('')
      setSuccess(t('napcat.baseAdded'))
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.baseAddFailed'))
    }
  }

  const handleRemoveBase = async (base: string) => {
    try {
      await api.updateNapCatConfig({ remove_base: base })
      setSuccess(t('napcat.baseRemoved'))
      await loadData()
    } catch (err: any) {
      setError(err.response?.data?.detail || t('napcat.baseRemoveFailed'))
    }
  }

  const copyScript = () => {
    navigator.clipboard.writeText(scriptPreview)
    setCopiedScript(true)
    setTimeout(() => setCopiedScript(false), 2000)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-12 h-12 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('napcat.title')}</h1>
          <p className="text-gray-500 mt-1">{t('napcat.description')}</p>
        </div>
        <button onClick={loadData} className="btn btn-secondary flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          {t('common.refresh')}
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError('')} className="text-red-700 hover:text-red-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 flex-shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess('')} className="text-green-700 hover:text-green-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* System Information */}
          {systemInfo && (
            <div className="card">
              <div className="flex items-center gap-3 mb-4">
                <Info className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">{t('napcat.systemInfo')}</h2>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.platform')}</span>
                  <span className="font-medium">{systemInfo.platform}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.system')}</span>
                  <span className="font-medium">{systemInfo.system} {systemInfo.release}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.machine')}</span>
                  <span className="font-medium">{systemInfo.machine}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Python</span>
                  <span className="font-medium">{systemInfo.python}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.isAdmin')}</span>
                  <span className={`font-medium ${systemInfo.is_admin ? 'text-green-600' : 'text-orange-600'}`}>
                    {systemInfo.is_admin ? t('common.yes') : t('common.no')}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.hasSudo')}</span>
                  <span className={`font-medium ${systemInfo.has_sudo ? 'text-green-600' : 'text-orange-600'}`}>
                    {systemInfo.has_sudo ? t('common.yes') : t('common.no')}
                  </span>
                </div>
              </div>
              
              <div className="mt-4 pt-4 border-t border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('napcat.availableCommands')}</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(systemInfo.commands).map(([cmd, available]) => (
                    <span
                      key={cmd}
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        available ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {cmd}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Installer Configuration */}
          {config && (
            <div className="card">
              <div className="flex items-center gap-3 mb-4">
                <Settings className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">{t('napcat.installerConfig')}</h2>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('napcat.currentInstallerBase')}
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={selectedInstallerBase}
                      onChange={(e) => setSelectedInstallerBase(e.target.value)}
                      className="input flex-1 text-sm"
                    >
                      <option value="">{t('napcat.useDefault')}</option>
                      <optgroup label={t('napcat.recommended')}>
                        {config.recommended_bases.map((base) => (
                          <option key={base} value={base}>
                            {base}
                          </option>
                        ))}
                      </optgroup>
                      {config.custom_bases.length > 0 && (
                        <optgroup label={t('napcat.custom')}>
                          {config.custom_bases.map((base) => (
                            <option key={base} value={base}>
                              {base}
                            </option>
                          ))}
                        </optgroup>
                      )}
                    </select>
                    <button onClick={handleSaveInstallerBase} className="btn btn-primary btn-sm">
                      {t('common.save')}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('napcat.addCustomBase')}
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCustomBase}
                      onChange={(e) => setNewCustomBase(e.target.value)}
                      placeholder={t('napcat.enterCustomBase')}
                      className="input flex-1 text-sm"
                    />
                    <button
                      onClick={handleAddCustomBase}
                      disabled={!newCustomBase.trim()}
                      className="btn btn-primary btn-sm"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {config.custom_bases.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {t('napcat.customBases')}
                    </label>
                    <div className="space-y-2">
                      {config.custom_bases.map((base) => (
                        <div key={base} className="flex items-center justify-between bg-gray-50 p-2 rounded-lg">
                          <span className="text-xs font-mono text-gray-700 truncate flex-1">{base}</span>
                          <button
                            onClick={() => handleRemoveBase(base)}
                            className="ml-2 text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Manual Path Setup - 显示当未安装或需要指定路径时 */}
          {!status?.install_path && (
            <div className="card">
              <div className="flex items-center gap-3 mb-4">
                <FolderOpen className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">{t('napcat.manualPath')}</h2>
              </div>

              <div className="space-y-4">
                <p className="text-sm text-gray-600">{t('napcat.manualPathDesc')}</p>
                
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={installPath}
                    onChange={(e) => setInstallPath(e.target.value)}
                    placeholder={t('napcat.enterPath')}
                    className="input flex-1 text-sm font-mono"
                  />
                  <button
                    onClick={() => setShowPathBrowser(true)}
                    className="btn btn-secondary btn-sm"
                    title={t('napcat.selectFolder')}
                  >
                    <FolderOpen className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setShowDockerPicker(true)}
                    className="btn btn-secondary btn-sm"
                    title={t('napcat.selectDockerContainer')}
                  >
                    <Server className="w-4 h-4" />
                  </button>
                </div>

                <button
                  onClick={async () => {
                    if (!installPath) {
                      setError(t('napcat.pathNotSet'))
                      return
                    }
                    try {
                      await api.setNapCatPath({ path: installPath })
                      setSuccess(t('napcat.pathSetSuccess'))
                      await loadData()
                    } catch (err: any) {
                      setError(err.response?.data?.detail || t('napcat.pathSetFailed'))
                    }
                  }}
                  className="btn btn-primary w-full"
                  disabled={!installPath}
                >
                  {t('napcat.setInstallPath')}
                </button>
              </div>
            </div>
          )}

          {/* Docker Sudo Password Settings */}
          {systemInfo?.commands.docker && (
            <div className="card">
              <div className="flex items-center gap-3 mb-4">
                <Settings className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">{t('napcat.dockerSudoSettings')}</h2>
              </div>
              <div className="space-y-3">
                <p className="text-sm text-gray-600">{t('napcat.dockerSudoDesc')}</p>
                <button
                  onClick={() => setShowSudoPasswordDialog(true)}
                  className="btn btn-secondary w-full"
                >
                  {t('napcat.configureSudoPassword')}
                </button>
              </div>
            </div>
          )}

          {/* Status and Control */}
          {status?.install_path && (
            <div className="card">
              <div className="flex items-center gap-3 mb-4">
                <Server className="w-5 h-5 text-primary-600" />
                <h2 className="text-lg font-semibold text-gray-900">{t('napcat.statusControl')}</h2>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">{t('napcat.status')}</span>
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full ${status.running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}
                    ></div>
                    <span className={`font-medium ${status.running ? 'text-green-600' : 'text-gray-500'}`}>
                      {status.running ? t('napcat.running') : t('napcat.stopped')}
                    </span>
                  </div>
                </div>

                <div className="text-sm">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-gray-600">{t('napcat.installPath')}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          const currentPath = status.install_path || ''
                          setInstallPath(currentPath)
                          setShowPathBrowser(true)
                        }}
                        className="btn btn-secondary btn-xs flex items-center gap-1"
                        title={t('napcat.selectFolder')}
                      >
                        <FolderOpen className="w-3 h-3" />
                        <span className="hidden sm:inline">{t('napcat.selectFolder')}</span>
                      </button>
                      <button
                        onClick={() => {
                          const currentPath = status.install_path || ''
                          setInstallPath(currentPath)
                          setShowDockerPicker(true)
                        }}
                        className="btn btn-secondary btn-xs flex items-center gap-1"
                        title={t('napcat.selectDockerContainer')}
                      >
                        <Server className="w-3 h-3" />
                        <span className="hidden sm:inline">{t('napcat.selectDockerContainer')}</span>
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 bg-gray-50 p-2 rounded text-xs font-mono break-all">{status.install_path}</div>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-3 border-t">
                  {!status.running ? (
                    <button
                      onClick={handleStart}
                      className="btn btn-primary btn-sm flex items-center justify-center gap-1"
                    >
                      <Play className="w-4 h-4" />
                      <span className="hidden sm:inline">{t('napcat.start')}</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleStop}
                      className="btn btn-secondary btn-sm flex items-center justify-center gap-1"
                    >
                      <Square className="w-4 h-4" />
                      <span className="hidden sm:inline">{t('napcat.stop')}</span>
                    </button>
                  )}

                  <button
                    onClick={handleOpenWebUI}
                    className="btn btn-secondary btn-sm flex items-center justify-center gap-1"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span className="hidden sm:inline">WebUI</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column -  flex  */}
        <div className="space-y-6 flex flex-col">
          {/* Installation Configuration */}
          <div className="card">
            <div className="flex items-center gap-3 mb-4">
              <Download className="w-5 h-5 text-primary-600" />
              <h2 className="text-lg font-semibold text-gray-900">{t('napcat.installConfig')}</h2>
            </div>

            <div className="space-y-4">
              {/* Platform Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('napcat.selectPlatform')}
                </label>
                <select
                  value={selectedPlatform}
                  onChange={(e) => setSelectedPlatform(e.target.value)}
                  className="input text-sm"
                  disabled={installing}
                >
                  <option value="auto">{t('napcat.autoDetect')}</option>
                  <option value="windows">Windows</option>
                  <option value="linux">Linux</option>
                  <option value="macos">macOS</option>
                  <option value="docker">Docker</option>
                  <option value="termux">Termux</option>
                </select>
              </div>

              {/* Docker  */}
              {selectedPlatform === 'docker' && (
                <div className="space-y-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-blue-800 text-sm font-medium">
                    <Info className="w-4 h-4" />
                    <span>{t('napcat.dockerModeConfig')}</span>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('napcat.dockerQQ')} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={dockerQQ}
                      onChange={(e) => setDockerQQ(e.target.value)}
                      placeholder={t('napcat.dockerQQPlaceholder')}
                      className="input text-sm w-full"
                      disabled={installing}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('napcat.dockerMode')}
                    </label>
                    <select
                      value={dockerMode}
                      onChange={(e) => setDockerMode(e.target.value)}
                      className="input text-sm w-full"
                      disabled={installing}
                    >
                      <option value="ws">WebSocket</option>
                      <option value="reverse_ws">Reverse WebSocket</option>
                      <option value="reverse_http">Reverse HTTP</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t('napcat.dockerProxy')} ({t('napcat.optional')})
                    </label>
                    <select
                      value={dockerProxy}
                      onChange={(e) => setDockerProxy(e.target.value)}
                      className="input text-sm w-full"
                      disabled={installing}
                    >
                      <option value="">不使用代理</option>
                      <option value="1">代理 1</option>
                      <option value="2">代理 2</option>
                      <option value="3">代理 3</option>
                      <option value="4">代理 4</option>
                      <option value="5">代理 5</option>
                      <option value="6">代理 6</option>
                      <option value="7">代理 7</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Install Path -  Docker  */}
              {selectedPlatform !== 'docker' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('napcat.installPath')}
                  </label>
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={useAutoPath}
                          onChange={() => setUseAutoPath(true)}
                          disabled={installing}
                          className="text-primary-600"
                        />
                        <span className="text-sm">{t('napcat.pathAutoDetect')}</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={!useAutoPath}
                          onChange={() => setUseAutoPath(false)}
                          disabled={installing}
                          className="text-primary-600"
                        />
                        <span className="text-sm">{t('napcat.pathManual')}</span>
                      </label>
                    </div>
                    
                    {!useAutoPath && (
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={installPath}
                          onChange={(e) => setInstallPath(e.target.value)}
                          placeholder={t('napcat.installPathPlaceholder')}
                          className="input flex-1 text-sm font-mono"
                          disabled={installing}
                        />
                        <button
                          onClick={() => setShowPathBrowser(true)}
                          className="btn btn-secondary btn-sm"
                          disabled={installing}
                        >
                          <FolderOpen className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-3 pt-4 border-t border-gray-200">
                <button
                  onClick={handleGenerateScript}
                  className="btn btn-secondary flex items-center justify-center gap-2"
                  disabled={installing}
                >
                  <Code className="w-4 h-4" />
                  {t('napcat.generateScript')}
                </button>
                <button
                  onClick={handleInstall}
                  className="btn btn-primary flex items-center justify-center gap-2"
                  disabled={installing}
                >
                  <Download className="w-4 h-4" />
                  {t('napcat.startInstall')}
                </button>
              </div>
            </div>
          </div>

          {/* Deploy Output -  */}
          <div className="card flex-1 flex flex-col">
            <div className="flex items-center gap-3 mb-4">
              <Terminal className="w-5 h-5 text-primary-600" />
              <h2 className="text-lg font-semibold text-gray-900">{t('napcat.deployOutput')}</h2>
            </div>

            {installing && installProgress ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">{installProgress.message}</span>
                  <span className="text-sm font-medium text-primary-600">{installProgress.percent}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${installProgress.percent}%` }}
                  ></div>
                </div>

                <div
                  ref={deployLogsContainerRef}
                  className="bg-gray-900 rounded-lg p-3 h-[400px] max-h-[400px] overflow-y-auto overflow-x-hidden"
                >
                  {installProgress.logs.length > 0 ? (
                    <div className="space-y-1">
                      {installProgress.logs.map((log, i) => (
                        <div key={i} className="text-xs text-green-400 font-mono whitespace-pre-wrap break-all">
                          {log}
                        </div>
                      ))}
                      <div ref={deployLogsEndRef} aria-hidden />
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <p className="text-sm text-gray-400">{t('napcat.waitingForLogs')}</p>
                    </div>
                  )}
                </div>

                <button
                  onClick={handleCancelInstall}
                  className="btn btn-secondary w-full"
                >
                  {t('common.cancel')}
                </button>
              </div>
            ) : (
              <div className="bg-gray-50 rounded-lg p-8 text-center flex items-center justify-center h-[400px]">
                <div className="flex flex-col items-center">
                  <Terminal className="w-12 h-12 text-gray-400 mb-3" />
                  <p className="text-sm text-gray-500">{t('napcat.noDeployOutput')}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Runtime Logs -  */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Terminal className="w-5 h-5 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">{t('napcat.runtimeLogs')}</h2>
            {status?.running && autoRefresh && (
              <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">
                {t('napcat.autoRefreshing')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {status?.running && (
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <span className="text-sm text-gray-600">{t('common.autoRefresh')}</span>
                <div className="relative inline-flex items-center">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={async (e) => {
                      const newValue = e.target.checked
                      setAutoRefresh(newValue)
                      if (newValue) {
                        // When enabling, reload all logs and start polling
                        setRuntimeLogs([])
                        await startLogsPolling()
                      } else {
                        // When disabling, stop polling but keep current logs
                        if (logsIntervalRef.current) {
                          clearInterval(logsIntervalRef.current)
                          logsIntervalRef.current = null
                        }
                      }
                    }}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </div>
              </label>
            )}
          </div>
        </div>

        <div
          ref={runtimeLogsContainerRef}
          className="bg-gray-900 rounded-lg p-3 h-[52vh] min-h-[360px] max-h-[70vh] overflow-y-auto overflow-x-hidden"
        >
          {!status?.running ? (
            <div className="text-center py-12">
              <Terminal className="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-400">{t('napcat.notRunning')}</p>
            </div>
          ) : runtimeLogs.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-gray-400">{t('napcat.noLogs')}</p>
            </div>
          ) : (
            <div className="space-y-1">
              {runtimeLogs.map((log, i) => (
                <div key={i} className="text-xs text-green-400 font-mono whitespace-pre-wrap break-all">
                  {log}
                </div>
              ))}
              <div ref={runtimeLogsEndRef} aria-hidden />
            </div>
          )}
        </div>
      </div>

      {/* Script Preview Modal */}
      {showScript && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">{t('napcat.installScript')}</h3>
              <button
                onClick={() => setShowScript(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto text-sm font-mono">
                {scriptPreview}
              </pre>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t border-gray-200">
              <button
                onClick={copyScript}
                className="btn btn-secondary flex items-center gap-2"
              >
                {copiedScript ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copiedScript ? t('common.copied') : t('common.copy')}
              </button>
              <button onClick={() => setShowScript(false)} className="btn btn-primary">
                {t('common.close')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Path Browser Modal */}
      {showPathBrowser && (
        <PathBrowser
          onSelect={handlePathSelect}
          onClose={() => setShowPathBrowser(false)}
          initialPath={installPath}
        />
      )}

      {showDockerPicker && (
        <DockerContainerPicker
          onSelect={handleDockerContainerSelect}
          onClose={() => setShowDockerPicker(false)}
        />
      )}

      {/* Sudo Password Dialog */}
      {showSudoPasswordDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">{t('napcat.configureSudoPassword')}</h3>
              <button onClick={() => setShowSudoPasswordDialog(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-4 space-y-4">
              <p className="text-sm text-gray-600">{t('napcat.sudoPasswordDesc')}</p>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('napcat.sudoPassword')}
                </label>
                <input
                  type="password"
                  value={sudoPassword}
                  onChange={(e) => setSudoPassword(e.target.value)}
                  placeholder={t('napcat.enterSudoPassword')}
                  className="input w-full"
                  autoComplete="new-password"
                />
                <p className="text-xs text-gray-500 mt-1">{t('napcat.sudoPasswordNote')}</p>
              </div>
            </div>

            <div className="flex justify-end gap-2 p-4 border-t border-gray-200">
              <button
                onClick={async () => {
                  try {
                    await api.setNapCatSudoPassword({ password: '' })
                    setSuccess(t('napcat.sudoPasswordCleared'))
                    setSudoPassword('')
                    setShowSudoPasswordDialog(false)
                  } catch (err: any) {
                    setError(err.response?.data?.detail || t('napcat.sudoPasswordClearFailed'))
                  }
                }}
                className="btn btn-secondary"
              >
                {t('napcat.clearPassword')}
              </button>
              <button
                onClick={async () => {
                  try {
                    await api.setNapCatSudoPassword({ password: sudoPassword })
                    setSuccess(t('napcat.sudoPasswordSet'))
                    setSudoPassword('')
                    setShowSudoPasswordDialog(false)
                  } catch (err: any) {
                    setError(err.response?.data?.detail || t('napcat.sudoPasswordSetFailed'))
                  }
                }}
                className="btn btn-primary"
              >
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}