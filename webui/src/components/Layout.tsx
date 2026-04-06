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
  Info,
  Server,
  FlaskConical,
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

  //  useMemo  i18n  navItems
  const navItems = useMemo(() => {
    return [
      { path: '/dashboard', icon: LayoutDashboard, label: t('nav.dashboard'), enabled: true },
      { path: '/onebot', icon: Radio, label: t('nav.onebot'), enabled: true },
      { path: '/napcat', icon: Server, label: t('nav.napcat'), enabled: true },
      { path: '/chat', icon: MessagesSquare, label: t('nav.chat'), enabled: true },
      { path: '/messages', icon: MessageSquare, label: t('nav.messages'), enabled: true },
      { path: '/plugins', icon: Puzzle, label: t('nav.plugins'), enabled: true },
      { path: '/ai', icon: Bot, label: t('nav.ai'), enabled: true },
      { path: '/sandbox', icon: FlaskConical, label: t('nav.sandbox'), enabled: true },
      { path: '/security', icon: Shield, label: t('nav.security'), enabled: true },
      { path: '/audit', icon: FileText, label: t('nav.audit'), enabled: true },
      { path: '/system', icon: Settings, label: t('nav.system'), enabled: true },
      { path: '/about', icon: Info, label: t('nav.about'), enabled: true },
    ]
  }, [t, i18n.language])

  return (
    <div className="min-h-screen bg-white overflow-x-hidden text-slate-900 font-sans">
      {/* Top Navigation */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-slate-100 fixed top-0 left-0 right-0 z-50 transition-all">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="md:hidden p-2.5 rounded-xl hover:bg-slate-50 text-slate-600 transition-colors"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <Link to="/dashboard" className="flex items-center gap-3">
                <div className="w-9 h-9 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-sm">
                  <span className="text-white font-extrabold text-sm tracking-widest">XQ</span>
                </div>
                <span className="font-bold text-xl tracking-tight hidden sm:block">Xiaoyi_QQ</span>
              </Link>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={toggleLanguage}
                className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
                title={i18n.language === 'zh' ? 'Switch to English' : ''}
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
        <aside className={`fixed inset-y-0 left-0 z-40 w-64 bg-white/90 backdrop-blur-xl border-r border-slate-100 transition-transform duration-300 ease-out top-16 h-[calc(100vh-4rem)] overflow-y-auto ${
          sidebarOpen 
            ? 'translate-x-0 shadow-2xl md:shadow-none' 
            : 'md:translate-x-0 -translate-x-full'
        }`}>
          <nav className="p-4 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              const isDisabled = !item.enabled
              
              if (isDisabled) {
                return (
                  <div
                    key={item.path}
                    className={cn(
                      'flex items-center gap-3 px-4 py-3 rounded-lg',
                      'text-gray-400 cursor-not-allowed opacity-50'
                    )}
                    title={t('nav.aiUnavailable')}
                  >
                    <Icon className="w-5 h-5" />
                    <span>{item.label}</span>
                  </div>
                )
              }
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  )}
                >
                  <Icon className={cn("w-5 h-5", isActive ? "text-primary-600" : "text-slate-400")} />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </aside>

        {/* Overlay for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
            style={{ top: '4rem' }} // Start below the top navigation bar
          />
        )}

        {/* Main Content */}
        <main className="flex-1 md:ml-64 max-w-full w-full bg-white">
          {/* Check if this is ChatPage or AI (full height, no padding) or regular page (with padding) */}
          {location.pathname === '/chat' || location.pathname.startsWith('/ai') ? (
            children
          ) : (
            <div className="p-4 sm:p-6 lg:p-8 min-h-[calc(100vh-4rem)] max-w-full overflow-x-hidden">
              <div className="max-w-full">
                {children}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
