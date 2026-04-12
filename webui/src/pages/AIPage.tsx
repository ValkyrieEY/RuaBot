import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Bot,
  BrainCircuit,
  Check,
  Cpu,
  ChevronDown,
  FileText,
  KeyRound,
  List,
  Plus,
  Server,
  Settings,
  Shield,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  User,
  Users,
  Workflow,
  Wrench,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useToast } from '@/components/Toast'
import { api, type AIWorkspaceMode } from '@/utils/api'
import { cn } from '@/utils/cn'

type Mode = AIWorkspaceMode
type AgentSection = 'sessions' | 'skills' | 'tasks' | 'tools' | 'settings'
type AssistantSection = 'groups' | 'personal' | 'providers' | 'models' | 'presets' | 'system'
type Section = AgentSection | AssistantSection

type NavItem<T extends string> = {
  key: T
  icon: LucideIcon
  label: string
}

type GroupPolicy = {
  id: string
  name: string
  enabled: boolean
  trigger: 'mention' | 'keyword' | 'prefix' | 'smart' | 'always'
  keywords: string
  prefixes: string
  model: string
  preset: string
  memory: 'off' | 'session' | 'long'
  cooldown: number
  dailyLimit: number
}

type PrivatePolicy = {
  id: string
  name: string
  enabled: boolean
  access: 'allow_all' | 'deny_all' | 'allow_list' | 'deny_list'
  model: string
  preset: string
  memory: 'off' | 'session' | 'long'
}

type ProviderConfig = {
  id: string
  name: string
  enabled: boolean
  baseUrl: string
  apiKey: string
  timeout: number
  priority: number
}

type ModelCapability = 'text' | 'image'
type ModelApiFormat = 'openai' | 'gemini'

type ModelConfig = {
  id: string
  provider: string
  enabled: boolean
  context: string
  capabilities: ModelCapability[]
  apiFormat: ModelApiFormat
  fallback: string
}

type PresetConfig = {
  id: string
  name: string
  enabled: boolean
  model: string
  temperature: number
  prompt: string
}

type SystemConfig = {
  enabled: boolean
  auditEnabled: boolean
  memoryEnabled: boolean
  safetyLevel: 'low' | 'balanced' | 'strict'
  maxConcurrent: number
  requestTimeout: number
}

type AssistantConfig = {
  groups: GroupPolicy[]
  personal: PrivatePolicy[]
  providers: ProviderConfig[]
  models: ModelConfig[]
  presets: PresetConfig[]
  system: SystemConfig
}

type ChatContact = {
  id?: string | number
  name?: string
  avatar?: string
  group_id?: string | number
  group_name?: string
  user_id?: string | number
  nickname?: string
  remark?: string
}

const modeLabel: Record<Mode, string> = {
  agent: 'Agent',
  assistant: 'Assistant',
}

const agentNavItems: NavItem<AgentSection>[] = [
  { key: 'sessions', icon: List, label: '会话' },
  { key: 'skills', icon: Sparkles, label: '技能' },
  { key: 'tasks', icon: Workflow, label: '任务' },
  { key: 'tools', icon: Wrench, label: '工具' },
  { key: 'settings', icon: SlidersHorizontal, label: '设置' },
]

const assistantNavItems: NavItem<AssistantSection>[] = [
  { key: 'groups', icon: Users, label: '群组开关' },
  { key: 'personal', icon: User, label: '个人开关' },
  { key: 'providers', icon: Server, label: '服务商设置' },
  { key: 'models', icon: Cpu, label: '模型设置' },
  { key: 'presets', icon: FileText, label: '预设设置' },
  { key: 'system', icon: Settings, label: '系统设置' },
]

const MODE_STORAGE_KEY = 'ai_workspace_mode'

const defaultAssistantConfig: AssistantConfig = {
  groups: [],
  personal: [],
  providers: [],
  models: [],
  presets: [],
  system: {
    enabled: true,
    auditEnabled: true,
    memoryEnabled: true,
    safetyLevel: 'balanced',
    maxConcurrent: 4,
    requestTimeout: 60,
  },
}

function normalizeMode(mode: string | null | undefined): Mode {
  return mode === 'assistant' ? 'assistant' : 'agent'
}

function normalizeModelCapabilities(value: any): ModelCapability[] {
  const rawValues = Array.isArray(value?.capabilities)
    ? value.capabilities
    : String(value?.capability || '').split(/[,，/、\s]+/)
  const normalized = new Set<ModelCapability>()
  rawValues.forEach((item: any) => {
    const text = String(item || '').trim().toLowerCase()
    if (!text) return
    if (['text', '文本', '文字'].includes(text)) normalized.add('text')
    if (['image', 'vision', '图片', '图像', '视觉', '多模态'].includes(text)) normalized.add('image')
  })
  if (normalized.size === 0) normalized.add('text')
  return Array.from(normalized)
}

function normalizeModelApiFormat(value: any): ModelApiFormat {
  const text = String(value || '').trim().toLowerCase()
  if (['gemini', 'genimi', 'google'].includes(text)) return 'gemini'
  return 'openai'
}

function normalizeModelConfig(item: any): ModelConfig {
  return {
    id: String(item?.id || ''),
    provider: String(item?.provider || ''),
    enabled: Boolean(item?.enabled),
    context: String(item?.context || '128K'),
    capabilities: normalizeModelCapabilities(item),
    apiFormat: normalizeModelApiFormat(item?.apiFormat || item?.format || item?.api_format),
    fallback: String(item?.fallback || ''),
  }
}

