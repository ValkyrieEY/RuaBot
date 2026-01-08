import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Save, Wrench } from 'lucide-react'

export default function ToolsManagementPage() {
  const [tools, setTools] = useState<any[]>([])
  const [enabledTools, setEnabledTools] = useState<Record<string, boolean>>({})
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [toolsList, enabledToolsData, globalConfig] = await Promise.all([
        api.listAITools(),
        api.getEnabledTools('global').catch(() => ({})),
        api.getAIConfig('global').catch(() => ({ config: {} }))
      ])

      setTools(toolsList)
      setToolsEnabled(globalConfig.config?.tools_enabled !== undefined ? globalConfig.config.tools_enabled : false)
      
      // 初始化工具开关：如果配置中没有，默认全部开启
      const toolsEnabledMap: Record<string, boolean> = {}
      toolsList.forEach((tool: any) => {
        const toolName = tool.name as string
        const enabledData = enabledToolsData as Record<string, boolean>
        toolsEnabledMap[toolName] = enabledData[toolName] !== undefined ? enabledData[toolName] : true
      })
      setEnabledTools(toolsEnabledMap)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      
      // 更新全局配置中的工具启用状态
      const currentConfig = (await api.getAIConfig('global')).config || {}
      await api.updateAIConfig('global', undefined, {
        config: {
          ...currentConfig,
          tools_enabled: toolsEnabled,
          enabled_tools: enabledTools
        }
      })
      
      // 同时更新工具开关
      await api.updateEnabledTools('global', undefined, enabledTools)
      
      alert('保存成功')
    } catch (error) {
      console.error('Failed to save:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="text-center py-8">加载中...</div>
  }

  // 按分类分组工具
  const toolsByCategory = tools.reduce((acc: Record<string, any[]>, tool: any) => {
    const category = tool.category || '其他'
    if (!acc[category]) acc[category] = []
    acc[category].push(tool)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center gap-3 mb-4">
          <Wrench className="w-6 h-6 text-blue-500" />
          <h2 className="text-xl font-semibold">工具调用总开关</h2>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={toolsEnabled}
              onChange={(e) => setToolsEnabled(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium">启用工具调用</span>
          </label>
          <p className="text-sm text-gray-500">
            允许AI调用工具（如群管理、发送消息、网页访问等）。如果不启用，AI将只返回文本回复
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">工具管理</h2>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
        
        <p className="text-sm text-gray-600 mb-6">
          控制AI可以使用的工具功能。关闭的工具将无法被AI调用。只有在"工具调用总开关"开启时，这些工具才会生效。
        </p>
        
        {/* 按分类分组显示工具 */}
        {Object.entries(toolsByCategory).map(([category, categoryTools]) => (
          <div key={category} className="mb-6">
            <h3 className="text-lg font-medium mb-3 text-gray-700 border-b pb-2">{category}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {categoryTools.map((tool: any) => (
                <div
                  key={tool.name}
                  className={`flex items-start gap-3 p-4 border rounded-lg transition-colors ${
                    tool.dangerous 
                      ? 'border-red-200 bg-red-50 hover:bg-red-100' 
                      : 'border-gray-200 bg-gray-50 hover:bg-gray-100'
                  } ${!toolsEnabled ? 'opacity-50' : ''}`}
                >
                  <input
                    type="checkbox"
                    id={`tool-${tool.name}`}
                    checked={enabledTools[tool.name] !== false}
                    onChange={(e) => {
                      setEnabledTools({
                        ...enabledTools,
                        [tool.name]: e.target.checked
                      })
                    }}
                    disabled={!toolsEnabled}
                    className="w-4 h-4 mt-1 flex-shrink-0"
                  />
                  <label
                    htmlFor={`tool-${tool.name}`}
                    className="flex-1 cursor-pointer"
                  >
                    <div className="font-medium text-gray-900">{tool.name}</div>
                    <div className="text-sm text-gray-600 mt-1">{tool.description}</div>
                    {tool.dangerous && (
                      <span className="inline-block mt-2 text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded">
                        危险操作
                      </span>
                    )}
                  </label>
                </div>
              ))}
            </div>
          </div>
        ))}
        
        <div className="mt-6 pt-4 border-t flex gap-2">
          <button
            onClick={() => {
              const allEnabled: Record<string, boolean> = {}
              tools.forEach((tool: any) => {
                allEnabled[tool.name] = true
              })
              setEnabledTools(allEnabled)
            }}
            disabled={!toolsEnabled}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            全部开启
          </button>
          <button
            onClick={() => {
              const allDisabled: Record<string, boolean> = {}
              tools.forEach((tool: any) => {
                allDisabled[tool.name] = false
              })
              setEnabledTools(allDisabled)
            }}
            disabled={!toolsEnabled}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            全部关闭
          </button>
        </div>
      </div>
    </div>
  )
}

