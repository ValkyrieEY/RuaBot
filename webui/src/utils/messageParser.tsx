import React, { useState } from 'react'
import { MessageSquare, X } from 'lucide-react'
import { api, type ForwardMessageNode } from '@/utils/api'
import { toast } from '@/components/Toast'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildMediaProxyUrl(kind: 'image' | 'video' | 'record' | 'file', params: { url?: string; file?: string; name?: string }): string {
  const search = new URLSearchParams()
  search.set('kind', kind)
  if (params.url) {
    search.set('url', params.url)
  }
  if (params.file) {
    search.set('file', params.file)
  }
  if (params.name) {
    search.set('name', params.name)
  }
  return `${API_BASE_URL}/chat/media-proxy?${search.toString()}`
}

/**
 * CQ码解析工具
 */

interface CQCode {
  type: string
  params: Record<string, string>
}

type MessageCardProps = {
  label: string
  title: string
  subtitle?: string
  body?: React.ReactNode
  href?: string
  imageSrc?: string
  isSelf: boolean
  children?: React.ReactNode
}

type MessageRenderOptions = {
  atNames?: Record<string, string>
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function getForwardNodePayload(node: ForwardMessageNode): Record<string, any> {
  if (node && typeof node.data === 'object' && node.data) {
    return node.data
  }
  return (node || {}) as Record<string, any>
}

function getForwardNodeSender(node: ForwardMessageNode, index: number) {
  const payload = getForwardNodePayload(node)
  const sender = node.sender || payload.sender || {}
  const userId = payload.user_id || payload.uin || node.user_id || sender.user_id || ''
  const nickname = payload.nickname || payload.name || node.nickname || sender.nickname || `用户 ${userId || index + 1}`
  return {
    userId: stringifyValue(userId),
    nickname: stringifyValue(nickname),
  }
}

function stringifyParams(data: Record<string, any>): Record<string, string> {
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, stringifyValue(value)]))
}

function oneBotMessageToText(message: unknown): string {
  if (typeof message === 'string') return message
  if (Array.isArray(message)) {
    return message.map(segmentToMessageText).join('')
  }
  if (message && typeof message === 'object') {
    return segmentToMessageText(message)
  }
  return stringifyValue(message)
}

function segmentToMessageText(segment: unknown): string {
  if (typeof segment === 'string') return segment
  if (!segment || typeof segment !== 'object') return stringifyValue(segment)

  const raw = segment as Record<string, any>
  const type = stringifyValue(raw.type || '').trim()
  const data = raw.data && typeof raw.data === 'object' ? raw.data as Record<string, any> : {}

  if (!type) return stringifyValue(raw)

  switch (type) {
    case 'text':
      return stringifyValue(data.text ?? raw.text ?? '')
    case 'image':
      return buildCQCode('image', {
        file: stringifyValue(data.file || data.url || ''),
        url: stringifyValue(data.url || ''),
        summary: stringifyValue(data.summary || ''),
      })
    case 'face':
      return buildCQCode('face', { id: stringifyValue(data.id || '') })
    case 'at':
      return buildCQCode('at', { qq: stringifyValue(data.qq || data.user_id || '') })
    case 'reply':
      return buildCQCode('reply', { id: stringifyValue(data.id || data.message_id || '') })
    case 'video':
      return buildCQCode('video', {
        file: stringifyValue(data.file || data.url || ''),
        url: stringifyValue(data.url || ''),
        file_size: stringifyValue(data.file_size || data.size || ''),
      })
    case 'record':
    case 'voice':
      return buildCQCode('record', {
        file: stringifyValue(data.file || data.url || ''),
        url: stringifyValue(data.url || ''),
        file_size: stringifyValue(data.file_size || data.size || ''),
      })
    case 'file':
      return buildCQCode('file', {
        file: stringifyValue(data.file || data.url || ''),
        url: stringifyValue(data.url || ''),
        name: stringifyValue(data.name || data.file_name || '文件'),
      })
    case 'forward':
      return buildCQCode('forward', {
        id: stringifyValue(data.id || data.resid || data.forward_id || raw.id || ''),
        summary: stringifyValue(data.summary || ''),
      })
    case 'json':
      return buildCQCode('json', { data: stringifyValue(data.data || raw.data || raw) })
    case 'xml':
      return buildCQCode('xml', { data: stringifyValue(data.data || raw.data || '') })
    case 'markdown':
      return buildCQCode('markdown', { content: stringifyValue(data.content || raw.content || '') })
    case 'miniapp':
      return buildCQCode('miniapp', { data: stringifyValue(data.data || raw.data || '') })
    case 'music':
    case 'mface':
    case 'location':
    case 'onlinefile':
      return buildCQCode(type, stringifyParams(data))
    case 'poke':
      return buildCQCode('poke', {
        type: stringifyValue(data.type || ''),
        id: stringifyValue(data.id || ''),
      })
    case 'dice':
      return buildCQCode('dice', { result: stringifyValue(data.result || '') })
    case 'rps':
      return buildCQCode('rps', { result: stringifyValue(data.result || '') })
    case 'contact':
      return buildCQCode('contact', {
        type: stringifyValue(data.type || ''),
        id: stringifyValue(data.id || ''),
      })
    case 'flashtransfer':
      return buildCQCode('flashtransfer', { fileSetId: stringifyValue(data.fileSetId || '') })
    case 'node':
      return oneBotMessageToText(data.message ?? data.content ?? raw.message ?? raw.content ?? '')
    default:
      return buildCQCode(type, stringifyParams(data))
  }
}

function forwardNodeToMessageText(node: ForwardMessageNode): string {
  const payload = getForwardNodePayload(node)
  const message = payload.message ?? payload.content ?? node.message ?? node.content ?? ''
  const text = oneBotMessageToText(message)
  return text.trim() ? text : stringifyValue(node)
}

