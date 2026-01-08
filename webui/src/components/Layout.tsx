import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useMemo } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useAppStore } from '@/store/appStore'
import {
  Menu,
  X,
  LayoutDashboard,
  Puzzle,
  MessageSquare,
  Shield,
  FileText,
  Settings,
  LogOut,
  Globe,
  Radio,
  MessagesSquare,
  Bot,
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { t, i18n } = useTranslation()
  const { logout } = useAuthStore()
  const { sidebarOpen, setSidebarOpen } = useAppStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const toggleLanguage = async () => {
    const newLang = i18n.language === 'zh' ? 'en' : 'zh'
    localStorage.setItem('language', newLang)
    await i18n.changeLanguage(newLang)
  }

  // 使用 useMemo 确保在 i18n 准备好后才计算 navItems
  const navItems = useMemo(() => {
    return [
      { path: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard') },
      { path: '/onebot', icon: Radio, label: t('nav.onebot') },
      { path: '/chat', icon: MessagesSquare, label: '消息发送' },
      { path: '/messages', icon: MessageSquare, label: t('nav.messages') },
      { path: '/plugins', icon: Puzzle, label: t('nav.plugins') },
      { path: '/ai', icon: Bot, label: '人工智能' },
      { path: '/security', icon: Shield, label: t('nav.security') },
      { path: '/audit', icon: FileText, label: t('nav.audit') },
      { path: '/system', icon: Settings, label: t('nav.system') },
    ]
  }, [t, i18n.language])

  return (
    <div className="min-h-screen bg-gray-50 overflow-x-hidden">
      {/* Top Navigation */}
      <nav className="bg-white border-b border-gray-200 shadow-sm fixed top-0 left-0 right-0 z-50">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <Link to="/dashboard" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">XQ</span>
                </div>
                <span className="font-bold text-xl text-gray-900">Xiaoyi_QQ</span>
              </Link>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={toggleLanguage}
                className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                title={i18n.language === 'zh' ? 'Switch to English' : '切换到中文'}
              >
                <Globe className="w-5 h-5 text-gray-600" />
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <LogOut className="w-5 h-5" />
                <span className="hidden sm:inline">{t('common.logout')}</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="flex relative pt-16">
        {/* Sidebar */}
        <aside
          className={cn(
            'fixed lg:fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 transition-transform duration-300 ease-in-out',
            'top-16 lg:top-16 h-[calc(100vh-4rem)] lg:h-[calc(100vh-4rem)] overflow-y-auto',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          )}
        >
          <nav className="p-4 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-50'
                  )}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </aside>

        {/* Overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            style={{ top: '4rem' }} // Start below the top navigation bar
          />
        )}

        {/* Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 min-h-[calc(100vh-4rem)] lg:ml-64 max-w-full overflow-x-hidden w-full">
          <div className="max-w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
