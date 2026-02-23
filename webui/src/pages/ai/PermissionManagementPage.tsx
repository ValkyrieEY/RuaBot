import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Shield, UserCog, FileCheck, Plus, Edit2, Trash2, X, Search, AlertCircle, CheckCircle, Clock } from 'lucide-react'

interface ToolPermission {
  tool_name: string
  requires_permission: boolean
  requires_admin_approval: boolean
  requires_ai_approval: boolean
  allowed_users: string[]
  tool_category?: string
  tool_description?: string
  danger_level: number
}

interface AdminUser {
  qq_number: string
  nickname?: string
  permission_level: number
  is_active: boolean
  can_approve_all_tools: boolean
  approved_tools: string[]
}

interface ApprovalLog {
  id: number
  tool_name: string
  tool_args: any
  user_qq: string
  user_nickname?: string
  chat_type: string
  chat_id: string
  ai_approved?: boolean
  ai_reason?: string
  admin_approved?: boolean
  admin_reason?: string
  final_approved: boolean
  final_reason: string
  executed: boolean
  execution_success?: boolean
  execution_result?: string
  created_at: string
}

type TabType = 'tools' | 'admins' | 'logs'

export default function PermissionManagementPage() {
  const [activeTab, setActiveTab] = useState<TabType>('tools')
  const [toolPermissions, setToolPermissions] = useState<ToolPermission[]>([])
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([])
  const [approvalLogs, setApprovalLogs] = useState<ApprovalLog[]>([])
  const [editingTool, setEditingTool] = useState<ToolPermission | null>(null)
  const [editingAdmin, setEditingAdmin] = useState<AdminUser | null>(null)
  const [showToolDialog, setShowToolDialog] = useState(false)
  const [showAdminDialog, setShowAdminDialog] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [activeTab])

  const loadData = async () => {
    setLoading(true)
    try {
      if (activeTab === 'tools') {
        await loadToolPermissions()
      } else if (activeTab === 'admins') {
        await loadAdminUsers()
      } else if (activeTab === 'logs') {
        await loadApprovalLogs()
      }
    } finally {
      setLoading(false)
    }
  }

  const loadToolPermissions = async () => {
    try {
      const data = await api.get('/ai/tool-permissions')
      setToolPermissions(data.permissions)
    } catch (error) {
      console.error('Failed to load tool permissions:', error)
    }
  }

  const loadAdminUsers = async () => {
    try {
      const data = await api.get('/ai/admin-users')
      setAdminUsers(data.admins)
    } catch (error) {
      console.error('Failed to load admin users:', error)
    }
  }

  const loadApprovalLogs = async () => {
    try {
      const data = await api.get('/ai/approval-logs?limit=10')
      setApprovalLogs(data.logs)
    } catch (error) {
      console.error('Failed to load approval logs:', error)
    }
  }

  const saveToolPermission = async () => {
    if (!editingTool) return
    try {
      await api.post('/ai/tool-permissions', editingTool)
      await loadToolPermissions()
      setShowToolDialog(false)
      setEditingTool(null)
    } catch (error) {
      console.error('Failed to save tool permission:', error)
      alert('保存失败: ' + (error as any).message)
    }
  }

  const deleteToolPermission = async (toolName: string) => {
    if (!confirm(`确定要删除工具 "${toolName}" 的权限配置吗？`)) return
    try {
      await api.delete(`/ai/tool-permissions/${toolName}`)
      await loadToolPermissions()
    } catch (error) {
      console.error('Failed to delete tool permission:', error)
      alert('删除失败: ' + (error as any).message)
    }
  }

  const saveAdminUser = async () => {
    if (!editingAdmin) return
    try {
      await api.post('/ai/admin-users', editingAdmin)
      await loadAdminUsers()
      setShowAdminDialog(false)
      setEditingAdmin(null)
    } catch (error) {
      console.error('Failed to save admin user:', error)
      alert('保存失败: ' + (error as any).message)
    }
  }

  const deleteAdminUser = async (qqNumber: string) => {
    if (!confirm(`确定要删除管理员 "${qqNumber}" 吗？`)) return
    try {
      await api.delete(`/ai/admin-users/${qqNumber}`)
      await loadAdminUsers()
    } catch (error) {
      console.error('Failed to delete admin user:', error)
      alert('删除失败: ' + (error as any).message)
    }
  }

  const getDangerLevelColor = (level: number) => {
    if (level >= 4) return 'bg-red-100 text-red-700 border-red-200'
    if (level >= 2) return 'bg-yellow-100 text-yellow-700 border-yellow-200'
    return 'bg-green-100 text-green-700 border-green-200'
  }

  const filteredTools = toolPermissions.filter(tool =>
    tool.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.tool_description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredAdmins = adminUsers.filter(admin =>
    admin.qq_number.includes(searchQuery) ||
    admin.nickname?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredLogs = approvalLogs.filter(log =>
    log.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.user_qq.includes(searchQuery)
  )

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 mb-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">权限管理</h1>
          <p className="text-sm text-gray-500 mt-1">配置工具权限和管理员</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-gray-100 p-1 rounded-xl mb-6 w-fit">
        {[
          { id: 'tools', label: '工具权限', icon: Shield },
          { id: 'admins', label: '管理员', icon: UserCog },
          { id: 'logs', label: '审核日志', icon: FileCheck },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as TabType)}
            className={`
              flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all
              ${activeTab === tab.id 
                ? 'bg-white text-gray-900 shadow-sm' 
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'
              }
            `}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search & Action Bar */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              activeTab === 'tools' ? '搜索工具...' : 
              activeTab === 'admins' ? '搜索管理员...' : '搜索日志...'
            }
            className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm"
          />
        </div>
        
        {activeTab === 'tools' && (
          <button
            onClick={() => {
              setEditingTool({
                tool_name: '',
                requires_permission: true,
                requires_admin_approval: false,
                requires_ai_approval: true,
                allowed_users: [],
                danger_level: 0
              })
              setShowToolDialog(true)
            }}
            className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-all shadow-sm hover:shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>添加工具</span>
          </button>
        )}
        
        {activeTab === 'admins' && (
          <button
            onClick={() => {
              setEditingAdmin({
                qq_number: '',
                permission_level: 1,
                is_active: true,
                can_approve_all_tools: false,
                approved_tools: []
              })
              setShowAdminDialog(true)
            }}
            className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 text-white text-sm font-medium rounded-xl hover:bg-purple-700 transition-all shadow-sm hover:shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>添加管理员</span>
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Tool Permissions List */}
          {activeTab === 'tools' && (
            <>
              {filteredTools.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200 text-gray-500">
                  暂无工具权限配置
                </div>
              ) : (
                filteredTools.map(tool => (
                  <div key={tool.tool_name} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all group flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-bold text-lg text-gray-900">{tool.tool_name}</h3>
                        <span className={`px-2 py-0.5 text-xs font-bold rounded-full border ${getDangerLevelColor(tool.danger_level)}`}>
                          Lv.{tool.danger_level}
                        </span>
                        {tool.tool_category && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full border border-gray-200">
                            {tool.tool_category}
                          </span>
                        )}
                      </div>
                      
                      {tool.tool_description && (
                        <p className="text-sm text-gray-600 mb-3 line-clamp-2">{tool.tool_description}</p>
                      )}
                      
                      <div className="flex flex-wrap gap-2 text-xs">
                        {tool.requires_permission && (
                          <span className="flex items-center gap-1 text-blue-700 bg-blue-50 px-2.5 py-1 rounded-lg border border-blue-100 font-medium">
                            <Shield className="w-3.5 h-3.5" />
                            权限检查
                          </span>
                        )}
                        {tool.requires_ai_approval && (
                          <span className="flex items-center gap-1 text-purple-700 bg-purple-50 px-2.5 py-1 rounded-lg border border-purple-100 font-medium">
                            <AlertCircle className="w-3.5 h-3.5" />
                            AI 审核
                          </span>
                        )}
                        {tool.requires_admin_approval && (
                          <span className="flex items-center gap-1 text-orange-700 bg-orange-50 px-2.5 py-1 rounded-lg border border-orange-100 font-medium">
                            <Clock className="w-3.5 h-3.5" />
                            人工审核
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setEditingTool({...tool})
                          setShowToolDialog(true)
                        }}
                        className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="编辑"
                      >
                        <Edit2 className="w-4.5 h-4.5" />
                      </button>
                      <button
                        onClick={() => deleteToolPermission(tool.tool_name)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="删除"
                      >
                        <Trash2 className="w-4.5 h-4.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </>
          )}

          {/* Admins List */}
          {activeTab === 'admins' && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {filteredAdmins.length === 0 ? (
                <div className="col-span-full text-center py-20 bg-white rounded-xl border border-dashed border-gray-200 text-gray-500">
                  暂无管理员
                </div>
              ) : (
                filteredAdmins.map(admin => (
                  <div key={admin.qq_number} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all group relative">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="font-bold text-lg text-gray-900">{admin.qq_number}</div>
                        {admin.nickname && <div className="text-sm text-gray-500">{admin.nickname}</div>}
                      </div>
                      <div className={`px-2.5 py-1 rounded-full text-xs font-bold border ${admin.is_active ? 'bg-green-50 text-green-700 border-green-100' : 'bg-gray-100 text-gray-500 border-gray-200'}`}>
                        {admin.is_active ? '活跃' : '停用'}
                      </div>
                    </div>
                    
                    <div className="space-y-1.5 text-xs text-gray-500 bg-gray-50 p-3 rounded-lg border border-gray-100">
                      <div className="flex justify-between">
                        <span>权限等级:</span>
                        <span className="font-mono text-gray-700">{admin.permission_level}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>审核范围:</span>
                        <span className={admin.can_approve_all_tools ? "text-blue-600 font-medium" : "text-gray-700"}>
                          {admin.can_approve_all_tools ? '全部工具' : `${admin.approved_tools.length} 个工具`}
                        </span>
                      </div>
                    </div>

                    <div className="absolute top-4 right-4 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => {
                          setEditingAdmin({...admin})
                          setShowAdminDialog(true)
                        }}
                        className="p-1.5 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteAdminUser(admin.qq_number)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Logs List */}
          {activeTab === 'logs' && (
            <>
              {filteredLogs.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-xl border border-dashed border-gray-200 text-gray-500">
                  暂无审核日志
                </div>
              ) : (
                filteredLogs.map(log => (
                  <div key={log.id} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-all">
                    <div className="flex items-center justify-between gap-4 mb-3">
                      <div className="flex items-center gap-2.5">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full ${
                          log.final_approved ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                        }`}>
                          {log.final_approved ? <CheckCircle className="w-4 h-4" /> : <X className="w-4 h-4" />}
                        </span>
                        <span className="font-bold text-gray-900 text-base">{log.tool_name}</span>
                      </div>
                      <span className="text-xs text-gray-400 font-mono">
                        {new Date(log.created_at).toLocaleString('zh-CN')}
                      </span>
                    </div>
                    
                    <div className="pl-8 space-y-3 text-sm">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded border border-gray-200">
                          用户: {log.user_qq}
                        </span>
                        {log.ai_reason && (
                          <span className={`px-2 py-1 rounded border ${log.ai_approved ? 'bg-purple-50 text-purple-700 border-purple-100' : 'bg-red-50 text-red-700 border-red-100'}`}>
                            AI: {log.ai_reason}
                          </span>
                        )}
                        {log.admin_reason && (
                          <span className={`px-2 py-1 rounded border ${log.admin_approved ? 'bg-orange-50 text-orange-700 border-orange-100' : 'bg-red-50 text-red-700 border-red-100'}`}>
                            Admin: {log.admin_reason}
                          </span>
                        )}
                      </div>
                      
                      <div className="text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100 text-xs font-mono break-all">
                        {log.final_reason}
                      </div>
                      
                      {log.executed && (
                         <div className={`text-xs font-medium flex items-center gap-1 ${log.execution_success ? 'text-blue-600' : 'text-red-600'}`}>
                           <span className={`w-1.5 h-1.5 rounded-full ${log.execution_success ? 'bg-blue-600' : 'bg-red-600'}`}></span>
                           执行结果: {log.execution_success ? '成功' : '失败'}
                         </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </>
          )}
        </div>
      )}

      {/* Dialogs ... (unchanged logic) */}
      {showToolDialog && editingTool && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          {/* ... Tool Dialog Content ... */}
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between z-10">
              <h3 className="text-lg font-bold text-gray-900">
                {editingTool.tool_name ? '编辑工具权限' : '添加工具权限'}
              </h3>
              <button onClick={() => setShowToolDialog(false)} className="p-1.5 hover:bg-gray-100 rounded-full text-gray-500">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">工具名称 *</label>
                <input
                  type="text"
                  value={editingTool.tool_name}
                  onChange={(e) => setEditingTool({...editingTool, tool_name: e.target.value})}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3"
                  placeholder="例如: send_message"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
                   <input
                    type="text"
                    value={editingTool.tool_category || ''}
                    onChange={(e) => setEditingTool({...editingTool, tool_category: e.target.value})}
                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3"
                    placeholder="消息管理"
                  />
                </div>
                <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">危险等级 (0-5)</label>
                   <input
                    type="number"
                    min="0"
                    max="5"
                    value={editingTool.danger_level}
                    onChange={(e) => setEditingTool({...editingTool, danger_level: parseInt(e.target.value)})}
                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                <textarea
                  value={editingTool.tool_description || ''}
                  onChange={(e) => setEditingTool({...editingTool, tool_description: e.target.value})}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3"
                  rows={2}
                />
              </div>
              
              <div className="space-y-3 pt-2">
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={editingTool.requires_permission}
                    onChange={(e) => setEditingTool({...editingTool, requires_permission: e.target.checked})}
                    className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">启用权限白名单</div>
                    <div className="text-xs text-gray-500">仅允许特定用户使用</div>
                  </div>
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={editingTool.requires_ai_approval}
                    onChange={(e) => setEditingTool({...editingTool, requires_ai_approval: e.target.checked})}
                    className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">需要 AI 智能审核</div>
                    <div className="text-xs text-gray-500">AI 将判断是否允许执行</div>
                  </div>
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={editingTool.requires_admin_approval}
                    onChange={(e) => setEditingTool({...editingTool, requires_admin_approval: e.target.checked})}
                    className="w-4 h-4 text-orange-600 rounded border-gray-300 focus:ring-orange-500"
                  />
                  <div>
                    <div className="text-sm font-medium text-gray-900">需要管理员人工审核</div>
                    <div className="text-xs text-gray-500">必须由管理员批准</div>
                  </div>
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">白名单用户 (QQ号，逗号分隔)</label>
                <input
                  type="text"
                  value={editingTool.allowed_users.join(', ')}
                  onChange={(e) => setEditingTool({
                    ...editingTool,
                    allowed_users: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                  })}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3"
                />
              </div>
            </div>
            <div className="sticky bottom-0 bg-gray-50 px-6 py-4 flex gap-3 justify-end border-t border-gray-100 rounded-b-2xl">
              <button
                onClick={() => setShowToolDialog(false)}
                className="px-5 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-white transition-colors"
              >
                取消
              </button>
              <button
                onClick={saveToolPermission}
                className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 shadow-sm transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {showAdminDialog && editingAdmin && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
          {/* ... Admin Dialog Content (similar style update) ... */}
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full">
            <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between rounded-t-2xl">
              <h3 className="text-lg font-bold text-gray-900">
                {editingAdmin.qq_number ? '编辑管理员' : '添加管理员'}
              </h3>
              <button onClick={() => setShowAdminDialog(false)} className="p-1.5 hover:bg-gray-100 rounded-full text-gray-500">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">QQ 号 *</label>
                <input
                  type="text"
                  value={editingAdmin.qq_number}
                  onChange={(e) => setEditingAdmin({...editingAdmin, qq_number: e.target.value})}
                  className="w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2 px-3"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">昵称</label>
                   <input
                    type="text"
                    value={editingAdmin.nickname || ''}
                    onChange={(e) => setEditingAdmin({...editingAdmin, nickname: e.target.value})}
                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2 px-3"
                  />
                </div>
                <div>
                   <label className="block text-sm font-medium text-gray-700 mb-1">权限等级</label>
                   <input
                    type="number"
                    min="1"
                    max="10"
                    value={editingAdmin.permission_level}
                    onChange={(e) => setEditingAdmin({...editingAdmin, permission_level: parseInt(e.target.value)})}
                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2 px-3"
                  />
                </div>
              </div>
              
              <div className="space-y-3 pt-2">
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={editingAdmin.is_active}
                    onChange={(e) => setEditingAdmin({...editingAdmin, is_active: e.target.checked})}
                    className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                  />
                  <span className="text-sm font-medium text-gray-700">账号激活</span>
                </label>
                <label className="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={editingAdmin.can_approve_all_tools}
                    onChange={(e) => setEditingAdmin({...editingAdmin, can_approve_all_tools: e.target.checked})}
                    className="w-4 h-4 text-purple-600 rounded border-gray-300 focus:ring-purple-500"
                  />
                  <span className="text-sm font-medium text-gray-700">可审核所有工具</span>
                </label>
              </div>

              {!editingAdmin.can_approve_all_tools && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">指定工具 (逗号分隔)</label>
                  <input
                    type="text"
                    value={editingAdmin.approved_tools.join(', ')}
                    onChange={(e) => setEditingAdmin({
                      ...editingAdmin,
                      approved_tools: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                    })}
                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2 px-3"
                  />
                </div>
              )}
            </div>
            <div className="bg-gray-50 px-6 py-4 flex gap-3 justify-end border-t border-gray-100 rounded-b-2xl">
              <button
                onClick={() => setShowAdminDialog(false)}
                className="px-5 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-white transition-colors"
              >
                取消
              </button>
              <button
                onClick={saveAdminUser}
                className="px-5 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 shadow-sm transition-colors"
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
