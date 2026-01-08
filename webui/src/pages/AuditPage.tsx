import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { RefreshCw, FileText, AlertCircle, Info, AlertTriangle, XCircle } from 'lucide-react'

interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
  [key: string]: any
}

export default function AuditPage() {
  const { t } = useTranslation()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [limit, setLimit] = useState(100)
  const [filterLevel, setFilterLevel] = useState<'all' | 'debug' | 'info' | 'warning' | 'error' | 'critical'>('all')
  const [autoRefresh, setAutoRefresh] = useState(false)

  useEffect(() => {
    loadLogs()
  }, [limit, filterLevel])

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        loadLogs(true)
      }, 5000) // Refresh every 5 seconds
      return () => clearInterval(interval)
    }
  }, [autoRefresh])

  const loadLogs = async (showRefreshing = false) => {
    if (showRefreshing) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    try {
      const data = await api.getSystemLogs(limit)
      setLogs(data)
    } catch (error) {
      console.error('Failed to load system logs:', error)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const formatted = date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      // Add milliseconds manually
      const ms = date.getMilliseconds().toString().padStart(3, '0')
      return `${formatted}.${ms}`
    } catch {
      return timestamp
    }
  }

  const getLevelIcon = (level: string) => {
    const levelLower = level.toLowerCase()
    if (levelLower === 'error' || levelLower === 'critical') {
      return <XCircle className="w-4 h-4 text-red-500" />
    } else if (levelLower === 'warning') {
      return <AlertTriangle className="w-4 h-4 text-yellow-500" />
    } else if (levelLower === 'info') {
      return <Info className="w-4 h-4 text-blue-500" />
    } else if (levelLower === 'debug') {
      return <AlertCircle className="w-4 h-4 text-gray-500" />
    }
    return <Info className="w-4 h-4 text-gray-500" />
  }

  const getLevelColor = (level: string) => {
    const levelLower = level.toLowerCase()
    if (levelLower === 'error' || levelLower === 'critical') {
      return 'bg-red-100 text-red-700 border-red-200'
    } else if (levelLower === 'warning') {
      return 'bg-yellow-100 text-yellow-700 border-yellow-200'
    } else if (levelLower === 'info') {
      return 'bg-blue-100 text-blue-700 border-blue-200'
    } else if (levelLower === 'debug') {
      return 'bg-gray-100 text-gray-700 border-gray-200'
    }
    return 'bg-gray-100 text-gray-700 border-gray-200'
  }

  const filteredLogs = logs.filter((log) => {
    if (filterLevel === 'all') return true
    return log.level.toLowerCase() === filterLevel
  })

  const levelCounts = {
    all: logs.length,
    debug: logs.filter(l => l.level.toLowerCase() === 'debug').length,
    info: logs.filter(l => l.level.toLowerCase() === 'info').length,
    warning: logs.filter(l => l.level.toLowerCase() === 'warning').length,
    error: logs.filter(l => l.level.toLowerCase() === 'error').length,
    critical: logs.filter(l => l.level.toLowerCase() === 'critical').length,
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-shrink">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('systemLog.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('systemLog.description')}</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value as any)}
              className="input py-2 text-sm min-w-[120px] max-w-[140px]"
            >
              <option value="all">全部级别</option>
              <option value="debug">DEBUG</option>
              <option value="info">INFO</option>
              <option value="warning">WARNING</option>
              <option value="error">ERROR</option>
              <option value="critical">CRITICAL</option>
            </select>
          </div>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="input py-2 text-sm min-w-[120px] max-w-[140px]"
          >
            <option value={50}>最近 50 条</option>
            <option value={100}>最近 100 条</option>
            <option value={200}>最近 200 条</option>
            <option value={500}>最近 500 条</option>
            <option value={1000}>最近 1000 条</option>
          </select>
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`btn ${autoRefresh ? 'btn-primary' : 'btn-secondary'} flex items-center gap-2 whitespace-nowrap text-sm`}
          >
            <RefreshCw className={`w-4 h-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{autoRefresh ? '自动刷新中' : '自动刷新'}</span>
            <span className="sm:hidden">{autoRefresh ? '刷新中' : '自动'}</span>
          </button>
          <button
            onClick={() => loadLogs(true)}
            disabled={refreshing}
            className="btn btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span>刷新</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">全部</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{levelCounts.all}</p>
            </div>
            <FileText className="w-8 h-8 text-gray-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">DEBUG</p>
              <p className="text-2xl font-bold text-gray-600 mt-1">{levelCounts.debug}</p>
            </div>
            <AlertCircle className="w-8 h-8 text-gray-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">INFO</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">{levelCounts.info}</p>
            </div>
            <Info className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">WARNING</p>
              <p className="text-2xl font-bold text-yellow-600 mt-1">{levelCounts.warning}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-yellow-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">ERROR</p>
              <p className="text-2xl font-bold text-red-600 mt-1">{levelCounts.error}</p>
            </div>
            <XCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">CRITICAL</p>
              <p className="text-2xl font-bold text-red-700 mt-1">{levelCounts.critical}</p>
            </div>
            <XCircle className="w-8 h-8 text-red-700" />
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="card p-0">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full min-w-[800px]">
            <thead className="sticky top-0 bg-gray-50 z-10">
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">时间</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">级别</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">日志器</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">消息</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-12 text-gray-500">
                    <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                    <p>暂无日志记录</p>
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log, index) => (
                  <tr key={index} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-4 text-sm text-gray-600 font-mono whitespace-nowrap">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        {getLevelIcon(log.level)}
                        <span className={`px-2 py-1 rounded text-xs font-medium border ${getLevelColor(log.level)}`}>
                          {log.level.toUpperCase()}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600 font-mono">
                      {log.logger || '-'}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-900">
                      <div className="max-w-2xl">
                        <div className="break-words">{log.message || JSON.stringify(log)}</div>
                        {log.exception && (
                          <details className="mt-2">
                            <summary className="text-xs text-red-600 cursor-pointer">查看异常详情</summary>
                            <pre className="mt-2 text-xs bg-red-50 p-2 rounded overflow-x-auto">
                              {log.exception}
                            </pre>
                          </details>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
