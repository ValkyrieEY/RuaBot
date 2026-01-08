import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { 
  Activity, 
  MessageSquare, 
  Puzzle, 
  Clock,
  Server,
  Cpu,
  HardDrive,
  Code,
  Package,
  Inbox,
  Send,
  User,
  Database,
  Wifi,
  Upload,
  Download
} from 'lucide-react'

interface SystemStatus {
  status: string
  event_bus: {
    total_events?: number
    history_size?: number
    today_received?: number
    today_sent?: number
    [key: string]: any
  }
  plugins: {
    total: number
    enabled: number
  }
  uptime?: string
  bot_status?: {
    online: boolean
    connection_type?: string
    status_text: string
  }
  system?: {
    platform: string
    platform_version: string
    architecture: string
    python_version: string
  }
  cpu?: {
    model: string
    cores: number
    frequency: string
    usage: number
    process_usage: number
  }
  memory?: {
    total: number
    used: number
    percent: number
    available: number
    process_memory: number
  }
  disk?: {
    total: number
    used: number
    free: number
    percent: number
  }
  network?: {
    bytes_sent: number
    bytes_recv: number
    packets_sent: number
    packets_recv: number
  }
  disk_io?: {
    read_bytes: number
    write_bytes: number
    read_count: number
    write_count: number
  }
  versions?: {
    framework: string
    onebot: string
    webui: string
    python: string
    typescript?: string
    react?: string
    vite?: string
  }
}

interface LoginInfo {
  user_id?: number
  nickname?: string
}

