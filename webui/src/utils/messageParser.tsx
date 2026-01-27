import React from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

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
 */
export function parseMessageContent(message: string): React.ReactNode[] {
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
      elements.push(renderCQCode(cq, match.index))
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
 */
function renderCQCode(cq: CQCode, key: number): React.ReactNode {
  switch (cq.type) {
    case 'image':
      // 优先使用 url，如果没有则使用 file
      let imgSrc = cq.params.url || cq.params.file
      
      // 如果 file 是文件名（不是 URL），显示占位符
      if (!imgSrc || (!imgSrc.startsWith('http://') && !imgSrc.startsWith('https://') && !imgSrc.startsWith('data:'))) {
        imgSrc = '' // 设置为空，显示占位符
      }
      
      if (!imgSrc) {
        // 如果没有有效的图片源，显示占位符
        return (
          <div key={`img-${key}`} className="my-2 p-4 bg-gray-100 rounded-lg border border-gray-300">
            <div className="flex items-center gap-2 text-gray-500">
              <div>
                <p className="text-sm font-medium">[图片]</p>
                {cq.params.file && <p className="text-xs text-gray-400">{cq.params.file}</p>}
              </div>
            </div>
          </div>
        )
      }
      
      // 对于 QQ 多媒体服务器的 URL，使用代理
      const isQQMultimedia = imgSrc.includes('multimedia.nt.qq.com.cn')
      const finalImgSrc = isQQMultimedia 
        ? `${API_BASE_URL}/chat/image-proxy?url=${encodeURIComponent(imgSrc)}`
        : imgSrc
      
      return (
        <div key={`img-${key}`} className="my-2">
          <img
            src={finalImgSrc}
            alt={cq.params.summary || '图片'}
            className="max-w-xs max-h-64 rounded-lg cursor-pointer hover:opacity-90 transition-opacity block"
            onClick={() => window.open(imgSrc, '_blank')}
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
                link.href = imgSrc
                link.target = '_blank'
                link.className = 'text-xs text-blue-600 hover:underline mt-1 block'
                link.textContent = '查看图片'
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
      return (
        <span key={`at-${key}`} className="text-blue-600 font-medium">
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
      const fileSize = cq.params.file_size ? parseInt(cq.params.file_size) : 0
      const fileSizeMB = fileSize > 0 ? (fileSize / 1024 / 1024).toFixed(2) : ''
      
      return (
        <div key={`video-${key}`} className="my-2">
          {videoSrc && (videoSrc.startsWith('http://') || videoSrc.startsWith('https://')) ? (
            <video
              src={videoSrc}
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
                      href={videoSrc}
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
      return (
        <div key={`audio-${key}`} className="my-1">
          <audio src={cq.params.url || cq.params.file} controls className="max-w-xs">
            您的浏览器不支持音频播放
          </audio>
        </div>
      )

    case 'file':
      return (
        <a
          key={`file-${key}`}
          href={cq.params.url || cq.params.file}
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

