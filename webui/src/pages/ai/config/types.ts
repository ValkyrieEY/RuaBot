export interface GroupConfig {
  config_type: string
  target_id: string
  enabled: boolean
  model_uuid: string | null
  preset_uuid: string | null
  message_count: number
  group_name?: string
  avatar?: string
  is_left?: boolean
}

export interface AIConfigProps {
  globalEnabled: boolean
  setGlobalEnabled: (val: boolean) => void
  globalModel: string
  setGlobalModel: (val: string) => void
  globalPreset: string
  setGlobalPreset: (val: string) => void
  globalDecisionModel: string
  setGlobalDecisionModel: (val: string) => void
  globalTriggerCommand: string
  setGlobalTriggerCommand: (val: string) => void
  triggerMode: 'command' | 'maxtoken'
  setTriggerMode: (val: 'command' | 'maxtoken') => void
  enableStreaming: boolean
  setEnableStreaming: (val: boolean) => void
  toolsEnabled: boolean
  setToolsEnabled: (val: boolean) => void
  models: any[]
  presets: any[]
  saving: boolean
  handleSaveGlobal: () => void
}

export interface RuaBotConfigProps {
  enableRuaBot: boolean
  setEnableRuaBot: (val: boolean) => void
  ruabotDecisionModel: string
  setRuabotDecisionModel: (val: string) => void
  botName: string
  setBotName: (val: string) => void
  thinkLevel: number
  setThinkLevel: (val: number) => void
  enableBrainMode: boolean
  setEnableBrainMode: (val: boolean) => void
  enableLearning: boolean
  setEnableLearning: (val: boolean) => void
  talkValue: number
  setTalkValue: (val: number) => void
  triggerMode: 'command' | 'maxtoken'
  models: any[]
  saving: boolean
  handleSaveGlobal: () => void
}

export interface VoiceConfigProps {
  ttsModeEnabled: boolean
  setTtsModeEnabled: (val: boolean) => void
  ttsModeType: 'voice_only' | 'text_and_voice'
  setTtsModeType: (val: 'voice_only' | 'text_and_voice') => void
  tencentSecretId: string
  setTencentSecretId: (val: string) => void
  tencentSecretKey: string
  setTencentSecretKey: (val: string) => void
  showTencentKey: boolean
  setShowTencentKey: (val: boolean) => void
  ttsConfigLoaded: boolean
  saving: boolean
  handleSaveGlobal: () => void
  handleSaveTTS: () => void
}

export interface GroupConfigProps {
  groupConfigs: GroupConfig[]
  models: any[]
  presets: any[]
  selectedGroups: Set<string>
  saving: boolean
  handleBatchUpdate: (enabled?: boolean, modelUuid?: string, presetUuid?: string) => void
  toggleGroupSelection: (groupId: string) => void
  toggleAllGroups: () => void
}

