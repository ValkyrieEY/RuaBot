import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit, Trash2 } from 'lucide-react'

export default function PresetManagementPage() {
  const [presets, setPresets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingPreset, setEditingPreset] = useState<any>(null)
  const [formData, setFormData] = useState({
    name: '',
    system_prompt: '',
    temperature: 1.0,
    max_tokens: 2000,
    description: '',
    top_p: undefined as number | undefined,
    top_k: undefined as number | undefined,
  })

  useEffect(() => {
    loadPresets()
  }, [])

  const loadPresets = async () => {
    try {
      setLoading(true)
      const data = await api.listPresets()
      setPresets(data)
    } catch (error) {
      console.error('Failed to load presets:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingPreset(null)
    setFormData({
      name: '',
      system_prompt: '',
      temperature: 1.0,
      max_tokens: 2000,
      description: '',
      top_p: undefined,
      top_k: undefined,
    })
    setShowModal(true)
  }

  const handleEdit = (preset: any) => {
    setEditingPreset(preset)
    setFormData({
      name: preset.name,
      system_prompt: preset.system_prompt,
      temperature: preset.temperature,
      max_tokens: preset.max_tokens,
      description: preset.description || '',
      top_p: preset.top_p,
      top_k: preset.top_k,
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      const data: any = { ...formData }
      if (!data.top_p) delete data.top_p
      if (!data.top_k) delete data.top_k

      if (editingPreset) {
        await api.updatePreset(editingPreset.uuid, data)
      } else {
        await api.createPreset(data)
      }
      setShowModal(false)
      await loadPresets()
    } catch (error) {
      console.error('Failed to save preset:', error)
      alert('保存失败')
    }
  }

  const handleDelete = async (uuid: string) => {
    if (!confirm('确定要删除这个预设吗？')) return
    try {
      await api.deletePreset(uuid)
      await loadPresets()
    } catch (error) {
      console.error('Failed to delete preset:', error)
      alert('删除失败')
    }
  }

  if (loading) {
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">预设管理</h2>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          <Plus className="w-4 h-4" />
          添加预设
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {presets.map((preset) => (
          <div
            key={preset.uuid}
            className="bg-white rounded-xl shadow p-4"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-lg">{preset.name}</h3>
              <div className="flex gap-2">
                <button
                  onClick={() => handleEdit(preset)}
                  className="text-blue-500 hover:text-blue-600"
                >
                  <Edit className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(preset.uuid)}
                  className="text-red-500 hover:text-red-600"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            {preset.description && (
              <p className="text-sm text-gray-600 mb-2">
                {preset.description}
              </p>
            )}
            <div className="text-sm space-y-1">
              <div>温度: {preset.temperature}</div>
              <div>最大Token: {preset.max_tokens}</div>
              {preset.top_p && <div>Top P: {preset.top_p}</div>}
              {preset.top_k && <div>Top K: {preset.top_k}</div>}
            </div>
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-gray-500 line-clamp-3">
                {preset.system_prompt}
              </p>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-semibold mb-4">
              {editingPreset ? '编辑预设' : '添加预设'}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">名称</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">系统提示词</label>
                <textarea
                  value={formData.system_prompt}
                  onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                  rows={8}
                  placeholder="输入系统提示词，定义AI的角色和行为..."
                />
                <div className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-xs font-medium text-gray-700 mb-2">可用变量（点击复制）：</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100" 
                            onClick={() => navigator.clipboard.writeText('{user_id}')}
                            title="点击复制">
                        {'{user_id}'}
                      </code>
                      <span className="text-gray-500">用户QQ号</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{user_name}')}
                            title="点击复制">
                        {'{user_name}'}
                      </code>
                      <span className="text-gray-500">用户名称（优先群名片）</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{user_nickname}')}
                            title="点击复制">
                        {'{user_nickname}'}
                      </code>
                      <span className="text-gray-500">用户昵称（QQ昵称）</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{group_id}')}
                            title="点击复制">
                        {'{group_id}'}
                      </code>
                      <span className="text-gray-500">群号</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{group_name}')}
                            title="点击复制">
                        {'{group_name}'}
                      </code>
                      <span className="text-gray-500">群名称</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{current_time}')}
                            title="点击复制">
                        {'{current_time}'}
                      </code>
                      <span className="text-gray-500">当前时间</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{current_date}')}
                            title="点击复制">
                        {'{current_date}'}
                      </code>
                      <span className="text-gray-500">当前日期</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <code className="px-1.5 py-0.5 bg-white border rounded cursor-pointer hover:bg-gray-100"
                            onClick={() => navigator.clipboard.writeText('{current_time_iso}')}
                            title="点击复制">
                        {'{current_time_iso}'}
                      </code>
                      <span className="text-gray-500">ISO时间</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">温度 (Temperature)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={formData.temperature}
                    onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">最大Token数</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.max_tokens}
                    onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Top P (可选)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={formData.top_p || ''}
                    onChange={(e) => setFormData({ ...formData, top_p: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Top K (可选)</label>
                  <input
                    type="number"
                    min="1"
                    value={formData.top_k || ''}
                    onChange={(e) => setFormData({ ...formData, top_k: e.target.value ? parseInt(e.target.value) : undefined })}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
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

