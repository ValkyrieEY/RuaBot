import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Settings, Moon, CheckCircle, Brain, Sparkles, Play, RefreshCw, Clock } from 'lucide-react'

const getClient = () => {
  const token = localStorage.getItem('access_token')
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  })
}

interface DreamConfig {
  enabled: boolean
  first_delay_seconds: number
  interval_minutes: number
  max_iterations: number
  dream_start_hour: number
  dream_end_hour: number
}

interface ExpressionCheckConfig {
  enabled: boolean
  interval_minutes: number
  batch_size: number
  limit: number
}

interface ExpressionReflectConfig {
  enabled: boolean
  interval_minutes: number
  min_usage_count: number
  limit: number
}

interface DreamStats {
  enabled: boolean
  total_cycles: number
  successful_cycles: number
  failed_cycles: number
  total_iterations: number
  avg_iterations: number
  total_cost_seconds: number
  avg_cost_seconds: number
  last_cycle_time: number | null
  is_running: boolean
}

interface ExpressionCheckStats {
  total_checked: number
  total_accepted: number
  total_rejected: number
  acceptance_rate: number
  last_check_time: number | null
}

interface ExpressionReflectStats {
  total_reflections: number
  total_analyzed: number
  total_recommendations: number
  last_reflection_time: number | null
  tracked_expressions: number
}

const AIMaintenancePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Configs
  const [dreamConfig, setDreamConfig] = useState<DreamConfig>({
    enabled: true,
    first_delay_seconds: 300,
    interval_minutes: 30,
    max_iterations: 15,
    dream_start_hour: 0,
    dream_end_hour: 6
  })

  const [expressionCheckConfig, setExpressionCheckConfig] = useState<ExpressionCheckConfig>({
    enabled: true,
    interval_minutes: 60,
    batch_size: 10,
    limit: 50
  })

  const [expressionReflectConfig, setExpressionReflectConfig] = useState<ExpressionReflectConfig>({
    enabled: true,
    interval_minutes: 120,
    min_usage_count: 5,
    limit: 30
  })

  // Stats
  const [dreamStats, setDreamStats] = useState<DreamStats | null>(null)
  const [checkStats, setCheckStats] = useState<ExpressionCheckStats | null>(null)
  const [reflectStats, setReflectStats] = useState<ExpressionReflectStats | null>(null)

  useEffect(() => {
    loadConfigs()
    loadStats()
    const interval = setInterval(loadStats, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadConfigs = async () => {
    setLoading(true)
    setError(null)
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/config'),
        getClient().get('/ai/maintenance/expression-check/config'),
        getClient().get('/ai/maintenance/expression-reflect/config')
      ])
      
      setDreamConfig({
        enabled: dreamRes.data.enabled ?? true,
        first_delay_seconds: dreamRes.data.first_delay_seconds ?? 300,
        interval_minutes: dreamRes.data.interval_minutes ?? 30,
        max_iterations: dreamRes.data.max_iterations ?? 15,
        dream_start_hour: dreamRes.data.dream_start_hour ?? 0,
        dream_end_hour: dreamRes.data.dream_end_hour ?? 6
      })
      
      setExpressionCheckConfig({
        enabled: checkRes.data.enabled ?? true,
        interval_minutes: checkRes.data.interval_minutes ?? 60,
        batch_size: checkRes.data.batch_size ?? 10,
        limit: checkRes.data.limit ?? 50
      })
      
      setExpressionReflectConfig({
        enabled: reflectRes.data.enabled ?? true,
        interval_minutes: reflectRes.data.interval_minutes ?? 120,
        min_usage_count: reflectRes.data.min_usage_count ?? 5,
        limit: reflectRes.data.limit ?? 30
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/stats'),
        getClient().get('/ai/maintenance/expression-check/stats'),
        getClient().get('/ai/maintenance/expression-reflect/stats')
      ])
      
      setDreamStats(dreamRes.data)
      setCheckStats(checkRes.data)
      setReflectStats(reflectRes.data)
    } catch (err: any) {
      console.error('Failed to load stats:', err)
    }
  }

  const saveConfig = async (type: 'dream' | 'check' | 'reflect') => {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      let config
      let endpoint
      
      if (type === 'dream') {
        config = dreamConfig
        endpoint = '/ai/maintenance/dream/config'
      } else if (type === 'check') {
        config = expressionCheckConfig
        endpoint = '/ai/maintenance/expression-check/config'
      } else {
        config = expressionReflectConfig
        endpoint = '/ai/maintenance/expression-reflect/config'
      }

      await getClient().put(endpoint, config)
      setSuccess('配置保存成功！')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  const triggerManualRun = async (type: 'dream' | 'check' | 'reflect') => {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      let endpoint
      
      if (type === 'dream') {
        endpoint = '/ai/maintenance/dream/run'
      } else if (type === 'check') {
        endpoint = '/ai/maintenance/expression-check/run'
      } else {
        endpoint = '/ai/maintenance/expression-reflect/run'
      }

      await getClient().post(endpoint)
      setSuccess('手动执行已启动！')
      setTimeout(() => {
        setSuccess(null)
        loadStats()
      }, 2000)
    } catch (err: any) {
      setError(err.response?.data?.detail || '启动失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-3 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-xl shadow-lg">
            <Settings className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              AI 自动维护
            </h1>
          </div>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border-2 border-red-200 rounded-xl text-red-700 animate-pulse">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-green-50 border-2 border-green-200 rounded-xl text-green-700 flex items-center gap-2">
          <CheckCircle className="w-5 h-5" />
          {success}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-2xl shadow-xl border-2 border-gray-200 overflow-hidden">
        <div className="flex border-b-2 border-gray-200">
          {[
            { id: 0, label: 'Dream 梦境', icon: Moon, color: 'blue' },
            { id: 1, label: '表达检查', icon: CheckCircle, color: 'green' },
            { id: 2, label: '表达反思', icon: Brain, color: 'purple' }
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex-1 flex items-center justify-center gap-2 px-6 py-4 font-medium transition-all relative
                  ${isActive 
                    ? `bg-gradient-to-r from-${tab.color}-50 to-${tab.color}-100 text-${tab.color}-700` 
                    : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'animate-pulse' : ''}`} />
                <span>{tab.label}</span>
                {isActive && (
                  <div className={`absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-${tab.color}-500 to-${tab.color}-600`} />
                )}
              </button>
            )
          })}
        </div>

        <div className="p-8">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            </div>
          ) : (
            <>
              {/* Dream Tab */}
              {activeTab === 0 && (
                <div className="space-y-6">
                  {/* Stats */}
                  {dreamStats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-white border-2 border-blue-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">总周期数</div>
                        <div className="text-3xl font-bold text-blue-600">{dreamStats.total_cycles}</div>
                      </div>
                      <div className="bg-white border-2 border-green-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">成功率</div>
                        <div className="text-3xl font-bold text-green-600">
                          {dreamStats.total_cycles > 0 
                            ? `${(dreamStats.successful_cycles / dreamStats.total_cycles * 100).toFixed(1)}%`
                            : '0%'
                          }
                        </div>
                      </div>
                      <div className="bg-white border-2 border-purple-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">平均迭代数</div>
                        <div className="text-3xl font-bold text-purple-600">
                          {(dreamStats.avg_iterations || 0).toFixed(1)}
                        </div>
                      </div>
                      <div className="bg-white border-2 border-orange-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">运行状态</div>
                        <div className="text-2xl font-bold">
                          {dreamStats.is_running ? (
                            <span className="text-green-600 flex items-center gap-2">
                              <Sparkles className="w-5 h-5 animate-pulse" />
                              运行中
                            </span>
                          ) : (
                            <span className="text-gray-400">已停止</span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Config Form */}
                  <div className="bg-white border-2 border-gray-200 rounded-xl p-6 space-y-5">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          id="dream-enabled"
                          checked={dreamConfig.enabled}
                          onChange={(e) => setDreamConfig({...dreamConfig, enabled: e.target.checked})}
                          className="w-5 h-5 text-blue-600 rounded"
                        />
                        <label htmlFor="dream-enabled" className="text-lg font-semibold text-gray-900 cursor-pointer">
                          启用 Dream 梦境维护
                        </label>
                      </div>
                      {dreamConfig.enabled && (
                        <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">已启用</span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                          <Clock className="w-4 h-4" />
                          首次延迟（秒）
                        </label>
                        <input
                          type="number"
                          value={dreamConfig.first_delay_seconds}
                          onChange={(e) => setDreamConfig({...dreamConfig, first_delay_seconds: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          min="0"
                        />
                        <p className="text-xs text-gray-500 mt-1">程序启动后多久开始第一次梦境维护</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                          <RefreshCw className="w-4 h-4" />
                          执行间隔（分钟）
                        </label>
                        <input
                          type="number"
                          value={dreamConfig.interval_minutes}
                          onChange={(e) => setDreamConfig({...dreamConfig, interval_minutes: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          min="1"
                        />
                        <p className="text-xs text-gray-500 mt-1">每次维护之间的间隔时间</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">最大迭代轮数</label>
                        <input
                          type="number"
                          value={dreamConfig.max_iterations}
                          onChange={(e) => setDreamConfig({...dreamConfig, max_iterations: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          min="1"
                          max="50"
                        />
                        <p className="text-xs text-gray-500 mt-1">每次维护最多执行多少轮操作</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">梦境时间窗口</label>
                        <div className="flex gap-2">
                          <input
                            type="number"
                            value={dreamConfig.dream_start_hour}
                            onChange={(e) => setDreamConfig({...dreamConfig, dream_start_hour: parseInt(e.target.value)})}
                            className="w-20 px-3 py-2 border-2 border-gray-300 rounded-lg text-center"
                            min="0"
                            max="23"
                          />
                          <span className="flex items-center text-gray-500">至</span>
                          <input
                            type="number"
                            value={dreamConfig.dream_end_hour}
                            onChange={(e) => setDreamConfig({...dreamConfig, dream_end_hour: parseInt(e.target.value)})}
                            className="w-20 px-3 py-2 border-2 border-gray-300 rounded-lg text-center"
                            min="0"
                            max="23"
                          />
                          <span className="flex items-center text-gray-500">点</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">只在指定时间段内执行梦境维护</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                      <button
                        onClick={() => saveConfig('dream')}
                        disabled={saving}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Settings className="w-5 h-5" />
                        {saving ? '保存中...' : '保存配置'}
                      </button>
                      <button
                        onClick={() => triggerManualRun('dream')}
                        disabled={saving}
                        className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-green-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Play className="w-5 h-5" />
                        立即执行
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Expression Check Tab */}
              {activeTab === 1 && (
                <div className="space-y-6">
                  {/* Stats */}
                  {checkStats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">已检查总数</div>
                        <div className="text-3xl font-bold text-gray-900">{checkStats.total_checked}</div>
                      </div>
                      <div className="bg-white border-2 border-green-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">接受数</div>
                        <div className="text-3xl font-bold text-green-600">{checkStats.total_accepted}</div>
                      </div>
                      <div className="bg-white border-2 border-red-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">拒绝数</div>
                        <div className="text-3xl font-bold text-red-600">{checkStats.total_rejected}</div>
                      </div>
                      <div className="bg-white border-2 border-blue-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">接受率</div>
                        <div className="text-3xl font-bold text-blue-600">
                          {(checkStats.acceptance_rate || 0).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Config Form */}
                  <div className="bg-white border-2 border-gray-200 rounded-xl p-6 space-y-5">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          id="check-enabled"
                          checked={expressionCheckConfig.enabled}
                          onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, enabled: e.target.checked})}
                          className="w-5 h-5 text-green-600 rounded"
                        />
                        <label htmlFor="check-enabled" className="text-lg font-semibold text-gray-900 cursor-pointer">
                          启用自动检查
                        </label>
                      </div>
                      {expressionCheckConfig.enabled && (
                        <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">已启用</span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">检查间隔（分钟）</label>
                        <input
                          type="number"
                          value={expressionCheckConfig.interval_minutes}
                          onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, interval_minutes: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                          min="1"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">批次大小</label>
                        <input
                          type="number"
                          value={expressionCheckConfig.batch_size}
                          onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, batch_size: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                          min="1"
                          max="20"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">每次检查上限</label>
                        <input
                          type="number"
                          value={expressionCheckConfig.limit}
                          onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, limit: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                          min="1"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                      <button
                        onClick={() => saveConfig('check')}
                        disabled={saving}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-green-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Settings className="w-5 h-5" />
                        {saving ? '保存中...' : '保存配置'}
                      </button>
                      <button
                        onClick={() => triggerManualRun('check')}
                        disabled={saving}
                        className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Play className="w-5 h-5" />
                        立即执行
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Expression Reflect Tab */}
              {activeTab === 2 && (
                <div className="space-y-6">
                  {/* Stats */}
                  {reflectStats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="bg-white border-2 border-gray-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">反思次数</div>
                        <div className="text-3xl font-bold text-gray-900">{reflectStats.total_reflections}</div>
                      </div>
                      <div className="bg-white border-2 border-blue-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">已分析数</div>
                        <div className="text-3xl font-bold text-blue-600">{reflectStats.total_analyzed}</div>
                      </div>
                      <div className="bg-white border-2 border-purple-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">生成建议</div>
                        <div className="text-3xl font-bold text-purple-600">{reflectStats.total_recommendations}</div>
                      </div>
                      <div className="bg-white border-2 border-green-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                        <div className="text-sm text-gray-600 mb-1">追踪表达</div>
                        <div className="text-3xl font-bold text-green-600">{reflectStats.tracked_expressions}</div>
                      </div>
                    </div>
                  )}

                  {/* Config Form */}
                  <div className="bg-white border-2 border-gray-200 rounded-xl p-6 space-y-5">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          id="reflect-enabled"
                          checked={expressionReflectConfig.enabled}
                          onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, enabled: e.target.checked})}
                          className="w-5 h-5 text-purple-600 rounded"
                        />
                        <label htmlFor="reflect-enabled" className="text-lg font-semibold text-gray-900 cursor-pointer">
                          启用自动反思
                        </label>
                      </div>
                      {expressionReflectConfig.enabled && (
                        <span className="px-3 py-1 bg-purple-100 text-purple-700 text-sm font-medium rounded-full">已启用</span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">反思间隔（分钟）</label>
                        <input
                          type="number"
                          value={expressionReflectConfig.interval_minutes}
                          onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, interval_minutes: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                          min="1"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">最小使用次数</label>
                        <input
                          type="number"
                          value={expressionReflectConfig.min_usage_count}
                          onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, min_usage_count: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                          min="1"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">每次分析上限</label>
                        <input
                          type="number"
                          value={expressionReflectConfig.limit}
                          onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, limit: parseInt(e.target.value)})}
                          className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                          min="1"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-4 border-t border-gray-200">
                      <button
                        onClick={() => saveConfig('reflect')}
                        disabled={saving}
                        className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white font-medium rounded-xl hover:from-purple-600 hover:to-purple-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Settings className="w-5 h-5" />
                        {saving ? '保存中...' : '保存配置'}
                      </button>
                      <button
                        onClick={() => triggerManualRun('reflect')}
                        disabled={saving}
                        className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition-all shadow-lg"
                      >
                        <Play className="w-5 h-5" />
                        立即执行
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default AIMaintenancePage
