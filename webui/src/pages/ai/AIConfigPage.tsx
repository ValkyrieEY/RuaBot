import { useEffect, useState } from 'react'
import { api } from '@/utils/api'
import { Save } from 'lucide-react'

interface GroupConfig {
  config_type: string
  target_id: string
  enabled: boolean
  model_uuid: string | null
  preset_uuid: string | null
  message_count: number
  group_name?: string
  avatar?: string
  is_left?: boolean  // 是否已退出群
}

export default function AIConfigPage() {
  const [globalEnabled, setGlobalEnabled] = useState(false)
  const [globalModel, setGlobalModel] = useState<string>('')
  const [globalPreset, setGlobalPreset] = useState<string>('')
  const [globalTriggerCommand, setGlobalTriggerCommand] = useState<string>('')
  const [triggerMode, setTriggerMode] = useState<'command' | 'maxtoken'>('command')
  const [enableStreaming, setEnableStreaming] = useState<boolean>(true)
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)
  const [ttsModeEnabled, setTtsModeEnabled] = useState<boolean>(false)
  const [ttsModeType, setTtsModeType] = useState<'voice_only' | 'text_and_voice'>('voice_only')
  const [talkValue, setTalkValue] = useState<number>(1.0)
  // RuaBot 配置
  const [enableRuaBot, setEnableRuaBot] = useState<boolean>(true)
  const [botName, setBotName] = useState<string>('AI助手')
  const [thinkLevel, setThinkLevel] = useState<number>(1)
  const [enableBrainMode, setEnableBrainMode] = useState<boolean>(true)
  const [enableLearning, setEnableLearning] = useState<boolean>(true)
  const [groupConfigs, setGroupConfigs] = useState<GroupConfig[]>([])
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set())
  const [models, setModels] = useState<any[]>([])
  const [presets, setPresets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      // 获取所有数据
      const [globalConfig, groups, modelsList, presetsList, contacts] = await Promise.all([
        api.getAIConfig('global'),
        api.listGroupConfigs(),
        api.listModels(),
        api.listPresets(),
        api.getChatContacts().catch((err) => {
          console.error('Failed to load contacts:', err)
          return { groups: [], friends: [] }
        }),
      ])

      setGlobalEnabled(globalConfig.enabled || false)
      setGlobalModel(globalConfig.model_uuid || '')
      setGlobalPreset(globalConfig.preset_uuid || '')
      setGlobalTriggerCommand(globalConfig.config?.trigger_command || '')
      setTriggerMode(globalConfig.config?.trigger_mode || 'command')
      setEnableStreaming(globalConfig.config?.enable_streaming !== undefined ? globalConfig.config.enable_streaming : true)
      setToolsEnabled(globalConfig.config?.tools_enabled !== undefined ? globalConfig.config.tools_enabled : false)
      setTtsModeEnabled(globalConfig.config?.tts_mode_enabled || false)
      setTtsModeType(globalConfig.config?.tts_mode_type || 'voice_only')
      setTalkValue(globalConfig.config?.talk_value !== undefined ? globalConfig.config.talk_value : 1.0)
      // 加载 RuaBot 配置
      setEnableRuaBot(globalConfig.config?.enable_RuaBot !== undefined ? globalConfig.config.enable_RuaBot : true)
      setBotName(globalConfig.config?.bot_name || 'AI助手')
      setThinkLevel(globalConfig.config?.think_level !== undefined ? globalConfig.config.think_level : 1)
      setEnableBrainMode(globalConfig.config?.enable_brain_mode !== undefined ? globalConfig.config.enable_brain_mode : true)
      setEnableLearning(globalConfig.config?.enable_learning !== undefined ? globalConfig.config.enable_learning : true)
      setModels(modelsList)
      setPresets(presetsList)

      console.log('Loaded contacts:', contacts)
      console.log('Loaded group configs:', groups)

      // 合并群组配置和实际群列表
      const groupMap = new Map<string, GroupConfig>()
      const actualGroupIds = new Set<string>() // 实际群列表中的群ID
      
      // 先收集实际群列表中的群信息
      if (contacts && contacts.groups) {
        contacts.groups.forEach((group: any) => {
          const groupId = String(group.id || group.group_id || '')
          if (groupId) {
            actualGroupIds.add(groupId)
          }
        })
      }
      
      // 先添加已有的配置，并标记是否已退出
      groups.forEach((config: GroupConfig) => {
        const isLeft = !actualGroupIds.has(config.target_id)
        // 确保有默认头像和名称
        const defaultAvatar = `http://p.qlogo.cn/gh/${config.target_id}/${config.target_id}/640/`
        groupMap.set(config.target_id, {
          ...config,
          group_name: config.group_name || `群 ${config.target_id}`,
          avatar: config.avatar || defaultAvatar,
          is_left: isLeft
        })
      })
      
      // 然后添加实际群列表中但配置中不存在的群
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
            // 更新已存在配置的群信息（名称、头像）
            const existing = groupMap.get(groupId)!
            existing.group_name = group.name || existing.group_name || '未知群'
            existing.avatar = group.avatar || existing.avatar || `http://p.qlogo.cn/gh/${groupId}/${groupId}/640/`
            existing.is_left = false
          }
        })
      }
      
      // 转换为数组并排序（未退出的群在前，已退出的在后）
      const allGroups = Array.from(groupMap.values()).sort((a, b) => {
        // 先按是否退出排序（未退出在前）
        if (a.is_left !== b.is_left) {
          return a.is_left ? 1 : -1
        }
        // 然后按群号排序
        return a.target_id.localeCompare(b.target_id)
      })
      
      console.log('Final group configs:', allGroups)
      setGroupConfigs(allGroups)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveGlobal = async () => {
    try {
      setSaving(true)
      const updates: any = {}
      if (globalEnabled !== undefined) updates.enabled = globalEnabled
      if (globalModel) updates.model_uuid = globalModel
      if (globalPreset) updates.preset_uuid = globalPreset
      
      // 更新config字段，保留其他配置
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
        // RuaBot 配置
        enable_RuaBot: enableRuaBot,
        bot_name: botName,
        think_level: thinkLevel,
        enable_brain_mode: enableBrainMode,
        enable_learning: enableLearning
      }
      
      await api.updateAIConfig('global', undefined, updates)
      alert('保存成功')
    } catch (error) {
      console.error('Failed to save:', error)
      alert('保存失败')
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
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-xl font-semibold mb-4">功能总开关</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={globalEnabled}
              onChange={(e) => setGlobalEnabled(e.target.checked)}
              className="w-4 h-4"
            />
            <span>启用AI功能</span>
          </label>
          <button
            onClick={handleSaveGlobal}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h2 className="text-xl font-semibold mb-4">全局设置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">默认模型</label>
            <select
              value={globalModel}
              onChange={(e) => setGlobalModel(e.target.value)}
              className="w-full px-3 py-2 border rounded"
            >
              <option value="">未选择</option>
              {models.map((model) => (
                <option key={model.uuid} value={model.uuid}>
                  {model.name} ({model.provider})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">默认预设</label>
            <select
              value={globalPreset}
              onChange={(e) => setGlobalPreset(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <option value="">未选择</option>
              {presets.map((preset) => (
                <option key={preset.uuid} value={preset.uuid}>
                  {preset.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">触发模式</label>
            <div className="space-y-3">
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="triggerMode"
                    value="command"
                    checked={triggerMode === 'command'}
                    onChange={(e) => setTriggerMode(e.target.value as 'command' | 'maxtoken')}
                    className="w-4 h-4"
                  />
                  <span className="text-sm font-medium">需要指令模式</span>
                </label>
                <p className="text-sm text-gray-500 ml-6">
                  只有以指定指令开头的消息才会触发AI回复。需要设置触发指令。
                </p>
                {triggerMode === 'command' && (
                  <div className="ml-6 mt-2">
                    <input
                      type="text"
                      value={globalTriggerCommand}
                      onChange={(e) => setGlobalTriggerCommand(e.target.value)}
                      placeholder="例如：@AI 或 /ai"
                      className="w-full px-3 py-2 border rounded-lg"
                    />
                    <p className="text-sm text-gray-500 mt-1">
                      设置触发指令后，只有以该指令开头的消息才会触发AI回复。例如：输入"@AI"后，只有"@AI 你好"这样的消息才会触发。
                    </p>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="triggerMode"
                    value="maxtoken"
                    checked={triggerMode === 'maxtoken'}
                    onChange={(e) => setTriggerMode(e.target.value as 'command' | 'maxtoken')}
                    className="w-4 h-4"
                  />
                  <span className="text-sm font-medium">MaxToken模式</span>
                </label>
                <p className="text-sm text-gray-500 ml-6">
                  所有消息都会上报给AI，AI自行判断是否需要回复。适合需要AI理解上下文但不想频繁回复的场景。
                </p>
                {triggerMode === 'maxtoken' && (
                  <div className="ml-6 mt-3 space-y-2">
                    <label className="block text-sm font-medium">发言频率 (Talk Value)</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={talkValue}
                        onChange={(e) => setTalkValue(parseFloat(e.target.value))}
                        className="flex-1"
                      />
                      <span className="text-sm font-medium w-16 text-right">{talkValue.toFixed(1)}</span>
                    </div>
                    <p className="text-xs text-gray-500">
                      控制AI在MaxToken模式下的发言频率。值越小，AI越安静（0.0-1.0，默认1.0）。例如：0.5表示只有50%的消息会被处理。
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enableStreaming}
                onChange={(e) => setEnableStreaming(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm font-medium">自动分割发送</span>
            </label>
            <p className="text-sm text-gray-500 mt-1 ml-6">
              启用后，AI的长回复会自动按段落和句子分割成多条消息发送，模拟流式输出效果。关闭后，AI会等待完整回复生成后一次性发送整条消息。
            </p>
          </div>
          
          <div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={toolsEnabled}
                onChange={(e) => setToolsEnabled(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm font-medium">启用工具调用</span>
            </label>
            <p className="text-sm text-gray-500 mt-1 ml-6">
              允许AI调用工具（如群管理、发送消息、网页访问等）。如果不启用，AI将只返回文本回复
            </p>
          </div>
          
          <div className="border-t pt-4 mt-4">
            <label className="flex items-center gap-2 cursor-pointer mb-3">
              <input
                type="checkbox"
                checked={ttsModeEnabled}
                onChange={(e) => setTtsModeEnabled(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm font-medium">始终TTS模式</span>
            </label>
            <p className="text-sm text-gray-500 mt-1 ml-6 mb-3">
              开启后，AI发送的所有消息都会自动转换为语音。不需要AI调用语音工具，系统会自动处理。
            </p>
            {ttsModeEnabled && (
              <div className="ml-6 space-y-2">
                <label className="block text-sm font-medium">TTS工作模式</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="ttsModeType"
                      value="voice_only"
                      checked={ttsModeType === 'voice_only'}
                      onChange={(e) => setTtsModeType(e.target.value as 'voice_only' | 'text_and_voice')}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">纯语音模式（只发送语音，不发送文本）</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="ttsModeType"
                      value="text_and_voice"
                      checked={ttsModeType === 'text_and_voice'}
                      onChange={(e) => setTtsModeType(e.target.value as 'voice_only' | 'text_and_voice')}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">文本+语音模式（同时发送文本和语音）</span>
                  </label>
                </div>
              </div>
            )}
          </div>
          
          {triggerMode === 'maxtoken' && (
            <div className="border-t pt-4 mt-4">
              <h3 className="text-lg font-semibold mb-3">RuaBot 高级配置</h3>
              <p className="text-sm text-gray-500 mb-4">
                RuaBot 是一个智能的 AI 系统，具有自主学习、智能规划、表达学习等高级功能。仅在 MaxToken 模式下可用。
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="flex items-center gap-2 cursor-pointer mb-2">
                    <input
                      type="checkbox"
                      checked={enableRuaBot}
                      onChange={(e) => setEnableRuaBot(e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm font-medium">启用 RuaBot</span>
                  </label>
                  <p className="text-sm text-gray-500 ml-6">
                    启用后将使用 RuaBot 的智能系统处理消息，包括自主学习、智能规划等功能
                  </p>
                </div>
                
                {enableRuaBot && (
                  <>
                    <div className="ml-6 space-y-4">
                      <div>
                        <label className="block text-sm font-medium mb-2">机器人名称</label>
                        <input
                          type="text"
                          value={botName}
                          onChange={(e) => setBotName(e.target.value)}
                          placeholder="AI助手"
                          className="w-full px-3 py-2 border rounded-lg"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          AI 的名字，会在对话中使用（例如：小助手、AI酱）
                        </p>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">思考等级 (Think Level)</label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="1"
                            value={thinkLevel}
                            onChange={(e) => setThinkLevel(parseInt(e.target.value))}
                            className="flex-1"
                          />
                          <span className="text-sm font-medium w-16 text-right">
                            {thinkLevel === 0 ? '简单' : '高级'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          0 = 简单模式（快速）/ 1 = 高级模式（更智能，但响应稍慢）
                        </p>
                      </div>
                      
                      <div>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={enableBrainMode}
                            onChange={(e) => setEnableBrainMode(e.target.checked)}
                            className="w-4 h-4"
                          />
                          <span className="text-sm font-medium">启用 Brain Planner（智能规划器）</span>
                        </label>
                        <p className="text-xs text-gray-500 mt-1 ml-6">
                          使用 ReAct 模式智能规划动作（reply/wait/complete_talk）。AI 会判断是否需要回复、等待或结束对话
                        </p>
                      </div>
                      
                      <div>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={enableLearning}
                            onChange={(e) => setEnableLearning(e.target.checked)}
                            className="w-4 h-4"
                          />
                          <span className="text-sm font-medium">启用学习功能</span>
                        </label>
                        <p className="text-xs text-gray-500 mt-1 ml-6">
                          自动学习群友的说话风格、黑话，并在回复中使用。包括表达学习和黑话学习
                        </p>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">群组功能开关</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleAllGroups}
              className="text-sm text-blue-500 hover:text-blue-600"
            >
              {selectedGroups.size === groupConfigs.length ? '取消全选' : '全选'}
            </button>
            <span className="text-sm text-gray-500">
              已选择 {selectedGroups.size} 个群组
            </span>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          <button
            onClick={() => handleBatchUpdate(true)}
            disabled={selectedGroups.size === 0 || saving}
            className="px-3 sm:px-4 py-2 text-sm sm:text-base bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 whitespace-nowrap"
          >
            批量开启
          </button>
          <button
            onClick={() => handleBatchUpdate(false)}
            disabled={selectedGroups.size === 0 || saving}
            className="px-3 sm:px-4 py-2 text-sm sm:text-base bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50 whitespace-nowrap"
          >
            批量关闭
          </button>
          <select
            onChange={(e) => {
              if (e.target.value) {
                handleBatchUpdate(undefined, e.target.value, undefined)
                e.target.value = ''
              }
            }}
            disabled={selectedGroups.size === 0 || saving}
            className="px-2 sm:px-3 py-2 text-sm sm:text-base border rounded-lg disabled:opacity-50 min-w-0 flex-1 sm:flex-initial sm:min-w-[140px]"
          >
            <option value="">批量设置模型</option>
            {models.map((model) => (
              <option key={model.uuid} value={model.uuid}>
                {model.name}
              </option>
            ))}
          </select>
          <select
            onChange={(e) => {
              if (e.target.value) {
                handleBatchUpdate(undefined, undefined, e.target.value)
                e.target.value = ''
              }
            }}
            disabled={selectedGroups.size === 0 || saving}
            className="px-2 sm:px-3 py-2 text-sm sm:text-base border rounded-lg disabled:opacity-50 min-w-0 flex-1 sm:flex-initial sm:min-w-[140px]"
          >
            <option value="">批量设置预设</option>
            {presets.map((preset) => (
              <option key={preset.uuid} value={preset.uuid}>
                {preset.name}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto -mx-4 sm:mx-0">
          <table className="w-full min-w-[600px]">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2 sm:p-3">
                  <input
                    type="checkbox"
                    checked={selectedGroups.size === groupConfigs.length && groupConfigs.length > 0}
                    onChange={toggleAllGroups}
                    className="w-4 h-4"
                  />
                </th>
                <th className="text-left p-2 sm:p-3">群信息</th>
                <th className="text-left p-2 sm:p-3">状态</th>
                <th className="text-left p-2 sm:p-3 hidden md:table-cell">模型</th>
                <th className="text-left p-2 sm:p-3 hidden lg:table-cell">预设</th>
                <th className="text-left p-2 sm:p-3">对话量</th>
              </tr>
            </thead>
            <tbody>
              {groupConfigs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center p-8 text-gray-500">
                    暂无群组数据，请确保已连接OneBot适配器
                  </td>
                </tr>
              ) : (
                groupConfigs.map((config) => (
                  <tr key={config.target_id} className={`border-b hover:bg-gray-50 ${config.is_left ? 'opacity-60' : ''}`}>
                    <td className="p-2 sm:p-3">
                      <input
                        type="checkbox"
                        checked={selectedGroups.has(config.target_id)}
                        onChange={() => toggleGroupSelection(config.target_id)}
                        className="w-4 h-4"
                        disabled={config.is_left}
                      />
                    </td>
                    <td className="p-2 sm:p-3 min-w-[200px]">
                      <div className="flex items-center gap-2">
                        <img
                          src={config.avatar || `http://p.qlogo.cn/gh/${config.target_id}/${config.target_id}/640/`}
                          alt={config.group_name || config.target_id}
                          className="w-10 h-10 rounded flex-shrink-0"
                          onError={(e) => {
                            // 头像加载失败时使用默认占位符
                            e.currentTarget.src = `data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0yMCAxMkMxNS41ODIyIDEyIDEyIDE1LjU4MjIgMTIgMjBDMTIgMjQuNDE3OCAxNS41ODIyIDI4IDIwIDI4QzI0LjQxNzggMjggMjggMjQuNDE3OCAyOCAyMEMyOCAxNS41ODIyIDI0LjQxNzggMTIgMjAgMTJaIiBmaWxsPSIjOUI5QkE1Ii8+Cjwvc3ZnPg==`
                          }}
                        />
                        <div className="flex flex-col min-w-0 flex-1">
                          <span className="font-medium truncate">{config.group_name || `群 ${config.target_id}`}</span>
                          <span className="text-xs sm:text-sm text-gray-500">{config.target_id}</span>
                          {config.is_left && (
                            <span className="text-xs text-red-500 mt-0.5">已退出</span>
                          )}
                          {/* 移动端显示模型和预设信息 */}
                          <div className="md:hidden mt-1 space-y-0.5">
                            <div className="text-xs text-gray-600">
                              模型: {models.find(m => m.uuid === config.model_uuid)?.name || '未设置'}
                            </div>
                            <div className="text-xs text-gray-600">
                              预设: {presets.find(p => p.uuid === config.preset_uuid)?.name || '未设置'}
                            </div>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="p-2 sm:p-3">
                    {config.is_left ? (
                      <span className="text-red-500 text-sm">已退出</span>
                    ) : config.enabled ? (
                      <span className="text-green-600 text-sm">已启用</span>
                    ) : (
                      <span className="text-gray-400 text-sm">已禁用</span>
                    )}
                    </td>
                    <td className="p-2 sm:p-3 hidden md:table-cell">
                      <span className="text-sm">{models.find(m => m.uuid === config.model_uuid)?.name || '未设置'}</span>
                    </td>
                    <td className="p-2 sm:p-3 hidden lg:table-cell">
                      <span className="text-sm">{presets.find(p => p.uuid === config.preset_uuid)?.name || '未设置'}</span>
                    </td>
                    <td className="p-2 sm:p-3">
                      <span className="text-sm">{config.message_count}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