function mergeAssistantConfig(value: any): AssistantConfig {
  if (!value || typeof value !== 'object') return defaultAssistantConfig
  return {
    groups: Array.isArray(value.groups)
      ? value.groups.map((item: any) => ({ keywords: '', prefixes: '/', memory: 'session', ...item }))
      : defaultAssistantConfig.groups,
    personal: Array.isArray(value.personal)
      ? value.personal.map((item: any) => ({ access: 'allow_list', memory: 'session', ...item }))
      : defaultAssistantConfig.personal,
    providers: Array.isArray(value.providers) ? value.providers : defaultAssistantConfig.providers,
    models: Array.isArray(value.models) ? value.models.map(normalizeModelConfig) : defaultAssistantConfig.models,
    presets: Array.isArray(value.presets) ? value.presets : defaultAssistantConfig.presets,
    system: value.system && typeof value.system === 'object'
      ? { ...defaultAssistantConfig.system, ...value.system }
      : defaultAssistantConfig.system,
  }
}

function firstModelId(config: AssistantConfig) {
  return config.models[0]?.id || ''
}

function enabledPresetNames(config: AssistantConfig) {
  return config.presets
    .filter((item) => item.enabled && item.name.trim())
    .map((item) => item.name.trim())
}

function normalizePresetReferences(config: AssistantConfig): AssistantConfig {
  const allowed = new Set(enabledPresetNames(config))
  const clearInvalidPreset = <T extends { preset: string }>(item: T): T => {
    const preset = String(item.preset || '').trim()
    if (!preset || allowed.has(preset)) return { ...item, preset }
    return { ...item, preset: '' }
  }

  return {
    ...config,
    groups: config.groups.map(clearInvalidPreset),
    personal: config.personal.map(clearInvalidPreset),
  }
}

function createGroupPolicyFromContact(contact: ChatContact, config: AssistantConfig): GroupPolicy {
  const id = String(contact.id ?? contact.group_id ?? '')
  return {
    id,
    name: String(contact.name ?? contact.group_name ?? `群聊 ${id}`),
    enabled: false,
    trigger: 'mention',
    keywords: '',
    prefixes: '/',
    model: firstModelId(config),
    preset: '',
    memory: 'session',
    cooldown: 10,
    dailyLimit: 100,
  }
}

function serializeAssistantConfig(config: AssistantConfig) {
  return JSON.stringify(config)
}

function createPrivatePolicyFromContact(contact: ChatContact, config: AssistantConfig): PrivatePolicy {
  const id = String(contact.id ?? contact.user_id ?? '')
  return {
    id,
    name: String(contact.name ?? contact.remark ?? contact.nickname ?? `用户 ${id}`),
    enabled: false,
    access: 'allow_list',
    model: firstModelId(config),
    preset: '',
    memory: 'session',
  }
}

function mergePoliciesWithContacts<T extends { id: string; name: string }>(
  saved: T[],
  contacts: ChatContact[],
  createPolicy: (contact: ChatContact) => T,
) {
  const savedById = new Map(saved.map((item) => [String(item.id), item]))
  const contactIds = new Set<string>()
  const merged = contacts
    .map((contact) => {
      const id = String(contact.id ?? contact.group_id ?? contact.user_id ?? '')
      if (!id) return null
      contactIds.add(id)
      const base = createPolicy(contact)
      return { ...base, ...savedById.get(id), id, name: base.name }
    })
    .filter((item): item is T => Boolean(item))

  return merged
}

function removeSeededDemoPolicies(config: AssistantConfig) {
  const demoGroupIds = new Set(['10001', '10002', '10003'])
  const demoPersonalIds = new Set(['admin', 'friends', 'strangers'])
  return {
    ...config,
    groups: config.groups.filter((item) => !demoGroupIds.has(String(item.id))),
    personal: config.personal.filter((item) => !demoPersonalIds.has(String(item.id))),
  }
}

