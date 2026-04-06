import React from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildMediaProxyUrl(kind: 'image' | 'video' | 'record' | 'file', params: { url?: string; file?: string }): string {
  const search = new URLSearchParams()
  search.set('kind', kind)
  if (params.url) {
    search.set('url', params.url)
  }
  if (params.file) {
    search.set('file', params.file)
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

/**
 * 解析CQ码
 */
function parseCQCode(cqString: string): CQCode | null {
  const match = cqString.match(/\[CQ:([^,\]]+)((?:,[^\]]+)*)\]/)
  if (!match) return null

  const type = match[1]
  const paramsStr = match[2]
  const params: Record<string, string> = {}

  if (paramsStr) {
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
      
      if (key && value) {
        // 解码 HTML 实体和 URL 编码
        try {
          // 先替换 &amp; 为 &
          value = value.replace(/&amp;/g, '&')
          // 尝试 URL 解码（如果包含 % 符号）
          if (value.includes('%')) {
            value = decodeURIComponent(value)
          }
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
export function parseMessageContent(message: string, isSelf: boolean = false): React.ReactNode[] {
  const elements: React.ReactNode[] = []
  let lastIndex = 0
  const cqRegex = /\[CQ:[^\]]+\]/g
  let match: RegExpExecArray | null

  while ((match = cqRegex.exec(message)) !== null) {
    // 添加CQ码之前的文本
    if (match.index > lastIndex) {
      const text = message.substring(lastIndex, match.index)
      elements.push(<span key={`text-${lastIndex}`}>{text}</span>)
    }

    // 解析并渲染CQ码
    const cq = parseCQCode(match[0])
    
    if (cq) {
      elements.push(renderCQCode(cq, match.index, isSelf))
    } else {
      // 如果解析失败，显示原始文本
      elements.push(<span key={`cq-${match.index}`}>{match[0]}</span>)
    }

    lastIndex = match.index + match[0].length
  }

  // 添加最后的文本
  if (lastIndex < message.length) {
    const text = message.substring(lastIndex)
    elements.push(<span key={`text-${lastIndex}`}>{text}</span>)
  }

  return elements.length > 0 ? elements : [message]
}

/**
 * 渲染CQ码为React组件
 * @param cq CQ码对象
 * @param key 唯一键
 * @param isSelf 是否是机器人自己的消息（用于调整样式）
 */
function renderCQCode(cq: CQCode, key: number, isSelf: boolean = false): React.ReactNode {
  switch (cq.type) {
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
                      alert('图片链接无效或已过期')
                    }
                  } catch (error) {
                    console.error('Failed to load image via proxy:', error)
                    alert('图片链接无效或已过期')
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
      // QQ表情
      return (
        <img
          key={`face-${key}`}
          src={`https://gxh.vip.qq.com/club/item/parcel/item/${cq.params.id}/raw300.gif`}
          alt={`表情${cq.params.id}`}
          className="inline-block w-6 h-6 mx-0.5"
          onError={(e) => {
            e.currentTarget.textContent = `[表情${cq.params.id}]`
          }}
        />
      )

    case 'at':
      // 如果是机器人自己的消息，使用白色文字；否则使用蓝色
      return (
        <span key={`at-${key}`} className={`font-medium ${isSelf ? 'text-white' : 'text-blue-600'}`}>
          @{cq.params.qq === 'all' ? '全体成员' : cq.params.qq}
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
      if (!fileRaw) {
        return (
          <span key={`file-${key}`} className="text-gray-500 text-sm">
            [文件]
          </span>
        )
      }
      const fileSrc = buildMediaProxyUrl('file', { url: cq.params.url, file: cq.params.file })
      return (
        <a
          key={`file-${key}`}
          href={fileSrc}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 underline"
        >
          📎 {cq.params.name || '文件'}
        </a>
      )

    default:
      return (
        <span key={`unknown-${key}`} className="text-gray-500 text-sm">
          [不支持的消息类型: {cq.type}]
        </span>
      )
  }
}

/**
 * 构建CQ码字符串
 */
export function buildCQCode(type: string, params: Record<string, string>): string {
  const paramStr = Object.entries(params)
    .map(([key, value]) => {
      // 对于 base64 图片数据，不进行 URL 编码
      if (key === 'file' && value.startsWith('data:')) {
        return `${key}=${value}`
      }
      // 对于 URL，也不需要编码
      if (key === 'url' || (key === 'file' && (value.startsWith('http://') || value.startsWith('https://')))) {
        return `${key}=${value}`
      }
      // 其他参数进行 URL 编码
      return `${key}=${value}`
    })
    .join(',')
  return `[CQ:${type}${paramStr ? ',' + paramStr : ''}]`
}
