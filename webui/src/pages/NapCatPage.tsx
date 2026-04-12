import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  Globe,
  Loader2,
  Play,
  QrCode,
  RefreshCw,
  Settings,
  Square,
  Terminal,
  X,
  type LucideIcon,
} from 'lucide-react'
import { api } from '@/utils/api'
import { useToast } from '@/components/Toast'

type NapCatTab = 'webui' | 'logs' | 'install' | 'config' | 'tools'

interface NapCatWebUIInfo {
  ok: boolean
  url: string
  port?: number
  token?: string
  source?: string
}

interface NapCatStatus {
  installed: boolean
  running: boolean
  platform: string
  install_path: string
  workdir: string
  entry: string
  webui?: NapCatWebUIInfo
}

interface NapCatLoginStatus {
  napcat?: NapCatStatus
  qrcode?: {
    exists?: boolean
    version?: string
    mtime?: number
    size?: number
  }
  webui?: NapCatWebUIInfo
  onebot?: {
    available?: boolean
    running?: boolean
    connected?: boolean
    connection_type?: string
    self_id?: string
    self_nickname?: string
    login_info?: any
    error?: string
  }
}

interface NapCatJob {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'error'
  percent: number
  message: string
  platform: string
  logs: string[]
  created_at: number
}

const tabs: Array<{ key: NapCatTab; label: string; icon: LucideIcon }> = [
  { key: 'webui', label: 'WebUI', icon: Globe },
  { key: 'logs', label: '运行日志', icon: Terminal },
  { key: 'install', label: '安装应用', icon: Download },
  { key: 'config', label: '配置中心', icon: Settings },
  { key: 'tools', label: '状态调试', icon: Terminal },
]

