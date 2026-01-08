import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit, Trash2, Star } from 'lucide-react'

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
      alert('保存失败')
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

  if (loading) {
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">模型管理</h2>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          <Plus className="w-4 h-4" />
          添加模型
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">名称</th>
              <th className="text-left p-3">服务商</th>
              <th className="text-left p-3">模型名称</th>
              <th className="text-left p-3">默认</th>
              <th className="text-left p-3">功能</th>
              <th className="text-left p-3">操作</th>
            </tr>
          </thead>
          <tbody>
            {models.map((model) => (
              <tr key={model.uuid} className="border-b hover:bg-gray-50">
                <td className="p-3">{model.name}</td>
                <td className="p-3">{model.provider}</td>
                <td className="p-3">{model.model_name}</td>
                <td className="p-3">
                  {model.is_default ? (
                    <Star className="w-5 h-5 text-yellow-500 fill-yellow-500" />
                  ) : (
                    <button
                      onClick={() => handleSetDefault(model.uuid)}
                      className="text-gray-400 hover:text-yellow-500"
                    >
                      <Star className="w-5 h-5" />
                    </button>
                  )}
                </td>
                <td className="p-3">
                  <div className="flex gap-2">
                    {model.supports_tools && (
                      <span className="px-2 py-1 text-xs bg-blue-100 rounded-md">工具</span>
                    )}
                    {model.supports_vision && (
                      <span className="px-2 py-1 text-xs bg-green-100 rounded-md">视觉</span>
                    )}
                  </div>
                </td>
                <td className="p-3">
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(model)}
                      className="text-blue-500 hover:text-blue-600"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(model.uuid)}
                      className="text-red-500 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl">
            <h3 className="text-xl font-semibold mb-4">
              {editingModel ? '编辑模型' : '添加模型'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">名称</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e => setFormData({ ...formData, name: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">服务商</label>
                <input
                  type="text"
                  value={formData.provider}
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="openai, anthropic, deepseek等"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">模型名称</label>
                <input
                  type="text"
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="gpt-4, claude-3等"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">API Key</label>
                <input
                  type="password"
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder={editingModel ? '留空则不更新' : '输入API Key'}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Base URL (可选)</label>
                <input
                  type="text"
                  value={formData.base_url}
                  onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="自定义API地址"
                />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.is_default}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span>设为默认</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.supports_tools}
                    onChange={(e) => setFormData({ ...formData, supports_tools: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span>支持工具调用</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.supports_vision}
                    onChange={(e) => setFormData({ ...formData, supports_vision: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <span>支持视觉</span>
                </label>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  rows={3}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                取消
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
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

