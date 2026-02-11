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
    { id: 'config' as TabType, label: t('ai.tabs.config'), icon: Settings },
    { id: 'models' as TabType, label: t('ai.tabs.models'), icon: Cpu },
    { id: 'memory' as TabType, label: t('ai.tabs.memory'), icon: Brain },
    { id: 'permissions' as TabType, label: t('ai.tabs.permissions'), icon: Shield },
    { id: 'mcp' as TabType, label: t('ai.tabs.mcp'), icon: Network },
    { id: 'presets' as TabType, label: t('ai.tabs.presets'), icon: FileText },
    { id: 'tools' as TabType, label: t('ai.tabs.tools'), icon: Wrench },
    { id: 'learning' as TabType, label: t('ai.tabs.learning'), icon: Database },
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
    <div className="flex flex-col h-full">
      {/* 横向导航栏 */}
      <div className="border-b border-gray-200 bg-white flex-shrink-0">
        <div className="overflow-x-auto overflow-y-hidden scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent -mx-4 sm:mx-0">
          <div className="flex space-x-1 px-4 min-w-max sm:min-w-0">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    flex items-center gap-1 sm:gap-2 px-2 sm:px-4 py-3 text-xs sm:text-sm font-medium transition-colors whitespace-nowrap
                    border-b-2 -mb-px rounded-t-lg flex-shrink-0
                    ${
                      activeTab === tab.id
                        ? 'border-blue-500 text-blue-600 bg-blue-50'
                        : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300 hover:bg-gray-50'
                    }
                  `}
                >
                  <Icon className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0" />
                  <span>{tab.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto p-6 bg-white">
        {renderContent()}
      </div>
    </div>
  )
}