export default function NapCatPage() {
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<NapCatTab>('webui')
  const [status, setStatus] = useState<NapCatStatus | null>(null)
  const [webui, setWebui] = useState<NapCatWebUIInfo | null>(null)
  const [runtimeLogs, setRuntimeLogs] = useState<string[]>([])
  const [job, setJob] = useState<NapCatJob | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState('')
  const [error, setError] = useState('')
  const [qrcodeUrl, setQrcodeUrl] = useState('')
  const [qrcodeError, setQrcodeError] = useState('')
  const [qrcodeLoading, setQrcodeLoading] = useState(false)
  const [qrcodeVersion, setQrcodeVersion] = useState('')
  const [configDraft, setConfigDraft] = useState<any>({ webui: {}, napcat: {}, onebot: {} })
  const [configMeta, setConfigMeta] = useState<any>(null)
  const [configLoading, setConfigLoading] = useState(false)
  const [configSaving, setConfigSaving] = useState('')
  const [configError, setConfigError] = useState('')
  const [loginStatus, setLoginStatus] = useState<NapCatLoginStatus | null>(null)
  const [loginStatusLoading, setLoginStatusLoading] = useState(false)
  const [debugAction, setDebugAction] = useState('get_login_info')
  const [debugParamsText, setDebugParamsText] = useState('{}')
  const [debugResultText, setDebugResultText] = useState('')
  const [debugLoading, setDebugLoading] = useState(false)
  const [debugError, setDebugError] = useState('')
  const progressTimer = useRef<number | null>(null)
  const logsTimer = useRef<number | null>(null)
  const qrcodeTimer = useRef<number | null>(null)
  const logsRef = useRef<HTMLDivElement>(null)
  const installLogsRef = useRef<HTMLDivElement>(null)
  const qrcodeObjectUrlRef = useRef('')

  const loadStatus = async () => {
    const data = await api.getNapCatStatus()
    setStatus(data)
    if (data.webui?.ok) {
      setWebui(data.webui)
    } else if (!data.running) {
      setWebui(null)
    }
  }

  const loadAll = async () => {
    setLoading(true)
    setError('')
    try {
      await Promise.all([loadStatus(), loadLogs()])
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '加载 NapCat 状态失败')
    } finally {
      setLoading(false)
    }
  }

  const loadLogs = async () => {
    const data = await api.getNapCatLogs()
    setRuntimeLogs(data.logs || [])
  }

  const loadWebUI = async () => {
    try {
      const data = await api.getNapCatWebUIInfo()
      setWebui(data.ok ? data : null)
    } catch (err: any) {
      setWebui(null)
      toast.error(err.response?.data?.detail || 'NapCat WebUI 还没准备好')
    }
  }

  useEffect(() => {
    void loadAll()

    logsTimer.current = window.setInterval(() => {
      void loadStatus().catch(() => undefined)
      void loadLogs().catch(() => undefined)
    }, 2500)

    return () => {
      if (logsTimer.current) window.clearInterval(logsTimer.current)
      if (progressTimer.current) window.clearInterval(progressTimer.current)
      if (qrcodeTimer.current) window.clearInterval(qrcodeTimer.current)
      if (qrcodeObjectUrlRef.current) URL.revokeObjectURL(qrcodeObjectUrlRef.current)
    }
  }, [])

  useEffect(() => {
    if (!qrcodeUrl) {
      if (qrcodeTimer.current) {
        window.clearInterval(qrcodeTimer.current)
        qrcodeTimer.current = null
      }
      return
    }

    qrcodeTimer.current = window.setInterval(() => {
      void refreshQRCodeIfChanged()
    }, 2500)

    return () => {
      if (qrcodeTimer.current) {
        window.clearInterval(qrcodeTimer.current)
        qrcodeTimer.current = null
      }
    }
  }, [qrcodeUrl, qrcodeVersion])

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight
  }, [runtimeLogs])

  useEffect(() => {
    if (installLogsRef.current) installLogsRef.current.scrollTop = installLogsRef.current.scrollHeight
  }, [job?.logs])

  useEffect(() => {
    if (activeTab === 'config') {
      void loadNapCatConfig()
    }
    if (activeTab === 'tools') {
      void loadNapCatLoginStatus()
    }
  }, [activeTab])

  const pollJob = (jobId: string) => {
    if (progressTimer.current) window.clearInterval(progressTimer.current)

    const tick = async () => {
      const data = await api.getNapCatProgress(jobId)
      setJob(data)
      if (['done', 'error'].includes(data.status)) {
        if (progressTimer.current) {
          window.clearInterval(progressTimer.current)
          progressTimer.current = null
        }
        setActionLoading('')
        await loadStatus()
      }
    }

    void tick()
    progressTimer.current = window.setInterval(() => {
      void tick().catch((err) => toast.error(err.response?.data?.detail || '安装进度读取失败'))
    }, 1000)
  }

  const handleInstall = async () => {
    setError('')
    setActionLoading('install')
    setActiveTab('install')
    try {
      const data = await api.installNapCat()
      setJob(data)
      toast.info('NapCat 安装任务已启动')
      pollJob(data.job_id)
    } catch (err: any) {
      setActionLoading('')
      toast.error(err.response?.data?.detail || '启动安装任务失败')
    }
  }

  const handleStart = async () => {
    setError('')
    setActionLoading('start')
    try {
      await api.startNapCat()
      await loadAll()
      await loadWebUI()
      toast.success('NapCat 已启动')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '启动 NapCat 失败')
    } finally {
      setActionLoading('')
    }
  }

  const handleStop = async () => {
    setError('')
    setActionLoading('stop')
    try {
      await api.stopNapCat()
      setWebui(null)
      await loadAll()
      toast.success('NapCat 已停止')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '停止 NapCat 失败')
    } finally {
      setActionLoading('')
    }
  }

  const closeQRCode = () => {
    if (qrcodeObjectUrlRef.current) URL.revokeObjectURL(qrcodeObjectUrlRef.current)
    qrcodeObjectUrlRef.current = ''
    setQrcodeUrl('')
    setQrcodeError('')
    setQrcodeVersion('')
  }

  const loadQRCodeImage = async (nextVersion?: string) => {
    const blob = await api.getNapCatQRCode()
    if (qrcodeObjectUrlRef.current) URL.revokeObjectURL(qrcodeObjectUrlRef.current)
    const objectUrl = URL.createObjectURL(blob)
    qrcodeObjectUrlRef.current = objectUrl
    setQrcodeUrl(objectUrl)
    if (nextVersion) setQrcodeVersion(nextVersion)
  }

  const refreshQRCodeIfChanged = async () => {
    try {
      const info = await api.getNapCatQRCodeInfo()
      if (!info.exists) {
        setQrcodeError('二维码已过期或暂未生成，请等待 NapCat 刷新')
        return
      }
      if (!qrcodeVersion || info.version !== qrcodeVersion) {
        await loadQRCodeImage(info.version)
        setQrcodeError('')
      }
    } catch (err: any) {
      setQrcodeError(err.response?.data?.detail || '二维码刷新失败')
    }
  }

  const handleShowQRCode = async () => {
    setQrcodeLoading(true)
    setQrcodeError('')
    try {
      const info = await api.getNapCatQRCodeInfo()
      if (!info.exists) {
        throw new Error('二维码还没生成，请先启动 NapCat')
      }
      await loadQRCodeImage(info.version)
    } catch (err: any) {
      setQrcodeError(err.response?.data?.detail || '二维码还没生成，请先启动 NapCat')
    } finally {
      setQrcodeLoading(false)
    }
  }

  const formatJson = (value: any) => JSON.stringify(value ?? {}, null, 2)

  const toBool = (value: any) => value === true || value === 'true'
  const toNumber = (value: any, fallback = 0) => {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
  }
  const toLines = (value: any) => Array.isArray(value) ? value.join('\n') : ''
  const fromLines = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)

  const updateConfigValue = (section: 'webui' | 'napcat' | 'onebot', path: Array<string | number>, value: any) => {
    setConfigDraft((current: any) => {
      const next = structuredClone(current || {})
      if (!next[section]) next[section] = {}
      let cursor = next[section]
      for (let index = 0; index < path.length - 1; index += 1) {
        const key = path[index]
        const nextKey = path[index + 1]
        if (cursor[key] === undefined || cursor[key] === null) {
          cursor[key] = typeof nextKey === 'number' ? [] : {}
        }
        cursor = cursor[key]
      }
      cursor[path[path.length - 1]] = value
      return next
    })
  }

  const getOneBotNetwork = () => configDraft.onebot?.network || {}
  const getOneBotMode = () => {
    const network = getOneBotNetwork()
    if ((network.websocketServers || []).length) return 'websocketServer'
    if ((network.websocketClients || []).length) return 'websocketClient'
    if ((network.httpServers || []).length) return 'httpServer'
    return 'disabled'
  }

  const firstEndpoint = (key: string) => (getOneBotNetwork()[key] || [])[0] || {}

  const setOneBotMode = (mode: string) => {
    setConfigDraft((current: any) => {
      const next = structuredClone(current || {})
      const onebot = next.onebot || {}
      const network = onebot.network || {}
      const token = (
        network.websocketServers?.[0]?.token ||
        network.websocketClients?.[0]?.token ||
        network.httpServers?.[0]?.token ||
        ''
      )
      network.httpServers = []
      network.websocketServers = []
      network.websocketClients = []
      if (mode === 'websocketServer') {
        network.websocketServers = [{
          enable: true,
          name: 'WebSocket',
          host: '127.0.0.1',
          port: 3001,
          reportSelfMessage: false,
          enableForcePushEvent: true,
          messagePostFormat: 'array',
          token,
          debug: false,
          heartInterval: 30000,
        }]
      } else if (mode === 'websocketClient') {
        network.websocketClients = [{
          enable: true,
          name: 'WebSocket Client',
          url: 'ws://127.0.0.1:8080/onebot/v11/ws',
          messagePostFormat: 'array',
          reportSelfMessage: false,
          reconnectInterval: 5000,
          token,
          debug: false,
          heartInterval: 30000,
        }]
      } else if (mode === 'httpServer') {
        network.httpServers = [{
          enable: true,
          name: 'HTTP',
          host: '127.0.0.1',
          port: 3000,
          enableCors: true,
          enableWebsocket: false,
          messagePostFormat: 'array',
          token,
          debug: false,
        }]
      }
      onebot.network = network
      next.onebot = onebot
      return next
    })
  }

  const updateOneBotEndpoint = (key: 'websocketServers' | 'websocketClients' | 'httpServers', field: string, value: any) => {
    setConfigDraft((current: any) => {
      const next = structuredClone(current || {})
      if (!next.onebot) next.onebot = {}
      if (!next.onebot.network) next.onebot.network = {}
      const list = [...(next.onebot.network[key] || [])]
      list[0] = { ...(list[0] || {}), [field]: value }
      next.onebot.network[key] = list
      return next
    })
  }

  const loadNapCatConfig = async () => {
    setConfigLoading(true)
    setConfigError('')
    try {
      const data = await api.getNapCatConfig()
      setConfigMeta(data)
      setConfigDraft({
        webui: data.webui || {},
        napcat: data.napcat || {},
        onebot: data.onebot || {},
      })
    } catch (err: any) {
      setConfigError(err.response?.data?.detail || '读取 NapCat 配置失败')
    } finally {
      setConfigLoading(false)
    }
  }

  const parseConfigText = () => ({
    webui: configDraft.webui || {},
    napcat: configDraft.napcat || {},
    onebot: configDraft.onebot || {},
  })

  const handleSaveNapCatConfig = async () => {
    setConfigSaving('save')
    setConfigError('')
    try {
      const payload = parseConfigText()
      const data = await api.saveNapCatConfig(payload)
      setConfigMeta(data)
      toast.success('配置已保存，部分配置需要重启 NapCat 后生效')
    } catch (err: any) {
      toast.error(err instanceof SyntaxError ? 'JSON 格式不正确，请检查配置内容' : (err.response?.data?.detail || '保存 NapCat 配置失败'))
    } finally {
      setConfigSaving('')
    }
  }

  const handleApplyFrameworkOneBot = async () => {
    setConfigSaving('onebot')
    setConfigError('')
    try {
      const data = await api.applyFrameworkOneBotToNapCat()
      setConfigDraft((current: any) => ({ ...(current || {}), onebot: data.onebot || {} }))
      toast.success(data.message || 'OneBot 配置已写入，重启 NapCat 后生效')
      await loadNapCatConfig()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || '一键写入 OneBot 配置失败')
    } finally {
      setConfigSaving('')
    }
  }

  const loadNapCatLoginStatus = async () => {
    setLoginStatusLoading(true)
    try {
      const data = await api.getNapCatLoginStatus()
      setLoginStatus(data)
    } catch (err: any) {
      setLoginStatus({
        onebot: {
          available: false,
          running: false,
          connected: false,
          error: err.response?.data?.detail || '读取登录状态失败',
        },
      })
    } finally {
      setLoginStatusLoading(false)
    }
  }

  const handleDebugOneBotApi = async () => {
    setDebugLoading(true)
    setDebugError('')
    try {
      const params = JSON.parse(debugParamsText || '{}')
      if (!params || Array.isArray(params) || typeof params !== 'object') {
        throw new Error('参数必须是 JSON 对象，比如 {}')
      }
      const data = await api.callNapCatOneBotApi({ action: debugAction, params, timeout: 20 })
      setDebugResultText(formatJson(data))
      await loadNapCatLoginStatus()
    } catch (err: any) {
      const message = err instanceof SyntaxError
        ? '参数 JSON 格式不正确'
        : (err.response?.data?.detail || err.message || '调用 OneBot API 失败')
      setDebugError(message)
      setDebugResultText('')
    } finally {
      setDebugLoading(false)
    }
  }

  const openWebUI = () => {
    if (webui?.url) window.open(webui.url, '_blank')
  }

  const isInstalling = actionLoading === 'install' || job?.status === 'queued' || job?.status === 'running'

  const StatusPill = () => {
    if (!status?.installed) {
      return <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-500">未安装</span>
    }
    if (status.running) {
      return <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">运行中</span>
    }
    return <span className="rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700">已安装，未启动</span>
  }

  const renderWebUI = () => {
    if (loading) {
      return (
        <div className="flex h-full items-center justify-center text-slate-500">
          <Loader2 className="mr-3 h-5 w-5 animate-spin" />
          正在读取 NapCat 状态
        </div>
      )
    }

    if (!status?.installed) {
      return (
        <div className="flex h-full items-center justify-center px-6">
          <div className="max-w-md text-center">
            <Download className="mx-auto mb-4 h-12 w-12 text-slate-300" />
            <div className="text-xl font-semibold text-slate-900">还没有安装 NapCat</div>
            <div className="mt-3 text-sm leading-6 text-slate-500">
              点击安装后会自动安装到当前框架目录下的 <span className="font-mono text-slate-800">./napcat</span>。
            </div>
            <button
              type="button"
              onClick={handleInstall}
              disabled={isInstalling}
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-60"
            >
              {isInstalling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              安装 NapCat
            </button>
          </div>
        </div>
      )
    }

    if (!status.running) {
      return (
        <div className="flex h-full items-center justify-center px-6">
          <div className="max-w-md text-center">
            <Play className="mx-auto mb-4 h-12 w-12 text-emerald-300" />
            <div className="text-xl font-semibold text-slate-900">NapCat 已安装，当前未启动</div>
            <div className="mt-3 text-sm leading-6 text-slate-500">
              启动后这里会自动内嵌 NapCat WebUI。OneBot 连接配置暂时仍然在 NapCat WebUI 里手动填写。
            </div>
            <button
              type="button"
              onClick={handleStart}
              disabled={actionLoading === 'start'}
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
            >
              {actionLoading === 'start' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              启动 NapCat
            </button>
          </div>
        </div>
      )
    }

    if (!webui?.url) {
      return (
        <div className="flex h-full items-center justify-center px-6">
          <div className="max-w-md text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-amber-300" />
            <div className="text-xl font-semibold text-slate-900">NapCat 已启动，等待 WebUI 地址</div>
            <div className="mt-3 text-sm leading-6 text-slate-500">
              WebUI token 通常会从 NapCat 日志里解析。你可以先去运行日志页看启动输出。
            </div>
            <button
              type="button"
              onClick={() => void loadWebUI()}
              className="mt-6 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              <RefreshCw className="h-4 w-4" />
              刷新 WebUI
            </button>
          </div>
        </div>
      )
    }

    return (
      <div className="flex h-full flex-col bg-slate-950">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 px-4">
          <div className="min-w-0 truncate text-sm text-slate-300">{webui.url}</div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => void loadWebUI()}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </button>
            <button
              type="button"
              onClick={openWebUI}
              className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-slate-900 hover:bg-slate-100"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              外部打开
            </button>
          </div>
        </div>
        <iframe title="NapCat WebUI" src={webui.url} className="h-full w-full border-0 bg-white" />
      </div>
    )
  }

  const renderLogs = () => (
    <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-h-0 flex-col bg-slate-950">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 px-4 md:px-6">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-rose-400" />
              <span className="h-3 w-3 rounded-full bg-amber-300" />
              <span className="h-3 w-3 rounded-full bg-emerald-400" />
            </div>
            <span className="text-sm text-slate-300">NapCat runtime</span>
          </div>
          <button
            type="button"
            onClick={() => void loadLogs()}
            className="inline-flex h-full items-center gap-2 border-l border-slate-800 px-4 text-xs text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-100"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            刷新
          </button>
        </div>
        <div ref={logsRef} className="custom-scrollbar flex-1 overflow-y-auto px-4 py-4 font-mono text-xs leading-6 text-slate-300 md:px-6">
          {runtimeLogs.length ? runtimeLogs.map((line, index) => (
            <div key={`${index}-${line}`} className="whitespace-pre-wrap break-all">{line}</div>
          )) : (
            <div className="text-slate-500">暂无运行日志。启动 NapCat 后会显示 stdout/stderr。</div>
          )}
        </div>
        <div className="h-8 shrink-0 border-t border-slate-200 bg-white" />
      </div>

      <div className="min-h-0 overflow-y-auto border-t border-slate-200 bg-white xl:border-l xl:border-t-0">
        <section className="border-b border-slate-200 pt-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">运行控制</div>
          <div className="mt-3 px-5 text-sm text-slate-700">
            当前状态：
            <span className={status?.running ? 'font-medium text-emerald-700' : status?.installed ? 'font-medium text-amber-700' : 'font-medium text-slate-500'}>
              {status?.running ? '运行中' : status?.installed ? '已安装，未启动' : '未安装'}
            </span>
          </div>
          <div className="mt-5 divide-y divide-slate-200 border-t border-slate-200">
            <button
              type="button"
              onClick={handleStart}
              disabled={!status?.installed || status?.running || actionLoading === 'start'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {actionLoading === 'start' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              启动
            </button>
            <button
              type="button"
              onClick={handleStop}
              disabled={!status?.running || actionLoading === 'stop'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {actionLoading === 'stop' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              停止
            </button>
            <button
              type="button"
              onClick={handleShowQRCode}
              disabled={qrcodeLoading}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {qrcodeLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <QrCode className="h-4 w-4" />}
              显示二维码
            </button>
          </div>
          {qrcodeError ? <div className="px-5 py-3 text-sm text-rose-600">{qrcodeError}</div> : null}
        </section>

        <section className="border-b border-slate-200 py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">日志说明</div>
          <div className="mt-4 space-y-3 px-5 text-sm leading-6 text-slate-600">
            <p>这里显示框架捕获到的 NapCat 进程 stdout/stderr。</p>
            <p>如果启动失败，先看启动入口、QQ 登录输出和 WebUI token 是否出现。</p>
            <p>二维码图片通常会保存在 <span className="font-mono text-slate-800">napcat/workdir/cache/qrcode.png</span>。</p>
          </div>
        </section>

        <section className="py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">路径</div>
          <div className="mt-4 space-y-3 px-5 text-xs leading-5 text-slate-500">
            <div>
              <div className="text-slate-400">启动入口</div>
              <div className="mt-1 break-all font-mono text-slate-700">{status?.entry || '未检测到'}</div>
            </div>
            <div>
              <div className="text-slate-400">工作目录</div>
              <div className="mt-1 break-all font-mono text-slate-700">{status?.workdir || './napcat/workdir'}</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )

  const renderInstall = () => (
    <div className="grid h-full min-h-0 overflow-hidden xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-h-0 flex-col overflow-y-auto bg-white xl:overflow-hidden">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-200 px-4 md:px-6">
          <div className="text-sm font-medium text-slate-900">一键安装 NapCat Shell</div>
          <StatusPill />
        </div>

        <div className="border-b border-slate-200 px-4 py-5 md:px-6">
          <div className="max-w-4xl text-sm leading-6 text-slate-600">
            Windows 会下载官方 <span className="font-mono text-slate-900">NapCat.Shell.Windows.OneKey.zip</span> 并运行
            <span className="mx-1 font-mono text-slate-900">NapCatInstaller.exe</span>。Linux 会执行官方 Shell 安装脚本，但安装根目录会被框架固定到
            <span className="mx-1 font-mono text-slate-900">./napcat/linux-root</span>，不写到用户公共目录。
          </div>
        </div>

        <div className="grid border-b border-slate-200 md:grid-cols-2 xl:grid-cols-4">
          <DetailCell label="安装目录" value={status?.install_path || './napcat'} />
          <DetailCell label="工作目录 NAPCAT_WORKDIR" value={status?.workdir || './napcat/workdir'} />
          <DetailCell label="启动入口" value={status?.entry || '安装完成后自动检测'} />
          <DetailCell label="平台" value={status?.platform || 'auto'} />
        </div>

        <div className="border-b border-slate-200 xl:hidden">
          <button
            type="button"
            onClick={handleInstall}
            disabled={isInstalling}
            className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-900 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
          >
            {isInstalling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {status?.installed ? '重新安装 / 修复' : '安装 NapCat'}
          </button>
          <button
            type="button"
            onClick={() => void loadAll()}
            className="inline-flex h-12 w-full items-center justify-center gap-2 border-t border-slate-200 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            <RefreshCw className="h-4 w-4" />
            刷新状态
          </button>
        </div>

        <div className="flex min-h-[420px] shrink-0 flex-col bg-slate-950 xl:min-h-0 xl:flex-1 xl:shrink">
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 px-4 md:px-6">
            <div className="text-sm text-slate-300">install output</div>
            <div className="text-xs text-slate-500">{job ? `${job.percent}% · ${job.message}` : '等待安装任务'}</div>
          </div>
          {job ? (
            <>
              <div className="h-1 bg-slate-800">
                <div className="h-full bg-emerald-500 transition-all" style={{ width: `${Math.max(0, Math.min(job.percent, 100))}%` }} />
              </div>
              <div ref={installLogsRef} className="custom-scrollbar flex-1 overflow-y-auto px-4 py-4 font-mono text-xs leading-6 text-slate-300 md:px-6">
                {job.logs.length ? job.logs.map((line, index) => (
                  <div key={`${index}-${line}`} className="whitespace-pre-wrap break-all">{line}</div>
                )) : <div className="text-slate-500">任务已创建，等待输出...</div>}
              </div>
            </>
          ) : (
            <div className="flex-1 px-4 py-4 text-sm text-slate-500 md:px-6">点击安装后会在这里显示下载、解压和安装日志。</div>
          )}
          <div className="h-8 shrink-0 border-t border-slate-200 bg-white" />
        </div>
      </div>

      <div className="hidden min-h-0 border-t border-slate-200 bg-white xl:block xl:overflow-y-auto xl:border-l xl:border-t-0">
        <section className="border-b border-slate-200 pt-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">安装操作</div>
          <div className="mt-5 divide-y divide-slate-200 border-t border-slate-200">
            <button
              type="button"
              onClick={handleInstall}
              disabled={isInstalling}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-900 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {isInstalling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {status?.installed ? '重新安装 / 修复' : '安装 NapCat'}
            </button>
            <button
              type="button"
              onClick={() => void loadAll()}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              <RefreshCw className="h-4 w-4" />
              刷新状态
            </button>
          </div>
        </section>

        <section className="border-b border-slate-200 py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">简化规则</div>
          <div className="mt-4 space-y-3 px-5 text-sm leading-6 text-slate-600">
            <p>只管理当前框架自己的 NapCat。</p>
            <p>所有文件都放在框架目录下的 <span className="font-mono text-slate-800">./napcat</span>。</p>
            <p>暂时不自动修改 OneBot 配置，安装后去 NapCat WebUI 填。</p>
          </div>
        </section>

        <section className="py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">目录结构</div>
          <div className="mt-4 space-y-2 px-5 font-mono text-xs leading-5 text-slate-600">
            <p>./napcat</p>
            <p>./napcat/linux-root</p>
            <p>./napcat/workdir/config</p>
            <p>./napcat/workdir/logs</p>
            <p>./napcat/workdir/cache</p>
          </div>
        </section>
      </div>
    </div>
  )

  const renderConfig = () => (
    <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-h-0 overflow-y-auto bg-white">
        <div className="flex h-12 items-center border-b border-slate-200 px-4 md:px-6">
          <div className="text-sm font-medium text-slate-900">NapCat 配置中心</div>
        </div>
        <section className="border-b border-slate-200 px-4 py-5 md:px-6">
          <div className="max-w-4xl text-sm leading-6 text-slate-600">
            这里用表单读写当前框架托管 NapCat 的 <span className="font-mono text-slate-900">workdir/config</span>。
            固定参数用选择框，保存后大部分配置需要重启 NapCat 才会生效。
          </div>
        </section>
        <section className="grid border-b border-slate-200 md:grid-cols-2">
          <DetailCell label="安装目录" value={status?.install_path || './napcat'} />
          <DetailCell label="工作目录" value={status?.workdir || './napcat/workdir'} />
          <DetailCell label="WebUI" value={webui?.url || '等待 NapCat 启动后解析'} />
          <DetailCell label="Token 来源" value={webui?.source || status?.webui?.source || '等待检测'} />
          <DetailCell label="启动入口" value={status?.entry || '未检测到'} />
          <DetailCell label="平台" value={status?.platform || 'auto'} />
        </section>

        <FormSection title="WebUI 设置" path={configMeta?.webui_path}>
          <FormField label="监听地址">
            <select value={configDraft.webui?.host ?? '::'} onChange={(event) => updateConfigValue('webui', ['host'], event.target.value)} className="form-select">
              <option value="127.0.0.1">127.0.0.1 本机</option>
              <option value="0.0.0.0">0.0.0.0 所有 IPv4</option>
              <option value="::">:: 所有 IPv6/IPv4</option>
              <option value="localhost">localhost</option>
            </select>
          </FormField>
          <FormField label="端口">
            <input type="number" value={configDraft.webui?.port ?? 6099} onChange={(event) => updateConfigValue('webui', ['port'], toNumber(event.target.value, 6099))} className="form-input" />
          </FormField>
          <FormField label="访问 Token">
            <input value={configDraft.webui?.token ?? ''} onChange={(event) => updateConfigValue('webui', ['token'], event.target.value)} className="form-input font-mono" placeholder="留空则由 NapCat 处理" />
          </FormField>
          <FormField label="登录频率">
            <input type="number" value={configDraft.webui?.loginRate ?? 10} onChange={(event) => updateConfigValue('webui', ['loginRate'], toNumber(event.target.value, 10))} className="form-input" />
          </FormField>
          <FormField label="自动登录账号">
            <input value={configDraft.webui?.autoLoginAccount ?? ''} onChange={(event) => updateConfigValue('webui', ['autoLoginAccount'], event.target.value)} className="form-input font-mono" placeholder="QQ 号，可留空" />
          </FormField>
          <FormField label="关闭 WebUI">
            <select value={String(!!configDraft.webui?.disableWebUI)} onChange={(event) => updateConfigValue('webui', ['disableWebUI'], toBool(event.target.value))} className="form-select">
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </FormField>
          <FormField label="访问控制">
            <select value={configDraft.webui?.accessControlMode ?? 'none'} onChange={(event) => updateConfigValue('webui', ['accessControlMode'], event.target.value)} className="form-select">
              <option value="none">不限制</option>
              <option value="whitelist">白名单</option>
              <option value="blacklist">黑名单</option>
            </select>
          </FormField>
          <FormField label="信任 X-Forwarded-For">
            <select value={String(!!configDraft.webui?.enableXForwardedFor)} onChange={(event) => updateConfigValue('webui', ['enableXForwardedFor'], toBool(event.target.value))} className="form-select">
              <option value="false">否</option>
              <option value="true">是</option>
            </select>
          </FormField>
          <FormField label="IP 白名单" wide>
            <textarea value={toLines(configDraft.webui?.ipWhitelist)} onChange={(event) => updateConfigValue('webui', ['ipWhitelist'], fromLines(event.target.value))} className="form-textarea" placeholder="一行一个 IP" />
          </FormField>
          <FormField label="IP 黑名单" wide>
            <textarea value={toLines(configDraft.webui?.ipBlacklist)} onChange={(event) => updateConfigValue('webui', ['ipBlacklist'], fromLines(event.target.value))} className="form-textarea" placeholder="一行一个 IP" />
          </FormField>
        </FormSection>

        <FormSection title="NapCat 运行设置" path={configMeta?.napcat_path}>
          <FormField label="文件日志">
            <select value={String(!!configDraft.napcat?.fileLog)} onChange={(event) => updateConfigValue('napcat', ['fileLog'], toBool(event.target.value))} className="form-select">
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </FormField>
          <FormField label="控制台日志">
            <select value={String(configDraft.napcat?.consoleLog ?? true)} onChange={(event) => updateConfigValue('napcat', ['consoleLog'], toBool(event.target.value))} className="form-select">
              <option value="true">开启</option>
              <option value="false">关闭</option>
            </select>
          </FormField>
          <FormField label="文件日志等级">
            <select value={configDraft.napcat?.fileLogLevel ?? 'debug'} onChange={(event) => updateConfigValue('napcat', ['fileLogLevel'], event.target.value)} className="form-select">
              <option value="debug">debug</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
            </select>
          </FormField>
          <FormField label="控制台日志等级">
            <select value={configDraft.napcat?.consoleLogLevel ?? 'info'} onChange={(event) => updateConfigValue('napcat', ['consoleLogLevel'], event.target.value)} className="form-select">
              <option value="debug">debug</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
            </select>
          </FormField>
          <FormField label="包后端">
            <select value={configDraft.napcat?.packetBackend ?? 'auto'} onChange={(event) => updateConfigValue('napcat', ['packetBackend'], event.target.value)} className="form-select">
              <option value="auto">auto</option>
            </select>
          </FormField>
          <FormField label="O3 Hook 模式">
            <select value={String(configDraft.napcat?.o3HookMode ?? 0)} onChange={(event) => updateConfigValue('napcat', ['o3HookMode'], toNumber(event.target.value, 0))} className="form-select">
              <option value="0">关闭</option>
              <option value="1">开启</option>
            </select>
          </FormField>
          <FormField label="自动时间同步">
            <select value={String(configDraft.napcat?.autoTimeSync ?? true)} onChange={(event) => updateConfigValue('napcat', ['autoTimeSync'], toBool(event.target.value))} className="form-select">
              <option value="true">开启</option>
              <option value="false">关闭</option>
            </select>
          </FormField>
          <FormField label="Packet Server">
            <input value={configDraft.napcat?.packetServer ?? ''} onChange={(event) => updateConfigValue('napcat', ['packetServer'], event.target.value)} className="form-input font-mono" placeholder="可留空" />
          </FormField>
        </FormSection>

        <FormSection title="OneBot 连接设置" path={configMeta?.onebot_path}>
          <FormField label="连接模式">
            <select value={getOneBotMode()} onChange={(event) => setOneBotMode(event.target.value)} className="form-select">
              <option value="websocketServer">WebSocket Server</option>
              <option value="websocketClient">WebSocket Client</option>
              <option value="httpServer">HTTP Server</option>
              <option value="disabled">不启用</option>
            </select>
          </FormField>
          <FormField label="消息格式">
            <select
              value={firstEndpoint('websocketServers').messagePostFormat || firstEndpoint('websocketClients').messagePostFormat || firstEndpoint('httpServers').messagePostFormat || 'array'}
              onChange={(event) => {
                if (getOneBotMode() === 'websocketServer') updateOneBotEndpoint('websocketServers', 'messagePostFormat', event.target.value)
                if (getOneBotMode() === 'websocketClient') updateOneBotEndpoint('websocketClients', 'messagePostFormat', event.target.value)
                if (getOneBotMode() === 'httpServer') updateOneBotEndpoint('httpServers', 'messagePostFormat', event.target.value)
              }}
              className="form-select"
            >
              <option value="array">array</option>
              <option value="string">string</option>
            </select>
          </FormField>
          {getOneBotMode() === 'websocketServer' ? (
            <>
              <FormField label="启用">
                <select value={String(firstEndpoint('websocketServers').enable ?? true)} onChange={(event) => updateOneBotEndpoint('websocketServers', 'enable', toBool(event.target.value))} className="form-select">
                  <option value="true">启用</option>
                  <option value="false">关闭</option>
                </select>
              </FormField>
              <FormField label="监听地址">
                <select value={firstEndpoint('websocketServers').host ?? '127.0.0.1'} onChange={(event) => updateOneBotEndpoint('websocketServers', 'host', event.target.value)} className="form-select">
                  <option value="127.0.0.1">127.0.0.1 本机</option>
                  <option value="0.0.0.0">0.0.0.0 所有 IPv4</option>
                  <option value="::">:: 所有 IPv6/IPv4</option>
                </select>
              </FormField>
              <FormField label="端口">
                <input type="number" value={firstEndpoint('websocketServers').port ?? 3001} onChange={(event) => updateOneBotEndpoint('websocketServers', 'port', toNumber(event.target.value, 3001))} className="form-input" />
              </FormField>
              <FormField label="Token">
                <input value={firstEndpoint('websocketServers').token ?? ''} onChange={(event) => updateOneBotEndpoint('websocketServers', 'token', event.target.value)} className="form-input font-mono" />
              </FormField>
              <FormField label="上报自身消息">
                <select value={String(!!firstEndpoint('websocketServers').reportSelfMessage)} onChange={(event) => updateOneBotEndpoint('websocketServers', 'reportSelfMessage', toBool(event.target.value))} className="form-select">
                  <option value="false">否</option>
                  <option value="true">是</option>
                </select>
              </FormField>
            </>
          ) : null}
          {getOneBotMode() === 'websocketClient' ? (
            <>
              <FormField label="启用">
                <select value={String(firstEndpoint('websocketClients').enable ?? true)} onChange={(event) => updateOneBotEndpoint('websocketClients', 'enable', toBool(event.target.value))} className="form-select">
                  <option value="true">启用</option>
                  <option value="false">关闭</option>
                </select>
              </FormField>
              <FormField label="连接地址" wide>
                <input value={firstEndpoint('websocketClients').url ?? ''} onChange={(event) => updateOneBotEndpoint('websocketClients', 'url', event.target.value)} className="form-input font-mono" placeholder="ws://127.0.0.1:8080/onebot/v11/ws" />
              </FormField>
              <FormField label="Token">
                <input value={firstEndpoint('websocketClients').token ?? ''} onChange={(event) => updateOneBotEndpoint('websocketClients', 'token', event.target.value)} className="form-input font-mono" />
              </FormField>
              <FormField label="重连间隔 ms">
                <input type="number" value={firstEndpoint('websocketClients').reconnectInterval ?? 5000} onChange={(event) => updateOneBotEndpoint('websocketClients', 'reconnectInterval', toNumber(event.target.value, 5000))} className="form-input" />
              </FormField>
            </>
          ) : null}
          {getOneBotMode() === 'httpServer' ? (
            <>
              <FormField label="启用">
                <select value={String(firstEndpoint('httpServers').enable ?? true)} onChange={(event) => updateOneBotEndpoint('httpServers', 'enable', toBool(event.target.value))} className="form-select">
                  <option value="true">启用</option>
                  <option value="false">关闭</option>
                </select>
              </FormField>
              <FormField label="监听地址">
                <select value={firstEndpoint('httpServers').host ?? '127.0.0.1'} onChange={(event) => updateOneBotEndpoint('httpServers', 'host', event.target.value)} className="form-select">
                  <option value="127.0.0.1">127.0.0.1 本机</option>
                  <option value="0.0.0.0">0.0.0.0 所有 IPv4</option>
                  <option value="::">:: 所有 IPv6/IPv4</option>
                </select>
              </FormField>
              <FormField label="端口">
                <input type="number" value={firstEndpoint('httpServers').port ?? 3000} onChange={(event) => updateOneBotEndpoint('httpServers', 'port', toNumber(event.target.value, 3000))} className="form-input" />
              </FormField>
              <FormField label="Token">
                <input value={firstEndpoint('httpServers').token ?? ''} onChange={(event) => updateOneBotEndpoint('httpServers', 'token', event.target.value)} className="form-input font-mono" />
              </FormField>
              <FormField label="启用 CORS">
                <select value={String(firstEndpoint('httpServers').enableCors ?? true)} onChange={(event) => updateOneBotEndpoint('httpServers', 'enableCors', toBool(event.target.value))} className="form-select">
                  <option value="true">开启</option>
                  <option value="false">关闭</option>
                </select>
              </FormField>
            </>
          ) : null}
          <FormField label="本地文件转 URL">
            <select value={String(!!configDraft.onebot?.enableLocalFile2Url)} onChange={(event) => updateConfigValue('onebot', ['enableLocalFile2Url'], toBool(event.target.value))} className="form-select">
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </FormField>
          <FormField label="解析合并转发">
            <select value={String(!!configDraft.onebot?.parseMultMsg)} onChange={(event) => updateConfigValue('onebot', ['parseMultMsg'], toBool(event.target.value))} className="form-select">
              <option value="false">关闭</option>
              <option value="true">开启</option>
            </select>
          </FormField>
          <FormField label="音乐签名 URL" wide>
            <input value={configDraft.onebot?.musicSignUrl ?? ''} onChange={(event) => updateConfigValue('onebot', ['musicSignUrl'], event.target.value)} className="form-input font-mono" placeholder="可留空" />
          </FormField>
          <FormField label="图片下载代理" wide>
            <input value={configDraft.onebot?.imageDownloadProxy ?? ''} onChange={(event) => updateConfigValue('onebot', ['imageDownloadProxy'], event.target.value)} className="form-input font-mono" placeholder="可留空" />
          </FormField>
        </FormSection>

      </div>

      <div className="min-h-0 overflow-y-auto border-t border-slate-200 bg-white xl:border-l xl:border-t-0">
        <section className="border-b border-slate-200 pt-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">配置操作</div>
          <div className="mt-5 divide-y divide-slate-200 border-t border-slate-200">
            <button
              type="button"
              onClick={handleApplyFrameworkOneBot}
              disabled={configSaving === 'onebot'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-900 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {configSaving === 'onebot' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Settings className="h-4 w-4" />}
              一键写入 OneBot 连接
            </button>
            <button
              type="button"
              onClick={handleSaveNapCatConfig}
              disabled={configSaving === 'save'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {configSaving === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              保存全部配置
            </button>
            <button
              type="button"
              onClick={() => void loadNapCatConfig()}
              disabled={configLoading}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {configLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              重新读取配置
            </button>
          </div>
          {configError ? <div className="px-5 py-3 text-sm text-rose-600">{configError}</div> : null}
        </section>

        <section className="py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">说明</div>
          <div className="mt-4 space-y-3 px-5 text-sm leading-6 text-slate-600">
            <p>一键写入会根据当前框架 <span className="font-mono text-slate-800">[onebot]</span> 配置生成 NapCat 的 <span className="font-mono text-slate-800">onebot11.json</span>。</p>
            <p>如果当前框架是 <span className="font-mono text-slate-800">ws_forward</span>，会让 NapCat 开 WebSocket Server；如果是 <span className="font-mono text-slate-800">ws_reverse</span>，会让 NapCat 主动连接框架。</p>
            <p>保存配置不会自动重启 NapCat，需要你手动停止再启动。</p>
          </div>
        </section>
      </div>
    </div>
  )

  const renderTools = () => (
    <div className="grid h-full min-h-0 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-h-0 overflow-y-auto bg-white">
        <div className="flex h-12 items-center border-b border-slate-200 px-4 md:px-6">
          <div className="text-sm font-medium text-slate-900">状态调试</div>
        </div>
        <section className="grid border-b border-slate-200 md:grid-cols-2 xl:grid-cols-4">
          <DetailCell label="NapCat" value={status?.running ? '运行中' : status?.installed ? '已安装，未启动' : '未安装'} />
          <DetailCell label="OneBot" value={loginStatus?.onebot?.connected ? '已连接' : loginStatus?.onebot?.running ? '适配器运行中' : '未连接'} />
          <DetailCell label="当前账号" value={loginStatus?.onebot?.self_id ? `${loginStatus.onebot.self_id}${loginStatus.onebot.self_nickname ? ` / ${loginStatus.onebot.self_nickname}` : ''}` : '未读取到'} />
          <DetailCell label="连接类型" value={loginStatus?.onebot?.connection_type || 'unknown'} />
        </section>
        {loginStatus?.onebot?.error ? (
          <section className="border-b border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 md:px-6">
            {loginStatus.onebot.error}
          </section>
        ) : null}
        <section>
          <div className="flex min-h-12 items-center justify-between border-b border-slate-200 px-4 md:px-6">
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">OneBot API 调试器</div>
            <div className="hidden text-xs text-slate-400 md:block">通过当前框架 OneBot 连接调用</div>
          </div>
          <div className="grid border-b border-slate-200 md:grid-cols-[280px_minmax(0,1fr)]">
            <div className="border-b border-slate-200 px-4 py-4 md:border-b-0 md:border-r md:px-6">
              <label className="text-xs uppercase tracking-[0.16em] text-slate-400">action</label>
              <input
                value={debugAction}
                onChange={(event) => setDebugAction(event.target.value)}
                className="mt-2 h-10 w-full border border-slate-200 bg-white px-3 font-mono text-sm text-slate-900 outline-none transition-colors focus:border-slate-400"
                placeholder="get_login_info"
              />
              <div className="mt-3 text-xs leading-5 text-slate-500">
                常用：get_login_info、get_status、get_version_info、get_friend_list、get_group_list。
              </div>
            </div>
            <div>
              <div className="flex min-h-10 items-center justify-between border-b border-slate-200 px-4 md:px-6">
                <div className="text-xs uppercase tracking-[0.16em] text-slate-400">params</div>
                <button type="button" onClick={() => setDebugParamsText('{}')} className="text-xs font-medium text-slate-500 hover:text-slate-900">
                  清空为 {}
                </button>
              </div>
              <textarea
                value={debugParamsText}
                onChange={(event) => setDebugParamsText(event.target.value)}
                spellCheck={false}
                className="custom-scrollbar h-40 w-full resize-y border-0 bg-slate-950 px-4 py-4 font-mono text-xs leading-6 text-slate-200 outline-none md:px-6"
                placeholder="{}"
              />
            </div>
          </div>
          <div className="divide-y divide-slate-200 border-b border-slate-200 md:flex md:divide-x md:divide-y-0">
            <button
              type="button"
              onClick={handleDebugOneBotApi}
              disabled={debugLoading || !debugAction.trim()}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-900 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white md:w-56"
            >
              {debugLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Terminal className="h-4 w-4" />}
              调用 API
            </button>
            <button
              type="button"
              onClick={() => {
                setDebugAction('get_login_info')
                setDebugParamsText('{}')
                setDebugResultText('')
                setDebugError('')
              }}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 md:w-44"
            >
              重置
            </button>
            <div className="flex h-12 min-w-0 flex-1 items-center px-4 text-sm text-rose-600 md:px-6">
              {debugError || ''}
            </div>
          </div>
          <textarea
            value={debugResultText}
            readOnly
            spellCheck={false}
            className="custom-scrollbar h-96 w-full resize-y border-0 bg-slate-950 px-4 py-4 font-mono text-xs leading-6 text-slate-200 outline-none md:px-6"
            placeholder="调用结果会显示在这里"
          />
        </section>
      </div>

      <div className="min-h-0 overflow-y-auto border-t border-slate-200 bg-white xl:border-l xl:border-t-0">
        <section className="border-b border-slate-200 pt-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">状态操作</div>
          <div className="mt-5 divide-y divide-slate-200 border-t border-slate-200">
            <button
              type="button"
              onClick={() => void loadNapCatLoginStatus()}
              disabled={loginStatusLoading}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {loginStatusLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新登录状态
            </button>
            <button
              type="button"
              onClick={handleStart}
              disabled={!status?.installed || status?.running || actionLoading === 'start'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {actionLoading === 'start' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              启动
            </button>
            <button
              type="button"
              onClick={handleStop}
              disabled={!status?.running || actionLoading === 'stop'}
              className="inline-flex h-12 w-full items-center justify-center gap-2 bg-white text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50 disabled:text-slate-300 disabled:hover:bg-white"
            >
              {actionLoading === 'stop' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
              停止
            </button>
          </div>
        </section>

        <section className="py-5">
          <div className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">说明</div>
          <div className="mt-4 space-y-3 px-5 text-sm leading-6 text-slate-600">
            <p>二维码入口只保留在运行日志页，避免同一个功能到处出现。</p>
            <p>调试器会真实调用 OneBot API，发送类 action 会真的发消息。</p>
          </div>
        </section>
      </div>
    </div>
  )

  return (
    <div className="fixed top-16 left-0 right-0 bottom-0 md:left-64 flex bg-white overflow-hidden">
      <div className="flex w-full min-w-0 flex-col">
        <div className="h-16 shrink-0 border-b border-slate-200 bg-white pl-4 md:pl-6">
          <div className="flex h-full items-stretch justify-between">
            <div className="flex min-w-0 items-center">
              <div className="flex items-center gap-3">
                <h1 className="truncate text-lg font-semibold text-slate-900">NapCat Manager</h1>
                <StatusPill />
              </div>
            </div>
            <div className="flex shrink-0 items-stretch border-l border-slate-200">
              {status?.running ? (
                <button
                  type="button"
                  onClick={handleStop}
                  disabled={actionLoading === 'stop'}
                  className="inline-flex h-full items-center gap-2 border-r border-slate-200 bg-white px-5 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50 disabled:opacity-50"
                >
                  {actionLoading === 'stop' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                  停止
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleStart}
                  disabled={!status?.installed || actionLoading === 'start'}
                  className="inline-flex h-full items-center gap-2 border-r border-slate-200 bg-white px-5 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 disabled:opacity-50"
                >
                  {actionLoading === 'start' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  启动
                </button>
              )}
              <button
                type="button"
                onClick={() => void loadAll()}
                className="inline-flex h-full items-center gap-2 bg-white px-5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
              >
                <RefreshCw className="h-4 w-4" />
                刷新
              </button>
            </div>
          </div>
        </div>

        <div className="h-14 shrink-0 border-b border-slate-200 bg-white overflow-x-auto">
          <div className="flex h-full min-w-max items-stretch px-2 md:px-4">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const active = activeTab === tab.key
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex h-full items-center gap-2 border-b-2 px-4 text-sm font-medium transition-colors ${
                    active
                      ? 'border-primary-600 text-primary-700'
                      : 'border-transparent text-slate-500 hover:text-slate-900'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {error ? (
          <div className="shrink-0 border-b border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 md:px-6">
            {error}
          </div>
        ) : null}

        <div className="flex-1 min-h-0 bg-slate-100">
          {activeTab === 'webui' && renderWebUI()}
          {activeTab === 'logs' && renderLogs()}
          {activeTab === 'install' && renderInstall()}
          {activeTab === 'config' && renderConfig()}
          {activeTab === 'tools' && renderTools()}
        </div>
      </div>
      {qrcodeUrl ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-4 backdrop-blur-sm" onClick={closeQRCode}>
          <div className="w-full max-w-sm bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                <QrCode className="h-4 w-4" />
                NapCat 登录二维码
              </div>
              <button
                type="button"
                onClick={closeQRCode}
                className="flex h-12 w-12 items-center justify-center text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-6">
              <img src={qrcodeUrl} alt="NapCat 登录二维码" className="mx-auto h-64 w-64 object-contain" />
              <div className="mt-4 text-center text-sm text-slate-500">使用手机 QQ 扫码授权登录，二维码变化会自动刷新</div>
              {qrcodeError ? <div className="mt-3 text-center text-sm text-rose-600">{qrcodeError}</div> : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-r border-slate-200 px-4 py-4 last:border-r-0 md:px-6">
      <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-2 break-all font-mono text-xs leading-5 text-slate-800" title={value}>{value}</div>
    </div>
  )
}

function FormSection({ title, path, children }: { title: string; path?: string; children: any }) {
  return (
    <section className="border-b border-slate-200">
      <div className="flex min-h-12 items-center justify-between border-b border-slate-200 px-4 md:px-6">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{title}</div>
        <div className="hidden max-w-[50%] truncate font-mono text-xs text-slate-400 md:block">{path || ''}</div>
      </div>
      <div className="grid md:grid-cols-2">{children}</div>
    </section>
  )
}

function FormField({ label, children, wide = false }: { label: string; children: any; wide?: boolean }) {
  return (
    <label className={`min-w-0 border-b border-r border-slate-200 px-4 py-4 md:px-6 ${wide ? 'md:col-span-2' : ''}`}>
      <div className="text-xs uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-2">{children}</div>
    </label>
  )
}
