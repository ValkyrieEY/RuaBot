import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Trash2, Search, Filter } from 'lucide-react'

export default function MemoryManagementPage() {
  const [memories, setMemories] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState<string>('')
  const [searchId, setSearchId] = useState<string>('')

  useEffect(() => {
    loadMemories()
  }, [filterType, searchId])

  const loadMemories = async () => {
    try {
      setLoading(true)
      const data = await api.listMemories(
        filterType || undefined,
        searchId || undefined
      )
      setMemories(data)
    } catch (error) {
      console.error('Failed to load memories:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (uuid: string) => {
    if (!confirm('确定要删除这条记忆吗？')) return
    try {
      await api.deleteMemory(uuid)
      await loadMemories()
    } catch (error) {
      console.error('Failed to delete memory:', error)
      alert('删除失败')
    }
  }

  const handleClear = async (memoryType: string, targetId: string, presetUuid?: string) => {
    if (!confirm('确定要清空这条记忆吗？')) return
    try {
      await api.clearMemory(memoryType, targetId, presetUuid)
      await loadMemories()
    } catch (error) {
      console.error('Failed to clear memory:', error)
      alert('清空失败')
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 border-b border-gray-200">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">记忆管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理 AI 的对话上下文记忆</p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="pl-2 pr-8 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          >
            <option value="">全部类型</option>
            <option value="group">群组</option>
            <option value="user">用户</option>
          </select>
        </div>
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchId}
            onChange={(e) => setSearchId(e.target.value)}
            placeholder="搜索群号或用户QQ"
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-gray-50 border-b border-gray-100 text-gray-500 font-medium">
              <tr>
                <th className="px-6 py-3 w-24">类型</th>
                <th className="px-6 py-3">目标ID</th>
                <th className="px-6 py-3">预设UUID</th>
                <th className="px-6 py-3 w-24">消息数</th>
                <th className="px-6 py-3">最后活跃</th>
                <th className="px-6 py-3 w-24 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {memories.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    暂无记忆数据
                  </td>
                </tr>
              ) : (
                memories.map((memory) => (
                  <tr key={memory.uuid} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        memory.memory_type === 'group'
                          ? 'bg-blue-50 text-blue-700 border border-blue-100'
                          : 'bg-green-50 text-green-700 border border-green-100'
                      }`}>
                        {memory.memory_type === 'group' ? '群组' : '用户'}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-gray-900">{memory.target_id}</td>
                    <td className="px-6 py-4 font-mono text-xs text-gray-500">
                      {memory.preset_uuid ? (
                        <span title={memory.preset_uuid}>
                          {memory.preset_uuid.substring(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-900">{memory.message_count}</td>
                    <td className="px-6 py-4 text-gray-500">
                      {memory.last_active
                        ? new Date(memory.last_active).toLocaleString('zh-CN')
                        : '-'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleClear(memory.memory_type, memory.target_id, memory.preset_uuid)}
                          className="text-sm text-orange-600 hover:text-orange-700 font-medium hover:underline"
                        >
                          清空
                        </button>
                        <button
                          onClick={() => handleDelete(memory.uuid)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="删除记录"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
