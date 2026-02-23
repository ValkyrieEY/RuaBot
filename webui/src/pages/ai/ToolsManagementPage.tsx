import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Save, Wrench, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

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
      
      const currentConfig = (await api.getAIConfig('global')).config || {}
      await api.updateAIConfig('global', undefined, {
        config: {
          ...currentConfig,
          tools_enabled: toolsEnabled,
          enabled_tools: enabledTools
        }
      })
      
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
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  const toolsByCategory = tools.reduce((acc: Record<string, any[]>, tool: any) => {
    const category = tool.category || '其他'
    if (!acc[category]) acc[category] = []
    acc[category].push(tool)
    return acc
  }, {})

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">工具管理</h1>
          <p className="text-sm text-gray-500 mt-1">配置 AI 可调用的功能</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存更改'}
          </button>
        </div>
      </div>

      <div className="bg-white border border-blue-100 rounded-xl p-6 mb-8 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
            <Wrench className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 mb-1">工具调用总开关</h3>
            <p className="text-sm text-gray-500 max-w-xl">
              控制是否允许 AI 调用外部工具（如群管理、发送消息、网页访问等）。如果不启用，AI 将只返回纯文本回复，无法执行任何操作。
            </p>
          </div>
        </div>
        <label className="relative inline-flex items-center cursor-pointer ml-auto sm:ml-0">
          <input
            type="checkbox"
            checked={toolsEnabled}
            onChange={(e) => setToolsEnabled(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>

      <div className={`transition-all duration-300 ${!toolsEnabled ? 'opacity-50 grayscale-[0.5]' : ''}`}>
        <div className={`flex justify-end gap-3 mb-6 ${!toolsEnabled ? 'pointer-events-none' : ''}`}>
          <button
            onClick={() => {
              const allEnabled: Record<string, boolean> = {}
              tools.forEach((tool: any) => { allEnabled[tool.name] = true })
              setEnabledTools(allEnabled)
            }}
            disabled={!toolsEnabled}
            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-blue-600 font-medium px-4 py-2 bg-white border border-gray-200 hover:border-blue-200 hover:bg-blue-50 rounded-lg transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle2 className="w-4 h-4" />
            全部开启
          </button>
          <button
            onClick={() => {
              const allDisabled: Record<string, boolean> = {}
              tools.forEach((tool: any) => { allDisabled[tool.name] = false })
              setEnabledTools(allDisabled)
            }}
            disabled={!toolsEnabled}
            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-red-600 font-medium px-4 py-2 bg-white border border-gray-200 hover:border-red-200 hover:bg-red-50 rounded-lg transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <XCircle className="w-4 h-4" />
            全部关闭
          </button>
        </div>

        <div className={`space-y-10 ${!toolsEnabled ? 'pointer-events-none' : ''}`}>
          {Object.entries(toolsByCategory).map(([category, categoryTools]) => (
            <div key={category}>
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2 px-1">
                <div className="w-1 h-6 bg-blue-600 rounded-full"></div>
                {category}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {categoryTools.map((tool: any) => (
                  <label
                    key={tool.name}
                    className={`
                      relative flex items-start gap-4 p-5 border rounded-xl cursor-pointer transition-all hover:shadow-md
                      ${enabledTools[tool.name] !== false
                        ? 'bg-white border-blue-200 shadow-sm ring-1 ring-blue-50'
                        : 'bg-gray-50 border-gray-200 opacity-70 hover:opacity-100'
                      }
                      ${!toolsEnabled ? 'cursor-not-allowed' : ''}
                    `}
                  >
                    <div className="flex h-6 items-center pt-0.5">
                      <input
                        type="checkbox"
                        checked={enabledTools[tool.name] !== false}
                        onChange={(e) => {
                          setEnabledTools({
                            ...enabledTools,
                            [tool.name]: e.target.checked
                          })
                        }}
                        disabled={!toolsEnabled}
                        className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={`font-bold text-base ${enabledTools[tool.name] !== false ? 'text-gray-900' : 'text-gray-500'}`}>
                          {tool.name}
                        </span>
                        {tool.dangerous && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-50 text-red-600 border border-red-100 uppercase tracking-wide" title="此工具包含危险操作">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            Dangerous
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 line-clamp-2 leading-relaxed">
                        {tool.description || '暂无描述'}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
