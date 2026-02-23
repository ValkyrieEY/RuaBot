import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit2, Trash2, Copy, FileText } from 'lucide-react'

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
    repetition_penalty: undefined as number | undefined,
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
      repetition_penalty: undefined,
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
      repetition_penalty: preset.repetition_penalty,
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      const data: any = { ...formData }
      if (!data.top_p) delete data.top_p
      if (!data.top_k) delete data.top_k
      if (!data.repetition_penalty) delete data.repetition_penalty

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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">预设管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理 AI 的人设和系统提示词</p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-sm hover:shadow-md"
        >
          <Plus className="w-4 h-4" />
          <span>添加预设</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {presets.map((preset) => (
          <div key={preset.uuid} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all flex flex-col group">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg text-white shadow-sm">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-gray-900 line-clamp-1" title={preset.name}>{preset.name}</h3>
                  {preset.description && (
                    <p className="text-xs text-gray-500 mt-0.5 line-clamp-1" title={preset.description}>{preset.description}</p>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleEdit(preset)}
                  className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="编辑"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleDelete(preset.uuid)}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            <div className="flex flex-wrap gap-2 mb-4">
              <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-50 text-gray-600 border border-gray-100">
                Temp: {preset.temperature}
              </span>
              <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-50 text-gray-600 border border-gray-100">
                Max: {preset.max_tokens}
              </span>
              {preset.top_p && (
                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-50 text-gray-600 border border-gray-100">
                  TopP: {preset.top_p}
                </span>
              )}
            </div>

            <div className="flex-1 bg-gray-50 rounded-lg border border-gray-100 p-3 relative group/code">
              <div className="text-xs text-gray-500 font-mono line-clamp-4 leading-relaxed">
                {preset.system_prompt}
              </div>
              <div className="absolute inset-0 bg-gray-50/50 opacity-0 group-hover/code:opacity-100 transition-opacity flex items-center justify-center rounded-lg backdrop-blur-[1px]">
                <button 
                  className="bg-white text-gray-700 text-xs px-3 py-1.5 rounded border border-gray-200 shadow-sm flex items-center gap-1.5 hover:text-blue-600 hover:border-blue-200 transition-colors"
                  onClick={() => {
                    navigator.clipboard.writeText(preset.system_prompt)
                    alert('已复制到剪贴板')
                  }}
                >
                  <Copy className="w-3 h-3" />
                  复制提示词
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between z-10 rounded-t-2xl">
              <h3 className="text-lg font-bold text-gray-900">
                {editingPreset ? '编辑预设' : '添加预设'}
              </h3>
              <button 
                onClick={() => setShowModal(false)} 
                className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500"
              >
                <span className="text-xl leading-none">×</span>
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">名称</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      placeholder="给预设起个名字"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">描述</label>
                    <input
                      type="text"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      placeholder="简单描述这个预设的作用"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-sm font-medium text-gray-700">温度 (Temperature)</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        value={formData.temperature}
                        onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-sm font-medium text-gray-700">最大Token数</label>
                      <input
                        type="number"
                        min="1"
                        value={formData.max_tokens}
                        onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5 px-3"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 pt-2 border-t border-gray-100">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide">Top P</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        placeholder="默认"
                        value={formData.top_p || ''}
                        onChange={(e) => setFormData({ ...formData, top_p: e.target.value ? parseFloat(e.target.value) : undefined })}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-2"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide">Top K</label>
                      <input
                        type="number"
                        min="1"
                        placeholder="默认"
                        value={formData.top_k || ''}
                        onChange={(e) => setFormData({ ...formData, top_k: e.target.value ? parseInt(e.target.value) : undefined })}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-2"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-xs font-bold text-gray-500 uppercase tracking-wide">重复惩罚</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="2"
                        placeholder="默认"
                        value={formData.repetition_penalty || ''}
                        onChange={(e) => setFormData({ ...formData, repetition_penalty: e.target.value ? parseFloat(e.target.value) : undefined })}
                        className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-2"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5 flex flex-col h-full">
                  <label className="block text-sm font-medium text-gray-700">系统提示词</label>
                  <textarea
                    value={formData.system_prompt}
                    onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                    className="block w-full flex-1 rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono py-2.5 px-3 min-h-[240px]"
                    placeholder="输入系统提示词，定义AI的角色和行为..."
                  />
                  <div className="mt-2 text-xs text-gray-500 bg-blue-50 p-3 rounded-lg border border-blue-100">
                    <p className="font-bold text-blue-800 mb-1.5">可用变量 (点击复制)：</p>
                    <div className="flex flex-wrap gap-1.5">
                      {['{user_id}', '{user_name}', '{group_id}', '{group_name}', '{current_time}'].map(v => (
                        <button 
                          key={v} 
                          className="px-1.5 py-0.5 bg-white border border-blue-200 rounded text-blue-600 hover:bg-blue-100 transition-colors font-mono"
                          onClick={() => navigator.clipboard.writeText(v)}
                          title="点击复制"
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
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
