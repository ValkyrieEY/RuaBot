import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Trash2, Search } from 'lucide-react'

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
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">记忆管理</h2>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex gap-4 mb-4">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 border rounded-lg"
          >
            <option value="">全部类型</option>
            <option value="group">群组</option>
            <option value="user">用户</option>
          </select>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              placeholder="搜索群号或用户QQ"
              className="w-full pl-10 pr-3 py-2 border rounded-lg bg-white"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-3">类型</th>
                <th className="text-left p-3">目标ID</th>
                <th className="text-left p-3">预设UUID</th>
                <th className="text-left p-3">消息数</th>
                <th className="text-left p-3">最后活跃</th>
                <th className="text-left p-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {memories.map((memory) => (
                <tr key={memory.uuid} className="border-b hover:bg-gray-50">
                  <td className="p-3">
                    <span className={`px-2 py-1 text-xs rounded ${
                      memory.memory_type === 'group'
                        ? 'bg-blue-100'
                        : 'bg-green-100'
                    }`}>
                      {memory.memory_type === 'group' ? '群组' : '用户'}
                    </span>
                  </td>
                  <td className="p-3">{memory.target_id}</td>
                  <td className="p-3">
                    {memory.preset_uuid ? (
                      <span className="text-sm text-gray-600">
                        {memory.preset_uuid.substring(0, 8)}...
                      </span>
                    ) : (
                      <span className="text-gray-400">无</span>
                    )}
                  </td>
                  <td className="p-3">{memory.message_count}</td>
                  <td className="p-3">
                    {memory.last_active
                      ? new Date(memory.last_active).toLocaleString('zh-CN')
                      : '-'}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleClear(memory.memory_type, memory.target_id, memory.preset_uuid)}
                        className="text-orange-500 hover:text-orange-600"
                        title="清空记忆"
                      >
                        清空
                      </button>
                      <button
                        onClick={() => handleDelete(memory.uuid)}
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
          {memories.length === 0 && (
            <div className="text-center py-8 text-gray-500">暂无记忆数据</div>
          )}
        </div>
      </div>
    </div>
  )
}

