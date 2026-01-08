import { useState, FormEvent, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Save, AlertCircle } from 'lucide-react'
import { api, type OneBotConfig } from '@/utils/api'

export default function OneBotPage() {
  const { t } = useTranslation()
  const [config, setConfig] = useState<OneBotConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const data: any = await api.getOneBotConfig()
      // Transform backend response to frontend format
      // Backend returns: version, connection_type, ws_url, etc.
      // Frontend expects: onebot_version, onebot_connection_type, onebot_ws_url, etc.
      const connectionType = data.connection_type || 'ws_forward'
      setConfig({
        onebot_enabled: true, // Default to enabled
        onebot_version: data.version || 'v11',
        onebot_connection_type: connectionType,
        onebot_ws_url: data.ws_url || '',
        onebot_ws_reverse_host: data.ws_reverse_host || '',
        onebot_ws_reverse_port: data.ws_reverse_port || 8080,
        onebot_http_url: data.http_url || '',
        onebot_access_token: data.access_token || '',
      })
    } catch (error) {
      console.error('Failed to load config:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!config) return

    setSaving(true)
    setSuccess(false)
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
      setSuccess(true)
      await loadConfig() // Reload to confirm changes
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('onebot.saveFailed'))
    } finally {
      setSaving(false)
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
        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
            {t('onebot.saveSuccess')}
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="label">OneBot 版本</label>
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
          <label className="label">连接类型</label>
          <select
            value={config.onebot_connection_type || 'ws_forward'}
            onChange={(e) =>
              setConfig({ ...config, onebot_connection_type: e.target.value })
            }
            className="input"
          >
            <option value="ws_forward">正向 WebSocket (ws)</option>
            <option value="ws_reverse">反向 WebSocket (ws_reverse)</option>
            <option value="http">HTTP</option>
          </select>
        </div>

        {(config.onebot_connection_type === 'ws_forward' || !config.onebot_connection_type) && (
          <div>
            <label className="label">WebSocket URL</label>
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
              <label className="label">反向 WS 主机</label>
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
              <label className="label">反向 WS 端口</label>
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
            <label className="label">HTTP URL</label>
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
          <label className="label">Access Token (可选)</label>
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

        <button
          type="submit"
          disabled={saving}
          className="btn btn-primary w-full flex items-center justify-center gap-2"
        >
          <Save className="w-5 h-5" />
          {saving ? t('common.loading') : t('common.save')}
        </button>
      </form>
    </div>
  )
}
