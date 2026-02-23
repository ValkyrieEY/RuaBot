import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Plus, Edit2, Trash2, Power, PowerOff, RefreshCw, Plug, Unplug, Wrench, Settings } from 'lucide-react'

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
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">MCP 管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理 Model Context Protocol 服务器连接</p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-sm hover:shadow-md"
        >
          <Plus className="w-4 h-4" />
          <span>添加 MCP 服务器</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {servers.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-500 bg-white rounded-xl border border-dashed border-gray-200">
            暂无 MCP 服务器配置
          </div>
        ) : (
          servers.map((server) => (
            <div key={server.uuid} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-all group">
              <div className="p-5 flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                      <Settings className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-gray-900">{server.name}</h3>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100">
                          {server.mode}
                        </span>
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border ${
                          server.status === 'connected' 
                            ? 'bg-green-50 text-green-700 border-green-100' 
                            : server.status === 'disconnected'
                            ? 'bg-gray-50 text-gray-700 border-gray-200'
                            : 'bg-red-50 text-red-700 border-red-100'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            server.status === 'connected' ? 'bg-green-500' : 
                            server.status === 'disconnected' ? 'bg-gray-400' : 'bg-red-500'
                          }`}></span>
                          {server.status === 'connected' ? '已连接' : 
                           server.status === 'disconnected' ? '未连接' : 
                           server.status || '未知'}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-2 line-clamp-2 ml-12">{server.description || '暂无描述'}</p>
                  
                  <div className="ml-12 flex items-center gap-2">
                    <button
                      onClick={() => handleToggleEnabled(server.uuid, server.enabled)}
                      className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded transition-colors ${
                        server.enabled
                          ? 'text-green-700 bg-green-50 hover:bg-green-100'
                          : 'text-gray-500 bg-gray-100 hover:bg-gray-200'
                      }`}
                    >
                      {server.enabled ? <Power className="w-3.5 h-3.5" /> : <PowerOff className="w-3.5 h-3.5" />}
                      {server.enabled ? '已启用' : '已禁用'}
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity self-center">
                  {server.status === 'connected' ? (
                    <button
                      onClick={() => handleDisconnect(server.uuid)}
                      className="p-2 text-orange-500 hover:bg-orange-50 rounded-lg transition-colors"
                      title="断开连接"
                    >
                      <Unplug className="w-4.5 h-4.5" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(server.uuid)}
                      className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                      title="连接"
                    >
                      <Plug className="w-4.5 h-4.5" />
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
                    className={`p-2 rounded-lg transition-colors ${expandedServer === server.uuid ? 'text-blue-700 bg-blue-50' : 'text-blue-600 hover:bg-blue-50'}`}
                    title="查看工具"
                  >
                    <Wrench className="w-4.5 h-4.5" />
                  </button>
                  <button
                    onClick={() => handleEdit(server)}
                    className="p-2 text-gray-500 hover:text-blue-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="w-4.5 h-4.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(server.uuid)}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4.5 h-4.5" />
                  </button>
                </div>
              </div>

              {expandedServer === server.uuid && (
                <div className="border-t border-gray-100 bg-gray-50/50 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="font-bold text-sm text-gray-900 flex items-center gap-2">
                      <Wrench className="w-4 h-4 text-gray-500" />
                      可用工具列表
                    </h4>
                    <button
                      onClick={() => loadServerTools(server.uuid)}
                      className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 hover:underline font-medium"
                    >
                      <RefreshCw className="w-3 h-3" />
                      刷新列表
                    </button>
                  </div>
                  
                  {server.status === 'connected' ? (
                    serverTools[server.uuid] && serverTools[server.uuid].length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {serverTools[server.uuid].map((tool: any, index: number) => (
                          <div key={index} className="p-3 border border-gray-200 rounded-lg bg-white shadow-sm">
                            <div className="font-mono font-bold text-xs text-gray-900 mb-1">{tool.name}</div>
                            <div className="text-xs text-gray-500 line-clamp-2 leading-relaxed" title={tool.description}>
                              {tool.description || '无描述'}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500 py-8 text-center bg-white rounded-lg border border-dashed border-gray-200">
                        此服务器未提供任何工具
                      </div>
                    )
                  ) : (
                    <div className="text-sm text-gray-500 py-8 text-center bg-white rounded-lg border border-dashed border-gray-200">
                      请先连接服务器以查看可用工具
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Modal ... (unchanged logic) */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* ... Modal content ... */}
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between z-10 rounded-t-2xl">
              <h3 className="text-lg font-bold text-gray-900">
                {editingServer ? '编辑 MCP 服务器' : '添加 MCP 服务器'}
              </h3>
              <button onClick={() => setShowModal(false)} className="p-2 hover:bg-gray-100 rounded-full text-gray-500 transition-colors">
                <span className="text-xl leading-none">×</span>
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">名称</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
                      placeholder="服务器名称"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">描述</label>
                    <input
                      type="text"
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
                      placeholder="简要描述"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">连接模式</label>
                    <select
                      value={formData.mode}
                      onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
                    >
                      <option value="stdio">Stdio (本地进程)</option>
                      <option value="sse">SSE (远程服务器)</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      id="server-enabled"
                      checked={formData.enabled}
                      onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <label htmlFor="server-enabled" className="text-sm text-gray-700 font-medium cursor-pointer">立即启用</label>
                  </div>
                </div>

                <div className="space-y-4">
                  {formData.mode === 'stdio' ? (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">执行命令</label>
                        <input
                          type="text"
                          value={formData.command}
                          onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
                          placeholder="例如: node, python, npx"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">参数 (Arguments)</label>
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={newArg}
                            onChange={(e) => setNewArg(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && addArg()}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                            placeholder="输入参数"
                          />
                          <button
                            onClick={addArg}
                            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium text-sm border border-gray-200"
                          >
                            添加
                          </button>
                        </div>
                        <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                          {formData.args.map((arg, index) => (
                            <span key={index} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 text-gray-700 rounded text-xs font-mono border border-gray-200">
                              {arg}
                              <button onClick={() => removeArg(index)} className="hover:text-red-500 ml-1 font-bold">×</button>
                            </span>
                          ))}
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">环境变量 (Env)</label>
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={newEnvKey}
                            onChange={(e) => setNewEnvKey(e.target.value)}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                            placeholder="KEY"
                          />
                          <input
                            type="text"
                            value={newEnvValue}
                            onChange={(e) => setNewEnvValue(e.target.value)}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                            placeholder="VALUE"
                          />
                          <button
                            onClick={addEnv}
                            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium text-sm border border-gray-200"
                          >
                            添加
                          </button>
                        </div>
                        <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                          {Object.entries(formData.env).map(([key, value]) => (
                            <div key={key} className="flex items-center justify-between px-2 py-1 bg-gray-50 rounded text-xs font-mono border border-gray-200">
                              <span className="truncate flex-1" title={`${key}=${value}`}>{key}={value}</span>
                              <button onClick={() => removeEnv(key)} className="text-gray-400 hover:text-red-500 ml-2 font-bold">×</button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">服务器 URL</label>
                        <input
                          type="text"
                          value={formData.url}
                          onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                          placeholder="https://example.com/mcp"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">HTTP Headers</label>
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={newHeaderKey}
                            onChange={(e) => setNewHeaderKey(e.target.value)}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                            placeholder="Header"
                          />
                          <input
                            type="text"
                            value={newHeaderValue}
                            onChange={(e) => setNewHeaderValue(e.target.value)}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm shadow-sm"
                            placeholder="Value"
                          />
                          <button
                            onClick={addHeader}
                            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium text-sm border border-gray-200"
                          >
                            添加
                          </button>
                        </div>
                        <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                          {Object.entries(formData.headers).map(([key, value]) => (
                            <div key={key} className="flex items-center justify-between px-2 py-1 bg-gray-50 rounded text-xs font-mono border border-gray-200">
                              <span className="truncate flex-1">{key}: {value}</span>
                              <button onClick={() => removeHeader(key)} className="text-gray-400 hover:text-red-500 ml-2 font-bold">×</button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">连接超时 (秒)</label>
                    <input
                      type="number"
                      value={formData.timeout}
                      onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm"
                      min="1"
                    />
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
