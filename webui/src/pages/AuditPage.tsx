import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft,
  ArrowDown,
  CalendarDays,
  FileClock,
  FileText,
  History,
  RefreshCw,
  Search,
  Terminal,
  Trash2,
} from 'lucide-react'
import { api, type SystemLogFile, type SystemLogFileContent } from '@/utils/api'
import { useToast } from '@/components/Toast'

interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
  exception?: string
  [key: string]: any
}

type LogTab = 'realtime' | 'history'

const LOG_LIMIT = 300
const POLL_INTERVAL_MS = 3000
const HISTORY_POLL_INTERVAL_MS = 15000
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
  const toast = useToast()
  const [activeTab, setActiveTab] = useState<LogTab>('realtime')
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loadingRealtime, setLoadingRealtime] = useState(true)
  const [realtimeError, setRealtimeError] = useState('')
  const [historyFiles, setHistoryFiles] = useState<SystemLogFile[]>([])
  const [historySearch, setHistorySearch] = useState('')
  const [historyDate, setHistoryDate] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [lastRealtimeUpdated, setLastRealtimeUpdated] = useState<Date | null>(null)
  const [selectedHistoryFileName, setSelectedHistoryFileName] = useState('')
  const [viewerFile, setViewerFile] = useState<SystemLogFileContent | null>(null)
  const [viewerLoading, setViewerLoading] = useState(false)
  const [viewerError, setViewerError] = useState('')
  const [deletingFileName, setDeletingFileName] = useState('')
  const [isRealtimeAtBottom, setIsRealtimeAtBottom] = useState(true)
  const terminalRef = useRef<HTMLDivElement | null>(null)
  const shouldStickRealtimeBottomRef = useRef(true)

  const scrollRealtimeToBottom = (behavior: ScrollBehavior = 'auto') => {
    const terminal = terminalRef.current
    if (!terminal) return
    terminal.scrollTo({ top: terminal.scrollHeight, behavior })
  }

  const updateRealtimeScrollState = () => {
    const terminal = terminalRef.current
    if (!terminal) return
    const nearBottom = terminal.scrollHeight - terminal.scrollTop - terminal.clientHeight <= 80
    shouldStickRealtimeBottomRef.current = nearBottom
    setIsRealtimeAtBottom(nearBottom)
  }

  const loadRealtimeLogs = async (initial = false) => {
    if (initial) setLoadingRealtime(true)

    try {
      const data = await api.getSystemLogs(LOG_LIMIT)
      setLogs(Array.isArray(data) ? data : [])
      setRealtimeError('')
      setLastRealtimeUpdated(new Date())
    } catch (error) {
      console.error('Failed to load system logs:', error)
      setRealtimeError('实时日志拉取失败，稍后自动重试')
    } finally {
      if (initial) {
        setLoadingRealtime(false)
      }
    }
  }

  const loadHistoryFiles = async (initial = false) => {
    if (initial) setLoadingHistory(true)

    try {
      const data = await api.getSystemLogFiles()
      setHistoryFiles(Array.isArray(data) ? data : [])
      setHistoryError('')
    } catch (error) {
      console.error('Failed to load system log files:', error)
      setHistoryError('历史日志列表加载失败，稍后再试')
    } finally {
      if (initial) {
        setLoadingHistory(false)
      }
    }
  }

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      await loadRealtimeLogs(true)
      if (cancelled) return
    }

    void run()

    const intervalId = window.setInterval(() => {
      if (!cancelled) {
        void loadRealtimeLogs(false)
      }
    }, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const run = async () => {
      await loadHistoryFiles(true)
      if (cancelled) return
    }

    void run()

    const intervalId = window.setInterval(() => {
      if (!cancelled) {
        void loadHistoryFiles(false)
      }
    }, HISTORY_POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [])

  const normalizedLogs = useMemo(() => {
    return [...logs].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  }, [logs])

  const filteredHistoryFiles = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase()

    return historyFiles.filter((file) => {
      const matchKeyword = !keyword || file.name.toLowerCase().includes(keyword)
      const matchDate = !historyDate || file.name.startsWith(historyDate)
      return matchKeyword && matchDate
    })
  }, [historyDate, historyFiles, historySearch])

  useEffect(() => {
    if (!terminalRef.current || activeTab !== 'realtime') return
    if (shouldStickRealtimeBottomRef.current) {
      scrollRealtimeToBottom('auto')
      setIsRealtimeAtBottom(true)
    }
  }, [activeTab, normalizedLogs])

  useEffect(() => {
    if (!viewerFile) return
    if (!historyFiles.some((file) => file.name === viewerFile.name)) {
      setViewerFile(null)
      setViewerError('')
      setSelectedHistoryFileName('')
    }
  }, [historyFiles, viewerFile])

  useEffect(() => {
    if (!selectedHistoryFileName) return
    if (!historyFiles.some((file) => file.name === selectedHistoryFileName)) {
      setSelectedHistoryFileName('')
      setViewerFile(null)
      setViewerError('')
    }
  }, [historyFiles, selectedHistoryFileName])

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

  const formatDateTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return timestamp
    }
  }

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    return `${(size / 1024 / 1024).toFixed(2)} MB`
  }

  const formatMessage = (log: LogEntry) => {
    const parsePythonDictLikeMessage = (raw: string): Record<string, string> | null => {
      const text = raw.trim()
      if (!text.startsWith('{') || !text.endsWith('}')) {
        return null
      }

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
    const extraFields = Object.entries(log).filter(([key, value]) => {
      if (standardFields.includes(key)) return false
      if (HIDDEN_EXTRA_FIELDS.has(key)) return false
      if (key.startsWith('_')) return false
      return value !== null && value !== undefined && String(value).trim() !== ''
    })

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
    if (lv === 'warning') return 'text-amber-300'
    if (lv === 'info') return 'text-cyan-300'
    if (lv === 'debug') return 'text-slate-300'
    return 'text-slate-200'
  }

  const openViewer = async (fileName: string) => {
    setSelectedHistoryFileName(fileName)
    setViewerLoading(true)
    setViewerError('')

    try {
      const data = await api.getSystemLogFile(fileName)
      setViewerFile(data)
    } catch (error: any) {
      console.error('Failed to open log viewer:', error)
      setViewerError(error?.response?.data?.detail || '日志读取失败')
      setViewerFile(null)
    } finally {
      setViewerLoading(false)
    }
  }

  const handleDelete = async (file: SystemLogFile) => {
    if (file.active) return

    const confirmed = window.confirm(`确认删除日志文件 ${file.name} 吗？`)
    if (!confirmed) return

    setDeletingFileName(file.name)
    try {
      await api.deleteSystemLogFile(file.name)
      if (viewerFile?.name === file.name || selectedHistoryFileName === file.name) {
        setSelectedHistoryFileName('')
        setViewerFile(null)
        setViewerError('')
      }
      await loadHistoryFiles(false)
    } catch (error: any) {
      console.error('Failed to delete log file:', error)
      toast.error(error?.response?.data?.detail || '删除日志文件失败')
    } finally {
      setDeletingFileName('')
    }
  }

  return (
    <div className="fixed top-16 left-0 right-0 bottom-0 md:left-64 flex bg-gray-50 overflow-hidden">
      <div className="flex w-full flex-col">
        <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6">
          <div className="flex items-stretch h-full min-w-0 -mb-px">
            <button
              type="button"
              onClick={() => setActiveTab('realtime')}
              className={`h-full px-4 md:px-6 text-sm transition-colors flex items-center gap-2 border-b-2 ${
                activeTab === 'realtime'
                  ? 'border-primary-600 text-primary-700 bg-gray-50'
                  : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <Terminal className="h-4 w-4" />
              <span>实时日志</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('history')}
              className={`h-full px-4 md:px-6 text-sm transition-colors flex items-center gap-2 border-b-2 ${
                activeTab === 'history'
                  ? 'border-primary-600 text-primary-700 bg-gray-50'
                  : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <History className="h-4 w-4" />
              <span>历史日志</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs md:text-sm text-gray-500">
            {activeTab === 'realtime' ? (
              <>
                <span className="hidden md:inline">自动刷新 {POLL_INTERVAL_MS / 1000}s</span>
                <button
                  type="button"
                  onClick={() => void loadRealtimeLogs(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="刷新"
                >
                  <RefreshCw className="h-4 w-4 text-gray-600" />
                </button>
              </>
            ) : (
              <>
                <span className="hidden md:inline">按日期自动分割</span>
                <button
                  type="button"
                  onClick={() => void loadHistoryFiles(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="刷新列表"
                >
                  <RefreshCw className="h-4 w-4 text-gray-600" />
                </button>
              </>
            )}
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-hidden">
          {activeTab === 'realtime' ? (
            <div className="relative flex h-full flex-col bg-slate-950">
              <div className="h-12 border-b border-slate-800 flex items-center justify-between px-4 md:px-6">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-rose-400"></span>
                    <span className="h-3 w-3 rounded-full bg-amber-300"></span>
                    <span className="h-3 w-3 rounded-full bg-emerald-400"></span>
                  </div>
                  <span className="text-sm text-slate-300">{t('systemLog.title')}</span>
                </div>
                <div className="text-xs text-slate-500">
                  {lastRealtimeUpdated ? `最后更新 ${lastRealtimeUpdated.toLocaleTimeString('zh-CN')}` : '正在连接'}
                </div>
              </div>

              <div
                ref={terminalRef}
                onScroll={updateRealtimeScrollState}
                className="custom-scrollbar flex-1 overflow-auto px-4 py-4 md:px-6 font-mono text-xs leading-6"
              >
                {loadingRealtime ? (
                  <div className="flex h-full items-center justify-center text-slate-400">正在连接日志流...</div>
                ) : (
                  <>
                    {realtimeError && (
                      <div className="mb-3 border border-red-500/30 bg-red-500/10 px-3 py-2 text-red-200">
                        {realtimeError}
                      </div>
                    )}

                    {normalizedLogs.length === 0 ? (
                      <div className="text-slate-500">{t('systemLog.noLogs')}</div>
                    ) : (
                      normalizedLogs.map((log, index) => (
                        <div
                          key={`${log.timestamp}-${index}`}
                          className={`${getLineColor(log.level)} break-words whitespace-pre-wrap`}
                        >
                          <span className="text-slate-500">[{formatTimestamp(log.timestamp)}]</span>{' '}
                          <span className="text-fuchsia-300">[{(log.level || 'info').toUpperCase()}]</span>{' '}
                          <span className="text-emerald-300">[{log.logger || '-'}]</span>{' '}
                          <span>{formatMessage(log)}</span>
                        </div>
                      ))
                    )}
                  </>
                )}
              </div>

              {!isRealtimeAtBottom ? (
                <button
                  type="button"
                  onClick={() => {
                    shouldStickRealtimeBottomRef.current = true
                    setIsRealtimeAtBottom(true)
                    scrollRealtimeToBottom('smooth')
                  }}
                  className="absolute bottom-5 right-5 z-10 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 text-xs font-medium text-slate-100 shadow-lg transition-colors hover:bg-slate-800"
                >
                  <ArrowDown className="h-4 w-4" />
                  返回底部
                </button>
              ) : null}

            </div>
          ) : (
            <div className="flex h-full overflow-hidden">
              <div
                className={`w-full md:w-80 md:shrink-0 bg-white md:border-r border-gray-200 flex-col ${
                  selectedHistoryFileName ? 'hidden md:flex' : 'flex'
                }`}
              >
                <div className="p-3 md:p-4 border-b border-gray-200">
                  <div className="flex items-center gap-2 mb-3">
                    <FileClock className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-900">历史日志文件</span>
                  </div>
                  <div className="relative mb-3">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      value={historySearch}
                      onChange={(e) => setHistorySearch(e.target.value)}
                      placeholder="搜索文件名"
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
                    />
                  </div>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <CalendarDays className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="date"
                        value={historyDate}
                        onChange={(e) => setHistoryDate(e.target.value)}
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
                      />
                    </div>
                    {(historySearch || historyDate) && (
                      <button
                        type="button"
                        onClick={() => {
                          setHistorySearch('')
                          setHistoryDate('')
                        }}
                        className="px-3 py-2 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg transition-colors text-sm"
                      >
                        清空
                      </button>
                    )}
                  </div>
                  <div className="mt-3 text-xs text-gray-500">
                    当前显示 {filteredHistoryFiles.length} / {historyFiles.length} 个文件
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto">
                  {loadingHistory ? (
                    <div className="flex items-center justify-center h-full text-sm text-gray-500">正在加载日志文件...</div>
                  ) : historyFiles.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-400 px-6 text-center">
                      <FileText className="w-12 h-12 mb-2" />
                      <p className="text-sm">暂无历史日志文件</p>
                    </div>
                  ) : filteredHistoryFiles.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-gray-400 px-6 text-center">
                      <Search className="w-12 h-12 mb-2" />
                      <p className="text-sm">没有匹配当前筛选条件的日志文件</p>
                    </div>
                  ) : (
                    <>
                      {historyError && (
                        <div className="mx-3 mt-3 border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 rounded-lg">
                          {historyError}
                        </div>
                      )}
                      {filteredHistoryFiles.map((file) => (
                        <div
                          key={file.name}
                          className={`border-b border-gray-100 transition-colors ${
                            selectedHistoryFileName === file.name ? 'bg-primary-50' : 'hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-stretch">
                            <button
                              type="button"
                              onClick={() => void openViewer(file.name)}
                              className="flex flex-1 items-start gap-3 px-3 md:px-4 py-3 text-left"
                            >
                              <div className="mt-0.5 text-gray-400">
                                <FileText className="w-4 h-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <div className="font-medium text-gray-900 truncate">{file.name}</div>
                                  {file.active && (
                                    <span className="px-2 py-0.5 text-xs bg-emerald-100 text-emerald-700 rounded">
                                      今日
                                    </span>
                                  )}
                                </div>
                                <div className="mt-1 text-xs text-gray-500">
                                  <div>大小 {formatFileSize(file.size)}</div>
                                  <div>更新于 {formatDateTime(file.modified_at)}</div>
                                </div>
                              </div>
                            </button>
                            <button
                              type="button"
                              disabled={file.active || deletingFileName === file.name}
                              onClick={() => void handleDelete(file)}
                              className={`w-14 flex items-center justify-center border-l transition-colors ${
                                file.active
                                  ? 'border-gray-100 text-gray-300 cursor-not-allowed'
                                  : 'border-red-100 bg-red-50 text-red-600 hover:bg-red-100'
                              }`}
                              title={file.active ? '当前正在写入的日志文件不可删除' : '删除日志文件'}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>

              <div
                className={`flex-1 min-w-0 flex-col bg-gray-50 ${
                  selectedHistoryFileName ? 'flex w-full' : 'hidden md:flex'
                }`}
              >
                <div className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6">
                  <div className="flex items-center gap-2 min-w-0">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedHistoryFileName('')
                        setViewerError('')
                      }}
                      className="md:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      title="返回列表"
                    >
                      <ArrowLeft className="w-5 h-5 text-gray-600" />
                    </button>
                    <History className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-900 truncate">
                      {selectedHistoryFileName || viewerFile?.name || '日志查看区'}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 hidden md:block">
                    {viewerFile ? '右侧直接显示完整日志内容' : '点击左侧文件直接在右侧查看'}
                  </div>
                </div>
                {viewerLoading ? (
                  <div className="flex-1 flex items-center justify-center text-gray-500">
                    正在加载日志内容...
                  </div>
                ) : viewerError ? (
                  <div className="flex-1 flex items-center justify-center px-6 text-center text-red-500">
                    {viewerError}
                  </div>
                ) : viewerFile ? (
                  <>
                    <div className="h-12 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6 text-xs text-gray-500">
                      <span>大小 {formatFileSize(viewerFile.size)}</span>
                      <span>更新于 {formatDateTime(viewerFile.modified_at)}</span>
                    </div>
                    <pre className="custom-scrollbar flex-1 min-w-0 overflow-auto bg-slate-950 px-4 py-4 md:px-6 font-mono text-xs leading-6 text-slate-200">
                      {viewerFile.content}
                    </pre>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-gray-400">
                    <div className="text-center px-6">
                      <History className="w-16 h-16 mx-auto mb-4" />
                      <p className="text-lg text-gray-600">选择左侧日志文件</p>
                      <p className="text-sm mt-2">右侧会直接显示完整历史日志内容</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="h-12 bg-white border-t border-gray-200"></div>
      </div>

    </div>
  )
}