export default function Dashboard() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loginInfo, setLoginInfo] = useState<LoginInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStatus()
    loadLoginInfo()
    const interval = setInterval(() => {
      loadStatus()
      loadLoginInfo()
    }, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.getSystemStatus()
      setStatus(data)
    } catch (error) {
      console.error('Failed to load system status:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadLoginInfo = async () => {
    try {
      const data = await api.getLoginInfo()
      console.log('Login info response:', data)
      if (data.status === 'ok' && data.data) {
        console.log('Setting login info:', data.data)
        setLoginInfo(data.data)
      } else {
        console.log('Login info not available:', data)
      }
    } catch (error) {
      console.error('Failed to load login info:', error)
    }
  }

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const isOnline = status?.status === 'running'
  const memoryPercent = status?.memory?.percent || 0
  const cpuPercent = status?.cpu?.usage || 0

  return (
    <div className="flex flex-col space-y-6 max-w-full overflow-x-hidden">
      {/* Header */}
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('dashboard.title')}</h1>
        <p className="text-gray-500 text-sm mt-1">系统概览和实时状态</p>
      </div>

      {/* Account Info Card */}
      {loginInfo && (loginInfo.user_id || loginInfo.user_id === 0) ? (
        <div className="card">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="flex-shrink-0">
              <img
                src={`http://q.qlogo.cn/headimg_dl?dst_uin=${loginInfo.user_id}&spec=640&img_type=jpg`}
                alt="Avatar"
                className="w-16 h-16 rounded-full border-2 border-gray-200"
                onError={(e) => {
                  // Fallback to default avatar if image fails to load
                  const target = e.target as HTMLImageElement
                  target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="64" height="64"%3E%3Crect width="64" height="64" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="24"%3E%3C/text%3E%3C/svg%3E'
                }}
              />
            </div>
            {/* Account Details */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <User className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-500">登录账号</span>
              </div>
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-gray-900 truncate">
                  {loginInfo.nickname || '未知'}
                </h2>
                <span className="text-sm text-gray-500">({loginInfo.user_id})</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="flex items-center gap-2 text-gray-500">
            <User className="w-4 h-4" />
            <span className="text-sm">账号信息加载中或未连接...</span>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">{t('dashboard.totalMessages')}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {status?.event_bus?.total_events || status?.event_bus?.history_size || 0}
              </p>
            </div>
            <MessageSquare className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">今日收到</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {status?.event_bus?.today_received || 0}
              </p>
            </div>
            <Inbox className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">今日发送</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {status?.event_bus?.today_sent || 0}
              </p>
            </div>
            <Send className="w-8 h-8 text-purple-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">{t('dashboard.activePlugins')}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {status?.plugins?.enabled || 0} / {status?.plugins?.total || 0}
              </p>
            </div>
            <Puzzle className="w-8 h-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Second Row Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">机器人状态</p>
              <p className="text-lg font-bold text-gray-900 mt-1">
                {status?.bot_status?.status_text || '离线'}
              </p>
              {status?.bot_status?.connection_type && (
                <p className="text-xs text-gray-500 mt-1">
                  {status.bot_status.connection_type === 'ws' || status.bot_status.connection_type === 'ws_forward' 
                    ? '正向WebSocket' 
                    : status.bot_status.connection_type === 'ws_reverse' 
                    ? '反向WebSocket' 
                    : 'HTTP'}
                </p>
              )}
            </div>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              status?.bot_status?.online ? 'bg-green-100' : 'bg-gray-100'
            }`}>
              <Activity className={`w-5 h-5 ${
                status?.bot_status?.online ? 'text-green-600' : 'text-gray-400'
              }`} />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">{t('dashboard.uptime')}</p>
              <p className="text-lg font-bold text-gray-900 mt-1">{status?.uptime || 'N/A'}</p>
            </div>
            <Clock className="w-8 h-8 text-orange-500" />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-green-500" />
              <span className="font-medium text-gray-900">系统状态</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${isOnline ? 'bg-green-500' : 'bg-gray-400'}`}></div>
              <span className={`text-sm font-medium ${isOnline ? 'text-green-600' : 'text-gray-500'}`}>
                {isOnline ? '运行中' : '已停止'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* System Resources and Version Information */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Resources */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-5 h-5 text-blue-500" />
            <span className="font-medium text-gray-900">系统资源</span>
          </div>

          {/* CPU Usage */}
          {status?.cpu && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-gray-500" />
                  <span className="text-sm text-gray-600">CPU 使用率</span>
                </div>
                <span className="text-sm font-medium text-gray-900">{cpuPercent.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${cpuPercent}%` }}
                ></div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {status.cpu.cores} 核心 · {status.cpu.frequency}
              </div>
            </div>
          )}

          {/* Memory Usage */}
          {status?.memory && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-gray-500" />
                  <span className="text-sm text-gray-600">内存使用率</span>
                </div>
                <span className="text-sm font-medium text-gray-900">{memoryPercent.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-purple-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${memoryPercent}%` }}
                ></div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {status.memory.used.toFixed(0)} MB / {status.memory.total.toFixed(0)} MB
              </div>
            </div>
          )}

          {/* Disk Usage */}
          {status?.disk && (
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-gray-500" />
                  <span className="text-sm text-gray-600">磁盘使用率</span>
                </div>
                <span className="text-sm font-medium text-gray-900">{(status.disk.percent || 0).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-orange-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${status.disk.percent || 0}%` }}
                ></div>
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {status.disk.used.toFixed(1)} GB / {status.disk.total.toFixed(1)} GB (可用: {status.disk.free.toFixed(1)} GB)
              </div>
            </div>
          )}

          {/* Network I/O */}
          {status?.network && (
            <div className="mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Wifi className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">网络 I/O</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1">
                    <Upload className="w-3 h-3 text-blue-500" />
                    <span className="text-gray-600">上传</span>
                  </div>
                  <span className="font-medium text-gray-900">{status.network.bytes_sent.toFixed(2)} MB</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1">
                    <Download className="w-3 h-3 text-green-500" />
                    <span className="text-gray-600">下载</span>
                  </div>
                  <span className="font-medium text-gray-900">{status.network.bytes_recv.toFixed(2)} MB</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  数据包: 发送 {status.network.packets_sent.toLocaleString()} / 接收 {status.network.packets_recv.toLocaleString()}
                </div>
              </div>
            </div>
          )}

          {/* Disk I/O */}
          {status?.disk_io && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <HardDrive className="w-4 h-4 text-gray-500" />
                <span className="text-sm text-gray-600">磁盘 I/O</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1">
                    <Download className="w-3 h-3 text-blue-500" />
                    <span className="text-gray-600">读取</span>
                  </div>
                  <span className="font-medium text-gray-900">{status.disk_io.read_bytes.toFixed(2)} MB</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1">
                    <Upload className="w-3 h-3 text-orange-500" />
                    <span className="text-gray-600">写入</span>
                  </div>
                  <span className="font-medium text-gray-900">{status.disk_io.write_bytes.toFixed(2)} MB</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  操作: 读取 {status.disk_io.read_count.toLocaleString()} 次 / 写入 {status.disk_io.write_count.toLocaleString()} 次
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Version Information */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Package className="w-5 h-5 text-blue-500" />
            <span className="font-medium text-gray-900">版本信息</span>
          </div>
          <div className="space-y-3">
            {status?.versions && (
              <>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">项目版本</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.versions.framework}</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">WebUI 版本</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.versions.webui}</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">OneBot 版本</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.versions.onebot}</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Code className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">Python 版本</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.versions.python}</span>
                </div>
                {status.versions.typescript && (
                  <div className="flex items-center justify-between py-2 border-b border-gray-100">
                    <div className="flex items-center gap-2">
                      <Code className="w-4 h-4 text-gray-400" />
                      <span className="text-sm text-gray-600">TypeScript 版本</span>
                    </div>
                    <span className="text-sm font-medium text-gray-900">{status.versions.typescript}</span>
                  </div>
                )}
                {status.versions.react && (
                  <div className="flex items-center justify-between py-2 border-b border-gray-100">
                    <div className="flex items-center gap-2">
                      <Code className="w-4 h-4 text-gray-400" />
                      <span className="text-sm text-gray-600">React 版本</span>
                    </div>
                    <span className="text-sm font-medium text-gray-900">{status.versions.react}</span>
                  </div>
                )}
                {status.versions.vite && (
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2">
                      <Code className="w-4 h-4 text-gray-400" />
                      <span className="text-sm text-gray-600">Vite 版本</span>
                    </div>
                    <span className="text-sm font-medium text-gray-900">{status.versions.vite}</span>
                  </div>
                )}
              </>
            )}
            {status?.system && (
              <>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">操作系统</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.system.platform}</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">系统版本</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900 text-xs">{status.system.platform_version}</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-600">架构</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">{status.system.architecture}</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
