import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit, Trash2, Power, PowerOff, RefreshCw, Plug, Unplug, Wrench } from 'lucide-react'

export default function MCPManagementPage() {
  const [servers, setServers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingServer, setEditingServer] = useState<any>(null)
  const [formData, setFormData] = useState({
    name: '',
    mode: 'stdio',
    enabled: false,
    description: '',
    command: '',
    args: [] as string[],
    env: {} as Record<string, string>,
    url: '',
    headers: {} as Record<string, string>,
    timeout: 10,
  })
  const [newArg, setNewArg] = useState('')
  const [newEnvKey, setNewEnvKey] = useState('')
  const [newEnvValue, setNewEnvValue] = useState('')
  const [newHeaderKey, setNewHeaderKey] = useState('')
  const [newHeaderValue, setNewHeaderValue] = useState('')
  const [expandedServer, setExpandedServer] = useState<string | null>(null)
  const [serverTools, setServerTools] = useState<Record<string, any[]>>({})

  useEffect(() => {
    loadServers()
  }, [])

  const loadServers = async () => {
    try {
      setLoading(true)
      const data = await api.listMCPServers()
      setServers(data)
      
      // Load tools for connected servers
      const toolsMap: Record<string, any[]> = {}
      for (const server of data) {
        if (server.status === 'connected') {
          try {
            const tools = await api.getMCPServerTools(server.uuid)
            toolsMap[server.uuid] = tools
          } catch (error) {
            console.error(`Failed to load tools for server ${server.uuid}:`, error)
            toolsMap[server.uuid] = []
          }
        }
      }
      setServerTools(toolsMap)
    } catch (error) {
      console.error('Failed to load servers:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const handleConnect = async (uuid: string) => {
    try {
      await api.connectMCPServer(uuid)
      await loadServers()
    } catch (error) {
      console.error('Failed to connect:', error)
      alert('连接失败')
    }
  }
  
  const handleDisconnect = async (uuid: string) => {
    try {
      await api.disconnectMCPServer(uuid)
      await loadServers()
    } catch (error) {
      console.error('Failed to disconnect:', error)
      alert('断开失败')
    }
  }
  
  const loadServerTools = async (uuid: string) => {
    try {
      const tools = await api.getMCPServerTools(uuid)
      setServerTools({ ...serverTools, [uuid]: tools })
    } catch (error) {
      console.error('Failed to load tools:', error)
      setServerTools({ ...serverTools, [uuid]: [] })
    }
  }

  const handleCreate = () => {
    setEditingServer(null)
    setFormData({
      name: '',
      mode: 'stdio',
      enabled: false,
      description: '',
      command: '',
      args: [],
      env: {},
      url: '',
      headers: {},
      timeout: 10,
    })
    setShowModal(true)
  }

  const handleEdit = (server: any) => {
    setEditingServer(server)
    setFormData({
      name: server.name,
      mode: server.mode,
      enabled: server.enabled,
      description: server.description || '',
      command: server.command || '',
      args: server.args || [],
      env: server.env || {},
      url: server.url || '',
      headers: server.headers || {},
      timeout: server.timeout || 10,
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    try {
      const data: any = {
        name: formData.name,
        mode: formData.mode,
        enabled: formData.enabled,
        description: formData.description,
        timeout: formData.timeout,
      }

      if (formData.mode === 'stdio') {
        data.command = formData.command
        data.args = formData.args
        data.env = formData.env
      } else {
        data.url = formData.url
        data.headers = formData.headers
      }

      if (editingServer) {
        await api.updateMCPServer(editingServer.uuid, data)
      } else {
        await api.createMCPServer(data)
      }
      setShowModal(false)
      await loadServers()
    } catch (error) {
      console.error('Failed to save server:', error)
      alert('保存失败')
    }
  }

  const handleDelete = async (uuid: string) => {
    if (!confirm('确定要删除这个MCP服务器吗？')) return
    try {
      await api.deleteMCPServer(uuid)
      await loadServers()
    } catch (error) {
      console.error('Failed to delete server:', error)
      alert('删除失败')
    }
  }

  const handleToggleEnabled = async (uuid: string, enabled: boolean) => {
    try {
      await api.updateMCPServer(uuid, { enabled: !enabled })
      await loadServers()
    } catch (error) {
      console.error('Failed to toggle server:', error)
      alert('操作失败')
    }
  }

  const addArg = () => {
    if (newArg.trim()) {
      setFormData({ ...formData, args: [...formData.args, newArg.trim()] })
      setNewArg('')
    }
  }

  const removeArg = (index: number) => {
    setFormData({ ...formData, args: formData.args.filter((_, i) => i !== index) })
  }

  const addEnv = () => {
    if (newEnvKey.trim() && newEnvValue.trim()) {
      setFormData({
        ...formData,
        env: { ...formData.env, [newEnvKey.trim()]: newEnvValue.trim() },
      })
      setNewEnvKey('')
      setNewEnvValue('')
    }
  }

  const removeEnv = (key: string) => {
    const newEnv = { ...formData.env }
    delete newEnv[key]
    setFormData({ ...formData, env: newEnv })
  }

  const addHeader = () => {
    if (newHeaderKey.trim() && newHeaderValue.trim()) {
      setFormData({
        ...formData,
        headers: { ...formData.headers, [newHeaderKey.trim()]: newHeaderValue.trim() },
      })
      setNewHeaderKey('')
      setNewHeaderValue('')
    }
  }

  const removeHeader = (key: string) => {
    const newHeaders = { ...formData.headers }
    delete newHeaders[key]
    setFormData({ ...formData, headers: newHeaders })
  }

  if (loading) {
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">MCP管理</h2>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          <Plus className="w-4 h-4" />
          添加MCP服务器
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-3">名称</th>
              <th className="text-left p-3">模式</th>
              <th className="text-left p-3">连接状态</th>
              <th className="text-left p-3">启用状态</th>
              <th className="text-left p-3">描述</th>
              <th className="text-left p-3">操作</th>
            </tr>
          </thead>
          <tbody>
            {servers.map((server) => (
              <>
                <tr key={server.uuid} className="border-b hover:bg-gray-50">
                  <td className="p-3">{server.name}</td>
                  <td className="p-3">
                    <span className="px-2 py-1 text-xs bg-blue-100 rounded-md">
                      {server.mode}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-1 text-xs rounded-md ${
                      server.status === 'connected' 
                        ? 'bg-green-100 text-green-700' 
                        : server.status === 'disconnected'
                        ? 'bg-gray-100 text-gray-700'
                        : 'bg-red-100 text-red-700'
                    }`}>
                      {server.status === 'connected' ? '已连接' : 
                       server.status === 'disconnected' ? '未连接' : 
                       server.status || '未知'}
                    </span>
                  </td>
                  <td className="p-3">
                    <button
                      onClick={() => handleToggleEnabled(server.uuid, server.enabled)}
                      className={`flex items-center gap-1 ${
                        server.enabled
                          ? 'text-green-600'
                          : 'text-gray-400'
                      }`}
                    >
                      {server.enabled ? (
                        <>
                          <Power className="w-4 h-4" />
                          <span>已启用</span>
                        </>
                      ) : (
                        <>
                          <PowerOff className="w-4 h-4" />
                          <span>已禁用</span>
                        </>
                      )}
                    </button>
                  </td>
                  <td className="p-3">
                    {server.description || <span className="text-gray-400">无</span>}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      {server.status === 'connected' ? (
                        <button
                          onClick={() => handleDisconnect(server.uuid)}
                          className="text-orange-500 hover:text-orange-600"
                          title="断开连接"
                        >
                          <Unplug className="w-4 h-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleConnect(server.uuid)}
                          className="text-green-500 hover:text-green-600"
                          title="连接"
                        >
                          <Plug className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => {
                          if (expandedServer === server.uuid) {
                            setExpandedServer(null)
                          } else {
                            setExpandedServer(server.uuid)
                            if (server.status === 'connected' && !serverTools[server.uuid]) {
                              loadServerTools(server.uuid)
                            }
                          }
                        }}
                        className="text-blue-500 hover:text-blue-600"
                        title="查看工具"
                      >
                        <Wrench className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleEdit(server)}
                        className="text-blue-500 hover:text-blue-600"
                        title="编辑"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(server.uuid)}
                        className="text-red-500 hover:text-red-600"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedServer === server.uuid && (
                  <tr>
                    <td colSpan={6} className="p-4 bg-gray-50">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium">工具列表</h4>
                          <button
                            onClick={() => loadServerTools(server.uuid)}
                            className="flex items-center gap-1 text-sm text-blue-500 hover:text-blue-600"
                          >
                            <RefreshCw className="w-4 h-4" />
                            刷新
                          </button>
                        </div>
                        {server.status === 'connected' ? (
                          serverTools[server.uuid] && serverTools[server.uuid].length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                              {serverTools[server.uuid].map((tool: any, index: number) => (
                                <div
                                  key={index}
                                  className="p-3 border rounded-lg bg-white"
                                >
                                  <div className="font-medium text-sm">{tool.name}</div>
                                  <div className="text-xs text-gray-600 mt-1">
                                    {tool.description || '无描述'}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-sm text-gray-500">暂无工具</div>
                          )
                        ) : (
                          <div className="text-sm text-gray-500">请先连接服务器以查看工具</div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-xl font-semibold mb-4">
              {editingServer ? '编辑MCP服务器' : '添加MCP服务器'}
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
                <label className="block text-sm font-medium mb-1">模式</label>
                <select
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="stdio">stdio</option>
                  <option value="sse">SSE</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="w-4 h-4"
                />
                <label>启用</label>
              </div>

              {formData.mode === 'stdio' ? (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">命令</label>
                    <input
                      type="text"
                      value={formData.command}
                      onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                      className="w-full px-3 py-2 border rounded-lg"
                      placeholder="例如: node, python, npx"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">参数</label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={newArg}
                        onChange={(e) => setNewArg(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && addArg()}
                        className="flex-1 px-3 py-2 border rounded-lg bg-white"
                        placeholder="输入参数后按回车"
                      />
                      <button
                        onClick={addArg}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                      >
                        添加
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {formData.args.map((arg, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-gray-100 rounded-md flex items-center gap-1"
                        >
                          {arg}
                          <button
                            onClick={() => removeArg(index)}
                            className="text-red-500 hover:text-red-600"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">环境变量</label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={newEnvKey}
                        onChange={(e) => setNewEnvKey(e.target.value)}
                        className="flex-1 px-3 py-2 border rounded-lg bg-white"
                        placeholder="键"
                      />
                      <input
                        type="text"
                        value={newEnvValue}
                        onChange={(e) => setNewEnvValue(e.target.value)}
                        className="flex-1 px-3 py-2 border rounded-lg bg-white"
                        placeholder="值"
                      />
                      <button
                        onClick={addEnv}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                      >
                        添加
                      </button>
                    </div>
                    <div className="space-y-1">
                      {Object.entries(formData.env).map(([key, value]) => (
                        <div
                          key={key}
                          className="flex items-center gap-2 px-2 py-1 bg-gray-100 rounded-md"
                        >
                          <span className="text-sm">
                            {key} = {value}
                          </span>
                          <button
                            onClick={() => removeEnv(key)}
                            className="text-red-500 hover:text-red-600"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">URL</label>
                    <input
                      type="text"
                      value={formData.url}
                      onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                      className="w-full px-3 py-2 border rounded-lg"
                      placeholder="https://example.com/mcp"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">HTTP Headers</label>
                    <div className="flex gap-2 mb-2">
                      <input
                        type="text"
                        value={newHeaderKey}
                        onChange={(e) => setNewHeaderKey(e.target.value)}
                        className="flex-1 px-3 py-2 border rounded-lg bg-white"
                        placeholder="键"
                      />
                      <input
                        type="text"
                        value={newHeaderValue}
                        onChange={(e) => setNewHeaderValue(e.target.value)}
                        className="flex-1 px-3 py-2 border rounded-lg bg-white"
                        placeholder="值"
                      />
                      <button
                        onClick={addHeader}
                        className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                      >
                        添加
                      </button>
                    </div>
                    <div className="space-y-1">
                      {Object.entries(formData.headers).map(([key, value]) => (
                        <div
                          key={key}
                          className="flex items-center gap-2 px-2 py-1 bg-gray-100 rounded-md"
                        >
                          <span className="text-sm">
                            {key}: {value}
                          </span>
                          <button
                            onClick={() => removeHeader(key)}
                            className="text-red-500 hover:text-red-600"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
              <div>
                <label className="block text-sm font-medium mb-1">超时时间 (秒)</label>
                <input
                  type="number"
                  value={formData.timeout}
                  onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border rounded-lg"
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

