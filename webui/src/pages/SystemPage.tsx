import { useState, FormEvent, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { Server, Settings as SettingsIcon, Lock, Save, AlertCircle, CheckCircle } from 'lucide-react'

interface SystemConfig {
  app_name: string
  app_version: string
  environment: string
  debug: boolean
  log_level: string
  plugin_auto_load: boolean
  web_ui_enabled: boolean
  ai_thread_pool_enabled?: boolean
  plugin_thread_pool_enabled?: boolean
  tencent_cloud?: {
    secret_id?: string
    secret_key_set?: boolean
  }
}

export default function SystemPage() {
  const { t } = useTranslation()
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  
  // Password reset
  const [showPasswordReset, setShowPasswordReset] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [resettingPassword, setResettingPassword] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  
  // Tencent Cloud TTS config
  const [tencentSecretId, setTencentSecretId] = useState('')
  const [tencentSecretKey, setTencentSecretKey] = useState('')
  const [showTencentKey, setShowTencentKey] = useState(false)
  
  // AI Thread Pool config
  const [aiThreadPoolEnabled, setAiThreadPoolEnabled] = useState(true)
  
  // Plugin Thread Pool config
  const [pluginThreadPoolEnabled, setPluginThreadPoolEnabled] = useState(true)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await api.getSystemConfig()
      setConfig(data)
      // Load Tencent Cloud config
      if (data.tencent_cloud) {
        setTencentSecretId(data.tencent_cloud.secret_id || '')
        // Don't load secret_key, only show if it's set
        setShowTencentKey(false)
      }
      // Load AI Thread Pool config
      setAiThreadPoolEnabled(data.ai_thread_pool_enabled !== undefined ? data.ai_thread_pool_enabled : true)
      // Load Plugin Thread Pool config
      setPluginThreadPoolEnabled(data.plugin_thread_pool_enabled !== undefined ? data.plugin_thread_pool_enabled : true)
    } catch (error) {
      console.error('Failed to load system config:', error)
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
      const updateData: any = {
        web_ui_enabled: config.web_ui_enabled,
        debug: config.debug,
        log_level: config.log_level,
        ai_thread_pool_enabled: aiThreadPoolEnabled,
        plugin_thread_pool_enabled: pluginThreadPoolEnabled,
      }
      
      // Include Tencent Cloud config if provided
      if (tencentSecretId || tencentSecretKey) {
        updateData.tencent_cloud = {
          secret_id: tencentSecretId,
          secret_key: tencentSecretKey || undefined,  // Only send if provided
        }
      }
      
      await api.updateSystemConfig(updateData)
      setSuccess(true)
      // Clear secret key input after saving
      if (tencentSecretKey) {
        setTencentSecretKey('')
        setShowTencentKey(false)
      }
      // Reload config after saving to ensure UI reflects saved values
      await loadConfig()
      setTimeout(() => setSuccess(false), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || t('system.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handlePasswordReset = async (e: FormEvent) => {
    e.preventDefault()
    
    if (newPassword.length < 6) {
      setPasswordError(t('system.passwordTooShort'))
      return
    }
    
    if (newPassword !== confirmPassword) {
      setPasswordError(t('system.passwordMismatch'))
      return
    }

    setResettingPassword(true)
    setPasswordError('')
    setPasswordSuccess(false)

    try {
      await api.resetAdminPassword({ password: newPassword })
      setPasswordSuccess(true)
      setNewPassword('')
      setConfirmPassword('')
      setShowPasswordReset(false)
      setTimeout(() => setPasswordSuccess(false), 3000)
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || t('system.passwordResetFailed'))
    } finally {
      setResettingPassword(false)
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
        <h3 className="text-lg font-medium text-gray-900 mb-2">{t('system.loadConfigFailed')}</h3>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('system.title')}</h1>
        <p className="text-gray-500 text-sm mt-1">{t('system.description')}</p>
      </div>

      {/* System Settings */}
      <form onSubmit={handleSubmit} className="card space-y-6">
        <div className="flex items-center gap-3 mb-4">
          <SettingsIcon className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">{t('system.systemSettings')}</h2>
        </div>

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <CheckCircle className="w-5 h-5" />
            <span>{t('system.settingsSaved')}</span>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
        )}

        {/* WebUI Enabled */}
        <div className="flex items-center justify-between py-3 border-b border-gray-100">
          <div>
            <label className="text-sm font-medium text-gray-900">{t('system.webUIEnabled')}</label>
            <p className="text-xs text-gray-500 mt-1">{t('system.webUIEnabledDesc')}</p>
          </div>
          <button
            type="button"
            onClick={() => setConfig({ ...config, web_ui_enabled: !config.web_ui_enabled })}
            className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
            style={{ backgroundColor: config.web_ui_enabled ? '#3b82f6' : '#d1d5db' }}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                config.web_ui_enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Debug Mode */}
        <div className="flex items-center justify-between py-3 border-b border-gray-100">
          <div>
            <label className="text-sm font-medium text-gray-900">{t('system.debugMode')}</label>
            <p className="text-xs text-gray-500 mt-1">{t('system.debugModeDesc')}</p>
          </div>
          <button
            type="button"
            onClick={() => setConfig({ ...config, debug: !config.debug })}
            className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
            style={{ backgroundColor: config.debug ? '#3b82f6' : '#d1d5db' }}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                config.debug ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Log Level */}
        <div>
          <label className="label">{t('system.logLevelLabel')}</label>
          <select
            value={config.log_level}
            onChange={(e) => setConfig({ ...config, log_level: e.target.value })}
            className="input"
          >
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>

        {/* AI Thread Pool Settings */}
        <div className="border-t border-gray-200 pt-4 mt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">{t('system.aiThreadPool')}</h3>
          
          {/* Thread Pool Enabled */}
          <div className="flex items-center justify-between py-3">
            <div>
              <label className="text-sm font-medium text-gray-900">{t('system.enableAiThreadPool')}</label>
              <p className="text-xs text-gray-500 mt-1">{t('system.aiThreadPoolDesc')}</p>
            </div>
            <button
              type="button"
              onClick={() => setAiThreadPoolEnabled(!aiThreadPoolEnabled)}
              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              style={{ backgroundColor: aiThreadPoolEnabled ? '#3b82f6' : '#d1d5db' }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  aiThreadPoolEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Plugin Thread Pool Settings */}
        <div className="border-t border-gray-200 pt-4 mt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">{t('system.pluginThreadPool')}</h3>
          
          {/* Plugin Thread Pool Enabled */}
          <div className="flex items-center justify-between py-3">
            <div>
              <label className="text-sm font-medium text-gray-900">{t('system.enablePluginThreadPool')}</label>
              <p className="text-xs text-gray-500 mt-1">{t('system.pluginThreadPoolDesc')}</p>
            </div>
            <button
              type="button"
              onClick={() => setPluginThreadPoolEnabled(!pluginThreadPoolEnabled)}
              className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              style={{ backgroundColor: pluginThreadPoolEnabled ? '#f59e0b' : '#d1d5db' }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  pluginThreadPoolEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="btn btn-primary w-full flex items-center justify-center gap-2"
        >
          <Save className="w-5 h-5" />
          {saving ? t('system.saving') : t('system.saveSettings')}
        </button>
      </form>

      {/* Tencent Cloud TTS Configuration */}
      <form onSubmit={handleSubmit} className="card space-y-6">
        <div className="flex items-center gap-3 mb-4">
          <Server className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">{t('system.ttsConfig')}</h2>
        </div>

        <p className="text-sm text-gray-600">
          {t('system.ttsConfigDesc')}
          <a 
            href="https://cloud.tencent.com/document/api/1073/37995" 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-primary-600 hover:text-primary-700 ml-1 underline"
          >
            {t('system.viewDocs')}
          </a>
        </p>

        {/* SecretId */}
        <div>
          <label className="label">
            {t('system.secretId')} <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={tencentSecretId}
            onChange={(e) => setTencentSecretId(e.target.value)}
            placeholder={t('system.secretIdPlaceholder')}
            className="input"
          />
          <p className="text-xs text-gray-500 mt-1">
            {t('system.secretIdHelp')}
          </p>
        </div>

        {/* SecretKey */}
        <div>
          <label className="label">
            {t('system.secretKey')} {config?.tencent_cloud?.secret_key_set && !showTencentKey && (
              <span className="text-green-600 text-xs ml-2">{t('system.secretKeySet')}</span>
            )}
          </label>
          <div className="relative">
            <input
              type={showTencentKey ? "text" : "password"}
              value={tencentSecretKey}
              onChange={(e) => setTencentSecretKey(e.target.value)}
              placeholder={config?.tencent_cloud?.secret_key_set ? t('system.secretKeyUpdatePlaceholder') : t('system.secretKeyPlaceholder')}
              className="input pr-10"
            />
            {config?.tencent_cloud?.secret_key_set && (
              <button
                type="button"
                onClick={() => setShowTencentKey(!showTencentKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 text-sm"
              >
                {showTencentKey ? t('system.hide') : t('system.show')}
              </button>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {config?.tencent_cloud?.secret_key_set 
              ? t('system.secretKeyUpdateHelp')
              : t('system.secretKeyHelp')}
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            <strong>{t('common.tips')}:</strong>{t('system.configTip')}
          </p>
        </div>

        <button
          type="submit"
          disabled={saving || !tencentSecretId}
          className="btn btn-primary w-full flex items-center justify-center gap-2"
        >
          <Save className="w-5 h-5" />
          {saving ? t('system.saving') : t('system.saveTTSConfig')}
        </button>
      </form>

      {/* Admin Password Reset */}
      <div className="card space-y-6">
        <div className="flex items-center gap-3 mb-4">
          <Lock className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">{t('system.adminPassword')}</h2>
        </div>

        {passwordSuccess && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <CheckCircle className="w-5 h-5" />
            <span>{t('system.passwordResetSuccess')}</span>
          </div>
        )}

        {passwordError && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>{passwordError}</span>
          </div>
        )}

        {!showPasswordReset ? (
          <button
            onClick={() => setShowPasswordReset(true)}
            className="btn btn-secondary w-full flex items-center justify-center gap-2"
          >
            <Lock className="w-5 h-5" />
            {t('system.resetAdminPassword')}
          </button>
        ) : (
          <form onSubmit={handlePasswordReset} className="space-y-4">
            <div>
              <label className="label">{t('system.newPassword')}</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t('system.newPasswordPlaceholder')}
                className="input"
                required
                minLength={6}
              />
            </div>
            <div>
              <label className="label">{t('system.confirmPassword')}</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder={t('system.confirmPasswordPlaceholder')}
                className="input"
                required
                minLength={6}
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={resettingPassword}
                className="btn btn-primary flex-1 flex items-center justify-center gap-2"
              >
                <Lock className="w-5 h-5" />
                {resettingPassword ? t('system.resetting') : t('system.confirmReset')}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowPasswordReset(false)
                  setNewPassword('')
                  setConfirmPassword('')
                  setPasswordError('')
                }}
                className="btn btn-secondary flex-1"
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* System Info (Read-only) */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Server className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">{t('system.systemInfo')}</h2>
        </div>
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-gray-100">
            <span className="text-gray-600">{t('system.appName')}</span>
            <span className="font-medium">{config.app_name}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-100">
            <span className="text-gray-600">{t('system.appVersion')}</span>
            <span className="font-medium">{config.app_version}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-100">
            <span className="text-gray-600">{t('system.environment')}</span>
            <span className="font-medium">{config.environment}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-gray-600">{t('system.pluginAutoLoad')}</span>
            <span className="font-medium">{config.plugin_auto_load ? t('common.yes') : t('common.no')}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