export default function AIPage() {
  const toast = useToast()
  const [mode, setMode] = useState<Mode>(() => normalizeMode(localStorage.getItem(MODE_STORAGE_KEY)))
  const [agentSection, setAgentSection] = useState<AgentSection>('sessions')
  const [assistantSection, setAssistantSection] = useState<AssistantSection>('groups')
  const [isSavingMode, setIsSavingMode] = useState(false)
  const [modeLoaded, setModeLoaded] = useState(false)
  const [assistantConfig, setAssistantConfig] = useState<AssistantConfig>(defaultAssistantConfig)
  const [assistantLoaded, setAssistantLoaded] = useState(false)
  const [, setIsSavingAssistant] = useState(false)
  const assistantSaveTimerRef = useRef<number | null>(null)
  const assistantSaveRequestRef = useRef(0)
  const assistantSaveSnapshotRef = useRef('')

  useEffect(() => {
    let cancelled = false

    const loadMode = async () => {
      try {
        const config = await api.getAIWorkspaceConfig()
        if (cancelled) return
        const loadedMode = normalizeMode(config?.mode)
        setMode(loadedMode)
        localStorage.setItem(MODE_STORAGE_KEY, loadedMode)
      } catch {
        if (cancelled) return
        const localMode = normalizeMode(localStorage.getItem(MODE_STORAGE_KEY))
        setMode(localMode)
      } finally {
        if (!cancelled) setModeLoaded(true)
      }
    }

    void loadMode()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadAssistantConfig = async () => {
      try {
        const [configResult, contactsResult] = await Promise.allSettled([
          api.getAIAssistantConfig(),
          api.getChatContacts(),
        ])
        if (cancelled) return

        if (configResult.status === 'rejected') {
          throw configResult.reason
        }

        let loadedConfig = removeSeededDemoPolicies(mergeAssistantConfig(configResult.value.config))
        if (contactsResult.status === 'fulfilled') {
          const contactGroups = Array.isArray(contactsResult.value.groups) ? contactsResult.value.groups : []
          const contactFriends = Array.isArray(contactsResult.value.friends) ? contactsResult.value.friends : []
          loadedConfig.groups = mergePoliciesWithContacts(
            loadedConfig.groups,
            contactGroups,
            (contact) => createGroupPolicyFromContact(contact, loadedConfig),
          )
          loadedConfig.personal = mergePoliciesWithContacts(
            loadedConfig.personal,
            contactFriends,
            (contact) => createPrivatePolicyFromContact(contact, loadedConfig),
          )
        } else {
          toast.warning('联系人加载失败，群组/个人开关仅显示已保存的手动策略')
        }

        const beforePresetNormalize = serializeAssistantConfig(loadedConfig)
        loadedConfig = normalizePresetReferences(loadedConfig)
        const afterPresetNormalize = serializeAssistantConfig(loadedConfig)
        assistantSaveSnapshotRef.current = beforePresetNormalize === afterPresetNormalize
          ? afterPresetNormalize
          : beforePresetNormalize
        setAssistantConfig(loadedConfig)
      } catch (error: any) {
        if (cancelled) return
        assistantSaveSnapshotRef.current = serializeAssistantConfig(defaultAssistantConfig)
        setAssistantConfig(defaultAssistantConfig)
        toast.error(error.response?.data?.detail || 'Assistant 配置加载失败')
      } finally {
        if (!cancelled) setAssistantLoaded(true)
      }
    }

    void loadAssistantConfig()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!assistantLoaded) return

    const snapshot = serializeAssistantConfig(assistantConfig)
    if (snapshot === assistantSaveSnapshotRef.current) return

    if (assistantSaveTimerRef.current) {
      window.clearTimeout(assistantSaveTimerRef.current)
    }

    const requestId = assistantSaveRequestRef.current + 1
    assistantSaveRequestRef.current = requestId
    setIsSavingAssistant(true)

    assistantSaveTimerRef.current = window.setTimeout(() => {
      const configToSave = assistantConfig

      void api.updateAIAssistantConfig(configToSave)
        .then(() => {
          if (assistantSaveRequestRef.current !== requestId) return
          assistantSaveSnapshotRef.current = snapshot
          toast.success('Assistant 配置已自动保存', 1800)
        })
        .catch((error: any) => {
          if (assistantSaveRequestRef.current !== requestId) return
          toast.error(error.response?.data?.detail || 'Assistant 配置自动保存失败')
        })
        .finally(() => {
          if (assistantSaveRequestRef.current !== requestId) return
          setIsSavingAssistant(false)
        })
    }, 700)

    return () => {
      if (assistantSaveTimerRef.current) {
        window.clearTimeout(assistantSaveTimerRef.current)
        assistantSaveTimerRef.current = null
      }
    }
  }, [assistantConfig, assistantLoaded])

  const assistantStats = useMemo(() => {
    const groups = assistantConfig.groups.filter((item) => item.enabled).length
    const personal = assistantConfig.personal.filter((item) => item.enabled).length
    const providers = assistantConfig.providers.filter((item) => item.enabled).length
    const models = assistantConfig.models.filter((item) => item.enabled).length
    return [
      { label: '群聊启用', value: `${groups}/${assistantConfig.groups.length}` },
      { label: '私聊启用', value: `${personal}/${assistantConfig.personal.length}` },
      { label: '服务商', value: `${providers}/${assistantConfig.providers.length}` },
      { label: '模型', value: `${models}/${assistantConfig.models.length}` },
    ]
  }, [assistantConfig])

  const handleModeSwitch = async (nextMode: Mode) => {
    if (nextMode === mode || isSavingMode) return

    const previousMode = mode
    setMode(nextMode)
    localStorage.setItem(MODE_STORAGE_KEY, nextMode)
    setIsSavingMode(true)

    try {
      await api.updateAIWorkspaceConfig(nextMode)
    } catch {
      setMode(previousMode)
      localStorage.setItem(MODE_STORAGE_KEY, previousMode)
      toast.error('模式保存失败，已回退到上一模式')
    } finally {
      setIsSavingMode(false)
    }
  }

  const navItems = mode === 'agent' ? agentNavItems : assistantNavItems
  const activeSection: Section = mode === 'agent' ? agentSection : assistantSection

  const handleSectionSwitch = (nextSection: Section) => {
    if (mode === 'agent') {
      setAgentSection(nextSection as AgentSection)
      return
    }
    setAssistantSection(nextSection as AssistantSection)
  }

  const updateAssistant = <K extends keyof AssistantConfig>(key: K, value: AssistantConfig[K]) => {
    setAssistantConfig((current) => normalizePresetReferences({ ...current, [key]: value }))
  }

  return (
    <div className="fixed top-16 left-0 md:left-64 right-0 bottom-0 overflow-hidden bg-white">
      <div className="h-full w-full flex flex-col bg-white">
        <header className="relative h-14 shrink-0 border-b border-slate-200 bg-white px-3 md:px-5 flex items-center justify-end">
          <div className="absolute left-1/2 -translate-x-1/2 h-9 border border-slate-200 rounded-xl p-1 bg-white flex items-center gap-1">
            {(['agent', 'assistant'] as Mode[]).map((item) => (
              <button
                key={item}
                type="button"
                disabled={isSavingMode || !modeLoaded}
                onClick={() => void handleModeSwitch(item)}
                className={cn(
                  'h-7 px-3 text-xs md:text-sm rounded-lg font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed',
                  mode === item
                    ? 'bg-primary-600 text-white'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100',
                )}
              >
                {modeLabel[item]}
              </button>
            ))}
          </div>

          <div className="text-xs text-slate-500">{isSavingMode ? '保存中...' : `${modeLabel[mode]} Mode`}</div>
        </header>

        <div className="min-h-0 flex-1 flex bg-white">
          <aside className="w-14 md:w-16 shrink-0 border-r border-slate-200 bg-white flex flex-col items-center py-3 gap-2">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = activeSection === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  title={item.label}
                  onClick={() => handleSectionSwitch(item.key)}
                  className={cn(
                    'h-10 w-10 rounded-lg flex items-center justify-center transition-colors',
                    active
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100',
                  )}
                >
                  <Icon className="w-4 h-4" />
                </button>
              )
            })}
          </aside>

          <div className="min-w-0 flex-1 flex flex-col bg-white">
            {mode === 'assistant' ? (
              <AssistantWorkspace
                section={assistantSection}
                config={assistantConfig}
                stats={assistantStats}
                loaded={assistantLoaded}
                onUpdate={updateAssistant}
              />
            ) : (
              <AgentWorkspace section={agentSection} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function AssistantWorkspace({
  section,
  config,
  stats,
  loaded,
  onUpdate,
}: {
  section: AssistantSection
  config: AssistantConfig
  stats: { label: string; value: string }[]
  loaded: boolean
  onUpdate: <K extends keyof AssistantConfig>(key: K, value: AssistantConfig[K]) => void
}) {
  const modelOptions = config.models.map((item) => item.id)
  const presetOptions = enabledPresetNames(config)

  return (
    <div className="flex-1 min-h-0 overflow-y-auto bg-slate-50">
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-5">
        <div className="bg-white border border-slate-200 rounded-2xl p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-primary-600" />
                <h1 className="text-xl font-bold text-slate-900">Assistant 模式</h1>
              </div>
              <p className="text-sm text-slate-500 mt-2">
                面向群聊和私聊的 AI 助手控制台：开关策略、服务商、模型、预设和系统策略统一管理。
              </p>
            </div>
            <div className="inline-flex items-center justify-center px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
              {!loaded ? '加载配置中...' : '自动保存已开启'}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
            {stats.map((item) => (
              <div key={item.label} className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-xs text-slate-500">{item.label}</p>
                <p className="text-lg font-semibold text-slate-900 mt-1">{item.value}</p>
              </div>
            ))}
          </div>
        </div>

        {section === 'groups' && (
          <GroupPolicyPanel
            groups={config.groups}
            modelOptions={modelOptions}
            presetOptions={presetOptions}
            onChange={(groups) => onUpdate('groups', groups)}
          />
        )}
        {section === 'personal' && (
          <PrivatePolicyPanel
            personal={config.personal}
            modelOptions={modelOptions}
            presetOptions={presetOptions}
            onChange={(personal) => onUpdate('personal', personal)}
          />
        )}
        {section === 'providers' && (
          <ProviderPanel
            providers={config.providers}
            onChange={(providers) => onUpdate('providers', providers)}
          />
        )}
        {section === 'models' && (
          <ModelPanel
            models={config.models}
            providers={config.providers}
            onChange={(models) => onUpdate('models', models)}
          />
        )}
        {section === 'presets' && (
          <PresetPanel
            presets={config.presets}
            modelOptions={modelOptions}
            onChange={(presets) => onUpdate('presets', presets)}
          />
        )}
        {section === 'system' && (
          <SystemPanel
            system={config.system}
            onChange={(system) => onUpdate('system', system)}
          />
        )}
      </div>
    </div>
  )
}

function AgentWorkspace({ section }: { section: AgentSection }) {
  const titleMap: Record<AgentSection, string> = {
    sessions: 'Agent 会话',
    skills: 'Agent 技能',
    tasks: 'Agent 任务',
    tools: 'Agent 工具',
    settings: 'Agent 设置',
  }

  return (
    <div className="flex-1 min-h-0 bg-white p-6">
      <div className="border border-slate-200 rounded-2xl p-6">
        <h1 className="text-xl font-bold text-slate-900">{titleMap[section]}</h1>
        <p className="text-sm text-slate-500 mt-2">Agent 模式后续开发，当前优先完成 Assistant。</p>
      </div>
    </div>
  )
}

function PanelShell({
  icon: Icon,
  title,
  description,
  children,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <section className="bg-white border border-slate-200 rounded-2xl">
      <div className="px-5 py-4 border-b border-slate-200 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center shrink-0">
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            <p className="text-sm text-slate-500 mt-1">{description}</p>
          </div>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function SwitchField({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cn('relative inline-flex h-6 w-11 min-w-[2.75rem] shrink-0 rounded-full transition-colors', checked ? 'bg-primary-600' : 'bg-slate-300')}
    >
      <span className={cn('absolute top-1 h-4 w-4 rounded-full bg-white transition-transform', checked ? 'translate-x-6' : 'translate-x-1')} />
    </button>
  )
}

function SelectField({
  value,
  onChange,
  children,
  emptyLabel,
}: {
  value: string
  onChange: (value: string) => void
  children: React.ReactNode
  emptyLabel?: string
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="w-full h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
    >
      {emptyLabel && <option value="">{emptyLabel}</option>}
      {children}
    </select>
  )
}

function TextField({ value, onChange, placeholder = '' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <input
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      className="w-full h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
    />
  )
}

function ReadOnlyValue({ value }: { value: string }) {
  return (
    <div className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-600 flex items-center">
      <span className="truncate">{value || '-'}</span>
    </div>
  )
}

function NumberField({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <input
      type="number"
      min={0}
      value={value}
      onChange={(event) => onChange(Number(event.target.value))}
      className="w-full h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
    />
  )
}

function CapabilityPicker({ value, onChange }: { value: ModelCapability[]; onChange: (value: ModelCapability[]) => void }) {
  const current = new Set<ModelCapability>(value.length ? value : ['text'])
  const [open, setOpen] = useState(false)
  const toggle = (capability: ModelCapability) => {
    const next = new Set(current)
    if (next.has(capability)) {
      next.delete(capability)
    } else {
      next.add(capability)
    }
    onChange(Array.from(next.size ? next : new Set<ModelCapability>(['text'])))
  }
  const label = [
    current.has('text') ? '文本' : '',
    current.has('image') ? '图片' : '',
  ].filter(Boolean).join('、') || '请选择能力'

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 text-left text-sm text-slate-700 transition-colors hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
      >
        <span className="truncate">{label}</span>
        <ChevronDown className={cn('h-4 w-4 shrink-0 text-slate-400 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-10 cursor-default"
            aria-label="关闭能力选择"
            onClick={() => setOpen(false)}
          />
          <div className="absolute left-0 right-0 top-10 z-20 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
            {([
              ['text', '文本'],
              ['image', '图片'],
            ] as Array<[ModelCapability, string]>).map(([key, itemLabel]) => {
              const checked = current.has(key)
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggle(key)}
                  className="flex w-full items-center justify-between px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50"
                >
                  <span>{itemLabel}</span>
                  <span
                    className={cn(
                      'flex h-5 w-5 items-center justify-center rounded border',
                      checked
                        ? 'border-primary-600 bg-primary-600 text-white'
                        : 'border-slate-300 bg-white text-transparent',
                    )}
                  >
                    <Check className="h-3.5 w-3.5" />
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function FieldLabel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-500 mb-1">{label}</span>
      {children}
    </label>
  )
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
      <p className="font-medium text-slate-800">{title}</p>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </div>
  )
}

function GroupPolicyPanel({
  groups,
  modelOptions,
  presetOptions,
  onChange,
}: {
  groups: GroupPolicy[]
  modelOptions: string[]
  presetOptions: string[]
  onChange: (groups: GroupPolicy[]) => void
}) {
  const toast = useToast()
  const [settingsGroupId, setSettingsGroupId] = useState<string | null>(null)
  const patch = (id: string, patchValue: Partial<GroupPolicy>) => {
    onChange(groups.map((item) => (item.id === id ? { ...item, ...patchValue } : item)))
  }
  const clearMemory = async (group: GroupPolicy, memoryType: 'session' | 'long') => {
    try {
      await api.clearAIAssistantMemory({ scope: 'group', target_id: group.id, memory_type: memoryType })
      toast.success(`${group.name} 的${memoryType === 'session' ? '会话' : '长期'}记忆已清空`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '清空记忆失败')
    }
  }

  return (
    <PanelShell
      icon={Users}
      title="群组开关"
      description="控制允许使用 AI 的群聊。触发关键词、前缀、记忆和限流模式。"
    >
      {groups.length === 0 && (
        <EmptyState title="没有可配置的群聊" description="请先确认 NapCat/OneBot 已连接并能获取群列表。" />
      )}
      <div className="space-y-3">
        {groups.map((group) => (
          <div key={group.id} className="relative border border-slate-200 rounded-xl p-4">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_8rem_11rem_11rem_5.5rem] xl:items-end">
              <FieldLabel label="群名称 / 群号">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <ReadOnlyValue value={group.name} />
                  <ReadOnlyValue value={group.id} />
                </div>
              </FieldLabel>
              <FieldLabel label="触发">
                <SelectField value={group.trigger} onChange={(trigger) => patch(group.id, { trigger: trigger as GroupPolicy['trigger'] })}>
                  <option value="mention">仅 @</option>
                  <option value="keyword">关键词</option>
                  <option value="prefix">前缀</option>
                  <option value="smart">智能判定</option>
                  <option value="always">全量响应</option>
                </SelectField>
              </FieldLabel>
              <FieldLabel label="模型">
                    <SelectField value={group.model} onChange={(model) => patch(group.id, { model })} emptyLabel="请先在模型设置中添加模型">
                      {modelOptions.map(optionNode)}
                    </SelectField>
                  </FieldLabel>
                  <FieldLabel label="预设">
                    <SelectField value={group.preset} onChange={(preset) => patch(group.id, { preset })} emptyLabel="无预设">
                      {presetOptions.map(optionNode)}
                    </SelectField>
              </FieldLabel>
              <div className="flex items-center justify-between xl:justify-end gap-3 pb-1">
                <button
                  type="button"
                  title="触发设置"
                  onClick={() => setSettingsGroupId(settingsGroupId === group.id ? null : group.id)}
                  className={cn(
                    'h-9 w-9 rounded-lg border flex items-center justify-center transition-colors',
                    settingsGroupId === group.id
                      ? 'border-primary-200 bg-primary-50 text-primary-700'
                      : 'border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900',
                  )}
                >
                  <Settings className="w-4 h-4" />
                </button>
                <SwitchField checked={group.enabled} onChange={(enabled) => patch(group.id, { enabled })} />
              </div>
            </div>
            {settingsGroupId === group.id && (
              <div className="absolute right-4 top-16 z-20 w-[min(30rem,calc(100vw-3rem))] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-900">触发设置</h3>
                    <p className="text-xs text-slate-500 mt-1">关键词和前缀互不影响；智能判定不走这些规则，会直接交给模型判断。</p>
                  </div>
                  <button type="button" onClick={() => setSettingsGroupId(null)} className="text-xs text-slate-500 hover:text-slate-900">
                    关闭
                  </button>
                </div>
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <FieldLabel label="记忆">
                      <SelectField value={group.memory} onChange={(memory) => patch(group.id, { memory: memory as GroupPolicy['memory'] })}>
                        <option value="off">关闭</option>
                        <option value="session">会话</option>
                        <option value="long">长期</option>
                      </SelectField>
                    </FieldLabel>
                    <FieldLabel label="冷却秒">
                      <NumberField value={group.cooldown} onChange={(cooldown) => patch(group.id, { cooldown })} />
                    </FieldLabel>
                    <FieldLabel label="日额度">
                      <NumberField value={group.dailyLimit} onChange={(dailyLimit) => patch(group.id, { dailyLimit })} />
                    </FieldLabel>
                  </div>
                  <FieldLabel label="本群关键词（逗号分隔）">
                    <TextField
                      value={group.keywords || ''}
                      onChange={(keywords) => patch(group.id, { keywords })}
                      placeholder="例如：小易,/ai,机器人"
                    />
                  </FieldLabel>
                  <FieldLabel label="本群前缀（逗号分隔）">
                    <TextField
                      value={group.prefixes || ''}
                      onChange={(prefixes) => patch(group.id, { prefixes })}
                      placeholder="例如：/,!,#"
                    />
                  </FieldLabel>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    <SmallActionButton label="清空会话记忆" onClick={() => void clearMemory(group, 'session')} />
                    <SmallActionButton label="清空长期记忆" onClick={() => void clearMemory(group, 'long')} danger />
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </PanelShell>
  )
}

function PrivatePolicyPanel({
  personal,
  modelOptions,
  presetOptions,
  onChange,
}: {
  personal: PrivatePolicy[]
  modelOptions: string[]
  presetOptions: string[]
  onChange: (personal: PrivatePolicy[]) => void
}) {
  const toast = useToast()
  const patch = (id: string, patchValue: Partial<PrivatePolicy>) => {
    onChange(personal.map((item) => (item.id === id ? { ...item, ...patchValue } : item)))
  }
  const clearMemory = async (policy: PrivatePolicy, memoryType: 'session' | 'long') => {
    try {
      await api.clearAIAssistantMemory({ scope: 'private', target_id: policy.id, memory_type: memoryType })
      toast.success(`${policy.name} 的${memoryType === 'session' ? '会话' : '长期'}记忆已清空`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '清空记忆失败')
    }
  }

  return (
    <PanelShell
      icon={User}
      title="个人开关"
      description="控制私聊是否允许使用 AI，右侧开关就是允许/拒绝，可单独配置模型、预设和记忆级别。"
    >
      {personal.length === 0 && (
        <EmptyState title="没有可配置的私聊对象" description="请先确认 NapCat/OneBot 已连接并能获取好友列表。" />
      )}
      <div className="space-y-3">
        {personal.map((policy) => (
          <div key={policy.id} className="border border-slate-200 rounded-xl p-4">
            <div className="grid gap-3 xl:grid-cols-[1fr_10rem_10rem_8rem_9rem_4rem] xl:items-end">
              <FieldLabel label="昵称 / QQ号">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <ReadOnlyValue value={policy.name} />
                  <ReadOnlyValue value={policy.id} />
                </div>
              </FieldLabel>
              <FieldLabel label="模型">
                <SelectField value={policy.model} onChange={(model) => patch(policy.id, { model })} emptyLabel="请先在模型设置中添加模型">
                  {modelOptions.map(optionNode)}
                </SelectField>
              </FieldLabel>
              <FieldLabel label="预设">
                <SelectField value={policy.preset} onChange={(preset) => patch(policy.id, { preset })} emptyLabel="无预设">
                  {presetOptions.map(optionNode)}
                </SelectField>
              </FieldLabel>
              <FieldLabel label="记忆">
                <SelectField value={policy.memory} onChange={(memory) => patch(policy.id, { memory: memory as PrivatePolicy['memory'] })}>
                  <option value="off">关闭</option>
                  <option value="session">会话</option>
                  <option value="long">长期</option>
                </SelectField>
              </FieldLabel>
              <FieldLabel label="清空记忆">
                <div className="grid grid-cols-2 gap-2">
                  <SmallActionButton label="会话" onClick={() => void clearMemory(policy, 'session')} />
                  <SmallActionButton label="长期" onClick={() => void clearMemory(policy, 'long')} danger />
                </div>
              </FieldLabel>
              <div className="flex items-center justify-between xl:justify-end gap-3 pb-1">
                <SwitchField checked={policy.enabled} onChange={(enabled) => patch(policy.id, { enabled })} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  )
}

function ProviderPanel({ providers, onChange }: { providers: ProviderConfig[]; onChange: (providers: ProviderConfig[]) => void }) {
  const patch = (id: string, patchValue: Partial<ProviderConfig>) => {
    onChange(providers.map((item) => (item.id === id ? { ...item, ...patchValue } : item)))
  }

  const addProvider = () => {
    onChange([
      ...providers,
      {
        id: `provider-${Date.now()}`,
        name: '新服务商',
        enabled: false,
        baseUrl: '',
        apiKey: '',
        timeout: 60,
        priority: providers.length + 1,
      },
    ])
  }

  return (
    <PanelShell
      icon={Server}
      title="服务商设置"
      description="配置模型服务商、API 地址、密钥、超时和优先级，供模型路由统一调用。"
      action={<AddButton onClick={addProvider} label="新增服务商" />}
    >
      {providers.length === 0 && (
        <EmptyState title="还没有模型服务商" description="请新增真实服务商并填写 Base URL 与 API Key，模型设置会引用这里的服务商。" />
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        {providers.map((provider) => (
          <div key={provider.id} className="border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-primary-600" />
                <span className="font-medium text-slate-900">{provider.name}</span>
              </div>
              <div className="flex items-center gap-3">
                <SwitchField checked={provider.enabled} onChange={(enabled) => patch(provider.id, { enabled })} />
                <IconButton title="删除服务商" onClick={() => onChange(providers.filter((item) => item.id !== provider.id))}>
                  <Trash2 className="w-4 h-4" />
                </IconButton>
              </div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <FieldLabel label="服务商 ID">
                <TextField value={provider.id} onChange={(id) => patch(provider.id, { id })} />
              </FieldLabel>
              <FieldLabel label="名称">
                <TextField value={provider.name} onChange={(name) => patch(provider.id, { name })} />
              </FieldLabel>
              <FieldLabel label="Base URL">
                <TextField value={provider.baseUrl} onChange={(baseUrl) => patch(provider.id, { baseUrl })} />
              </FieldLabel>
              <FieldLabel label="API Key">
                <TextField value={provider.apiKey} onChange={(apiKey) => patch(provider.id, { apiKey })} placeholder="留空表示未配置" />
              </FieldLabel>
              <FieldLabel label="超时秒数">
                <NumberField value={provider.timeout} onChange={(timeout) => patch(provider.id, { timeout })} />
              </FieldLabel>
              <FieldLabel label="优先级">
                <NumberField value={provider.priority} onChange={(priority) => patch(provider.id, { priority })} />
              </FieldLabel>
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  )
}

function ModelPanel({
  models,
  providers,
  onChange,
}: {
  models: ModelConfig[]
  providers: ProviderConfig[]
  onChange: (models: ModelConfig[]) => void
}) {
  const patch = (id: string, patchValue: Partial<ModelConfig>) => {
    onChange(models.map((item) => (item.id === id ? { ...item, ...patchValue } : item)))
  }

  const addModel = () => {
    onChange([
      ...models,
      {
        id: `model-${Date.now()}`,
        provider: providers[0]?.name || 'OpenAI',
        enabled: false,
        context: '128K',
        capabilities: ['text'],
        apiFormat: 'openai',
        fallback: models[0]?.id || '',
      },
    ])
  }

  return (
    <PanelShell
      icon={Cpu}
      title="模型设置"
      description="配置模型能力、上下文长度、所属服务商和失败降级模型，供群聊/私聊策略引用。"
      action={<AddButton onClick={addModel} label="新增模型" />}
    >
      {models.length === 0 && (
        <EmptyState title="还没有模型" description="请新增真实模型 ID，并绑定已经配置好的服务商。" />
      )}
      <div className="space-y-3">
        {models.map((model) => (
          <div key={model.id} className="border border-slate-200 rounded-xl p-4">
            <div className="grid gap-3 xl:grid-cols-[1fr_10rem_8rem_10rem_11rem_10rem_6rem] xl:items-end">
              <FieldLabel label="模型 ID">
                <TextField value={model.id} onChange={(id) => patch(model.id, { id })} />
              </FieldLabel>
              <FieldLabel label="服务商">
                <SelectField value={model.provider} onChange={(provider) => patch(model.id, { provider })}>
                  {providers.map((provider) => (
                    <option key={provider.id} value={provider.name}>{provider.name}</option>
                  ))}
                </SelectField>
              </FieldLabel>
              <FieldLabel label="上下文">
                <TextField value={model.context} onChange={(context) => patch(model.id, { context })} />
              </FieldLabel>
              <FieldLabel label="接口格式">
                <SelectField value={model.apiFormat} onChange={(apiFormat) => patch(model.id, { apiFormat: apiFormat as ModelApiFormat })}>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                </SelectField>
              </FieldLabel>
              <FieldLabel label="能力标签">
                <CapabilityPicker
                  value={model.capabilities}
                  onChange={(capabilities) => patch(model.id, { capabilities })}
                />
              </FieldLabel>
              <FieldLabel label="降级模型">
                <SelectField value={model.fallback} onChange={(fallback) => patch(model.id, { fallback })}>
                  <option value="">无降级</option>
                  {models.map((item) => (
                    <option key={item.id} value={item.id} disabled={item.id === model.id}>{item.id}</option>
                  ))}
                </SelectField>
              </FieldLabel>
              <div className="flex items-center justify-between xl:justify-end gap-3 pb-1">
                <SwitchField checked={model.enabled} onChange={(enabled) => patch(model.id, { enabled })} />
                <IconButton title="删除" onClick={() => onChange(models.filter((item) => item.id !== model.id))}>
                  <Trash2 className="w-4 h-4" />
                </IconButton>
              </div>
            </div>
          </div>
        ))}
      </div>
    </PanelShell>
  )
}

function PresetPanel({
  presets,
  modelOptions,
  onChange,
}: {
  presets: PresetConfig[]
  modelOptions: string[]
  onChange: (presets: PresetConfig[]) => void
}) {
  const [activeId, setActiveId] = useState(presets[0]?.id || '')
  const active = presets.find((item) => item.id === activeId) || presets[0]

  const patch = (id: string, patchValue: Partial<PresetConfig>) => {
    onChange(presets.map((item) => (item.id === id ? { ...item, ...patchValue } : item)))
  }

  const addPreset = () => {
    const next: PresetConfig = {
      id: `preset-${Date.now()}`,
      name: '新预设',
      enabled: true,
      model: modelOptions[0] || '',
      temperature: 0.4,
      prompt: '请在这里编写系统提示词。',
    }
    onChange([...presets, next])
    setActiveId(next.id)
  }

  const deletePreset = (id: string) => {
    const nextPresets = presets.filter((item) => item.id !== id)
    onChange(nextPresets)
    if (activeId === id) {
      setActiveId(nextPresets[0]?.id || '')
    }
  }

  return (
    <PanelShell
      icon={FileText}
      title="预设设置"
      description="配置自定义预设，包括默认模型、温度和系统提示词，群聊与私聊策略可以复用。"
      action={<AddButton onClick={addPreset} label="新增预设" />}
    >
      {presets.length === 0 ? (
        <EmptyState title="还没有预设" description="请新增预设并填写系统提示词，群组/个人策略会引用这里的预设名称。" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[18rem_1fr]">
          <div className="space-y-2">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => setActiveId(preset.id)}
                className={cn(
                  'w-full text-left rounded-xl border px-4 py-3 transition-colors',
                  active?.id === preset.id
                    ? 'border-primary-200 bg-primary-50 text-primary-800'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{preset.name}</span>
                  <span className={cn('w-2 h-2 rounded-full', preset.enabled ? 'bg-emerald-500' : 'bg-slate-300')} />
                </div>
                <p className="text-xs text-slate-500 mt-1">{preset.model}</p>
              </button>
            ))}
          </div>

          {active && (
          <div className="border border-slate-200 rounded-xl p-4">
            <div className="flex items-center justify-between gap-3 mb-4">
              <h3 className="font-semibold text-slate-900">{active.name}</h3>
              <div className="flex items-center gap-3">
                <SwitchField checked={active.enabled} onChange={(enabled) => patch(active.id, { enabled })} />
                <IconButton title="删除预设" onClick={() => deletePreset(active.id)}>
                  <Trash2 className="w-4 h-4" />
                </IconButton>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <FieldLabel label="预设 ID">
                <TextField value={active.id} onChange={(id) => patch(active.id, { id })} />
              </FieldLabel>
              <FieldLabel label="名称">
                <TextField value={active.name} onChange={(name) => patch(active.id, { name })} />
              </FieldLabel>
              <FieldLabel label="默认模型">
                <SelectField value={active.model} onChange={(model) => patch(active.id, { model })} emptyLabel="请先在模型设置中添加模型">
                  {modelOptions.map(optionNode)}
                </SelectField>
              </FieldLabel>
            </div>
            <div className="mt-4">
              <FieldLabel label={`温度 ${active.temperature}`}>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={active.temperature}
                  onChange={(event) => patch(active.id, { temperature: Number(event.target.value) })}
                  className="w-full accent-primary-600"
                />
              </FieldLabel>
            </div>
            <div className="mt-4">
              <FieldLabel label="系统提示词">
                <textarea
                  value={active.prompt}
                  onChange={(event) => patch(active.id, { prompt: event.target.value })}
                  className="w-full min-h-44 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </FieldLabel>
            </div>
          </div>
          )}
        </div>
      )}
    </PanelShell>
  )
}

function SystemPanel({ system, onChange }: { system: SystemConfig; onChange: (system: SystemConfig) => void }) {
  const patch = (patchValue: Partial<SystemConfig>) => onChange({ ...system, ...patchValue })

  return (
    <PanelShell
      icon={Settings}
      title="系统设置"
      description="配置 Assistant 全局运行策略，包括总开关、审计、记忆、安全、并发和请求超时。"
    >
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <div className="grid gap-4 lg:grid-cols-2">
          <SystemToggle
            icon={Zap}
            title="Assistant 总开关"
            description="关闭后不会处理任何群聊或私聊 AI 请求。"
            checked={system.enabled}
            onChange={(enabled) => patch({ enabled })}
          />
          <SystemToggle
            icon={Shield}
            title="审计记录"
            description="记录触发规则、模型选择、调用耗时和响应结果。"
            checked={system.auditEnabled}
            onChange={(auditEnabled) => patch({ auditEnabled })}
          />
          <SystemToggle
            icon={BrainCircuit}
            title="记忆系统"
            description="允许 Assistant 使用会话摘要和长期用户画像。"
            checked={system.memoryEnabled}
            onChange={(memoryEnabled) => patch({ memoryEnabled })}
          />
          <div className="border border-slate-200 rounded-xl p-4">
            <FieldLabel label="安全等级">
              <SelectField value={system.safetyLevel} onChange={(safetyLevel) => patch({ safetyLevel: safetyLevel as SystemConfig['safetyLevel'] })}>
                <option value="low">宽松</option>
                <option value="balanced">平衡</option>
                <option value="strict">严格</option>
              </SelectField>
            </FieldLabel>
            <p className="mt-2 text-xs text-slate-500">
              宽松只拦截高危请求；平衡会拦截违法、隐私、危险操作；严格会额外收紧成人、辱骂和越狱类内容。
            </p>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <FieldLabel label="最大并发">
                <NumberField value={system.maxConcurrent} onChange={(maxConcurrent) => patch({ maxConcurrent })} />
              </FieldLabel>
              <FieldLabel label="请求超时秒">
                <NumberField value={system.requestTimeout} onChange={(requestTimeout) => patch({ requestTimeout })} />
              </FieldLabel>
            </div>
          </div>
        </div>

        <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
          <h3 className="font-semibold text-slate-900">Assistant 运行链路</h3>
          <div className="mt-4 space-y-3">
            {['消息接入', '开关判断', '安全过滤', '上下文装配', '模型路由', '生成回复', '审计落库'].map((step, index) => (
              <div key={step} className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary-600 text-white text-xs flex items-center justify-center">{index + 1}</span>
                <span className="text-sm text-slate-700">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PanelShell>
  )
}

function SystemToggle({
  icon: Icon,
  title,
  description,
  checked,
  onChange,
}: {
  icon: LucideIcon
  title: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="border border-slate-200 rounded-xl p-4 flex items-start justify-between gap-4">
      <div className="min-w-0 flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary-50 text-primary-600 flex items-center justify-center shrink-0">
          <Icon className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <h3 className="font-medium text-slate-900">{title}</h3>
          <p className="text-sm text-slate-500 mt-1">{description}</p>
        </div>
      </div>
      <SwitchField checked={checked} onChange={onChange} />
    </div>
  )
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-300 text-sm font-medium text-slate-700 hover:bg-slate-50"
    >
      <Plus className="w-4 h-4" />
      {label}
    </button>
  )
}

function SmallActionButton({ label, onClick, danger = false }: { label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'h-9 rounded-lg border px-2 text-xs font-medium transition-colors',
        danger
          ? 'border-red-200 text-red-600 hover:bg-red-50'
          : 'border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900',
      )}
    >
      {label}
    </button>
  )
}

function IconButton({ title, children, onClick }: { title: string; children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="h-9 w-9 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center"
    >
      {children}
    </button>
  )
}

function optionNode(value: string) {
  return (
    <option key={value} value={value}>
      {value}
    </option>
  )
}
