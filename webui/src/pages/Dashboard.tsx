import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { useDashboardStore } from '@/store/dashboardStore'
import { CircularProgress } from '@/components/CircularProgress'
import { ThreadPoolMonitor } from '@/components/ThreadPoolMonitor'
import { 
  Activity, 
  MessageSquare, 
  Puzzle, 
  Clock,
  Code,
  Package,
  Inbox,
  Send,
  Wifi,
  Upload,
  Download,
  Zap,
  HardDrive,
  Monitor,
  Terminal,
  Layers,
  Shield,
  Radio,
  RefreshCw
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
  const [threadPoolStats, setThreadPoolStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [currentTime, setCurrentTime] = useState(new Date())
  
  // Realtime rate calculation and thread pool history from store
  const { rates, threadPoolHistory } = useDashboardStore()

  useEffect(() => {
    loadStatus()
    loadLoginInfo()
    loadThreadPoolStats()
    const interval = setInterval(() => {
      loadStatus()
      loadLoginInfo()
      loadThreadPoolStats()
    }, 5000) // Refresh every 5 seconds

    const timeInterval = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    return () => {
      clearInterval(interval)
      clearInterval(timeInterval)
    }
  }, [])

  const loadStatus = async () => {
    try {
      const data = await api.getSystemStatus()
      
      // Get state directly from store instance to avoid closure staleness in setInterval
      const { lastStatus, lastTime, rates: currentRates, setDashboardState } = useDashboardStore.getState()
      
      // Calculate rates (events/min)
      const now = Date.now()
      // Use max(0.001, ...) to avoid division by zero
      const timeDiff = Math.max(0.001, (now - lastTime) / 1000 / 60) // minutes
      
      let newRates = currentRates
      
      if (lastStatus && timeDiff < 60) { // Ignore extremely large gaps (> 1 hour)
        // Ensure values are numbers
        const currentTotal = Number(data.event_bus?.total_events || 0)
        const lastTotal = Number(lastStatus.event_bus?.total_events || 0)
        const currentReceived = Number(data.event_bus?.today_received || 0)
        const lastReceived = Number(lastStatus.event_bus?.today_received || 0)
        const currentSent = Number(data.event_bus?.today_sent || 0)
        const lastSent = Number(lastStatus.event_bus?.today_sent || 0)
        
        const eventsDiff = Math.max(0, currentTotal - lastTotal)
        const receivedDiff = Math.max(0, currentReceived - lastReceived)
        const sentDiff = Math.max(0, currentSent - lastSent)
        
        // Calculate per minute rate
        const rateEvents = Math.round(eventsDiff / timeDiff)
        const rateReceived = Math.round(receivedDiff / timeDiff)
        const rateSent = Math.round(sentDiff / timeDiff)
        
        newRates = {
          events: rateEvents,
          received: rateReceived,
          sent: rateSent
        }
      }
      
      setDashboardState(data, now, newRates)
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
      if (data.status === 'ok' && data.data) {
        setLoginInfo(data.data)
      }
    } catch (error) {
      console.error('Failed to load login info:', error)
    }
  }

  const loadThreadPoolStats = async () => {
    try {
      const data = await api.getThreadPoolStats()
      setThreadPoolStats(data)
      
      // 
      const now = Date.now()
      const prev = useDashboardStore.getState().threadPoolHistory
      const newHistory = { ...prev }
      
      // Helper function to process history with trend calculation
      const processHistory = (currentTotalTasks: number, history: any[]) => {
        // Ensure we have a valid number
        const totalTasks = typeof currentTotalTasks === 'number' ? currentTotalTasks : 0
        
        // Calculate the change rate (tasks per interval)
        let taskChange = 0
        if (history.length > 0) {
          const lastTotal = history[history.length - 1].total || 0
          taskChange = Math.max(0, totalTasks - lastTotal)
        } else {
          // First data point, use current total as initial value
          taskChange = totalTasks
        }
        
        // Add new data point with both total and change rate
        const updated = [
          ...history,
          {
            time: 'Now',
            tasks: taskChange, // Show change rate (trend) instead of cumulative
            total: totalTasks, // Keep total for next calculation
            timestamp: now
          }
        ].slice(-12) // Keep only last 12 points (1 minute of data at 5s intervals)
        
        // Update time labels
        return updated.map((item, index) => {
          const totalPoints = updated.length
          const position = totalPoints - 1 - index
          let timeLabel = ''
          if (index === totalPoints - 1) {
            timeLabel = 'Now'
          } else if (position % 2 === 0 || position === 0) {
            const seconds = position * 5
            timeLabel = seconds >= 60 ? `-${Math.floor(seconds / 60)}m` : `-${seconds}s`
          }
          return { 
            ...item, 
            time: timeLabel,
            tasks: item.tasks || 0, // Ensure tasks is always a number
            total: item.total || 0 // Keep total for trend calculation
          }
        })
      }

      // Update plugin thread pool history - show trend (change rate) instead of cumulative
      if (data.plugin_threadpool && data.plugin_threadpool.initialized) {
        const totalTasks = data.plugin_threadpool.total_tasks || 0
        newHistory.plugin = processHistory(totalTasks, prev.plugin || [])
      } else if (data.plugin_threadpool === null && prev.plugin && prev.plugin.length > 0) {
        // If thread pool is disabled, keep existing history
      }
      
      useDashboardStore.getState().setThreadPoolHistory(newHistory)
    } catch (error) {
      console.error('Failed to load thread pool stats:', error)
    }
  }

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          <p className="text-gray-500 font-medium">Loading Dashboard...</p>
        </div>
      </div>
    )
  }

  const isOnline = status?.status === 'running'
  const botOnline = status?.bot_status?.online
  const memoryPercent = status?.memory?.percent || 0
  const cpuPercent = status?.cpu?.usage || 0
  const primaryThreadPoolStats = threadPoolStats?.plugin_threadpool ?? null
  
  // Formatters
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const getTimeGreeting = () => {
    const hour = currentTime.getHours()
    if (hour < 5) return t('dashboard.welcome.night')
    if (hour < 12) return t('dashboard.welcome.morning')
    if (hour < 14) return t('dashboard.welcome.afternoon')
    if (hour < 18) return t('dashboard.welcome.evening')
    return t('dashboard.welcome.evening')
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden pb-8 animate-fade-in">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-white p-6 shadow-sm border border-gray-100 sm:p-10">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-50 via-white to-purple-50 opacity-50"></div>
        <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center gap-4 sm:gap-6 w-full sm:w-auto">
            <div className="relative group flex-shrink-0">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-pink-500 to-violet-500 rounded-full opacity-75 group-hover:opacity-100 transition duration-200 blur"></div>
              <img
                src={loginInfo?.user_id ? `https://q.qlogo.cn/headimg_dl?dst_uin=${loginInfo.user_id}&spec=640&img_type=jpg` : 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="64" height="64"%3E%3Crect width="64" height="64" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="24"%3E%3C/text%3E%3C/svg%3E'}
                alt="Avatar"
                className="relative w-16 h-16 sm:w-20 sm:h-20 rounded-full border-4 border-white shadow-md object-cover"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="64" height="64"%3E%3Crect width="64" height="64" fill="%23e5e7eb"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%239ca3af" font-size="24"%3E%3C/text%3E%3C/svg%3E'
                }}
              />
              <div className={`absolute bottom-0 right-0 w-5 h-5 sm:w-6 sm:h-6 rounded-full border-3 sm:border-4 border-white ${botOnline ? 'bg-green-500' : 'bg-gray-400'}`}></div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-xs sm:text-sm font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full whitespace-nowrap">
                  {loginInfo?.user_id ? 'Administrator' : 'Guest'}
                </span>
                <span className="text-xs text-gray-400 font-mono">
                  {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              <h1 className="text-xl sm:text-3xl font-bold text-gray-900 tracking-tight">
                {getTimeGreeting()},{loginInfo?.nickname || 'User'}
              </h1>
              <p className="text-sm sm:text-base text-gray-500 mt-1">
                {t('dashboard.welcome.welcomeBack')}
              </p>
            </div>
          </div>
          
          <div className="flex flex-col sm:items-end gap-3 w-full sm:w-auto bg-white/50 backdrop-blur-sm p-4 rounded-xl border border-gray-100 sm:bg-transparent sm:border-0 sm:p-0">
            <div className="flex items-center gap-3">
              <div className="flex flex-col items-end">
                <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">{t('dashboard.systemStatus')}</span>
                <span className={`text-sm font-bold ${isOnline ? 'text-green-600' : 'text-gray-500'}`}>
                  {isOnline ? 'ACTIVE' : 'STOPPED'}
                </span>
              </div>
              <div className={`p-2 rounded-lg ${isOnline ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'}`}>
                <Activity className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex flex-col items-end">
                <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">{t('dashboard.uptime')}</span>
                <span className="text-sm font-bold text-gray-900">{status?.uptime || '0m'}</span>
              </div>
              <div className="p-2 rounded-lg bg-orange-100 text-orange-600">
                <Clock className="w-5 h-5" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { 
            label: t('dashboard.totalMessages'), 
            value: (status?.event_bus?.total_events || 0).toLocaleString(), 
            icon: MessageSquare, 
            color: 'blue',
            bg: 'bg-blue-50',
            text: 'text-blue-600',
            trend: rates.events > 0 ? `+${rates.events}/m` : 'N/A' 
          },
          { 
            label: t('dashboard.todayReceived'), 
            value: (status?.event_bus?.today_received || 0).toLocaleString(), 
            icon: Inbox, 
            color: 'emerald',
            bg: 'bg-emerald-50',
            text: 'text-emerald-600',
            trend: rates.received > 0 ? `+${rates.received}/m` : 'N/A'
          },
          { 
            label: t('dashboard.todaySent'), 
            value: (status?.event_bus?.today_sent || 0).toLocaleString(), 
            icon: Send, 
            color: 'violet',
            bg: 'bg-violet-50',
            text: 'text-violet-600',
            trend: rates.sent > 0 ? `+${rates.sent}/m` : 'N/A'
          },
          { 
            label: t('dashboard.activePlugins'), 
            value: `${status?.plugins?.enabled || 0} / ${status?.plugins?.total || 0}`, 
            icon: Puzzle, 
            color: 'amber',
            bg: 'bg-amber-50',
            text: 'text-amber-600',
            trend: status?.plugins?.total ? `${Math.round((status.plugins.enabled / status.plugins.total) * 100)}%` : '0%'
          }
        ].map((item, index) => (
          <div key={index} className="bg-white rounded-xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 group">
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-xl ${item.bg} ${item.text} group-hover:scale-110 transition-transform duration-200`}>
                <item.icon className="w-6 h-6" />
              </div>
              <span className={`text-xs font-medium px-2 py-1 rounded-full ${item.trend.startsWith('+') || item.trend.endsWith('%') ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                {item.trend}
              </span>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-1">{item.value}</h3>
            <p className="text-sm text-gray-500 font-medium">{item.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: System Monitor */}
        <div className="lg:col-span-2 space-y-6">
          {/* Resource Usage */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-6 border-b border-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-50 rounded-lg">
                  <Monitor className="w-5 h-5 text-indigo-600" />
                </div>
                <h2 className="text-lg font-bold text-gray-900">{t('dashboard.systemResources')}</h2>
              </div>
              <div className="flex gap-2">
                <span className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                  Live
                </span>
              </div>
            </div>
            
            <div className="p-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
                {/* CPU */}
                <div className="flex flex-col items-center relative group">
                  <div className="absolute inset-0 bg-blue-50/50 blur-3xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                  <CircularProgress
                    percentage={cpuPercent}
                    size={140}
                    strokeWidth={10}
                    color="#3b82f6"
                    label={t('dashboard.cpu')}
                    sublabel={`${status?.cpu?.cores || 0} ${t('dashboard.cores')}`}
                  />
                  <div className="mt-4 text-center">
                    <p className="text-sm font-medium text-gray-900">{status?.cpu?.model.split(' ')[0] || 'Unknown'}</p>
                    <p className="text-xs text-gray-500">{status?.cpu?.frequency || 'N/A'}</p>
                  </div>
                </div>

                {/* Memory */}
                <div className="flex flex-col items-center relative group">
                  <div className="absolute inset-0 bg-purple-50/50 blur-3xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                  <CircularProgress
                    percentage={memoryPercent}
                    size={140}
                    strokeWidth={10}
                    color="#8b5cf6"
                    label={t('dashboard.memory')}
                    sublabel={`${(status?.memory?.used || 0).toFixed(1)} MB`}
                  />
                  <div className="mt-4 text-center">
                    <p className="text-sm font-medium text-gray-900">
                      {status?.memory ? `${(status.memory.used / 1024).toFixed(1)} / ${(status.memory.total / 1024).toFixed(1)} GB` : 'N/A'}
                    </p>
                    <p className="text-xs text-gray-500">{t('dashboard.usage')}</p>
                  </div>
                </div>

                {/* Disk */}
                <div className="flex flex-col items-center relative group">
                  <div className="absolute inset-0 bg-orange-50/50 blur-3xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                  <CircularProgress
                    percentage={status?.disk?.percent || 0}
                    size={140}
                    strokeWidth={10}
                    color="#f59e0b"
                    label={t('dashboard.disk')}
                    sublabel={`${status?.disk?.used.toFixed(1) || 0} GB`}
                  />
                  <div className="mt-4 text-center">
                    <p className="text-sm font-medium text-gray-900">
                      {status?.disk ? `${status.disk.free.toFixed(1)} GB ${t('dashboard.free')}` : 'N/A'}
                    </p>
                    <p className="text-xs text-gray-500">{t('dashboard.total')} {status?.disk?.total.toFixed(1)} GB</p>
                  </div>
                </div>
              </div>
            </div>

            {/* IO Stats Footer */}
            <div className="bg-gray-50/50 border-t border-gray-100 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-gray-100">
              {/* Network IO */}
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-1.5 bg-blue-100 rounded text-blue-600">
                    <Wifi className="w-4 h-4" />
                  </div>
                  <span className="font-semibold text-gray-900">{t('dashboard.network')}</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                      <Upload className="w-3 h-3" /> {t('dashboard.upload')}
                    </p>
                    <p className="text-lg font-bold text-gray-900">{status?.network?.bytes_sent ? formatBytes(status.network.bytes_sent * 1024 * 1024) : '0 B'}</p>
                    <p className="text-xs text-gray-400">{status?.network?.packets_sent.toLocaleString()} pkts</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                      <Download className="w-3 h-3" /> {t('dashboard.download')}
                    </p>
                    <p className="text-lg font-bold text-gray-900">{status?.network?.bytes_recv ? formatBytes(status.network.bytes_recv * 1024 * 1024) : '0 B'}</p>
                    <p className="text-xs text-gray-400">{status?.network?.packets_recv.toLocaleString()} pkts</p>
                  </div>
                </div>
              </div>

              {/* Disk IO */}
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-1.5 bg-orange-100 rounded text-orange-600">
                    <HardDrive className="w-4 h-4" />
                  </div>
                  <span className="font-semibold text-gray-900">{t('dashboard.diskIo')}</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                      <Download className="w-3 h-3" /> {t('dashboard.read')}
                    </p>
                    <p className="text-lg font-bold text-gray-900">{status?.disk_io?.read_bytes ? formatBytes(status.disk_io.read_bytes * 1024 * 1024) : '0 B'}</p>
                    <p className="text-xs text-gray-400">{status?.disk_io?.read_count.toLocaleString()} ops</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1 flex items-center gap-1">
                      <Upload className="w-3 h-3" /> {t('dashboard.write')}
                    </p>
                    <p className="text-lg font-bold text-gray-900">{status?.disk_io?.write_bytes ? formatBytes(status.disk_io.write_bytes * 1024 * 1024) : '0 B'}</p>
                    <p className="text-xs text-gray-400">{status?.disk_io?.write_count.toLocaleString()} ops</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Thread Pool Monitor (plugin pool takes the primary slot) */}
          <div className="grid grid-cols-1 gap-6">
            <ThreadPoolMonitor
              stats={primaryThreadPoolStats}
              title="Plugin Thread Pool"
              color="#3b82f6"
              icon={<Puzzle className="w-5 h-5 text-blue-500" />}
              historyData={threadPoolHistory.plugin}
            />
          </div>
        </div>

        {/* Right Column: Info & Status */}
        <div className="space-y-6">
          {/* Bot Status Card */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-500" />
              {t('dashboard.botStatus')}
            </h3>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${status?.bot_status?.online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                  <span className="text-sm font-medium text-gray-700">OneBot Connection</span>
                </div>
                <span className={`text-sm font-bold ${status?.bot_status?.online ? 'text-green-600' : 'text-red-600'}`}>
                  {status?.bot_status?.status_text || t('dashboard.offline')}
                </span>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">{t('dashboard.protocol')}</p>
                  <p className="text-sm font-bold text-gray-900 flex items-center gap-1">
                    <Radio className="w-3 h-3 text-blue-500" />
                    {status?.bot_status?.connection_type === 'ws' || status?.bot_status?.connection_type === 'ws_forward' 
                      ? t('dashboard.connectionTypes.ws_forward')
                      : status?.bot_status?.connection_type === 'ws_reverse' 
                      ? t('dashboard.connectionTypes.ws_reverse')
                      : t('dashboard.connectionTypes.http')}
                  </p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">{t('dashboard.lastSync')}</p>
                  <p className="text-sm font-bold text-gray-900 flex items-center gap-1">
                    <RefreshCw className="w-3 h-3 text-orange-500" />
                    {t('chat.justNow')}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Version Info List */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
             <div className="p-4 border-b border-gray-100 bg-gray-50/50">
               <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                 <Package className="w-4 h-4 text-gray-500" />
                 {t('dashboard.softwareVersions')}
               </h3>
             </div>
             <div className="divide-y divide-gray-100">
               {[
                 { name: 'XQNEXT Framework', version: status?.versions?.framework, icon: Layers },
                 { name: 'WebUI Interface', version: status?.versions?.webui, icon: Monitor },
                 { name: 'OneBot Protocol', version: status?.versions?.onebot, icon: Shield },
                 { name: 'Python Runtime', version: status?.versions?.python, icon: Terminal },
                 { name: 'React', version: status?.versions?.react, icon: Code },
                 { name: 'Vite', version: status?.versions?.vite, icon: Zap },
               ].map((item, i) => (
                 <div key={i} className="flex items-center justify-between p-3 hover:bg-gray-50 transition-colors">
                   <div className="flex items-center gap-3">
                     <item.icon className="w-4 h-4 text-gray-400" />
                     <span className="text-sm text-gray-600">{item.name}</span>
                   </div>
                   <span className="text-sm font-mono font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded text-xs">
                     {item.version || 'Unknown'}
                   </span>
                 </div>
               ))}
             </div>
          </div>
          
          {/* OS Info */}
          <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-xl shadow-md p-6 text-white">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
              <Terminal className="w-5 h-5" />
              {t('dashboard.environment')}
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">OS</span>
                <span className="font-mono text-sm">{status?.system?.platform}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Arch</span>
                <span className="font-mono text-sm">{status?.system?.architecture}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Python</span>
                <span className="font-mono text-sm">{status?.system?.python_version}</span>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-gray-700 text-xs text-gray-500 font-mono">
              {status?.system?.platform_version}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
