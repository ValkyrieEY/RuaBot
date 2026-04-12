import { useState, FormEvent, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Save, AlertCircle, RefreshCw } from 'lucide-react'
import { api, type OneBotConfig } from '@/utils/api'
import { useToast } from '@/components/Toast'

export default function OneBotPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const [config, setConfig] = useState<OneBotConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState('')
  
  // 用于防止竞态条件
  const loadingRequestRef = useRef(0)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    const currentRequest = ++loadingRequestRef.current
    setLoading(true)
    setError('') // 清除之前的错误
    
    try {
      const data: any = await api.getOneBotConfig()
      
      // 只有最新的请求才更新状态
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // Transform backend response to frontend format
      // Backend returns: version, connection_type, ws_url, etc.
      // Frontend expects: onebot_version, onebot_connection_type, onebot_ws_url, etc.
      
      // 验证数据完整性
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid configuration data received')
      }
      
      const connectionType = data.connection_type || 'ws_forward'
      setConfig({
        onebot_enabled: data.enabled !== undefined ? data.enabled : true,
        onebot_version: data.version || 'v11',
        onebot_connection_type: connectionType,
        onebot_ws_url: data.ws_url || '',
        onebot_ws_reverse_host: data.ws_reverse_host || '',
        onebot_ws_reverse_port: data.ws_reverse_port !== undefined ? data.ws_reverse_port : 8080,
        onebot_http_url: data.http_url || '',
        onebot_access_token: data.access_token || '',
      })
    } catch (err: any) {
      // 只有最新的请求才更新错误状态
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load config:', err)
      const errorMessage = err.response?.data?.detail || 
                          err.message || 
                          t('onebot.loadFailed')
      setError(errorMessage)
    } finally {
      // 只有最新的请求才更新加载状态
      if (currentRequest === loadingRequestRef.current) {
        setLoading(false)
      }
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!config) return

    setSaving(true)
    setError('')

    try {
      // Transform frontend format to backend format
      const updateData: any = {
        version: config.onebot_version,
        connection_type: config.onebot_connection_type,
        ws_url: config.onebot_ws_url,
        ws_reverse_host: config.onebot_ws_reverse_host,
        ws_reverse_port: config.onebot_ws_reverse_port,
        http_url: config.onebot_http_url,
        access_token: config.onebot_access_token,
      }
      await api.updateOneBotConfig(updateData)
      toast.success(t('onebot.saveSuccess'))
      await loadConfig() // Reload to confirm changes
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('onebot.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleReconnect = async () => {
    setReconnecting(true)
    setError('')

    try {
      const result = await api.reconnectOneBot()
      if (result.success) {
        toast.success(t('onebot.reconnectSuccess'))
      } else {
        toast.error(result.message || t('onebot.reconnectFailed'))
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || t('onebot.reconnectFailed'))
    } finally {
      setReconnecting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="card text-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          {t('onebot.loadFailed')}
        </h3>
        {error && (
          <p className="text-sm text-gray-600 mb-4">{error}</p>
        )}
        <button
          onClick={loadConfig}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          {t('common.retry') || '重试'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('onebot.title')}</h1>
        <p className="text-gray-500 text-sm mt-1">{t('onebot.description')}</p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="label">{t('onebot.onebotVersion')}</label>
          <select
            value={config.onebot_version || 'v11'}
            onChange={(e) => setConfig({ ...config, onebot_version: e.target.value })}
            className="input"
          >
            <option value="v11">v11</option>
            <option value="v12">v12</option>
          </select>
        </div>

        <div>
          <label className="label">{t('onebot.connectionType')}</label>
          <select
            value={config.onebot_connection_type || 'ws_forward'}
            onChange={(e) =>
              setConfig({ ...config, onebot_connection_type: e.target.value })
            }
            className="input"
          >
            <option value="ws_forward">{t('dashboard.connectionTypes.ws_forward')}</option>
            <option value="ws_reverse">{t('dashboard.connectionTypes.ws_reverse')}</option>
            <option value="http">{t('dashboard.connectionTypes.http')}</option>
          </select>
        </div>

        {(config.onebot_connection_type === 'ws_forward' || !config.onebot_connection_type) && (
          <div>
            <label className="label">{t('onebot.wsUrl')}</label>
            <input
              type="text"
              value={config.onebot_ws_url || ''}
              onChange={(e) => setConfig({ ...config, onebot_ws_url: e.target.value })}
              placeholder="ws://localhost:3001"
              className="input"
            />
          </div>
        )}

        {config.onebot_connection_type === 'ws_reverse' && (
          <>
            <div>
              <label className="label">{t('onebot.reverseHost')}</label>
              <input
                type="text"
                value={config.onebot_ws_reverse_host || ''}
                onChange={(e) =>
                  setConfig({ ...config, onebot_ws_reverse_host: e.target.value })
                }
                placeholder="0.0.0.0"
                className="input"
              />
            </div>
            <div>
              <label className="label">{t('onebot.reversePort')}</label>
              <input
                type="number"
                value={config.onebot_ws_reverse_port || 8080}
                onChange={(e) =>
                  setConfig({ ...config, onebot_ws_reverse_port: parseInt(e.target.value) })
                }
                className="input"
              />
            </div>
          </>
        )}

        {config.onebot_connection_type === 'http' && (
          <div>
            <label className="label">{t('onebot.httpUrl')}</label>
            <input
              type="text"
              value={config.onebot_http_url || ''}
              onChange={(e) => setConfig({ ...config, onebot_http_url: e.target.value })}
              placeholder="http://localhost:5700"
              className="input"
            />
          </div>
        )}

        <div>
          <label className="label">{t('onebot.accessToken')}</label>
          <input
            type="text"
            value={config.onebot_access_token || ''}
            onChange={(e) =>
              setConfig({ ...config, onebot_access_token: e.target.value })
            }
            placeholder="your-access-token"
            className="input"
          />
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving || reconnecting}
            className="btn btn-primary flex-1 flex items-center justify-center gap-2"
          >
            <Save className="w-5 h-5" />
            {saving ? t('common.saving') : t('common.save')}
          </button>
          <button
            type="button"
            onClick={handleReconnect}
            disabled={saving || reconnecting}
            className="btn flex items-center justify-center gap-2 px-6 bg-indigo-100 hover:bg-indigo-200 text-indigo-700 border-indigo-200"
          >
            <RefreshCw className={`w-5 h-5 ${reconnecting ? 'animate-spin' : ''}`} />
            {reconnecting ? t('onebot.reconnecting') : t('onebot.reconnect')}
          </button>
        </div>
      </form>
    </div>
  )
}
