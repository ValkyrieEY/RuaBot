import { useEffect, useState, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { 
  Github, 
  Heart, 
  Code, 
  Package,
  Users,
  ExternalLink,
  Sparkles,
  Box,
  MessageCircle
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
  const { t } = useTranslation()
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
    { icon: Package, title: t('about.features.pluginSystem'), desc: t('about.features.pluginSystemDesc') },
    { icon: Sparkles, title: t('about.features.aiIntegration'), desc: t('about.features.aiIntegrationDesc') },
    { icon: Code, title: t('about.features.modern'), desc: t('about.features.modernDesc') },
    { icon: Box, title: t('about.features.extensible'), desc: t('about.features.extensibleDesc') }
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
          {t('about.subtitle')}
        </p>
        <p className="text-sm text-gray-500">
          {t('about.desc')}
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
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 rounded-xl p-8 mb-6 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Github className="w-12 h-12 text-white" />
            <div>
              <h3 className="text-xl font-bold text-white mb-1">{t('about.openSource')}</h3>
              <p className="text-gray-300 text-sm">{t('about.welcomeStar')}</p>
            </div>
          </div>
          <a
            href="https://github.com/ValkyrieEY/RuaBot"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-100 transition-colors"
          >
            {t('about.visitGithub')}
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* QQ Group Link */}
      <div className="bg-gradient-to-r from-blue-600 to-cyan-600 rounded-xl p-8 mb-12 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <MessageCircle className="w-12 h-12 text-white" />
            <div>
              <h3 className="text-xl font-bold text-white mb-1">
                {t('about.qqGroup')} <span className="font-mono">615122348</span>
              </h3>
              <p className="text-blue-100 text-sm">{t('about.qqGroupDesc')}</p>
            </div>
          </div>
          <a
            href="https://qm.qq.com/q/9hOh1RoB9Y"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-6 py-3 bg-white text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-colors whitespace-nowrap"
          >
            {t('about.joinGroup')}
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Contributors */}
      <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 mb-12">
        <div className="flex items-center gap-2 mb-6">
          <Users className="w-6 h-6 text-primary-600" />
          <h2 className="text-2xl font-bold text-gray-900">{t('about.contributors')}</h2>
        </div>
        
        <div className="text-center">
          <p className="text-gray-600 mb-6">
            {t('about.contributorsDesc')}
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
            {t('about.license')}
          </h3>
          <p className="text-gray-600 text-sm mb-2">
            {t('about.licenseDesc')}
          </p>
          <ul className="text-gray-600 text-sm space-y-1">
            <li>{t('about.licenseNote1')}</li>
            <li>{t('about.licenseNote2')}</li>
          </ul>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Heart className="w-5 h-5 text-red-500" />
            {t('about.specialThanks')}
          </h3>
          <p className="text-gray-600 text-sm mb-2">
            {t('about.specialThanksDesc')}
          </p>
          <ul className="text-gray-600 text-sm space-y-1">
            <li>{t('about.onebotProtocol')}</li>
            <li>{t('about.allContributors')}</li>
          </ul>
        </div>
      </div>

      {/* Footer */}
      <div className="text-center text-gray-500 text-sm py-8 border-t border-gray-200">
        <p>{t('about.footer')}</p>
        <p className="mt-2">
          {t('about.copyright', { year: new Date().getFullYear() })}
        </p>
      </div>
    </div>
  )
}

