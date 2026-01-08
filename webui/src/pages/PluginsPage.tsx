import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, type PluginInfo } from '@/utils/api'
import { 
  Play, 
  Square, 
  RotateCw, 
  Settings, 
  AlertCircle, 
  Upload,
  X,
  Save,
  CheckCircle,
  Trash2
} from 'lucide-react'

interface PluginConfigModalProps {
  pluginName: string
  isOpen: boolean
  onClose: () => void
  onSave: (config: any) => void
}

function PluginConfigModal({ pluginName, isOpen, onClose, onSave }: PluginConfigModalProps) {
  const [config, setConfig] = useState<any>({})
  const [schema, setSchema] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen && pluginName) {
      loadConfigSchema()
    }
  }, [isOpen, pluginName])

  const loadConfigSchema = async () => {
    try {
      setLoading(true)
      const data = await api.getPluginConfigSchema(pluginName)
      setSchema(data)
      // Use current_config if available, otherwise fall back to default_config
      let loadedConfig = data.current_config || data.default_config || {}
      
      // Convert string format to array format for array fields (compatibility)
      if (data.config_schema) {
        Object.keys(data.config_schema).forEach((key) => {
          const field = data.config_schema[key]
          if (field.type === 'array') {
            // Initialize as array if not exists
            if (!(key in loadedConfig)) {
              loadedConfig[key] = []
            }
            // Convert string to array if it's a string
            else if (typeof loadedConfig[key] === 'string') {
              const str = loadedConfig[key].trim()
              if (str) {
                loadedConfig[key] = str.split(/[\n,\s]+/).filter((item: string) => item.trim())
              } else {
                loadedConfig[key] = []
              }
            }
            // Ensure it's an array
            else if (!Array.isArray(loadedConfig[key])) {
              loadedConfig[key] = []
            }
          }
        })
      }
      
      setConfig(loadedConfig)
    } catch (error) {
      console.error('Failed to load config schema:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updatePluginConfig(pluginName, config)
      // Reload config schema to get updated values
      await loadConfigSchema()
      onSave(config)
      onClose()
    } catch (error: any) {
      alert(error.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">插件设置: {pluginName}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          ) : schema && schema.config_schema ? (
            <div className="space-y-4">
              {Object.entries(schema.config_schema).map(([key, field]: [string, any]) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label || key}
                    {field.required && <span className="text-red-500 ml-1">*</span>}
                  </label>
                  {field.description && (
                    <p className="text-xs text-gray-500 mb-2">{field.description}</p>
                  )}
                  {field.type === 'string' && (
                    <input
                      type="text"
                      value={config[key] || ''}
                      onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                      className="input w-full"
                      required={field.required}
                    />
                  )}
                  {field.type === 'number' && (
                    <input
                      type="number"
                      value={config[key] ?? ''}
                      onChange={(e) => {
                        const value = e.target.value
                        // Handle empty string - keep current value or use default from schema
                        if (value === '') {
                          // Don't update if empty, let user clear it or use default
                          const defaultValue = schema?.default_config?.[key] ?? config[key] ?? 0
                          setConfig({ ...config, [key]: defaultValue })
                        } else {
                          const numValue = Number(value)
                          // Only update if it's a valid number
                          if (!isNaN(numValue)) {
                            setConfig({ ...config, [key]: numValue })
                          }
                        }
                      }}
                      className="input w-full"
                      required={field.required}
                    />
                  )}
                  {field.type === 'boolean' && (
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={config[key] || false}
                        onChange={(e) => setConfig({ ...config, [key]: e.target.checked })}
                        className="rounded border-gray-300 text-primary-600"
                      />
                      <span className="text-sm text-gray-600">启用</span>
                    </label>
                  )}
                  {field.type === 'select' && (
                    <select
                      value={config[key] || ''}
                      onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                      className="input w-full"
                      required={field.required}
                    >
                      {field.options?.map((opt: any) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  )}
                  {field.type === 'textarea' && (
                    <textarea
                      value={config[key] || ''}
                      onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                      className="input w-full"
                      rows={4}
                      required={field.required}
                    />
                  )}
                  {field.type === 'array' && (
                    <div className="space-y-2">
                      {(!config[key] || !Array.isArray(config[key]) || config[key].length === 0) ? (
                        <div className="text-sm text-gray-500 py-2 border border-dashed border-gray-300 rounded p-3 text-center">
                          暂无项目，点击下方"添加项"按钮添加
                        </div>
                      ) : (
                        (config[key] || []).map((item: any, index: number) => (
                          <div key={index} className="flex items-center gap-2">
                            <input
                              type="text"
                              value={item || ''}
                              onChange={(e) => {
                                const currentArray = Array.isArray(config[key]) ? config[key] : []
                                const newArray = [...currentArray]
                                newArray[index] = e.target.value
                                setConfig({ ...config, [key]: newArray })
                              }}
                              className="input flex-1"
                              placeholder={field.items?.type === 'string' ? '输入QQ号' : '输入值'}
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const currentArray = Array.isArray(config[key]) ? config[key] : []
                                const newArray = [...currentArray]
                                newArray.splice(index, 1)
                                setConfig({ ...config, [key]: newArray })
                              }}
                              className="btn btn-secondary px-3 py-1 text-sm hover:bg-red-50 hover:text-red-600"
                            >
                              删除
                            </button>
                          </div>
                        ))
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          const currentArray = Array.isArray(config[key]) ? config[key] : []
                          setConfig({ ...config, [key]: [...currentArray, ''] })
                        }}
                        className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
                      >
                        <span className="text-lg">+</span>
                        <span>添加项</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              此插件没有可配置项
            </div>
          )}
        </div>
        
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="btn btn-secondary"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleUpload = async () => {
    if (!file) {
      setError('请选择文件')
      return
    }

    setUploading(true)
    setError('')
    setSuccess(false)

    try {
      await api.uploadPlugin(file)
      setSuccess(true)
      setTimeout(() => {
        onSuccess()
        onClose()
        setFile(null)
        setSuccess(false)
      }, 1500)
    } catch (err: any) {
      setError(err.response?.data?.detail || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            上传插件
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          {success ? (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle className="w-5 h-5" />
              <span>上传成功！</span>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  选择 ZIP 文件
                </label>
                <input
                  type="file"
                  accept=".zip"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="input w-full"
                />
              </div>
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                  {error}
                </div>
              )}
            </>
          )}
        </div>
        
        {!success && (
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <button
              onClick={onClose}
              className="btn btn-secondary"
              disabled={uploading}
            >
              取消
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || !file}
              className="btn btn-primary flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {uploading ? '上传中...' : '上传'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function PluginsPage() {
  const { t } = useTranslation()
  const [plugins, setPlugins] = useState<PluginInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [configPlugin, setConfigPlugin] = useState<string | null>(null)

  useEffect(() => {
    const loadInitialData = async () => {
      await loadPlugins()
      setInitialLoading(false)
    }
    loadInitialData()
  }, [])

  const loadPlugins = async () => {
    try {
      setLoading(true)
      const data = await api.getPlugins()
      console.log('Loaded plugins:', data)
      setPlugins(data)
    } catch (error) {
      console.error('Failed to load plugins:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAction = async (pluginName: string, action: string) => {
    setActionLoading(pluginName)
    try {
      await api.pluginAction(pluginName, action)
      await loadPlugins() // Reload plugins after action
    } catch (error: any) {
      alert(error.response?.data?.detail || t('plugins.actionFailed'))
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (pluginName: string) => {
    if (!confirm(`确定要删除插件 "${pluginName}" 吗？此操作将删除插件数据库记录和文件目录，无法恢复！`)) {
      return
    }
    
    setActionLoading(pluginName)
    try {
      await api.deletePlugin(pluginName)
      await loadPlugins() // Reload plugins after deletion
      alert(`插件 "${pluginName}" 已成功删除`)
    } catch (error: any) {
      alert(error.response?.data?.detail || '删除插件失败')
    } finally {
      setActionLoading(null)
    }
  }

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-full overflow-x-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="min-w-0 flex-shrink">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('plugins.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('plugins.description')}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Upload className="w-4 h-4" />
            {t('plugins.uploadPlugin')}
          </button>
          <button
            onClick={loadPlugins}
            className="btn btn-secondary flex items-center gap-2"
          >
            <RotateCw className="w-4 h-4" />
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {plugins.length === 0 ? (
        <div className="card text-center py-12">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
            <AlertCircle className="w-8 h-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {t('plugins.noPlugins')}
          </h3>
          <p className="text-gray-500 mb-4">{t('plugins.noPluginsDescription')}</p>
          <button
            onClick={() => setShowUploadModal(true)}
            className="btn btn-primary flex items-center gap-2 mx-auto"
          >
            <Upload className="w-4 h-4" />
            {t('plugins.uploadPlugin')}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {plugins.map((plugin) => (
            <div key={plugin.name} className="card flex flex-col h-full">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1 min-h-[80px]">
                  <h3 className="font-semibold text-gray-900 mb-1">{plugin.name}</h3>
                  {(plugin.metadata?.description || plugin.description) && (
                    <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                      {plugin.metadata?.description || plugin.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    {(plugin.metadata?.version || plugin.version) && (
                      <span>v{plugin.metadata?.version || plugin.version}</span>
                    )}
                    {(plugin.metadata?.author || plugin.author) && (
                      <>
                        {(plugin.metadata?.version || plugin.version) && <span>•</span>}
                        <span>{plugin.metadata?.author || plugin.author}</span>
                      </>
                    )}
                  </div>
                  {(plugin as any).adapter && (
                    <div className="text-xs text-gray-500 mt-1">
                      {t('plugins.adapter')}: <span className="font-medium">{(plugin as any).adapter}</span>
                    </div>
                  )}
                </div>
                <div
                  className={`px-2 py-1 rounded text-xs font-medium flex-shrink-0 h-fit ${
                    plugin.enabled
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {plugin.enabled ? t('common.enabled') : t('common.disabled')}
                </div>
              </div>

              <div className="flex gap-2 mt-auto">
                {plugin.enabled === true ? (
                  <>
                    <button
                      onClick={() => handleAction(plugin.name, 'reload')}
                      disabled={actionLoading === plugin.name || loading}
                      className="btn btn-secondary flex-1 flex items-center justify-center gap-2 text-sm"
                    >
                      <RotateCw className="w-4 h-4" />
                      {t('plugins.reload')}
                    </button>
                    <button
                      onClick={() => handleAction(plugin.name, 'disable')}
                      disabled={actionLoading === plugin.name || loading}
                      className="btn btn-secondary flex-1 flex items-center justify-center gap-2 text-sm"
                    >
                      <Square className="w-4 h-4" />
                      {t('plugins.disable')}
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => handleAction(plugin.name, 'enable')}
                    disabled={actionLoading === plugin.name || loading}
                    className="btn btn-primary flex-1 flex items-center justify-center gap-2 text-sm"
                  >
                    <Play className="w-4 h-4" />
                    {t('plugins.enable')}
                  </button>
                )}
                <button
                  onClick={() => setConfigPlugin(plugin.name)}
                  disabled={loading}
                  className="btn btn-secondary p-2"
                  title="配置"
                >
                  <Settings className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(plugin.name)}
                  disabled={actionLoading === plugin.name || loading}
                  className="btn btn-danger p-2"
                  title="删除插件"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onSuccess={loadPlugins}
      />

      <PluginConfigModal
        pluginName={configPlugin || ''}
        isOpen={configPlugin !== null}
        onClose={() => setConfigPlugin(null)}
        onSave={loadPlugins}
      />
    </div>
  )
}