function formatForwardNodeTime(node: ForwardMessageNode): string | null {
  const payload = getForwardNodePayload(node)
  const rawTime = payload.time ?? node.time
  if (!rawTime) return null
  const timestamp = typeof rawTime === 'number' && rawTime < 10000000000 ? rawTime * 1000 : Number(rawTime)
  if (!Number.isFinite(timestamp)) return null
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFileSize(size: string | number | undefined): string {
  const bytes = Number(size || 0)
  if (!Number.isFinite(bytes) || bytes <= 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function buildQQFaceUrl(id: string): string {
  const faceId = id.trim()
  if (!/^\d+$/.test(faceId)) return ''
  return `https://cdn.jsdelivr.net/gh/kyubotics/coolq-http-api@master/docs/qq-face/${faceId}.gif`
}

function QQFace({ id, isSelf }: { id: string; isSelf: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = buildQQFaceUrl(id)
  const label = id ? `[表情${id}]` : '[表情]'

  if (!src || failed) {
    return (
      <span className={`mx-0.5 inline-flex items-center rounded px-1.5 py-0.5 align-middle text-xs ${
        isSelf ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-700'
      }`}>
        {label}
      </span>
    )
  }

  return (
    <img
      src={src}
      alt={label}
      title={label}
      className="mx-0.5 inline-block h-6 w-6 align-middle"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

function safeJsonParse(value: string): any | null {
  if (!value || typeof value !== 'string') return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function findFirstString(value: unknown, keys: string[]): string {
  if (!value || typeof value !== 'object') return ''
  const stack = [value as Record<string, any>]
  const seen = new Set<unknown>()

  while (stack.length > 0) {
    const current = stack.shift()
    if (!current || seen.has(current)) continue
    seen.add(current)

    for (const key of keys) {
      const found = current[key]
      if (typeof found === 'string' && found.trim()) return found.trim()
      if (typeof found === 'number') return String(found)
    }

    for (const child of Object.values(current)) {
      if (child && typeof child === 'object') {
        stack.push(child as Record<string, any>)
      }
    }
  }

  return ''
}

function paramsToBody(params: Record<string, string>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== '')
  if (entries.length === 0) return ''
  return entries.map(([key, value]) => `${key}: ${value}`).join('\n')
}

function MessageInfoCard({
  label,
  title,
  subtitle,
  body,
  href,
  imageSrc,
  isSelf,
  children,
}: MessageCardProps) {
  const cardClass = isSelf
    ? 'border-white/30 bg-white/10 text-white'
    : 'border-slate-200 bg-slate-50 text-slate-900'
  const mutedClass = isSelf ? 'text-white/75' : 'text-slate-500'
  const linkClass = isSelf ? 'text-white underline' : 'text-blue-600 hover:text-blue-700 underline'

  return (
    <div className={`my-1 max-w-sm rounded-lg border px-3 py-2 text-left ${cardClass}`}>
      <div className={`text-[11px] font-medium uppercase tracking-[0.16em] ${mutedClass}`}>{label}</div>
      <div className="mt-1 flex items-start gap-2">
        {imageSrc ? (
          <img
            src={imageSrc}
            alt={title}
            className="h-12 w-12 shrink-0 rounded-lg object-cover"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{title}</div>
          {subtitle ? <div className={`mt-0.5 truncate text-xs ${mutedClass}`}>{subtitle}</div> : null}
        </div>
      </div>
      {body ? <div className={`mt-2 whitespace-pre-wrap break-words text-xs leading-5 ${mutedClass}`}>{body}</div> : null}
      {children}
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={`mt-2 inline-block text-xs ${linkClass}`}
          onClick={(event) => event.stopPropagation()}
        >
          打开链接
        </a>
      ) : null}
    </div>
  )
}

function renderStructuredBody(value: string, isSelf: boolean) {
  if (!value) return null
  const parsed = safeJsonParse(value)
  const text = parsed ? JSON.stringify(parsed, null, 2) : value
  return (
    <pre className={`mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-lg p-2 text-xs leading-5 ${
      isSelf ? 'bg-white/10 text-white/80' : 'bg-white text-slate-600'
    }`}>
      {text}
    </pre>
  )
}

function summarizeRichPayload(rawValue: string, fallbackTitle: string) {
  const parsed = safeJsonParse(rawValue)
  const title = findFirstString(parsed, ['title', 'prompt', 'summary', 'desc', 'text']) || fallbackTitle
  const subtitle = findFirstString(parsed, ['app', 'source', 'tag', 'name'])
  const href = findFirstString(parsed, ['url', 'jumpUrl', 'jump_url', 'preview'])
  const image = findFirstString(parsed, ['image', 'picUrl', 'pic_url', 'cover'])
  return { title, subtitle, href, image }
}

function stripMarkdownToPlainText(content: string) {
  return content
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/^>\s?/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/(\*\*|__|~~|\*|_)/g, '')
    .replace(/^-{3,}$/gm, '')
}

function normalizeDuplicateText(value: string) {
  try {
    value = decodeCQParamValue(value)
  } catch {
    // Keep the original text when partial entities are malformed.
  }
  return stripMarkdownToPlainText(value)
    .replace(/@\d+/g, '')
    .replace(/[|｜]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizeDuplicateLine(value: string) {
  return normalizeDuplicateText(value)
    .replace(/[^\p{L}\p{N}\u4e00-\u9fff]+/gu, '')
    .trim()
}

function shouldSuppressMarkdownFallback(text: string, markdownContent: string | null) {
  if (!markdownContent || !text.trim()) return false

  const textWhole = normalizeDuplicateText(text)
  const markdownWhole = normalizeDuplicateText(markdownContent)
  if (textWhole.length > 40 && (markdownWhole.includes(textWhole) || textWhole.includes(markdownWhole))) {
    return true
  }

  const textLines = text
    .split(/\r?\n/)
    .map(normalizeDuplicateLine)
    .filter((line) => line.length >= 3)
  if (textLines.length === 0) return false

  const markdownLines = new Set(
    markdownContent
      .split(/\r?\n/)
      .map(normalizeDuplicateLine)
      .filter((line) => line.length >= 3)
  )
  const matched = textLines.filter((line) => markdownLines.has(line)).length
  return matched >= Math.max(3, Math.ceil(textLines.length * 0.55))
}

function parseMarkdownImageAlt(alt: string) {
  const parts = alt.split('#').filter(Boolean)
  const label = parts[0] || '图片'
  const width = parts.find((part) => /^\d+px$/.test(part))
  const height = parts.find((part, index) => index > 0 && /^\d+px$/.test(part) && part !== width)
  return { label, width, height }
}

function renderMarkdownInline(text: string, keyPrefix: string) {
  const parts: React.ReactNode[] = []
  const inlinePattern = /!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|~~([^~]+)~~|\*([^*]+)\*|_([^_]+)_/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = inlinePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={`${keyPrefix}-text-${lastIndex}`}>{text.slice(lastIndex, match.index)}</span>)
    }

    if (match[1] !== undefined && match[2] !== undefined) {
      const { label, width, height } = parseMarkdownImageAlt(match[1] || '')
      const smallImage = width === '20px' || height === '20px'
      parts.push(
        <img
          key={`${keyPrefix}-img-${match.index}`}
          src={match[2]}
          alt={label}
          className={smallImage ? 'mx-1 inline-block align-middle rounded' : 'my-2 block max-w-full rounded-lg'}
          style={{
            width: smallImage ? width || height || '20px' : undefined,
            height: smallImage ? height || width || '20px' : undefined,
            maxHeight: smallImage ? undefined : '420px',
            objectFit: 'contain',
          }}
          onError={(e) => {
            e.currentTarget.style.display = 'none'
          }}
        />
      )
    } else if (match[3] !== undefined && match[4] !== undefined) {
      parts.push(
        <a
          key={`${keyPrefix}-link-${match.index}`}
          href={match[4]}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2"
          onClick={(event) => event.stopPropagation()}
        >
          {renderMarkdownInline(match[3], `${keyPrefix}-link-${match.index}`)}
        </a>
      )
    } else if (match[5] !== undefined) {
      parts.push(
        <code key={`${keyPrefix}-code-${match.index}`} className="rounded bg-black/10 px-1 py-0.5 font-mono text-[0.92em]">
          {match[5]}
        </code>
      )
    } else if (match[6] !== undefined || match[7] !== undefined) {
      const value = match[6] ?? match[7] ?? ''
      parts.push(<strong key={`${keyPrefix}-bold-${match.index}`}>{renderMarkdownInline(value, `${keyPrefix}-bold-${match.index}`)}</strong>)
    } else if (match[8] !== undefined) {
      parts.push(<span key={`${keyPrefix}-strike-${match.index}`} className="line-through">{renderMarkdownInline(match[8], `${keyPrefix}-strike-${match.index}`)}</span>)
    } else if (match[9] !== undefined || match[10] !== undefined) {
      const value = match[9] ?? match[10] ?? ''
      parts.push(<em key={`${keyPrefix}-em-${match.index}`}>{renderMarkdownInline(value, `${keyPrefix}-em-${match.index}`)}</em>)
    }

    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push(<span key={`${keyPrefix}-text-${lastIndex}`}>{text.slice(lastIndex)}</span>)
  }

  return parts.length > 0 ? parts : text
}

function isMarkdownBlockStart(line: string) {
  const trimmed = line.trim()
  return (
    !trimmed ||
    /^```/.test(trimmed) ||
    /^#{1,6}\s+/.test(trimmed) ||
    /^-{3,}$/.test(trimmed) ||
    /^>\s?/.test(trimmed) ||
    /^([-*+])\s+/.test(trimmed) ||
    /^\d+\.\s+/.test(trimmed) ||
    /^!\[[^\]]*\]\([^)]+\)$/.test(trimmed) ||
    /\|/.test(trimmed)
  )
}

function splitMarkdownTableRow(line: string) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function renderMarkdownContent(content: string, isSelf: boolean) {
  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
  const mutedClass = isSelf ? 'text-white/70' : 'text-slate-500'
  const nodes: React.ReactNode[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      nodes.push(<div key={`md-empty-${index}`} className="h-2" />)
      index += 1
      continue
    }

    const fence = /^```([\w-]+)?/.exec(trimmed)
    if (fence) {
      const start = index
      const codeLines: string[] = []
      index += 1
      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        codeLines.push(lines[index])
        index += 1
      }
      if (index < lines.length) index += 1
      nodes.push(
        <pre key={`md-code-${start}`} className={`my-2 overflow-x-auto rounded-lg p-3 text-xs leading-5 ${
          isSelf ? 'bg-white/10 text-white' : 'bg-slate-900 text-slate-50'
        }`}>
          {fence[1] ? <div className={`mb-2 text-[11px] ${isSelf ? 'text-white/60' : 'text-slate-400'}`}>{fence[1]}</div> : null}
          <code>{codeLines.join('\n')}</code>
        </pre>
      )
      continue
    }

    if (/^-{3,}$/.test(trimmed)) {
      nodes.push(<div key={`md-hr-${index}`} className={`my-3 border-t ${isSelf ? 'border-white/25' : 'border-slate-200'}`} />)
      index += 1
      continue
    }

    const heading = /^(#{1,6})(.*)$/.exec(line)
    if (heading) {
      const level = heading[1].length
      const text = heading[2].trim()
      const sizeClass = level <= 2 ? 'text-base' : 'text-sm'
      nodes.push(
        <div key={`md-heading-${index}`} className={`${sizeClass} font-semibold leading-7`}>
          {renderMarkdownInline(text, `md-heading-${index}`)}
        </div>
      )
      index += 1
      continue
    }

    const onlyImage = /^!\[[^\]]*\]\([^)]+\)$/.test(trimmed)
    if (onlyImage) {
      nodes.push(
        <div key={`md-image-${index}`} className="leading-6">
          {renderMarkdownInline(trimmed, `md-image-${index}`)}
        </div>
      )
      index += 1
      continue
    }

    if (/^>\s?/.test(trimmed)) {
      const start = index
      const quoteLines: string[] = []
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ''))
        index += 1
      }
      nodes.push(
        <div key={`md-quote-${start}`} className={`my-2 border-l-2 pl-3 ${isSelf ? 'border-white/35 text-white/80' : 'border-slate-300 text-slate-600'}`}>
          {quoteLines.map((quoteLine, quoteIndex) => (
            <div key={`md-quote-${start}-${quoteIndex}`} className="whitespace-pre-wrap break-words leading-6">
              {renderMarkdownInline(quoteLine, `md-quote-${start}-${quoteIndex}`)}
            </div>
          ))}
        </div>
      )
      continue
    }

    const unordered = /^([-*+])\s+(?:\[([ xX])\]\s+)?(.+)$/.exec(trimmed)
    const ordered = /^(\d+)\.\s+(.+)$/.exec(trimmed)
    if (unordered || ordered) {
      const start = index
      const orderedList = Boolean(ordered)
      const items: Array<{ checked?: boolean; text: string }> = []
      while (index < lines.length) {
        const itemLine = lines[index].trim()
        const unorderedItem = /^([-*+])\s+(?:\[([ xX])\]\s+)?(.+)$/.exec(itemLine)
        const orderedItem = /^(\d+)\.\s+(.+)$/.exec(itemLine)
        if (orderedList && orderedItem) {
          items.push({ text: orderedItem[2] })
        } else if (!orderedList && unorderedItem) {
          items.push({
            checked: unorderedItem[2] ? unorderedItem[2].toLowerCase() === 'x' : undefined,
            text: unorderedItem[3],
          })
        } else {
          break
        }
        index += 1
      }
      const ListTag = orderedList ? 'ol' : 'ul'
      nodes.push(
        <ListTag key={`md-list-${start}`} className={`my-1 list-inside ${orderedList ? 'list-decimal' : 'list-disc'}`}>
          {items.map((item, itemIndex) => (
            <li key={`md-list-${start}-${itemIndex}`} className="leading-6">
              {item.checked !== undefined ? (
                <span className="mr-1 font-mono">{item.checked ? '[x]' : '[ ]'}</span>
              ) : null}
              {renderMarkdownInline(item.text, `md-list-${start}-${itemIndex}`)}
            </li>
          ))}
        </ListTag>
      )
      continue
    }

    if (/\|/.test(trimmed) && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])) {
      const start = index
      const header = splitMarkdownTableRow(lines[index])
      index += 2
      const rows: string[][] = []
      while (index < lines.length && /\|/.test(lines[index].trim())) {
        rows.push(splitMarkdownTableRow(lines[index]))
        index += 1
      }
      nodes.push(
        <div key={`md-table-${start}`} className="my-2 max-w-full overflow-x-auto">
          <table className={`min-w-full border-collapse text-xs ${isSelf ? 'text-white' : 'text-slate-800'}`}>
            <thead>
              <tr>
                {header.map((cell, cellIndex) => (
                  <th key={`md-th-${start}-${cellIndex}`} className={`border px-2 py-1 text-left font-semibold ${isSelf ? 'border-white/25' : 'border-slate-200'}`}>
                    {renderMarkdownInline(cell, `md-th-${start}-${cellIndex}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`md-tr-${start}-${rowIndex}`}>
                  {header.map((_, cellIndex) => (
                    <td key={`md-td-${start}-${rowIndex}-${cellIndex}`} className={`border px-2 py-1 ${isSelf ? 'border-white/20' : 'border-slate-200'}`}>
                      {renderMarkdownInline(row[cellIndex] || '', `md-td-${start}-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      continue
    }

    const start = index
    const paragraphLines = [line]
    index += 1
    while (index < lines.length && !isMarkdownBlockStart(lines[index])) {
      paragraphLines.push(lines[index])
      index += 1
    }

    const paragraph = paragraphLines.join('\n')
    nodes.push(
      <div key={`md-line-${index}`} className={`whitespace-pre-wrap break-words leading-6 ${trimmed.startsWith('可用指令') ? mutedClass : ''}`}>
        {renderMarkdownInline(paragraph, `md-line-${start}`)}
      </div>
    )
  }

  return nodes
}

function MarkdownMessage({
  content,
  isSelf,
}: {
  content: string
  isSelf: boolean
}) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            setOpen(true)
          }
        }}
        className="cursor-pointer"
        title="点击查看原始 Markdown"
      >
        {renderMarkdownContent(content, isSelf)}
      </div>

      {open ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-slate-950/20 md:hidden"
            onClick={() => setOpen(false)}
            aria-label="关闭详情"
          />
          <div className="fixed right-0 top-16 bottom-0 z-40 w-full border-l border-slate-200 bg-white shadow-2xl md:w-[520px]">
            <div className="flex h-full min-w-0 flex-col">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-4 md:px-6">
                <div className="min-w-0">
                  <div className="text-base font-semibold text-slate-900">Markdown 原文</div>
                  <div className="mt-1 truncate text-xs text-slate-500">点击消息打开</div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="ml-4 flex h-10 w-10 shrink-0 items-center justify-center text-slate-500 hover:text-slate-900"
                  aria-label="关闭详情"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
                <pre className="whitespace-pre-wrap break-words text-[14px] leading-7 text-slate-800">
                  {content || '[空 Markdown]'}
                </pre>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  )
}

