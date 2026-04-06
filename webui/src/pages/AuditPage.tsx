import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { Terminal } from 'lucide-react'

interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
  [key: string]: any
}

const LOG_LIMIT = 300
const POLL_INTERVAL_MS = 3000
const HIDDEN_EXTRA_FIELDS = new Set([
  'taskName',
  '_logger',
  '_name',
  'name',
  'created',
  'msecs',
  'relativeCreated',
  'pathname',
  'filename',
  'module',
  'exc_info',
  'exc_text',
  'stack_info',
  'lineno',
  'funcName',
  'processName',
  'process',
  'threadName',
  'thread',
])

export default function AuditPage() {
  const { t } = useTranslation()
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [loadError, setLoadError] = useState('')
  const terminalRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadLogs = async (initial = false) => {
      if (initial) setLoading(true)

      try {
        const data = await api.getSystemLogs(LOG_LIMIT)
        if (cancelled) return
        setLogs(Array.isArray(data) ? data : [])
        setLoadError('')
        setLastUpdated(new Date())
      } catch (error) {
        if (cancelled) return
        console.error('Failed to load system logs:', error)
        setLoadError('日志拉取失败，稍后自动重试')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadLogs(true)

    const intervalId = window.setInterval(() => {
      void loadLogs(false)
    }, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const normalizedLogs = useMemo(() => {
    return [...logs].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  }, [logs])

  useEffect(() => {
    if (!terminalRef.current) return
    terminalRef.current.scrollTop = terminalRef.current.scrollHeight
  }, [normalizedLogs])

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const formatted = date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      const ms = date.getMilliseconds().toString().padStart(3, '0')
      return `${formatted}.${ms}`
    } catch {
      return timestamp
    }
  }

  const formatMessage = (log: LogEntry) => {
    const parsePythonDictLikeMessage = (raw: string): Record<string, string> | null => {
      const text = raw.trim()
      if (!text.startsWith('{') || !text.endsWith('}')) {
        return null
      }

      // Extract simple Python-dict style pairs: 'key': 'value' / number / True/False/None
      const pairRegex = /'([^']+)'\s*:\s*('(?:[^'\\]|\\.)*'|True|False|None|-?\d+(?:\.\d+)?)/g
      const out: Record<string, string> = {}
      let match: RegExpExecArray | null = null

      while (true) {
        match = pairRegex.exec(text)
        if (!match) break
        const key = match[1]
        let value = match[2]
        if (value.startsWith("'") && value.endsWith("'")) {
          value = value.slice(1, -1)
        } else if (value === 'True') {
          value = 'true'
        } else if (value === 'False') {
          value = 'false'
        } else if (value === 'None') {
          value = 'null'
        }
        out[key] = value
      }

      return Object.keys(out).length > 0 ? out : null
    }

    const parts: string[] = []
    const seenPairs = new Set<string>()

    if (log.message && log.message !== '{}') {
      const parsedMessage = parsePythonDictLikeMessage(String(log.message))
      if (parsedMessage) {
        const eventText = parsedMessage.event || ''
        if (eventText) {
          parts.push(eventText)
        }
        Object.entries(parsedMessage)
          .filter(([key, value]) => {
            if (!value) return false
            if (HIDDEN_EXTRA_FIELDS.has(key)) return false
            return !['event', 'timestamp', 'logger', 'level'].includes(key)
          })
          .forEach(([key, value]) => {
            const pair = `${key}=${value}`
            if (!seenPairs.has(pair)) {
              seenPairs.add(pair)
              parts.push(pair)
            }
          })
      } else {
        parts.push(String(log.message))
      }
    }

    const standardFields = ['timestamp', 'level', 'logger', 'message', 'event', 'exception']
    const extraFields = Object.entries(log)
      .filter(
        ([key, value]) => {
          if (standardFields.includes(key)) return false
          if (HIDDEN_EXTRA_FIELDS.has(key)) return false
          if (key.startsWith('_')) return false
          return value !== null && value !== undefined && String(value).trim() !== ''
        },
      )

    if (extraFields.length > 0) {
      const fieldStrings = extraFields
        .map(([key, value]) =>
          typeof value === 'object' ? `${key}=${JSON.stringify(value)}` : `${key}=${String(value)}`,
        )
        .filter((pair) => {
          if (seenPairs.has(pair)) return false
          seenPairs.add(pair)
          return true
        })
      parts.push(fieldStrings.join(' | '))
    }

    if (log.exception) {
      parts.push(`exception=${String(log.exception)}`)
    }

    return parts.filter(Boolean).join(' | ')
  }

  const getLineColor = (level: string) => {
    const lv = level.toLowerCase()
    if (lv === 'error' || lv === 'critical') return 'text-red-300'
    if (lv === 'warning') return 'text-yellow-300'
    if (lv === 'info') return 'text-sky-300'
    if (lv === 'debug') return 'text-slate-300'
    return 'text-slate-200'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-4 max-w-full overflow-x-hidden">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{t('systemLog.title')}</h1>
          <p className="text-gray-500 text-sm mt-1">{t('systemLog.description')}</p>
        </div>
        <div className="text-xs text-gray-500 text-right">
          <div>自动刷新中（{POLL_INTERVAL_MS / 1000}s）</div>
          <div>{lastUpdated ? `最后更新: ${lastUpdated.toLocaleTimeString('zh-CN')}` : '正在连接日志流...'}</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-300 bg-slate-950 shadow-inner overflow-hidden">
        <div className="h-8 border-b border-slate-800 flex items-center px-3 text-xs text-slate-300 gap-2">
          <Terminal className="w-3.5 h-3.5" />
          <span>system.log</span>
        </div>

        <div
          ref={terminalRef}
          className="h-[calc(100vh-260px)] min-h-[420px] overflow-auto p-3 font-mono text-xs leading-6"
        >
          {loadError && <div className="text-red-300 mb-2">{loadError}</div>}

          {normalizedLogs.length === 0 ? (
            <div className="text-slate-400">{t('systemLog.noLogs')}</div>
          ) : (
            normalizedLogs.map((log, index) => (
              <div key={`${log.timestamp}-${index}`} className={`${getLineColor(log.level)} break-words whitespace-pre-wrap`}>
                <span className="text-slate-500">[{formatTimestamp(log.timestamp)}]</span>{' '}
                <span className="text-violet-300">[{(log.level || 'info').toUpperCase()}]</span>{' '}
                <span className="text-emerald-300">[{log.logger || '-'}]</span>{' '}
                <span>{formatMessage(log)}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
