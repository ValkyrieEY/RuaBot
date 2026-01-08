import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Moon, CheckCircle, Brain } from 'lucide-react';

// Get axios instance with authentication
const getClient = () => {
  const token = localStorage.getItem('access_token');
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  });
};

interface DreamConfig {
  enabled: boolean;
  first_delay_seconds: number;
  interval_minutes: number;
  max_iterations: number;
  dream_start_hour: number;
  dream_end_hour: number;
}

interface ExpressionCheckConfig {
  enabled: boolean;
  interval_minutes: number;
  batch_size: number;
  limit: number;
}

interface ExpressionReflectConfig {
  enabled: boolean;
  interval_minutes: number;
  min_usage_count: number;
  limit: number;
}

interface DreamStats {
  enabled: boolean;
  total_cycles: number;
  successful_cycles: number;
  failed_cycles: number;
  total_iterations: number;
  avg_iterations: number;
  total_cost_seconds: number;
  avg_cost_seconds: number;
  last_cycle_time: number | null;
  is_running: boolean;
}

interface ExpressionCheckStats {
  total_checked: number;
  total_accepted: number;
  total_rejected: number;
  acceptance_rate: number;
  last_check_time: number | null;
}

interface ExpressionReflectStats {
  total_reflections: number;
  total_analyzed: number;
  total_recommendations: number;
  last_reflection_time: number | null;
  tracked_expressions: number;
}

const AIMaintenancePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Configs
  const [dreamConfig, setDreamConfig] = useState<DreamConfig>({
    enabled: true,
    first_delay_seconds: 300,
    interval_minutes: 30,
    max_iterations: 15,
    dream_start_hour: 0,
    dream_end_hour: 6
  });

  const [expressionCheckConfig, setExpressionCheckConfig] = useState<ExpressionCheckConfig>({
    enabled: true,
    interval_minutes: 60,
    batch_size: 10,
    limit: 50
  });

  const [expressionReflectConfig, setExpressionReflectConfig] = useState<ExpressionReflectConfig>({
    enabled: true,
    interval_minutes: 120,
    min_usage_count: 5,
    limit: 30
  });

  // Stats
  const [dreamStats, setDreamStats] = useState<DreamStats | null>(null);
  const [checkStats, setCheckStats] = useState<ExpressionCheckStats | null>(null);
  const [reflectStats, setReflectStats] = useState<ExpressionReflectStats | null>(null);

  useEffect(() => {
    loadConfigs();
    loadStats();
    const interval = setInterval(loadStats, 30000); // Update stats every 30s
    return () => clearInterval(interval);
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/config'),
        getClient().get('/ai/maintenance/expression-check/config'),
        getClient().get('/ai/maintenance/expression-reflect/config')
      ]);
      
      // Set configs with defaults
      setDreamConfig({
        enabled: dreamRes.data.enabled ?? true,
        first_delay_seconds: dreamRes.data.first_delay_seconds ?? 300,
        interval_minutes: dreamRes.data.interval_minutes ?? 30,
        max_iterations: dreamRes.data.max_iterations ?? 15,
        dream_start_hour: dreamRes.data.dream_start_hour ?? 0,
        dream_end_hour: dreamRes.data.dream_end_hour ?? 6
      });
      
      setExpressionCheckConfig({
        enabled: checkRes.data.enabled ?? true,
        interval_minutes: checkRes.data.interval_minutes ?? 60,
        batch_size: checkRes.data.batch_size ?? 10,
        limit: checkRes.data.limit ?? 50
      });
      
      setExpressionReflectConfig({
        enabled: reflectRes.data.enabled ?? true,
        interval_minutes: reflectRes.data.interval_minutes ?? 120,
        min_usage_count: reflectRes.data.min_usage_count ?? 5,
        limit: reflectRes.data.limit ?? 30
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/stats'),
        getClient().get('/ai/maintenance/expression-check/stats'),
        getClient().get('/ai/maintenance/expression-reflect/stats')
      ]);
      
      setDreamStats(dreamRes.data);
      setCheckStats(checkRes.data);
      setReflectStats(reflectRes.data);
    } catch (err: any) {
      console.error('Failed to load stats:', err);
    }
  };

  const saveConfig = async (type: 'dream' | 'check' | 'reflect') => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      let config;
      let endpoint;
      
      if (type === 'dream') {
        config = dreamConfig;
        endpoint = '/ai/maintenance/dream/config';
      } else if (type === 'check') {
        config = expressionCheckConfig;
        endpoint = '/ai/maintenance/expression-check/config';
      } else {
        config = expressionReflectConfig;
        endpoint = '/ai/maintenance/expression-reflect/config';
      }

      await getClient().put(endpoint, config);
      setSuccess('配置保存成功！');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const triggerManualRun = async (type: 'dream' | 'check' | 'reflect') => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      let endpoint;
      
      if (type === 'dream') {
        endpoint = '/ai/maintenance/dream/run';
      } else if (type === 'check') {
        endpoint = '/ai/maintenance/expression-check/run';
      } else {
        endpoint = '/ai/maintenance/expression-reflect/run';
      }

      await getClient().post(endpoint);
      setSuccess('手动执行已启动！');
      setTimeout(() => {
        setSuccess(null);
        loadStats();
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '启动失败');
    } finally {
      setSaving(false);
    }
  };


  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 flex items-center">
          <Settings className="w-8 h-8 mr-3 text-blue-600" />
          AI 自动维护配置
        </h1>
        <p className="text-gray-600 mt-2">
          配置 Dream 梦境维护、表达方式自动检查和反思等自动维护功能
        </p>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
          {success}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <div className="flex space-x-1 overflow-x-auto">
            {['Dream 梦境维护', '表达方式自动检查', '表达方式反思'].map((label, index) => (
              <button
                key={index}
                onClick={() => setActiveTab(index)}
                className={`px-6 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === index
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6">
          {loading && (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
          )}

          {/* Dream Config */}
          {activeTab === 0 && !loading && (
            <div>
              <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <h3 className="font-semibold text-blue-900 flex items-center mb-2">
                  <Moon className="w-5 h-5 mr-2" />
                  Dream 梦境维护系统
                </h3>
                <p className="text-sm text-blue-700">
                  AI 会在后台自动整理和维护聊天记忆，合并冗余记录，删除无用信息，提升记忆质量。
                </p>
              </div>

              {/* Stats */}
              {dreamStats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">总周期数</div>
                    <div className="text-2xl font-bold text-gray-900">{dreamStats.total_cycles}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">成功率</div>
                    <div className="text-2xl font-bold text-green-600">
                      {dreamStats.total_cycles > 0 
                        ? `${(dreamStats.successful_cycles / dreamStats.total_cycles * 100).toFixed(1)}%`
                        : '0%'
                      }
                    </div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">平均迭代数</div>
                    <div className="text-2xl font-bold text-blue-600">
                      {(dreamStats.avg_iterations || 0).toFixed(1)}
                    </div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">运行状态</div>
                    <div className="text-2xl font-bold">
                      {dreamStats.is_running ? (
                        <span className="text-green-600">运行中</span>
                      ) : (
                        <span className="text-gray-400">已停止</span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Config Form */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="dream-enabled"
                    checked={dreamConfig.enabled}
                    onChange={(e) => setDreamConfig({...dreamConfig, enabled: e.target.checked})}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <label htmlFor="dream-enabled" className="ml-2 text-sm font-medium text-gray-900">
                    启用 Dream 梦境维护
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    首次延迟（秒）
                  </label>
                  <input
                    type="number"
                    value={dreamConfig.first_delay_seconds}
                    onChange={(e) => setDreamConfig({...dreamConfig, first_delay_seconds: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">程序启动后多久开始第一次梦境维护</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    执行间隔（分钟）
                  </label>
                  <input
                    type="number"
                    value={dreamConfig.interval_minutes}
                    onChange={(e) => setDreamConfig({...dreamConfig, interval_minutes: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次维护之间的间隔时间</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    最大迭代轮数
                  </label>
                  <input
                    type="number"
                    value={dreamConfig.max_iterations}
                    onChange={(e) => setDreamConfig({...dreamConfig, max_iterations: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                    max="50"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次维护最多执行多少轮操作</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      梦境开始时间（小时）
                    </label>
                    <input
                      type="number"
                      value={dreamConfig.dream_start_hour}
                      onChange={(e) => setDreamConfig({...dreamConfig, dream_start_hour: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border rounded-lg"
                      min="0"
                      max="23"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      梦境结束时间（小时）
                    </label>
                    <input
                      type="number"
                      value={dreamConfig.dream_end_hour}
                      onChange={(e) => setDreamConfig({...dreamConfig, dream_end_hour: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border rounded-lg"
                      min="0"
                      max="23"
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-500">只在指定时间段内执行梦境维护（例如：0:00-6:00）</p>

                <div className="flex space-x-3 pt-4">
                  <button
                    onClick={() => saveConfig('dream')}
                    disabled={saving}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {saving ? '保存中...' : '保存配置'}
                  </button>
                  <button
                    onClick={() => triggerManualRun('dream')}
                    disabled={saving}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    立即执行一次
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Expression Check Config */}
          {activeTab === 1 && !loading && (
            <div>
              <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
                <h3 className="font-semibold text-green-900 flex items-center mb-2">
                  <CheckCircle className="w-5 h-5 mr-2" />
                  表达方式自动检查系统
                </h3>
                <p className="text-sm text-green-700">
                  定期自动检查学习的表达方式质量，使用 LLM 评估并标记低质量的表达方式。
                </p>
              </div>

              {/* Stats */}
              {checkStats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">已检查总数</div>
                    <div className="text-2xl font-bold text-gray-900">{checkStats.total_checked}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">接受数</div>
                    <div className="text-2xl font-bold text-green-600">{checkStats.total_accepted}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">拒绝数</div>
                    <div className="text-2xl font-bold text-red-600">{checkStats.total_rejected}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">接受率</div>
                    <div className="text-2xl font-bold text-blue-600">
                      {(checkStats.acceptance_rate || 0).toFixed(1)}%
                    </div>
                  </div>
                </div>
              )}

              {/* Config Form */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="check-enabled"
                    checked={expressionCheckConfig.enabled}
                    onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, enabled: e.target.checked})}
                    className="w-4 h-4 text-green-600 rounded"
                  />
                  <label htmlFor="check-enabled" className="ml-2 text-sm font-medium text-gray-900">
                    启用自动检查
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    检查间隔（分钟）
                  </label>
                  <input
                    type="number"
                    value={expressionCheckConfig.interval_minutes}
                    onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, interval_minutes: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次自动检查之间的间隔</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    批次大小
                  </label>
                  <input
                    type="number"
                    value={expressionCheckConfig.batch_size}
                    onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, batch_size: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                    max="20"
                  />
                  <p className="text-xs text-gray-500 mt-1">每批次处理多少个表达方式</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    每次检查上限
                  </label>
                  <input
                    type="number"
                    value={expressionCheckConfig.limit}
                    onChange={(e) => setExpressionCheckConfig({...expressionCheckConfig, limit: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次最多检查多少个表达方式</p>
                </div>

                <div className="flex space-x-3 pt-4">
                  <button
                    onClick={() => saveConfig('check')}
                    disabled={saving}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    {saving ? '保存中...' : '保存配置'}
                  </button>
                  <button
                    onClick={() => triggerManualRun('check')}
                    disabled={saving}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    立即执行一次
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Expression Reflect Config */}
          {activeTab === 2 && !loading && (
            <div>
              <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                <h3 className="font-semibold text-purple-900 flex items-center mb-2">
                  <Brain className="w-5 h-5 mr-2" />
                  表达方式反思系统
                </h3>
                <p className="text-sm text-purple-700">
                  分析表达方式的使用效果，识别低效表达方式并提供改进建议。
                </p>
              </div>

              {/* Stats */}
              {reflectStats && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">反思次数</div>
                    <div className="text-2xl font-bold text-gray-900">{reflectStats.total_reflections}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">已分析数</div>
                    <div className="text-2xl font-bold text-blue-600">{reflectStats.total_analyzed}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">生成建议</div>
                    <div className="text-2xl font-bold text-purple-600">{reflectStats.total_recommendations}</div>
                  </div>
                  <div className="bg-white border rounded-lg p-4">
                    <div className="text-sm text-gray-600">追踪表达</div>
                    <div className="text-2xl font-bold text-green-600">{reflectStats.tracked_expressions}</div>
                  </div>
                </div>
              )}

              {/* Config Form */}
              <div className="space-y-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="reflect-enabled"
                    checked={expressionReflectConfig.enabled}
                    onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, enabled: e.target.checked})}
                    className="w-4 h-4 text-purple-600 rounded"
                  />
                  <label htmlFor="reflect-enabled" className="ml-2 text-sm font-medium text-gray-900">
                    启用自动反思
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    反思间隔（分钟）
                  </label>
                  <input
                    type="number"
                    value={expressionReflectConfig.interval_minutes}
                    onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, interval_minutes: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次自动反思之间的间隔</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    最小使用次数
                  </label>
                  <input
                    type="number"
                    value={expressionReflectConfig.min_usage_count}
                    onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, min_usage_count: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">至少使用多少次才进行反思分析</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    每次分析上限
                  </label>
                  <input
                    type="number"
                    value={expressionReflectConfig.limit}
                    onChange={(e) => setExpressionReflectConfig({...expressionReflectConfig, limit: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border rounded-lg"
                    min="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">每次最多分析多少个表达方式</p>
                </div>

                <div className="flex space-x-3 pt-4">
                  <button
                    onClick={() => saveConfig('reflect')}
                    disabled={saving}
                    className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                  >
                    {saving ? '保存中...' : '保存配置'}
                  </button>
                  <button
                    onClick={() => triggerManualRun('reflect')}
                    disabled={saving}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    立即执行一次
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIMaintenancePage;

