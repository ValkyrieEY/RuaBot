import { useState, FormEvent, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { Settings as SettingsIcon, Lock, Save, AlertCircle, CheckCircle } from 'lucide-react'

interface SystemConfig {
  app_name: string
  app_version: string
  environment: string
  log_level: string
  plugin_auto_load: boolean
  web_ui_enabled: boolean
  plugin_thread_pool_enabled?: boolean
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
  
  // Plugin Thread Pool config
  const [pluginThreadPoolEnabled, setPluginThreadPoolEnabled] = useState(true)
  
  // 
  const loadingRequestRef = useRef(0)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    const currentRequest = ++loadingRequestRef.current
    setLoading(true)
    setError('') // 
    
    try {
      const data = await api.getSystemConfig()
      
      // 
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      // 
      if (!data || typeof data !== 'object') {
        throw new Error('Invalid configuration data received')
      }
      
      setConfig(data)
      // Load Plugin Thread Pool config
      setPluginThreadPoolEnabled(data.plugin_thread_pool_enabled !== undefined ? data.plugin_thread_pool_enabled : true)
    } catch (err: any) {
      // 
      if (currentRequest !== loadingRequestRef.current) {
        return
      }
      
      console.error('Failed to load system config:', err)
      const errorMessage = err.response?.data?.detail || 
                          err.message || 
                          t('system.loadConfigFailed')
      setError(errorMessage)
    } finally {
      // 
      if (currentRequest === loadingRequestRef.current) {
        setLoading(false)
      }
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
        log_level: config.log_level,
        plugin_thread_pool_enabled: pluginThreadPoolEnabled,
      }
      
      await api.updateSystemConfig(updateData)
      setSuccess(true)
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

        {/* Plugin Thread Pool Settings */}
        <div className="border-t border-gray-200 pt-4 mt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">{t('system.pluginThreadPool')}</h3>
          
          {/* Plugin Thread Pool Enabled */}
          <div className="flex items-center justify-between gap-3 py-3">
            <div className="min-w-0 pr-2">
              <label className="text-sm font-medium text-gray-900 whitespace-nowrap">{t('system.enablePluginThreadPool')}</label>
              <p className="text-xs text-gray-500 mt-1 truncate">{t('system.pluginThreadPoolDesc')}</p>
            </div>
            <div className="flex-shrink-0">
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
          <SettingsIcon className="w-6 h-6 text-primary-600" />
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
