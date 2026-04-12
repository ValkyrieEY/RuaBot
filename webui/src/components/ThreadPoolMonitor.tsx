import React from 'react'
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { Zap, CheckCircle, AlertCircle, TrendingUp, Box } from 'lucide-react'

interface ThreadPoolStats {
  max_workers: number
  max_workers_auto?: boolean
  live_workers?: number
  initialized: boolean
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  active_tasks: number
  success_rate: number
  uptime_seconds: number
}

interface ThreadPoolMonitorProps {
  stats: ThreadPoolStats | null
  title: string
  color: string
  icon?: React.ReactNode
  historyData?: Array<{ time: string; tasks: number; timestamp: number }>
}

export const ThreadPoolMonitor: React.FC<ThreadPoolMonitorProps> = ({
  stats,
  title,
  color,
  icon,
  historyData = []
}) => {
  if (!stats || !stats.initialized) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-3 opacity-70">
          <div className="rounded-xl bg-slate-200 p-2 text-slate-500">
            {icon}
          </div>
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-slate-500">
          <AlertCircle className="mb-3 h-12 w-12 opacity-60" />
          <p className="text-sm font-semibold">Thread Pool Not Initialized</p>
          <p className="mt-1 text-xs text-slate-400">Enable the blocking task pool in system settings to start monitoring.</p>
        </div>
      </div>
    )
  }

  const utilizationRate = stats.max_workers > 0 
    ? (stats.active_tasks / stats.max_workers) * 100 
    : 0

  // Format uptime
  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  // Get Chart Data
  const getChartData = () => {
    if (historyData && historyData.length > 0) {
      // Use actual history data
      return historyData.map((item, index) => ({
        tasks: item.tasks || 0,
        index: index,
        time: item.time || ''
      }))
    }
    // If no history data, create initial data points with current value
    const currentTasks = stats.active_tasks || 0
    const points = 12 // Match the history length
    return Array.from({ length: points }, (_, i) => ({
      tasks: currentTasks,
      index: i,
      time: i === points - 1 ? 'Now' : ''
    }))
  }

  const chartData = getChartData()
  const gradientId = `gradient-${title.replace(/\s+/g, '-').toLowerCase()}`
  
  // Theme configuration
  const isAmber = color === '#f59e0b'
  const theme = isAmber 
    ? { 
        bgFrom: 'from-amber-500',
        bgTo: 'to-orange-500',
        lightBg: 'bg-amber-50',
        ringColor: 'ring-amber-200',
        textColor: 'text-amber-700',
        iconBg: 'bg-amber-100',
        iconColor: 'text-amber-600',
        progressBg: 'bg-amber-100',
        progressBar: 'bg-gradient-to-r from-amber-400 to-orange-500'
      }
    : { 
        bgFrom: 'from-blue-500',
        bgTo: 'to-indigo-500',
        lightBg: 'bg-blue-50',
        ringColor: 'ring-blue-200',
        textColor: 'text-blue-700',
        iconBg: 'bg-blue-100',
        iconColor: 'text-blue-600',
        progressBg: 'bg-blue-100',
        progressBar: 'bg-gradient-to-r from-blue-400 to-indigo-500'
      }

  return (
    <div className="relative overflow-hidden rounded-2xl bg-white shadow-lg border border-gray-200 hover:shadow-xl transition-all duration-300">
      {/* Header with gradient background */}
      <div className={`relative bg-gradient-to-r ${theme.bgFrom} ${theme.bgTo} p-5`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-white/20 backdrop-blur-sm">
              {icon && React.cloneElement(icon as React.ReactElement, { 
                className: 'w-5 h-5 text-white' 
              })}
            </div>
            <div>
              <h3 className="font-bold text-white text-lg tracking-tight">{title}</h3>
              <p className="text-[11px] text-white/80 mt-0.5">Framework blocking work executor</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-300 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400"></span>
                </span>
                <span className="text-xs text-white/90 font-medium">
                  UP {formatUptime(stats.uptime_seconds)}
                </span>
              </div>
            </div>
          </div>
          
          {/* Active Tasks Display */}
          <div className="text-right">
            <div className="text-4xl font-black text-white tracking-tighter tabular-nums">
              {stats.active_tasks}
            </div>
            <div className="text-[10px] font-bold text-white/70 uppercase tracking-widest">
              Active
            </div>
          </div>
        </div>

        {/* Load Progress Bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold text-white/90">Load</span>
            <span className="text-xs font-bold text-white tabular-nums">
              {utilizationRate.toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-white/20 rounded-full h-2 overflow-hidden backdrop-blur-sm">
            <div 
              className="h-full bg-white/90 rounded-full transition-all duration-500 shadow-sm"
              style={{ width: `${Math.min(utilizationRate, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div className="p-5 bg-gray-50/50">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="w-4 h-4 text-gray-500" />
          <h4 className="text-xs font-bold text-gray-600 uppercase tracking-wider">Task Throughput Trend</h4>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -7, bottom: 5 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={color} stopOpacity={0.05}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="index" 
                hide={true}
              />
              <YAxis 
                stroke="#999" 
                tick={{ fontSize: 11, fill: '#666' }}
                width={32}
                domain={[0, 'auto']}
                allowDecimals={false}
              />
              <Tooltip
                formatter={(value: number | string) => [`${value} tasks/s`, 'Throughput']}
                contentStyle={{ 
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: '12px',
                  padding: '8px 12px'
                }}
                labelStyle={{ fontWeight: 'bold', color: '#374151' }}
              />
              <Area 
                type="monotone" 
                dataKey="tasks" 
                stroke={color} 
                fill={`url(#${gradientId})`} 
                strokeWidth={2.5}
                isAnimationActive={true}
                animationDuration={800}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="px-5 pb-5">
        <div className="grid grid-cols-3 gap-3">
          {/* Workers */}
          <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-3.5 border border-gray-200">
            <div className="flex items-center gap-1.5 mb-2">
              <Zap className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">In Use</span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-black text-gray-900 tabular-nums">
                {(stats.live_workers ?? 0)} / {stats.max_workers}
              </span>
              {stats.max_workers_auto && (
                <span className="text-[9px] font-bold text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded">AUTO</span>
              )}
            </div>
          </div>
          
          {/* Success Rate */}
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-3.5 border border-green-200">
            <div className="flex items-center gap-1.5 mb-2">
              <CheckCircle className="w-3.5 h-3.5 text-green-600" />
              <span className="text-[10px] font-bold text-green-700 uppercase tracking-wider">Success</span>
            </div>
            <div className="flex items-baseline gap-0.5">
              <span className="text-2xl font-black text-green-900 tabular-nums">{stats.success_rate.toFixed(0)}</span>
              <span className="text-sm font-bold text-green-600">%</span>
            </div>
          </div>

          {/* Total Tasks */}
          <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-xl p-3.5 border border-purple-200">
            <div className="flex items-center gap-1.5 mb-2">
              <Box className="w-3.5 h-3.5 text-purple-600" />
              <span className="text-[10px] font-bold text-purple-700 uppercase tracking-wider">Total</span>
            </div>
            <div className="text-2xl font-black text-purple-900 tabular-nums">
              {stats.total_tasks > 999 ? `${(stats.total_tasks / 1000).toFixed(1)}k` : stats.total_tasks}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
