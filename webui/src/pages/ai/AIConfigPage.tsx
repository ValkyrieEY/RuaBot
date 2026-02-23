import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Settings, Brain, Mic, Users } from 'lucide-react'
import { GroupConfig } from './config/types'
import BasicConfig from './config/BasicConfig'
import RuaBotConfig from './config/RuaBotConfig'
import VoiceConfig from './config/VoiceConfig'
import GroupConfigPanel from './config/GroupConfig'

export default function AIConfigPage() {
  // 状态管理
  const [activeTab, setActiveTab] = useState<'basic' | 'ruabot' | 'voice' | 'group'>('basic')
  
  // 基础配置状态
  const [globalEnabled, setGlobalEnabled] = useState(false)
  const [globalModel, setGlobalModel] = useState<string>('')
  const [globalPreset, setGlobalPreset] = useState<string>('')
  const [globalDecisionModel, setGlobalDecisionModel] = useState<string>('')
  const [globalTriggerCommand, setGlobalTriggerCommand] = useState<string>('')
  const [triggerMode, setTriggerMode] = useState<'command' | 'maxtoken'>('command')
  const [enableStreaming, setEnableStreaming] = useState<boolean>(true)
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)
  
  // 语音配置状态
  const [ttsModeEnabled, setTtsModeEnabled] = useState<boolean>(false)
  const [ttsModeType, setTtsModeType] = useState<'voice_only' | 'text_and_voice'>('voice_only')
  const [talkValue, setTalkValue] = useState<number>(1.0)
  
  // RuaBot 配置状态
  const [enableRuaBot, setEnableRuaBot] = useState<boolean>(true)
  const [ruabotDecisionModel, setRuabotDecisionModel] = useState<string>('')
  const [botName, setBotName] = useState<string>('AI助手')
  const [thinkLevel, setThinkLevel] = useState<number>(1)
  const [enableBrainMode, setEnableBrainMode] = useState<boolean>(true)
  const [enableLearning, setEnableLearning] = useState<boolean>(true)
  
  // 数据列表状态
  const [groupConfigs, setGroupConfigs] = useState<GroupConfig[]>([])
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set())
  const [models, setModels] = useState<any[]>([])
  const [presets, setPresets] = useState<any[]>([])
  
  // 加载状态
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // TTS 密钥状态
  const [tencentSecretId, setTencentSecretId] = useState('')
  const [tencentSecretKey, setTencentSecretKey] = useState('')
  const [showTencentKey, setShowTencentKey] = useState(false)
  const [ttsConfigLoaded, setTtsConfigLoaded] = useState(false)

  // 初始化加载
  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      
      // 使用 Promise.allSettled 确保单个请求失败不影响整体
      const results = await Promise.allSettled([
        api.getAIConfig('global'),
        api.listGroupConfigs(),
        api.listModels(),
        api.listPresets(),
        api.getChatContacts(),
        api.getSystemConfig(),
      ])
      
      // 提取结果，失败的使用默认值
      const globalConfig = results[0].status === 'fulfilled' ? results[0].value : { enabled: false, config: {} }
      const groups = results[1].status === 'fulfilled' ? results[1].value : []
      const modelsList = results[2].status === 'fulfilled' ? results[2].value : []
      const presetsList = results[3].status === 'fulfilled' ? results[3].value : []
      const contacts = results[4].status === 'fulfilled' ? results[4].value : { groups: [], friends: [] }
      const systemConfig = results[5].status === 'fulfilled' ? results[5].value : null
      
      // 记录失败的请求
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          const names = ['AI配置', '群组配置', '模型列表', '预设列表', '联系人列表', '系统配置']
          console.error(`Failed to load ${names[index]}:`, result.reason)
        }
      })
      
      // 加载TTS配置
      if (systemConfig?.tencent_cloud) {
        setTencentSecretId(systemConfig.tencent_cloud.secret_id || '')
        setTtsConfigLoaded(true)
      }

      // 设置基础状态
      setGlobalEnabled(globalConfig.enabled || false)
      setGlobalModel(globalConfig.model_uuid || '')
      setGlobalPreset(globalConfig.preset_uuid || '')
      setGlobalDecisionModel(globalConfig.config?.decision_model_uuid || '')
      setGlobalTriggerCommand(globalConfig.config?.trigger_command || '')
      setTriggerMode(globalConfig.config?.trigger_mode || 'command')
      setEnableStreaming(globalConfig.config?.enable_streaming !== undefined ? globalConfig.config.enable_streaming : true)
      setToolsEnabled(globalConfig.config?.tools_enabled !== undefined ? globalConfig.config.tools_enabled : false)
      setTtsModeEnabled(globalConfig.config?.tts_mode_enabled || false)
      setTtsModeType(globalConfig.config?.tts_mode_type || 'voice_only')
      setTalkValue(globalConfig.config?.talk_value !== undefined ? globalConfig.config.talk_value : 1.0)
      
      // 设置 RuaBot 状态
      setEnableRuaBot(globalConfig.config?.enable_RuaBot !== undefined ? globalConfig.config.enable_RuaBot : true)
      setRuabotDecisionModel(globalConfig.config?.ruabot_decision_model_uuid || '')
      setBotName(globalConfig.config?.bot_name || 'AI助手')
      setThinkLevel(globalConfig.config?.think_level !== undefined ? globalConfig.config.think_level : 1)
      setEnableBrainMode(globalConfig.config?.enable_brain_mode !== undefined ? globalConfig.config.enable_brain_mode : true)
      setEnableLearning(globalConfig.config?.enable_learning !== undefined ? globalConfig.config.enable_learning : true)
      
      setModels(modelsList)
      setPresets(presetsList)

      // 处理群组数据
      processGroupData(groups, contacts)
      
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const processGroupData = (groups: any[], contacts: any) => {
    const groupMap = new Map<string, GroupConfig>()
    const actualGroupIds = new Set<string>()
    
    if (contacts && contacts.groups) {
      contacts.groups.forEach((group: any) => {
        const groupId = String(group.id || group.group_id || '')
        if (groupId) actualGroupIds.add(groupId)
      })
    }
    
    groups.forEach((config: GroupConfig) => {
      const isLeft = !actualGroupIds.has(config.target_id)
      const defaultAvatar = `http://p.qlogo.cn/gh/${config.target_id}/${config.target_id}/640/`
      groupMap.set(config.target_id, {
        ...config,
        group_name: config.group_name || `群 ${config.target_id}`,
        avatar: config.avatar || defaultAvatar,
        is_left: isLeft
      })
    })
    
    if (contacts && contacts.groups) {
      contacts.groups.forEach((group: any) => {
        const groupId = String(group.id || group.group_id || '')
        if (groupId && !groupMap.has(groupId)) {
          groupMap.set(groupId, {
            config_type: 'group',
            target_id: groupId,
            enabled: false,
            model_uuid: null,
            preset_uuid: null,
            message_count: 0,
            group_name: group.name || '未知群',
            avatar: group.avatar || `http://p.qlogo.cn/gh/${groupId}/${groupId}/640/`,
            is_left: false
          })
        } else if (groupId && groupMap.has(groupId)) {
          const existing = groupMap.get(groupId)!
          existing.group_name = group.name || existing.group_name || '未知群'
          existing.avatar = group.avatar || existing.avatar || `http://p.qlogo.cn/gh/${groupId}/${groupId}/640/`
          existing.is_left = false
        }
      })
    }
    
    const allGroups = Array.from(groupMap.values()).sort((a, b) => {
      if (a.is_left !== b.is_left) return a.is_left ? 1 : -1
      return a.target_id.localeCompare(b.target_id)
    })
    
    setGroupConfigs(allGroups)
  }

  const handleSaveGlobal = async () => {
    try {
      setSaving(true)
      const updates: any = {}
      if (globalEnabled !== undefined) updates.enabled = globalEnabled
      if (globalModel) updates.model_uuid = globalModel
      if (globalPreset) updates.preset_uuid = globalPreset
      
      const currentConfig = (await api.getAIConfig('global')).config || {}
      updates.config = {
        ...currentConfig,
        trigger_command: triggerMode === 'command' ? (globalTriggerCommand || undefined) : undefined,
        trigger_mode: triggerMode,
        enable_streaming: enableStreaming,
        tools_enabled: toolsEnabled,
        tts_mode_enabled: ttsModeEnabled,
        tts_mode_type: ttsModeType,
        talk_value: talkValue,
        decision_model_uuid: globalDecisionModel || undefined,
        // RuaBot
        enable_RuaBot: enableRuaBot,
        ruabot_decision_model_uuid: ruabotDecisionModel || undefined,
        bot_name: botName,
        think_level: thinkLevel,
        enable_brain_mode: enableBrainMode,
        enable_learning: enableLearning
      }
      
      await api.updateAIConfig('global', undefined, updates)
      alert('全局配置保存成功')
    } catch (error) {
      console.error('Failed to save:', error)
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }
  
  const handleSaveTTS = async () => {
    try {
      setSaving(true)
      const updateData: any = {}
      
      if (tencentSecretId || tencentSecretKey) {
        updateData.tencent_cloud = {
          secret_id: tencentSecretId,
          secret_key: tencentSecretKey || undefined,
        }
      }
      
      await api.updateSystemConfig(updateData)
      if (tencentSecretKey) {
        setTencentSecretKey('')
        setShowTencentKey(false)
      }
      setTtsConfigLoaded(true)
      alert('TTS配置保存成功')
    } catch (error) {
      console.error('Failed to save TTS config:', error)
      alert('TTS配置保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleBatchUpdate = async (enabled?: boolean, modelUuid?: string, presetUuid?: string) => {
    if (selectedGroups.size === 0) {
      alert('请先选择群组')
      return
    }

    try {
      setSaving(true)
      const updates: any = {}
      if (enabled !== undefined) updates.enabled = enabled
      if (modelUuid !== undefined) updates.model_uuid = modelUuid
      if (presetUuid !== undefined) updates.preset_uuid = presetUuid

      await api.batchUpdateGroups(Array.from(selectedGroups), updates)
      await loadData()
      setSelectedGroups(new Set())
      alert('批量更新成功')
    } catch (error) {
      console.error('Failed to batch update:', error)
      alert('批量更新失败')
    } finally {
      setSaving(false)
    }
  }

  const toggleGroupSelection = (groupId: string) => {
    const newSelected = new Set(selectedGroups)
    if (newSelected.has(groupId)) {
      newSelected.delete(groupId)
    } else {
      newSelected.add(groupId)
    }
    setSelectedGroups(newSelected)
  }

  const toggleAllGroups = () => {
    if (selectedGroups.size === groupConfigs.length) {
      setSelectedGroups(new Set())
    } else {
      setSelectedGroups(new Set(groupConfigs.map(g => g.target_id)))
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-500 font-medium">正在加载配置...</p>
        </div>
      </div>
    )
  }

  // 导航配置
  const tabs = [
    { id: 'basic', label: '基础设置', icon: Settings },
    { id: 'ruabot', label: '拟人与行为', icon: Brain },
    { id: 'voice', label: '语音服务', icon: Mic },
    { id: 'group', label: '群组管理', icon: Users },
  ]

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-1">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 tracking-tight">AI 核心配置</h1>
          <p className="text-sm text-gray-500 mt-1">管理 AI 的行为、模型与功能开关</p>
        </div>
      </div>

      {/* Tab 导航 - 扁平化风格 */}
      <div className="border-b border-gray-200">
        <nav className="flex -mb-px space-x-6 sm:space-x-8 overflow-x-auto no-scrollbar" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`
                  flex items-center gap-2 py-3 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors
                  ${isActive 
                    ? 'border-blue-600 text-blue-600' 
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* 内容区域 */}
      <div className="min-h-[400px]">
        {activeTab === 'basic' && (
          <BasicConfig
            globalEnabled={globalEnabled}
            setGlobalEnabled={setGlobalEnabled}
            globalModel={globalModel}
            setGlobalModel={setGlobalModel}
            globalPreset={globalPreset}
            setGlobalPreset={setGlobalPreset}
            globalDecisionModel={globalDecisionModel}
            setGlobalDecisionModel={setGlobalDecisionModel}
            globalTriggerCommand={globalTriggerCommand}
            setGlobalTriggerCommand={setGlobalTriggerCommand}
            triggerMode={triggerMode}
            setTriggerMode={setTriggerMode}
            enableStreaming={enableStreaming}
            setEnableStreaming={setEnableStreaming}
            toolsEnabled={toolsEnabled}
            setToolsEnabled={setToolsEnabled}
            models={models}
            presets={presets}
            saving={saving}
            handleSaveGlobal={handleSaveGlobal}
          />
        )}

        {activeTab === 'ruabot' && (
          <RuaBotConfig
            enableRuaBot={enableRuaBot}
            setEnableRuaBot={setEnableRuaBot}
            ruabotDecisionModel={ruabotDecisionModel}
            setRuabotDecisionModel={setRuabotDecisionModel}
            botName={botName}
            setBotName={setBotName}
            thinkLevel={thinkLevel}
            setThinkLevel={setThinkLevel}
            enableBrainMode={enableBrainMode}
            setEnableBrainMode={setEnableBrainMode}
            enableLearning={enableLearning}
            setEnableLearning={setEnableLearning}
            talkValue={talkValue}
            setTalkValue={setTalkValue}
            triggerMode={triggerMode}
            models={models}
            saving={saving}
            handleSaveGlobal={handleSaveGlobal}
          />
        )}

        {activeTab === 'voice' && (
          <VoiceConfig
            ttsModeEnabled={ttsModeEnabled}
            setTtsModeEnabled={setTtsModeEnabled}
            ttsModeType={ttsModeType}
            setTtsModeType={setTtsModeType}
            tencentSecretId={tencentSecretId}
            setTencentSecretId={setTencentSecretId}
            tencentSecretKey={tencentSecretKey}
            setTencentSecretKey={setTencentSecretKey}
            showTencentKey={showTencentKey}
            setShowTencentKey={setShowTencentKey}
            ttsConfigLoaded={ttsConfigLoaded}
            saving={saving}
            handleSaveGlobal={handleSaveGlobal}
            handleSaveTTS={handleSaveTTS}
          />
        )}

        {activeTab === 'group' && (
          <GroupConfigPanel
            groupConfigs={groupConfigs}
            models={models}
            presets={presets}
            selectedGroups={selectedGroups}
            saving={saving}
            handleBatchUpdate={handleBatchUpdate}
            toggleGroupSelection={toggleGroupSelection}
            toggleAllGroups={toggleAllGroups}
          />
        )}
      </div>
    </div>
  )
}
