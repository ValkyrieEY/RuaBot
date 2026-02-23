import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Settings, Cpu, Brain, Shield, Network, FileText, Wrench, Database } from 'lucide-react'
import AIConfigPage from './ai/AIConfigPage'
import ModelManagementPage from './ai/ModelManagementPage'
import MemoryManagementPage from './ai/MemoryManagementPage'
import PermissionManagementPage from './ai/PermissionManagementPage'
import MCPManagementPage from './ai/MCPManagementPage'
import PresetManagementPage from './ai/PresetManagementPage'
import ToolsManagementPage from './ai/ToolsManagementPage'
import AILearningPage from './ai/AILearningPage'

type TabType = 'config' | 'models' | 'memory' | 'permissions' | 'mcp' | 'presets' | 'tools' | 'learning'

export default function AIPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabType>('config')

  const tabs = [
    { id: 'config' as TabType, label: t('ai.tabs.config') || '配置', icon: Settings },
    { id: 'models' as TabType, label: t('ai.tabs.models') || '模型', icon: Cpu },
    { id: 'presets' as TabType, label: t('ai.tabs.presets') || '预设', icon: FileText },
    { id: 'memory' as TabType, label: t('ai.tabs.memory') || '记忆', icon: Brain },
    { id: 'learning' as TabType, label: t('ai.tabs.learning') || '学习', icon: Database },
    { id: 'tools' as TabType, label: t('ai.tabs.tools') || '工具', icon: Wrench },
    { id: 'permissions' as TabType, label: t('ai.tabs.permissions') || '权限', icon: Shield },
    { id: 'mcp' as TabType, label: t('ai.tabs.mcp') || 'MCP', icon: Network },
  ]

  const renderContent = () => {
    switch (activeTab) {
      case 'config':
        return <AIConfigPage />
      case 'models':
        return <ModelManagementPage />
      case 'memory':
        return <MemoryManagementPage />
      case 'permissions':
        return <PermissionManagementPage />
      case 'mcp':
        return <MCPManagementPage />
      case 'presets':
        return <PresetManagementPage />
      case 'tools':
        return <ToolsManagementPage />
      case 'learning':
        return <AILearningPage />
      default:
        return <AIConfigPage />
    }
  }

  return (
    <div className="space-y-6">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">AI 智能管理</h1>
        <p className="text-gray-500 text-sm mt-1">统一管理 AI 配置、模型、记忆和权限</p>
      </div>

      <div className="border-b border-gray-200">
        <nav className="flex -mb-px space-x-6 overflow-x-auto no-scrollbar" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors
                  ${isActive
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <Icon className={`-ml-0.5 mr-2 h-5 w-5 ${isActive ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-500'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      <div className="min-h-[400px] animate-fadeIn">
        {renderContent()}
      </div>
    </div>
  )
}
