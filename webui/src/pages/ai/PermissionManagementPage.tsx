import { useState, useEffect } from 'react'
import { api } from '@/utils/api'

interface ToolPermission {
  tool_name: string
  requires_permission: boolean
  requires_admin_approval: boolean
  requires_ai_approval: boolean
  allowed_users: string[]
  tool_category?: string
  tool_description?: string
  danger_level: number
  created_at?: string
  updated_at?: string
}

interface AdminUser {
  qq_number: string
  nickname?: string
  permission_level: number
  is_active: boolean
  can_approve_all_tools: boolean
  approved_tools: string[]
  total_approvals: number
  total_rejections: number
  created_at?: string
  updated_at?: string
  last_active_at?: string
}

interface ApprovalLog {
  id: number
  tool_name: string
  tool_args?: any
  user_qq: string
  user_nickname?: string
  chat_type: string
  chat_id: string
  ai_approved?: boolean
  ai_reason?: string
  admin_approved?: boolean
  admin_qq?: string
  admin_reason?: string
  final_approved: boolean
  final_reason?: string
  executed: boolean
  execution_success?: boolean
  execution_result?: string
  created_at: string
  approved_at?: string
  executed_at?: string
}

export default function PermissionManagementPage() {
  const [activeTab, setActiveTab] = useState<'tools' | 'admins' | 'logs'>('tools')
  
  // Tool permissions state
  const [toolPermissions, setToolPermissions] = useState<ToolPermission[]>([])
  const [editingTool, setEditingTool] = useState<ToolPermission | null>(null)
  const [showToolDialog, setShowToolDialog] = useState(false)
  
  // Admin users state
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([])
  const [editingAdmin, setEditingAdmin] = useState<AdminUser | null>(null)
  const [showAdminDialog, setShowAdminDialog] = useState(false)
  
  // Approval logs state
  const [approvalLogs, setApprovalLogs] = useState<ApprovalLog[]>([])
  
  // Load data
  useEffect(() => {
    loadToolPermissions()
    loadAdminUsers()
    loadApprovalLogs()
  }, [])
  
  const loadToolPermissions = async () => {
    try {
      const data = await api.get('/api/ai/tool-permissions')
      setToolPermissions(data.permissions)
    } catch (error) {
      console.error('Failed to load tool permissions:', error)
    }
  }
  
  const loadAdminUsers = async () => {
    try {
      const data = await api.get('/api/ai/admin-users')
      setAdminUsers(data.admins)
    } catch (error) {
      console.error('Failed to load admin users:', error)
    }
  }
  
  const loadApprovalLogs = async () => {
    try {
      const data = await api.get('/api/ai/approval-logs?limit=50')
      setApprovalLogs(data.logs)
    } catch (error) {
      console.error('Failed to load approval logs:', error)
    }
  }
  
  const saveToolPermission = async () => {
    if (!editingTool) return
    
    try {
      await api.post('/api/ai/tool-permissions', editingTool)
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
      await api.delete(`/api/ai/tool-permissions/${toolName}`)
      await loadToolPermissions()
    } catch (error) {
      console.error('Failed to delete tool permission:', error)
      alert('删除失败: ' + (error as any).message)
    }
  }
  
  const saveAdminUser = async () => {
    if (!editingAdmin) return
    
    try {
      await api.post('/api/ai/admin-users', editingAdmin)
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
      await api.delete(`/api/ai/admin-users/${qqNumber}`)
      await loadAdminUsers()
    } catch (error) {
      console.error('Failed to delete admin user:', error)
      alert('删除失败: ' + (error as any).message)
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-xl font-semibold mb-2">工具权限管理</h2>
        <p className="text-gray-600 text-sm">
          管理 AI 工具的使用权限，设置管理员 QQ，并查看审核日志
        </p>
      </div>
      
      {/* Tabs */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="border-b border-gray-200">
          <div className="flex space-x-1 p-2">
            <button
              onClick={() => setActiveTab('tools')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'tools'
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              工具权限配置
            </button>
            <button
              onClick={() => setActiveTab('admins')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'admins'
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              管理员设置
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`px-4 py-2 rounded-lg transition-colors ${
                activeTab === 'logs'
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              审核日志
            </button>
          </div>
        </div>
        
        <div className="p-6">
          {/* Tool Permissions Tab */}
          {activeTab === 'tools' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-600">
                  配置哪些工具需要权限检查、AI 审核或管理员审核
                </p>
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
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  + 添加工具权限
                </button>
              </div>
              
              {toolPermissions.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  还没有配置任何工具权限，点击"添加工具权限"开始配置
                </div>
              ) : (
                <div className="space-y-3">
                  {toolPermissions.map(tool => (
                    <div key={tool.tool_name} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="font-semibold">{tool.tool_name}</h3>
                            {tool.tool_category && (
                              <span className="text-xs px-2 py-1 bg-gray-100 rounded">
                                {tool.tool_category}
                              </span>
                            )}
                            <span className={`text-xs px-2 py-1 rounded ${
                              tool.danger_level >= 4 ? 'bg-red-100 text-red-700' :
                              tool.danger_level >= 2 ? 'bg-yellow-100 text-yellow-700' :
                              'bg-green-100 text-green-700'
                            }`}>
                              危险等级: {tool.danger_level}
                            </span>
                          </div>
                          {tool.tool_description && (
                            <p className="text-sm text-gray-600 mt-1">{tool.tool_description}</p>
                          )}
                          <div className="flex flex-wrap gap-2 mt-2">
                            {tool.requires_permission && (
                              <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                                需要权限
                              </span>
                            )}
                            {tool.requires_ai_approval && (
                              <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded">
                                AI 审核
                              </span>
                            )}
                            {tool.requires_admin_approval && (
                              <span className="text-xs px-2 py-1 bg-orange-100 text-orange-700 rounded">
                                管理员审核
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-500 mt-2">
                            允许的用户: {tool.allowed_users.length > 0 ? tool.allowed_users.join(', ') : '无'}
                          </div>
                        </div>
                        <div className="flex space-x-2 ml-4">
                          <button
                            onClick={() => {
                              setEditingTool({...tool})
                              setShowToolDialog(true)
                            }}
                            className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => deleteToolPermission(tool.tool_name)}
                            className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {/* Admin Users Tab */}
          {activeTab === 'admins' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-600">
                  设置可以审批工具使用的管理员 QQ
                </p>
                <button
                  onClick={() => {
                    setEditingAdmin({
                      qq_number: '',
                      nickname: '',
                      permission_level: 1,
                      is_active: true,
                      can_approve_all_tools: false,
                      approved_tools: [],
                      total_approvals: 0,
                      total_rejections: 0
                    })
                    setShowAdminDialog(true)
                  }}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  + 添加管理员
                </button>
              </div>
              
              {adminUsers.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  还没有配置任何管理员，点击"添加管理员"开始配置
                </div>
              ) : (
                <div className="space-y-3">
                  {adminUsers.map(admin => (
                    <div key={admin.qq_number} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="font-semibold">{admin.qq_number}</h3>
                            {admin.nickname && (
                              <span className="text-sm text-gray-600">({admin.nickname})</span>
                            )}
                            <span className={`text-xs px-2 py-1 rounded ${
                              admin.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                            }`}>
                              {admin.is_active ? '活跃' : '已禁用'}
                            </span>
                            <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                              权限等级: {admin.permission_level}
                            </span>
                          </div>
                          <div className="text-sm text-gray-600 mt-2">
                            {admin.can_approve_all_tools ? (
                              <span className="text-green-600">可审批所有工具</span>
                            ) : (
                              <span>可审批工具: {admin.approved_tools.length > 0 ? admin.approved_tools.join(', ') : '无'}</span>
                            )}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            统计: 批准 {admin.total_approvals} 次，拒绝 {admin.total_rejections} 次
                          </div>
                        </div>
                        <div className="flex space-x-2 ml-4">
                          <button
                            onClick={() => {
                              setEditingAdmin({...admin})
                              setShowAdminDialog(true)
                            }}
                            className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => deleteAdminUser(admin.qq_number)}
                            className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {/* Approval Logs Tab */}
          {activeTab === 'logs' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-600">
                  查看工具使用的审核记录
                </p>
                <button
                  onClick={loadApprovalLogs}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  刷新
                </button>
              </div>
              
              {approvalLogs.length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  暂无审核日志
                </div>
              ) : (
                <div className="space-y-3">
                  {approvalLogs.map(log => (
                    <div key={log.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="font-semibold">{log.tool_name}</h3>
                            <span className={`text-xs px-2 py-1 rounded ${
                              log.final_approved ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                            }`}>
                              {log.final_approved ? '已批准' : '已拒绝'}
                            </span>
                            {log.executed && (
                              <span className={`text-xs px-2 py-1 rounded ${
                                log.execution_success ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'
                              }`}>
                                {log.execution_success ? '执行成功' : '执行失败'}
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-gray-600 mt-2">
                            用户: {log.user_qq} {log.user_nickname && `(${log.user_nickname})`}
                          </div>
                          <div className="text-sm text-gray-600">
                            聊天: {log.chat_type === 'group' ? '群' : '私聊'} {log.chat_id}
                          </div>
                          {log.ai_reason && (
                            <div className="text-sm text-gray-600 mt-1">
                              AI 审核: {log.ai_approved ? '通过' : '拒绝'} - {log.ai_reason}
                            </div>
                          )}
                          {log.admin_reason && (
                            <div className="text-sm text-gray-600">
                              管理员审核: {log.admin_approved ? '通过' : '拒绝'} ({log.admin_qq}) - {log.admin_reason}
                            </div>
                          )}
                          {log.final_reason && (
                            <div className="text-sm text-gray-600">
                              最终理由: {log.final_reason}
                            </div>
                          )}
                          <div className="text-xs text-gray-500 mt-2">
                            创建时间: {new Date(log.created_at).toLocaleString('zh-CN')}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Tool Permission Edit Dialog */}
      {showToolDialog && editingTool && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">
              {editingTool.tool_name ? '编辑工具权限' : '添加工具权限'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  工具名称 *
                </label>
                <input
                  type="text"
                  value={editingTool.tool_name}
                  onChange={(e) => setEditingTool({...editingTool, tool_name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="例如: set_group_ban"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  工具分类
                </label>
                <input
                  type="text"
                  value={editingTool.tool_category || ''}
                  onChange={(e) => setEditingTool({...editingTool, tool_category: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="例如: 群管理"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  工具描述
                </label>
                <textarea
                  value={editingTool.tool_description || ''}
                  onChange={(e) => setEditingTool({...editingTool, tool_description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  rows={2}
                  placeholder="工具功能说明"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  危险等级 (0-5)
                </label>
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={editingTool.danger_level}
                  onChange={(e) => setEditingTool({...editingTool, danger_level: parseInt(e.target.value) || 0})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={editingTool.requires_permission}
                  onChange={(e) => setEditingTool({...editingTool, requires_permission: e.target.checked})}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">需要权限检查</label>
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={editingTool.requires_ai_approval}
                  onChange={(e) => setEditingTool({...editingTool, requires_ai_approval: e.target.checked})}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">需要 AI 审核</label>
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={editingTool.requires_admin_approval}
                  onChange={(e) => setEditingTool({...editingTool, requires_admin_approval: e.target.checked})}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">需要管理员审核</label>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  允许的用户 QQ (逗号分隔)
                </label>
                <input
                  type="text"
                  value={editingTool.allowed_users.join(', ')}
                  onChange={(e) => setEditingTool({
                    ...editingTool,
                    allowed_users: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="例如: 123456789, 987654321"
                />
              </div>
            </div>
            
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowToolDialog(false)
                  setEditingTool(null)
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                取消
              </button>
              <button
                onClick={saveToolPermission}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Admin User Edit Dialog */}
      {showAdminDialog && editingAdmin && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">
              {editingAdmin.qq_number ? '编辑管理员' : '添加管理员'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  QQ 号 *
                </label>
                <input
                  type="text"
                  value={editingAdmin.qq_number}
                  onChange={(e) => setEditingAdmin({...editingAdmin, qq_number: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="管理员的 QQ 号"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  昵称
                </label>
                <input
                  type="text"
                  value={editingAdmin.nickname || ''}
                  onChange={(e) => setEditingAdmin({...editingAdmin, nickname: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="管理员昵称"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  权限等级 (1=普通管理, 2=超级管理)
                </label>
                <input
                  type="number"
                  min="1"
                  max="2"
                  value={editingAdmin.permission_level}
                  onChange={(e) => setEditingAdmin({...editingAdmin, permission_level: parseInt(e.target.value) || 1})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={editingAdmin.is_active}
                  onChange={(e) => setEditingAdmin({...editingAdmin, is_active: e.target.checked})}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">启用</label>
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={editingAdmin.can_approve_all_tools}
                  onChange={(e) => setEditingAdmin({...editingAdmin, can_approve_all_tools: e.target.checked})}
                  className="rounded"
                />
                <label className="text-sm text-gray-700">可审批所有工具</label>
              </div>
              
              {!editingAdmin.can_approve_all_tools && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    可审批的工具 (逗号分隔)
                  </label>
                  <input
                    type="text"
                    value={editingAdmin.approved_tools.join(', ')}
                    onChange={(e) => setEditingAdmin({
                      ...editingAdmin,
                      approved_tools: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="例如: set_group_ban, set_group_kick"
                  />
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowAdminDialog(false)
                  setEditingAdmin(null)
                }}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                取消
              </button>
              <button
                onClick={saveAdminUser}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
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
