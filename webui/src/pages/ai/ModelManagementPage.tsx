import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit2, Trash2, Star, Cpu, Eye, Wrench, Info } from 'lucide-react'

export default function ModelManagementPage() {
  const [models, setModels] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingModel, setEditingModel] = useState<any>(null)
  const [formData, setFormData] = useState({
    name: '',
    provider: '',
    model_name: '',
    api_key: '',
    base_url: '',
    is_default: false,
    supports_tools: false,
    supports_vision: false,
    description: '',
    config: {
      api_format: 'openai' as 'openai' | 'gemini'
    }
  })

  useEffect(() => {
    loadModels()
  }, [])

  const loadModels = async () => {
    try {
      setLoading(true)
      const data = await api.listModels()
      setModels(data)
    } catch (error) {
      console.error('Failed to load models:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingModel(null)
    setFormData({
      name: '',
      provider: '',
      model_name: '',
      api_key: '',
      base_url: '',
      is_default: false,
      supports_tools: false,
      supports_vision: false,
      description: '',
      config: {
        api_format: 'openai'
      }
    })
    setShowModal(true)
  }

  const handleEdit = (model: any) => {
    setEditingModel(model)
    setFormData({
      name: model.name,
      provider: model.provider,
      model_name: model.model_name,
      api_key: '', // Don't show API key for security
      base_url: model.base_url || '',
      is_default: model.is_default,
      supports_tools: model.supports_tools,
      supports_vision: model.supports_vision,
      description: model.description || '',
      config: {
        api_format: model.config?.api_format || 'openai'
      }
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      if (editingModel) {
        await api.updateModel(editingModel.uuid, formData)
      } else {
        await api.createModel(formData)
      }
      setShowModal(false)
      await loadModels()
    } catch (error) {
      console.error('Failed to save model:', error)
      alert('保存失败: ' + (error as any).message)
    }
  }

  const handleDelete = async (uuid: string) => {
    if (!confirm('确定要删除这个模型吗？')) return
    try {
      await api.deleteModel(uuid)
      await loadModels()
    } catch (error) {
      console.error('Failed to delete model:', error)
      alert('删除失败')
    }
  }

  const handleSetDefault = async (uuid: string) => {
    try {
      await api.updateModel(uuid, { is_default: true })
      await loadModels()
    } catch (error) {
      console.error('Failed to set default:', error)
      alert('设置失败')
    }
  }

  const getApiFormatBadge = (model: any) => {
    const format = model.config?.api_format || 'openai'
    if (format === 'gemini') {
      return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 border border-purple-200">Gemini</span>
    }
    return <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">OpenAI</span>
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">模型管理</h1>
          <p className="text-sm text-gray-500 mt-1">配置 LLM 接口，支持 OpenAI 和 Gemini 格式</p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-sm hover:shadow-md"
        >
          <Plus className="w-4 h-4" />
          <span>添加模型</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {models.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-xl border border-gray-200 border-dashed">
            <Cpu className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">暂无模型配置</p>
          </div>
        ) : (
          models.map((model) => (
            <div key={model.uuid} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all group">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg shadow-sm">
                      <Cpu className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-lg text-gray-900 truncate">{model.name}</h3>
                        {model.is_default && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
                            <Star className="w-3 h-3 fill-current" />
                            默认
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 font-mono mt-0.5 flex items-center gap-1.5">
                        <span>{model.provider}</span>
                        <span className="text-gray-300">/</span>
                        <span>{model.model_name}</span>
                        <span className="text-gray-300">|</span>
                        {getApiFormatBadge(model)}
                      </div>
                    </div>
                  </div>
                  
                  {model.description && (
                    <p className="text-sm text-gray-600 mb-3 ml-12 line-clamp-2 leading-relaxed">{model.description}</p>
                  )}
                  
                  <div className="flex flex-wrap gap-2 ml-12">
                    {model.supports_tools && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-green-700 bg-green-50 border border-green-100">
                        <Wrench className="w-3.5 h-3.5" />
                        工具调用
                      </span>
                    )}
                    {model.supports_vision && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-pink-700 bg-pink-50 border border-pink-100">
                        <Eye className="w-3.5 h-3.5" />
                        视觉识别
                      </span>
                    )}
                    {model.base_url && (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200">
                        <Info className="w-3.5 h-3.5" />
                        自定义端点
                      </span>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {!model.is_default && (
                    <button
                      onClick={() => handleSetDefault(model.uuid)}
                      className="p-2 text-gray-400 hover:text-amber-500 hover:bg-amber-50 rounded-lg transition-colors"
                      title="设为默认"
                    >
                      <Star className="w-4.5 h-4.5" />
                    </button>
                  )}
                  <button
                    onClick={() => handleEdit(model)}
                    className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="w-4.5 h-4.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(model.uuid)}
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4.5 h-4.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal ... (unchanged logic, just styling tweaks if needed) */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* ... Modal content similar to previous, ensuring clean layout ... */}
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between z-10 rounded-t-2xl">
              <h3 className="text-lg font-bold text-gray-900">
                {editingModel ? '编辑模型' : '添加模型'}
              </h3>
              <button 
                onClick={() => setShowModal(false)} 
                className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500"
              >
                <span className="text-xl leading-none">×</span>
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              <div className="space-y-4">
                <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-1 h-4 bg-blue-500 rounded-full"></span>
                  基本信息
                </h4>
                
                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700">
                    模型名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                    placeholder="例如: GPT-4 Turbo"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">
                      服务商 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.provider}
                      onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                      className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      placeholder="openai"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">
                      模型标识 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.model_name}
                      onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                      className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      placeholder="gpt-4-turbo"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700">描述</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                    rows={2}
                    placeholder="简要描述此模型的用途..."
                  />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-1 h-4 bg-purple-500 rounded-full"></span>
                  API 配置
                </h4>

                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    API 格式 <span className="text-red-500">*</span>
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setFormData({ 
                        ...formData, 
                        config: { ...formData.config, api_format: 'openai' }
                      })}
                      className={`p-3 border rounded-xl text-left transition-all ${
                        formData.config.api_format === 'openai'
                          ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="font-bold text-sm text-gray-900">OpenAI 格式</div>
                      <div className="text-xs text-gray-500 mt-0.5">GPT, Claude, DeepSeek 等</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setFormData({ 
                        ...formData, 
                        config: { ...formData.config, api_format: 'gemini' }
                      })}
                      className={`p-3 border rounded-xl text-left transition-all ${
                        formData.config.api_format === 'gemini'
                          ? 'border-purple-500 bg-purple-50 ring-1 ring-purple-500'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      <div className="font-bold text-sm text-gray-900">Gemini 格式</div>
                      <div className="text-xs text-gray-500 mt-0.5">Google Gemini API</div>
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700">
                    API Key {editingModel && <span className="text-gray-400 font-normal text-xs">(留空则不更新)</span>}
                  </label>
                  <input
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono py-2.5 px-3"
                    placeholder="sk-..."
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-sm font-medium text-gray-700">
                    Base URL <span className="text-gray-400 font-normal text-xs">(可选)</span>
                  </label>
                  <input
                    type="text"
                    value={formData.base_url}
                    onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                    className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono py-2.5 px-3"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-bold text-gray-900 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-1 h-4 bg-green-500 rounded-full"></span>
                  功能特性
                </h4>

                <div className="space-y-3">
                  <label className="flex items-center gap-3 cursor-pointer select-none p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={formData.is_default}
                      onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-gray-700">设为默认模型</span>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer select-none p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={formData.supports_tools}
                      onChange={(e) => setFormData({ ...formData, supports_tools: e.target.checked })}
                      className="w-4 h-4 text-green-600 rounded border-gray-300 focus:ring-green-500"
                    />
                    <span className="text-sm font-medium text-gray-700">支持工具调用 (Function Calling)</span>
                  </label>

                  <label className="flex items-center gap-3 cursor-pointer select-none p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                    <input
                      type="checkbox"
                      checked={formData.supports_vision}
                      onChange={(e) => setFormData({ ...formData, supports_vision: e.target.checked })}
                      className="w-4 h-4 text-pink-600 rounded border-gray-300 focus:ring-pink-500"
                    />
                    <span className="text-sm font-medium text-gray-700">支持视觉识别 (Vision)</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="sticky bottom-0 bg-gray-50 px-6 py-4 flex gap-3 justify-end border-t border-gray-100 rounded-b-2xl">
              <button
                onClick={() => setShowModal(false)}
                className="px-5 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-xl hover:bg-white hover:text-gray-900 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors shadow-sm"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