function ForwardMessageCard({
  forwardId,
  summary,
  isSelf,
}: {
  forwardId: string
  summary?: string
  isSelf: boolean
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [nodes, setNodes] = useState<ForwardMessageNode[]>([])
  const [error, setError] = useState<string | null>(null)

  const title = summary || '合并转发消息'

  const loadForward = async () => {
    if (loaded || loading) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getForwardMessage(forwardId)
      setNodes(Array.isArray(data.messages) ? data.messages : [])
      setLoaded(true)
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || '加载合并转发消息失败'
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const openViewer = () => {
    setOpen(true)
    loadForward()
  }

  const footerText = loading
    ? '正在加载转发消息'
    : loaded && nodes.length > 0
      ? `查看 ${nodes.length} 条转发消息`
      : '查看转发消息'
  const previewText = summary || '点击查看合并消息'

  return (
    <>
      <button
        key={`forward-${forwardId}`}
        type="button"
        onClick={openViewer}
        className={`my-1 block w-[292px] max-w-full overflow-hidden rounded border text-left transition-colors ${
          isSelf
            ? 'border-white/30 bg-slate-100 text-slate-900 hover:bg-slate-200'
            : 'border-slate-200 bg-slate-100 text-slate-900 hover:bg-slate-200'
        }`}
      >
        <div className="px-3 pb-2 pt-3">
          <div className="truncate text-[15px] font-semibold leading-5 text-slate-800">合并转发消息</div>
          <div className="mt-3 truncate pl-3 text-[13px] leading-5 text-slate-500">
            {previewText}
          </div>
        </div>
        <div className="bg-slate-200 px-3 py-1.5 text-[13px] leading-5 text-slate-500">
          {footerText}
        </div>
      </button>

      {open ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-30 bg-slate-950/20 md:hidden"
            onClick={() => setOpen(false)}
            aria-label="关闭详情"
          />
          <div className="fixed right-0 top-16 bottom-0 z-40 w-full border-l border-slate-200 bg-white shadow-2xl md:w-[520px]">
            <div className="flex h-full min-w-0 flex-col">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-4 md:px-6">
                <div className="min-w-0">
                  <div className="text-base font-semibold text-slate-900">合并转发消息</div>
                  <div className="mt-1 truncate text-xs text-slate-500">ID {forwardId}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="ml-4 flex h-10 w-10 shrink-0 items-center justify-center text-slate-500 hover:text-slate-900"
                  aria-label="关闭详情"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-5 md:px-6">
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-slate-500">
                  <MessageSquare className="h-4 w-4" />
                  <span>{title}</span>
                </div>

                {loading ? (
                  <div className="mt-6 text-sm text-slate-500">正在加载合并消息...</div>
                ) : error ? (
                  <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {error}
                  </div>
                ) : nodes.length === 0 ? (
                  <div className="mt-6 text-sm text-slate-500">没有可显示的合并消息内容</div>
                ) : (
                  <div className="mt-5 space-y-3">
                    {nodes.map((node, index) => {
                      const sender = getForwardNodeSender(node, index)
                      const nodeTime = formatForwardNodeTime(node)
                      const content = forwardNodeToMessageText(node)

                      return (
                        <div key={`${sender.userId || 'node'}-${index}`} className="rounded-lg border border-slate-200 bg-white p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-slate-900">{sender.nickname}</div>
                              {sender.userId ? (
                                <div className="mt-0.5 truncate text-xs text-slate-500">{sender.userId}</div>
                              ) : null}
                            </div>
                            {nodeTime ? (
                              <div className="shrink-0 text-xs text-slate-400">{nodeTime}</div>
                            ) : null}
                          </div>
                          <div className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-800">
                            {parseMessageContent(content, false)}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  )
}

/**
 * 解析CQ码
 */
function findCQEnd(message: string, start: number): number {
  const typeEndCandidates = [message.indexOf(',', start + 4), message.indexOf(']', start + 4)]
    .filter((index) => index !== -1)
  const typeEnd = Math.min(...typeEndCandidates)
  if (!Number.isFinite(typeEnd)) return -1

  const type = message.slice(start + 4, typeEnd)
  const richTypes = new Set(['markdown', 'json', 'xml', 'miniapp'])
  if (!richTypes.has(type)) {
    return message.indexOf(']', typeEnd)
  }

  let cursor = typeEnd + 1
  while (cursor < message.length) {
    const candidate = message.indexOf(']', cursor)
    if (candidate === -1) return -1

    const nextChar = message[candidate + 1] || ''
    if (nextChar === '(') {
      cursor = candidate + 1
      continue
    }

    if (!nextChar || message.startsWith('[CQ:', candidate + 1)) {
      return candidate
    }

    const rest = message.slice(candidate + 1)
    if (/^\s*(?:@\d+|[|｜])/.test(rest)) {
      return candidate
    }

    cursor = candidate + 1
  }

  return -1
}

function decodeCQEntities(value: string): string {
  return value
    .replace(/&#44;/g, ',')
    .replace(/&#91;/g, '[')
    .replace(/&#93;/g, ']')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

function decodeCQParamValue(value: string): string {
  let decoded = decodeCQEntities(value)
  if (decoded.includes('%')) {
    decoded = decodeURIComponent(decoded)
  }
  return decoded
}

function parseCQCode(cqString: string): CQCode | null {
  if (!cqString.startsWith('[CQ:') || !cqString.endsWith(']')) return null

  const body = cqString.slice(4, -1)
  const commaIndex = body.indexOf(',')
  const type = (commaIndex === -1 ? body : body.slice(0, commaIndex)).trim()
  const paramsStr = commaIndex === -1 ? '' : `,${body.slice(commaIndex + 1)}`
  const params: Record<string, string> = {}
  if (!type) return null

  if (paramsStr) {
    if (['markdown', 'json', 'xml', 'miniapp'].includes(type)) {
      const rawParam = paramsStr.slice(1)
      const equalIndex = rawParam.indexOf('=')
      if (equalIndex !== -1) {
        const key = rawParam.slice(0, equalIndex).trim()
        const value = rawParam.slice(equalIndex + 1)
        if (key) {
          try {
            params[key] = decodeCQParamValue(value)
          } catch (e) {
            console.warn('Failed to decode rich param value:', key, value.substring(0, 50), e)
            params[key] = value
          }
        }
      }
      return { type, params }
    }

    // 手动解析参数，处理值中可能包含逗号的情况
    // 思路：找到所有 key= 的位置，然后提取到下一个 key= 或结尾之间的值
    const paramStr = paramsStr.slice(1) // 去掉开头的逗号
    
    // 找到所有 key= 的位置
    const keyPattern = /([^=,]+)=/g
    const keyPositions: Array<{ key: string; start: number; end: number }> = []
    let keyMatch: RegExpExecArray | null
    
    while ((keyMatch = keyPattern.exec(paramStr)) !== null) {
      const key = keyMatch[1].trim()
      const start = keyMatch.index + keyMatch[0].length // value 开始位置
      
      // 找到下一个 key= 的位置，或者到字符串结尾
      const nextKeyMatch = /,([^=,]+)=/.exec(paramStr.slice(start))
      const end = nextKeyMatch ? start + nextKeyMatch.index : paramStr.length
      
      keyPositions.push({ key, start, end })
    }
    
    // 提取每个参数的值
    keyPositions.forEach(({ key, start, end }) => {
      let value = paramStr.substring(start, end)
      
      // 去掉末尾的逗号（如果有）
      if (value.endsWith(',')) {
        value = value.slice(0, -1)
      }
      
      if (key && value !== undefined) {
        // 解码 HTML 实体和 URL 编码
        try {
          value = decodeCQParamValue(value)
        } catch (e) {
          // 如果解码失败，使用原始值
          console.warn('Failed to decode param value:', key, value.substring(0, 50), e)
        }
        params[key] = value
      }
    })
  }

  return { type, params }
}

/**
 * 将消息文本转换为React元素
 * @param message 消息文本
 * @param isSelf 是否是机器人自己的消息（用于调整样式）
 */
export function parseMessageContent(
  message: string,
  isSelf: boolean = false,
  options: MessageRenderOptions = {}
): React.ReactNode[] {
  const elements: React.ReactNode[] = []
  let lastIndex = 0
  let lastMarkdownContent: string | null = null

  while (lastIndex < message.length) {
    const start = message.indexOf('[CQ:', lastIndex)
    if (start === -1) {
      break
    }

    // 添加CQ码之前的文本
    if (start > lastIndex) {
      const text = message.substring(lastIndex, start)
      if (!shouldSuppressMarkdownFallback(text, lastMarkdownContent)) {
        elements.push(<span key={`text-${lastIndex}`}>{decodeCQEntities(text)}</span>)
      }
    }

    const end = findCQEnd(message, start)
    if (end === -1 || end < start) {
      elements.push(<span key={`text-${start}`}>{decodeCQEntities(message.substring(start))}</span>)
      lastIndex = message.length
      break
    }

    const cqText = message.substring(start, end + 1)

    // 解析并渲染CQ码
    const cq = parseCQCode(cqText)
    
    if (cq) {
      if (lastMarkdownContent && cq.type === 'at') {
        const nextStart = message.indexOf('[CQ:', end + 1)
        const followingTextEnd = nextStart === -1 ? message.length : nextStart
        const followingText = message.substring(end + 1, followingTextEnd)
        if (shouldSuppressMarkdownFallback(followingText, lastMarkdownContent)) {
          lastIndex = followingTextEnd
          continue
        }
      }

      elements.push(renderCQCode(cq, start, isSelf, options))
      if (cq.type === 'markdown') {
        lastMarkdownContent = cq.params.content || cq.params.data || ''
      } else if (!lastMarkdownContent) {
        lastMarkdownContent = null
      }
    } else {
      // 如果解析失败，显示原始文本
      elements.push(<span key={`cq-${start}`}>{cqText}</span>)
      lastMarkdownContent = null
    }

    lastIndex = end + 1
  }

  // 添加最后的文本
  if (lastIndex < message.length) {
    const text = message.substring(lastIndex)
    if (!shouldSuppressMarkdownFallback(text, lastMarkdownContent)) {
      elements.push(<span key={`text-${lastIndex}`}>{decodeCQEntities(text)}</span>)
    }
  }

  return elements.length > 0 ? elements : [decodeCQEntities(message)]
}

/**
 * 渲染CQ码为React组件
 * @param cq CQ码对象
 * @param key 唯一键
 * @param isSelf 是否是机器人自己的消息（用于调整样式）
 */
function renderCQCode(
  cq: CQCode,
  key: number,
  isSelf: boolean = false,
  options: MessageRenderOptions = {}
): React.ReactNode {
  switch (cq.type) {
    case 'text':
      return <span key={`text-cq-${key}`}>{cq.params.text || ''}</span>

    case 'image':
      // 优先使用 url，如果没有则使用 file
      const imageUrl = cq.params.url
      const imageFile = cq.params.file
      
      let imgSrc = imageUrl || imageFile
      if (!imgSrc) {
        // 如果既没有url也没有file，显示占位符
        return (
          <div key={`img-${key}`} className="my-2 p-4 bg-gray-100 rounded-lg border border-gray-300">
            <div className="flex items-center gap-2 text-gray-500">
              <div>
                <p className="text-sm font-medium">[图片]</p>
              </div>
            </div>
          </div>
        )
      }

      // 统一走本地媒体代理，避免 QQ 直链失效
      const finalImgSrc = buildMediaProxyUrl('image', { url: imageUrl, file: imageFile })
      
      return (
        <div key={`img-${key}`} className="my-2">
          <img
            src={finalImgSrc}
            alt={cq.params.summary || '图片'}
            className="max-w-xs max-h-64 rounded-lg cursor-pointer hover:opacity-90 transition-opacity block"
            onClick={() => {
              window.open(finalImgSrc, '_blank')
            }}
            onError={(e) => {
              console.error('Image load failed:', finalImgSrc)
              const target = e.currentTarget as HTMLImageElement
              target.style.display = 'none'
              
              // 创建错误提示
              const parent = target.parentNode as HTMLElement
              if (parent && !parent.querySelector('.image-error')) {
                const fallback = document.createElement('div')
                fallback.className = 'image-error p-3 bg-gray-100 rounded-lg border border-gray-300'
                fallback.innerHTML = `
                  <div class="flex items-center gap-2 text-gray-500">
                    <div>
                      <p class="text-sm font-medium">[图片加载失败]</p>
                      <p class="text-xs text-gray-400">点击查看原链接</p>
                    </div>
                  </div>
                `
                const link = document.createElement('a')
                link.href = '#'
                link.className = 'text-xs text-blue-600 hover:underline mt-1 block cursor-pointer'
                link.textContent = '查看图片'
                link.onclick = async (event) => {
                  event.preventDefault()
                  // 尝试通过代理打开图片
                  try {
                    const response = await fetch(finalImgSrc)
                    if (response.ok) {
                      window.open(finalImgSrc, '_blank')
                    } else {
                      toast.error('图片链接无效或已过期')
                    }
                  } catch (error) {
                    console.error('Failed to load image via proxy:', error)
                    toast.error('图片链接无效或已过期')
                  }
                }
                fallback.appendChild(link)
                parent.appendChild(fallback)
              }
            }}
          />
        </div>
      )

    case 'face':
      return <QQFace key={`face-${key}`} id={cq.params.id || ''} isSelf={isSelf} />

    case 'mface':
      const emojiId = cq.params.emoji_id || cq.params.id || ''
      const emojiDir = emojiId.slice(0, 2)
      const mfaceUrl = cq.params.url || (emojiId && emojiDir ? `https://gxh.vip.qq.com/club/item/parcel/item/${emojiDir}/${emojiId}/raw300.gif` : '')
      return (
        <MessageInfoCard
          key={`mface-${key}`}
          label="商城表情"
          title={cq.params.summary || cq.params.name || '商城表情'}
          subtitle={emojiId ? `ID ${emojiId}` : undefined}
          imageSrc={mfaceUrl}
          isSelf={isSelf}
        />
      )

    case 'at':
      // 如果是机器人自己的消息，使用白色文字；否则使用蓝色
      const atTarget = cq.params.qq || ''
      const atName = atTarget === 'all'
        ? '全体成员'
        : cq.params.name || cq.params.card || cq.params.nickname || options.atNames?.[atTarget] || atTarget
      return (
        <span key={`at-${key}`} className={`font-medium ${isSelf ? 'text-white' : 'text-blue-600'}`}>
          @{atName}
        </span>
      )

    case 'reply':
      return (
        <span key={`reply-${key}`} className="text-gray-500 text-sm italic">
          [回复]
        </span>
      )

    case 'video':
      const videoSrc = cq.params.url || cq.params.file
      const finalVideoSrc = videoSrc ? buildMediaProxyUrl('video', { url: cq.params.url, file: cq.params.file }) : ''
      const fileSize = cq.params.file_size ? parseInt(cq.params.file_size) : 0
      const fileSizeMB = fileSize > 0 ? (fileSize / 1024 / 1024).toFixed(2) : ''
      
      return (
        <div key={`video-${key}`} className="my-2">
          {videoSrc ? (
            <video
              src={finalVideoSrc}
              controls
              className="max-w-sm max-h-64 rounded-lg"
              preload="metadata"
            >
              您的浏览器不支持视频播放
            </video>
          ) : (
            <div className="p-4 bg-gray-100 rounded-lg border border-gray-300">
              <div className="flex items-center gap-2 text-gray-500">
                <span className="text-2xl">🎬</span>
                <div>
                  <p className="text-sm font-medium">[视频]</p>
                  {cq.params.file && <p className="text-xs text-gray-400">{cq.params.file}</p>}
                  {fileSizeMB && <p className="text-xs text-gray-400">大小: {fileSizeMB} MB</p>}
                  {videoSrc && (
                    <a
                      href={finalVideoSrc}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline mt-1 block"
                    >
                      下载视频
                    </a>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )

    case 'record':
    case 'voice':
      const recordRaw = cq.params.url || cq.params.file
      if (!recordRaw) {
        return (
          <span key={`audio-${key}`} className="text-gray-500 text-sm">
            [语音]
          </span>
        )
      }
      const recordSrc = buildMediaProxyUrl('record', { url: cq.params.url, file: cq.params.file })
      return (
        <div key={`audio-${key}`} className="my-1">
          <audio src={recordSrc} controls className="max-w-xs">
            您的浏览器不支持音频播放
          </audio>
        </div>
      )

    case 'file':
      const fileRaw = cq.params.url || cq.params.file
      const fileName = cq.params.name || cq.params.file_name || cq.params.file || '文件'
      const fileDetail = [
        formatFileSize(cq.params.file_size || cq.params.size),
        cq.params.file_id ? `ID ${cq.params.file_id}` : '',
      ].filter(Boolean).join(' · ')
      if (!fileRaw) {
        return (
          <MessageInfoCard
            key={`file-${key}`}
            label="文件"
            title={fileName}
            subtitle={fileDetail || undefined}
            isSelf={isSelf}
          />
        )
      }
      const fileSrc = buildMediaProxyUrl('file', { url: cq.params.url, file: cq.params.file, name: fileName })
      return (
        <MessageInfoCard
          key={`file-${key}`}
          label="文件"
          title={fileName}
          subtitle={fileDetail || undefined}
          href={fileSrc}
          isSelf={isSelf}
        />
      )

    case 'forward':
      const forwardId = cq.params.id || cq.params.forward_id || cq.params.resid || cq.params.file
      if (!forwardId) {
        return (
          <span key={`forward-${key}`} className="text-gray-500 text-sm">
            [合并转发消息]
          </span>
        )
      }
      return (
        <ForwardMessageCard
          key={`forward-${key}`}
          forwardId={forwardId}
          summary={cq.params.summary || cq.params.title}
          isSelf={isSelf}
        />
      )

    case 'markdown':
      return (
        <MarkdownMessage
          key={`markdown-${key}`}
          content={cq.params.content || cq.params.data || ''}
          isSelf={isSelf}
        />
      )

    case 'json':
    case 'miniapp':
      const richType = cq.type === 'miniapp' ? '小程序' : 'JSON'
      const richValue = cq.params.data || ''
      const richSummary = summarizeRichPayload(richValue, `${richType} 消息`)
      return (
        <MessageInfoCard
          key={`${cq.type}-${key}`}
          label={richType}
          title={cq.params.title || cq.params.summary || richSummary.title}
          subtitle={cq.params.desc || richSummary.subtitle}
          href={cq.params.url || richSummary.href}
          imageSrc={cq.params.image || richSummary.image}
          isSelf={isSelf}
        >
          {renderStructuredBody(richValue, isSelf)}
        </MessageInfoCard>
      )

    case 'xml':
      const xmlValue = cq.params.data || ''
      const xmlBrief = /brief="([^"]+)"/.exec(xmlValue)?.[1] || /brief='([^']+)'/.exec(xmlValue)?.[1]
      return (
        <MessageInfoCard
          key={`xml-${key}`}
          label="XML"
          title={cq.params.title || xmlBrief || 'XML 消息'}
          isSelf={isSelf}
        >
          {renderStructuredBody(xmlValue, isSelf)}
        </MessageInfoCard>
      )

    case 'music':
      return (
        <MessageInfoCard
          key={`music-${key}`}
          label="音乐"
          title={cq.params.title || `${cq.params.type || '音乐'}${cq.params.id ? ` #${cq.params.id}` : ''}`}
          subtitle={cq.params.content || cq.params.singer || cq.params.type}
          href={cq.params.url || cq.params.audio}
          imageSrc={cq.params.image}
          isSelf={isSelf}
        />
      )

    case 'share':
      return (
        <MessageInfoCard
          key={`share-${key}`}
          label="分享"
          title={cq.params.title || '分享消息'}
          subtitle={cq.params.content}
          href={cq.params.url}
          imageSrc={cq.params.image}
          isSelf={isSelf}
        />
      )

    case 'poke':
      return (
        <MessageInfoCard
          key={`poke-${key}`}
          label="戳一戳"
          title="戳一戳消息"
          subtitle={[cq.params.type && `类型 ${cq.params.type}`, cq.params.id && `ID ${cq.params.id}`].filter(Boolean).join(' · ')}
          isSelf={isSelf}
        />
      )

    case 'dice':
      return (
        <MessageInfoCard
          key={`dice-${key}`}
          label="骰子"
          title={`骰子结果 ${cq.params.result || '?'}`}
          isSelf={isSelf}
        />
      )

    case 'rps':
      const rpsMap: Record<string, string> = { '1': '石头', '2': '剪刀', '3': '布' }
      return (
        <MessageInfoCard
          key={`rps-${key}`}
          label="猜拳"
          title={`猜拳结果 ${rpsMap[cq.params.result] || cq.params.result || '?'}`}
          isSelf={isSelf}
        />
      )

    case 'contact':
      return (
        <MessageInfoCard
          key={`contact-${key}`}
          label="联系人"
          title={cq.params.type === 'group' ? '群推荐' : '好友推荐'}
          subtitle={cq.params.id}
          isSelf={isSelf}
        />
      )

    case 'location':
      const lat = cq.params.lat
      const lon = cq.params.lon
      const mapHref = lat && lon ? `https://uri.amap.com/marker?position=${encodeURIComponent(lon)},${encodeURIComponent(lat)}&name=${encodeURIComponent(cq.params.title || '位置')}` : undefined
      return (
        <MessageInfoCard
          key={`location-${key}`}
          label="位置"
          title={cq.params.title || '位置消息'}
          subtitle={cq.params.content || (lat && lon ? `${lat}, ${lon}` : undefined)}
          href={mapHref}
          isSelf={isSelf}
        />
      )

    case 'onlinefile':
      return (
        <MessageInfoCard
          key={`onlinefile-${key}`}
          label={cq.params.isDir === 'true' ? '在线文件夹' : '在线文件'}
          title={cq.params.fileName || '在线文件'}
          subtitle={formatFileSize(cq.params.fileSize)}
          body={[cq.params.msgId && `消息ID: ${cq.params.msgId}`, cq.params.elementId && `元素ID: ${cq.params.elementId}`].filter(Boolean).join('\n')}
          isSelf={isSelf}
        />
      )

    case 'flashtransfer':
      return (
        <MessageInfoCard
          key={`flashtransfer-${key}`}
          label="QQ闪传"
          title="闪传消息"
          subtitle={cq.params.fileSetId ? `文件集 ${cq.params.fileSetId}` : undefined}
          isSelf={isSelf}
        />
      )

    case 'node':
      return (
        <MessageInfoCard
          key={`node-${key}`}
          label="转发节点"
          title={cq.params.nickname || cq.params.name || '转发节点'}
          subtitle={cq.params.user_id || cq.params.uin}
          body={cq.params.content || cq.params.message || paramsToBody(cq.params)}
          isSelf={isSelf}
        />
      )

    default:
      return (
        <MessageInfoCard
          key={`unknown-${key}`}
          label="消息"
          title={`${cq.type} 消息`}
          body={paramsToBody(cq.params)}
          isSelf={isSelf}
        />
      )
  }
}

/**
 * 构建CQ码字符串
 */
export function buildCQCode(type: string, params: Record<string, string>): string {
  const escapeCQValue = (value: string) => value
    .replace(/&/g, '&amp;')
    .replace(/\[/g, '&#91;')
    .replace(/\]/g, '&#93;')
    .replace(/,/g, '&#44;')

  const paramStr = Object.entries(params)
    .map(([key, value]) => {
      if (value === undefined || value === null) {
        return ''
      }
      const rawValue = String(value)
      // 对于浏览器上传的 data URL，不转义，避免破坏历史发送逻辑。
      if (key === 'file' && value.startsWith('data:')) {
        return `${key}=${rawValue}`
      }
      return `${key}=${escapeCQValue(rawValue)}`
    })
    .filter(Boolean)
    .join(',')
  return `[CQ:${type}${paramStr ? ',' + paramStr : ''}]`
}
