import { useState, FormEvent, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { Settings as SettingsIcon, Lock, Save, AlertCircle, User } from 'lucide-react'
import { useToast } from '@/components/Toast'
import { useAuthStore } from '@/store/authStore'

interface SystemConfig {
  app_name: string
  app_version: string
  environment: string
  log_level: string
  plugin_auto_load: boolean
  web_ui_enabled: boolean
  web_ui_username?: string
  blocking_task_pool_enabled?: boolean
  blocking_task_pool_max_workers?: number
}

export default function SystemPage() {
  const { t } = useTranslation()
  const toast = useToast()
  const checkAuth = useAuthStore((state) => state.checkAuth)
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  
  // Admin account
  const [adminUsername, setAdminUsername] = useState('')
  const [savingUsername, setSavingUsername] = useState(false)
  const [showPasswordReset, setShowPasswordReset] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [resettingPassword, setResettingPassword] = useState(false)
  
  // Blocking Task Pool config
  const [blockingTaskPoolEnabled, setBlockingTaskPoolEnabled] = useState(true)
  const [blockingTaskPoolMaxWorkers, setBlockingTaskPoolMaxWorkers] = useState(0)
  
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
      setAdminUsername(data.web_ui_username || 'admin')
      // Load Blocking Task Pool config
      setBlockingTaskPoolEnabled(data.blocking_task_pool_enabled !== undefined ? data.blocking_task_pool_enabled : true)
      setBlockingTaskPoolMaxWorkers(data.blocking_task_pool_max_workers !== undefined ? data.blocking_task_pool_max_workers : 0)
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
    setError('')

    try {
      const updateData: any = {
        web_ui_enabled: config.web_ui_enabled,
        log_level: config.log_level,
        blocking_task_pool_enabled: blockingTaskPoolEnabled,
        blocking_task_pool_max_workers: blockingTaskPoolMaxWorkers,
      }
      
      await api.updateSystemConfig(updateData)
      toast.success(t('system.settingsSaved'))
      // Reload config after saving to ensure UI reflects saved values
      await loadConfig()
    } catch (err: any) {
      const message = err.response?.data?.detail || t('system.saveFailed')
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  const handleUsernameUpdate = async (e: FormEvent) => {
    e.preventDefault()
    if (!config) return

    const nextUsername = adminUsername.trim()
    if (nextUsername.length < 3 || nextUsername.length > 64) {
      toast.warning(t('system.usernameInvalid'))
      return
    }
    if (/\s/.test(nextUsername)) {
      toast.warning(t('system.usernameNoWhitespace'))
      return
    }

    setSavingUsername(true)

    try {
      const result = await api.updateAdminUsername({ username: nextUsername })
      const savedUsername = result?.username || nextUsername
      setConfig({ ...config, web_ui_username: savedUsername })
      setAdminUsername(savedUsername)
      await checkAuth()
      toast.success(t('system.usernameUpdateSuccess'))
    } catch (err: any) {
      const message = err.response?.data?.detail || t('system.usernameUpdateFailed')
      toast.error(message)
    } finally {
      setSavingUsername(false)
    }
  }

  const handlePasswordReset = async (e: FormEvent) => {
    e.preventDefault()
    
    if (newPassword.length < 6) {
      toast.warning(t('system.passwordTooShort'))
      return
    }
    
    if (newPassword !== confirmPassword) {
      toast.warning(t('system.passwordMismatch'))
      return
    }

    setResettingPassword(true)

    try {
      await api.resetAdminPassword({ password: newPassword })
      toast.success(t('system.passwordResetSuccess'))
      setNewPassword('')
      setConfirmPassword('')
      setShowPasswordReset(false)
    } catch (err: any) {
      const message = err.response?.data?.detail || t('system.passwordResetFailed')
      toast.error(message)
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

        {/* Blocking Task Pool Settings */}
        <div className="border-t border-gray-200 pt-4 mt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">{t('system.blockingTaskPool')}</h3>
          
          {/* Blocking Task Pool Enabled */}
          <div className="flex items-center justify-between gap-3 py-3">
            <div className="min-w-0 pr-2">
              <label className="text-sm font-medium text-gray-900 whitespace-nowrap">{t('system.enableBlockingTaskPool')}</label>
              <p className="text-xs text-gray-500 mt-1 truncate">{t('system.blockingTaskPoolDesc')}</p>
            </div>
            <div className="flex-shrink-0">
              <button
                type="button"
                onClick={() => setBlockingTaskPoolEnabled(!blockingTaskPoolEnabled)}
                className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                style={{ backgroundColor: blockingTaskPoolEnabled ? '#f59e0b' : '#d1d5db' }}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    blockingTaskPoolEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-900">{t('system.blockingTaskPoolWorkers')}</label>
            <input
              type="number"
              min="0"
              step="1"
              value={blockingTaskPoolMaxWorkers}
              onChange={(e) => setBlockingTaskPoolMaxWorkers(Math.max(0, Number.parseInt(e.target.value || '0', 10) || 0))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-500">{t('system.blockingTaskPoolWorkersDesc')}</p>
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

      {/* Admin Account */}
      <div className="card space-y-6">
        <div className="flex items-center gap-3 mb-4">
          <User className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900">{t('system.adminAccount')}</h2>
        </div>

        <form onSubmit={handleUsernameUpdate} className="space-y-4">
          <div>
            <label className="label">{t('system.adminUsername')}</label>
            <input
              type="text"
              value={adminUsername}
              onChange={(e) => setAdminUsername(e.target.value)}
              placeholder={t('system.adminUsernamePlaceholder')}
              className="input"
              required
              minLength={3}
              maxLength={64}
            />
            <p className="text-xs text-gray-500 mt-2">{t('system.adminUsernameHelp')}</p>
          </div>
          <button
            type="submit"
            disabled={savingUsername || adminUsername.trim() === (config.web_ui_username || 'admin')}
            className="btn btn-secondary w-full flex items-center justify-center gap-2"
          >
            <User className="w-5 h-5" />
            {savingUsername ? t('system.savingUsername') : t('system.saveAdminUsername')}
          </button>
        </form>

        <div className="border-t border-gray-200 pt-6">
          <div className="flex items-center gap-3 mb-4">
            <Lock className="w-5 h-5 text-primary-600" />
            <h3 className="text-base font-semibold text-gray-900">{t('system.adminPassword')}</h3>
          </div>

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
                }}
                className="btn btn-secondary flex-1"
              >
                {t('common.cancel')}
              </button>
            </div>
          </form>
        )}
        </div>
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
