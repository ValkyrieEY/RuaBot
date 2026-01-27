import { useEffect, useState, useRef } from 'react'
import { api } from '@/utils/api'
import { 
  Github, 
  Heart, 
  Code, 
  Package,
  Users,
  ExternalLink,
  Sparkles,
  Box
} from 'lucide-react'

interface SystemStatus {
  versions?: {
    framework: string
    onebot: string
    webui: string
    python: string
  }
}

export default function AboutPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [logoSrc, setLogoSrc] = useState<string>('https://github.com/ValkyrieEY.png')
  const [logoError, setLogoError] = useState(false)
  const logoTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  // 图片加载超时处理
  useEffect(() => {
    // 清除之前的超时
    if (logoTimeoutRef.current) {
      clearTimeout(logoTimeoutRef.current)
      logoTimeoutRef.current = null
    }

    if (logoSrc.startsWith('http://') || logoSrc.startsWith('https://')) {
      // 设置2秒超时
      logoTimeoutRef.current = setTimeout(() => {
        // 如果2秒内图片还没加载完成，切换到本地图片
        if (!logoError) {
          setLogoSrc('/logo.jpg')
        }
        logoTimeoutRef.current = null
      }, 2000)
    }
    
    return () => {
      if (logoTimeoutRef.current) {
        clearTimeout(logoTimeoutRef.current)
        logoTimeoutRef.current = null
      }
    }
  }, [logoSrc, logoError])

  const loadStatus = async () => {
    try {
      const data = await api.getSystemStatus() as SystemStatus
      setStatus(data)
    } catch (error) {
      console.error('Failed to load system status:', error)
    } finally {
      setLoading(false)
    }
  }

  const features = [
    { icon: Package, title: '插件系统', desc: '强大的插件架构，支持热重载和跨进程通信' },
    { icon: Sparkles, title: 'AI 集成', desc: '完整的AI功能支持，包括多模型、记忆管理和工具调用' },
    { icon: Code, title: '现代化', desc: '基于 Python + React + TypeScript 的现代技术栈' },
    { icon: Box, title: '可扩展', desc: '松耦合架构设计，易于扩展和定制' }
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="flex justify-center mb-6">
          <div className="w-48 h-48 rounded-3xl shadow-2xl transform hover:scale-105 transition-transform duration-300 overflow-hidden bg-gray-100 flex items-center justify-center">
            {logoError ? (
              // 如果所有图片都加载失败，显示占位符
              <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary-400 to-primary-600">
                <span className="text-white text-6xl font-bold">R</span>
              </div>
            ) : (
              <img 
                src={logoSrc} 
                alt="RuaBot Logo"
                className="w-full h-full object-cover"
                onLoad={() => {
                  // 图片加载成功，清除超时
                  if (logoTimeoutRef.current) {
                    clearTimeout(logoTimeoutRef.current)
                    logoTimeoutRef.current = null
                  }
                }}
                onError={(e) => {
                  const target = e.currentTarget
                  // 清除超时
                  if (logoTimeoutRef.current) {
                    clearTimeout(logoTimeoutRef.current)
                    logoTimeoutRef.current = null
                  }
                  // 如果当前是网络图片，尝试加载本地图片
                  if (logoSrc.startsWith('http://') || logoSrc.startsWith('https://')) {
                    setLogoSrc('/logo.jpg')
                  } else {
                    // 如果本地图片也加载失败，显示占位符
                    setLogoError(true)
                    target.style.display = 'none'
                  }
                }}
              />
            )}
          </div>
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-3">RuaBot</h1>
        <p className="text-xl text-gray-600 mb-2">
          基于 OneBot v11/12 协议的现代化 QQ 机器人框架
        </p>
        <p className="text-sm text-gray-500">
          A Modern Bot Development Platform Based on OneBot Protocol
        </p>
        
        {/* Version badges */}
        {status?.versions && (
          <div className="flex justify-center gap-3 mt-6 flex-wrap">
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
              v{status.versions.framework}
            </span>
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
              OneBot {status.versions.onebot}
            </span>
            <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium">
              Python
            </span>
            <span className="px-3 py-1 bg-orange-100 text-orange-700 rounded-full text-sm font-medium">
              TypeScript
            </span>
          </div>
        )}
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        {features.map((feature, index) => {
          const Icon = feature.icon
          return (
            <div
              key={index}
              className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start gap-4">
                <div className="p-3 bg-primary-50 rounded-lg">
                  <Icon className="w-6 h-6 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">{feature.title}</h3>
                  <p className="text-gray-600 text-sm">{feature.desc}</p>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* GitHub Link */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-xl p-8 mb-12 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Github className="w-12 h-12 text-white" />
            <div>
              <h3 className="text-xl font-bold text-white mb-1">开源项目</h3>
              <p className="text-gray-300 text-sm">欢迎 Star 和贡献代码</p>
            </div>
          </div>
          <a
            href="https://github.com/ValkyrieEY/RuaBot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-100 transition-colors"
          >
            访问 GitHub
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Contributors */}
      <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 mb-12">
        <div className="flex items-center gap-2 mb-6">
          <Users className="w-6 h-6 text-primary-600" />
          <h2 className="text-2xl font-bold text-gray-900">贡献者</h2>
        </div>
        
        <div className="text-center">
          <p className="text-gray-600 mb-6">
            感谢所有为 RuaBot 做出贡献的开发者们
          </p>
          <a 
            href="https://github.com/ValkyrieEY/RuaBot/graphs/contributors"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block hover:opacity-80 transition-opacity"
          >
            <img 
              src="https://contrib.rocks/image?repo=ValkyrieEY/RuaBot" 
              alt="Contributors"
              className="rounded-lg"
            />
          </a>
        </div>
      </div>

      {/* License and Thanks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Code className="w-5 h-5 text-primary-600" />
            开源协议
          </h3>
          <p className="text-gray-600 text-sm mb-3">
            本项目采用 MIT License 开源协议
          </p>
          <p className="text-gray-500 text-xs">
            您可以自由使用、修改和分发本项目，但需要保留原作者的版权信息
          </p>
          <p className="text-gray-500 text-xs">
            请勿用于违规当地法律的用途
          </p>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Heart className="w-5 h-5 text-red-500" />
            特别感谢
          </h3>
          <p className="text-gray-600 text-sm mb-2">
            感谢以下项目和社区的支持：
          </p>
          <ul className="text-gray-600 text-sm space-y-1">
            <li>OneBot 协议标准</li>
            <li>所有贡献者和用户</li>
          </ul>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-gray-500 text-sm py-8 border-t border-gray-200">
        <p>Made with love by ValkyrieEY and the RuaBot Community</p>
        <p className="mt-2">
          © {new Date().getFullYear()} RuaBot. All rights reserved.
        </p>
      </div>
    </div>
  )
}

