import React from 'react'
import { CircularProgress } from './CircularProgress'
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { Activity, Zap, CheckCircle, XCircle, Clock } from 'lucide-react'

interface ThreadPoolStats {
  max_workers: number
  max_workers_auto?: boolean
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
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          {icon}
          <h3 className="font-semibold text-gray-900">{title}</h3>
        </div>
        <div className="text-center py-8 text-gray-400">
          <Activity className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>线程池未初始化</p>
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

  // 使用真实历史数据，如果没有则使用当前活跃任务数填充
  const getChartData = () => {
    if (historyData && historyData.length > 0) {
      // 使用真实历史数据，过滤掉空时间标签（用于显示优化）
      return historyData
        .map(item => ({
          time: item.time,
          tasks: item.tasks
        }))
        .filter(item => item.time !== '') // 移除空标签，但保留数据点
    } else {
      // 如果没有历史数据，使用当前活跃任务数作为单点数据
      return [
        {
          time: 'Now',
          tasks: stats.active_tasks || 0
        }
      ]
    }
  }

  const chartData = getChartData()
  
  // 确保至少有一个数据点
  if (chartData.length === 0) {
    chartData.push({
      time: 'Now',
      tasks: stats.active_tasks || 0
    })
  }

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-semibold text-gray-900">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${stats.initialized ? 'bg-green-500' : 'bg-gray-400'}`}></div>
          <span className="text-xs text-gray-500">
            {stats.initialized ? '运行中' : '已停止'}
          </span>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Utilization Rate */}
        <div className="flex flex-col items-center">
          <CircularProgress
            percentage={utilizationRate}
            size={100}
            strokeWidth={6}
            color={color}
            label="利用率"
          />
        </div>

        {/* Success Rate */}
        <div className="flex flex-col items-center">
          <CircularProgress
            percentage={stats.success_rate}
            size={100}
            strokeWidth={6}
            color="#10b981"
            label="成功率"
          />
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-blue-50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-4 h-4 text-blue-600" />
            <span className="text-xs text-gray-600">工作线程</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="text-xl font-bold text-gray-900">{stats.max_workers || 'N/A'}</div>
            {stats.max_workers_auto && (
              <span className="text-xs text-blue-600 font-medium">自动</span>
            )}
          </div>
        </div>

        <div className="bg-orange-50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-orange-600" />
            <span className="text-xs text-gray-600">活跃任务</span>
          </div>
          <div className="text-xl font-bold text-gray-900">{stats.active_tasks}</div>
        </div>

        <div className="bg-green-50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-xs text-gray-600">已完成</span>
          </div>
          <div className="text-xl font-bold text-gray-900">{stats.completed_tasks}</div>
        </div>

        <div className="bg-red-50 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="w-4 h-4 text-red-600" />
            <span className="text-xs text-gray-600">失败</span>
          </div>
          <div className="text-xl font-bold text-gray-900">{stats.failed_tasks}</div>
        </div>
      </div>

      {/* Activity Chart */}
      <div className="border-t pt-4">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">活跃度趋势</span>
        </div>
        <ResponsiveContainer width="100%" height={80}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="time" 
              tick={{ fontSize: 10 }}
              stroke="#9ca3af"
              tickFormatter={(value) => value || ''}  // 空标签不显示
              interval="preserveStartEnd"  // 只显示首尾标签
            />
            <YAxis 
              tick={{ fontSize: 10 }}
              stroke="#9ca3af"
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.9)',
                border: '1px solid #e5e7eb',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            />
            <Area 
              type="monotone" 
              dataKey="tasks" 
              stroke={color} 
              fill={`url(#gradient-${title})`}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Footer Stats */}
      <div className="border-t pt-3 mt-3 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3" />
          <span>运行时间: {formatUptime(stats.uptime_seconds)}</span>
        </div>
        <div>
          总任务: {stats.total_tasks}
        </div>
      </div>
    </div>
  )
}

