import { useEffect, useState } from 'react'
import {
  BrainCircuit,
  CalendarClock,
  List,
  SlidersHorizontal,
  Sparkles,
  Workflow,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api, type AIWorkspaceMode } from '@/utils/api'
import { cn } from '@/utils/cn'

type Mode = AIWorkspaceMode
type AgentSection = 'sessions' | 'skills' | 'tasks' | 'tools' | 'settings'
type AssistantSection = 'sessions' | 'schedule' | 'notes' | 'preferences' | 'settings'
type Section = AgentSection | AssistantSection

type NavItem<T extends string> = {
  key: T
  icon: LucideIcon
  label: string
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
  { key: 'sessions', icon: List, label: '会话' },
  { key: 'schedule', icon: CalendarClock, label: '日程' },
  { key: 'notes', icon: BrainCircuit, label: '记录' },
  { key: 'preferences', icon: SlidersHorizontal, label: '偏好' },
  { key: 'settings', icon: Workflow, label: '设置' },
]

const MODE_STORAGE_KEY = 'ai_workspace_mode'

function normalizeMode(mode: string | null | undefined): Mode {
  return mode === 'assistant' ? 'assistant' : 'agent'
}

export default function AIPage() {
  const [mode, setMode] = useState<Mode>(() => normalizeMode(localStorage.getItem(MODE_STORAGE_KEY)))
  const [agentSection, setAgentSection] = useState<AgentSection>('sessions')
  const [assistantSection, setAssistantSection] = useState<AssistantSection>('sessions')
  const [isSavingMode, setIsSavingMode] = useState(false)
  const [modeLoaded, setModeLoaded] = useState(false)
  const [modeSaveError, setModeSaveError] = useState('')

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

  const handleModeSwitch = async (nextMode: Mode) => {
    if (nextMode === mode || isSavingMode) return

    const previousMode = mode
    setMode(nextMode)
    localStorage.setItem(MODE_STORAGE_KEY, nextMode)
    setModeSaveError('')
    setIsSavingMode(true)

    try {
      await api.updateAIWorkspaceConfig(nextMode)
    } catch {
      setMode(previousMode)
      localStorage.setItem(MODE_STORAGE_KEY, previousMode)
      setModeSaveError('模式保存失败，已回退到上一模式')
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

        {modeSaveError && (
          <div className="px-4 py-2 text-xs text-red-600 bg-red-50 border-b border-red-100">{modeSaveError}</div>
        )}

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
            <div className="flex-1 min-h-0 bg-white" />
          </div>
        </div>
      </div>
    </div>
  )
}
