import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect, Suspense, lazy } from 'react'
import { useAuthStore } from './store/authStore'
import { ToastProvider } from './components/Toast'
import { api } from './utils/api'
import LoginPage from './pages/LoginPage'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import PluginsPage from './pages/PluginsPage'
import OneBotPage from './pages/OneBotPage'
import ChatPage from './pages/ChatPage'
import MessageLogPage from './pages/MessageLogPage'
import SecurityPage from './pages/SecurityPage'
import AuditPage from './pages/AuditPage'
import SystemPage from './pages/SystemPage'
import AIPage from './pages/AIPage'
import AboutPage from './pages/AboutPage'

// 动态导入开屏动画组件，支持热插拔
// 如果文件不存在，lazy 会在运行时捕获错误
const SplashScreen = lazy(() => 
  import('../splash_screen/SplashScreen').catch(() => {
    // 返回一个空组件作为回退
    return { default: () => <></> }
  })
) as React.LazyExoticComponent<React.ComponentType<{ onComplete: () => void }>>

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function AppContent() {
  const { checkAuth } = useAuthStore()

  // 检查认证状态（用于已登录用户）
  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/plugins"
        element={
          <PrivateRoute>
            <Layout>
              <PluginsPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/onebot"
        element={
          <PrivateRoute>
            <Layout>
              <OneBotPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <PrivateRoute>
            <Layout>
              <ChatPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/messages"
        element={
          <PrivateRoute>
            <Layout>
              <MessageLogPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/security"
        element={
          <PrivateRoute>
            <Layout>
              <SecurityPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/audit"
        element={
          <PrivateRoute>
            <Layout>
              <AuditPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/system"
        element={
          <PrivateRoute>
            <Layout>
              <SystemPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/ai"
        element={
          <PrivateRoute>
            <Layout>
              <AIPage />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/about"
        element={
          <PrivateRoute>
            <Layout>
              <AboutPage />
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  )
}

function App() {
  const [showSplash, setShowSplash] = useState(true)
  const [checkingSplash, setCheckingSplash] = useState(true)
  const [splashAvailable, setSplashAvailable] = useState(false)

  useEffect(() => {
    const checkSplashScreen = async () => {
      try {
        const result = await api.checkSplashScreen()
        setShowSplash(result.should_show)
        setSplashAvailable(result.should_show)
      } catch (error) {
        console.error('Failed to check splash screen:', error)
        // 出错时默认不显示
        setShowSplash(false)
        setSplashAvailable(false)
      } finally {
        setCheckingSplash(false)
      }
    }

    checkSplashScreen()
  }, [])

  const handleSplashComplete = () => {
    // 开屏动画结束后，直接导航到登录页（首次启动肯定未登录）
    window.history.replaceState(null, '', '/login')
    setShowSplash(false)
  }

  // 如果正在检查或需要显示开屏动画，显示开屏动画
  if (checkingSplash || (showSplash && splashAvailable)) {
    return (
      <Suspense fallback={<div className="fixed inset-0 bg-black" />}>
        <SplashScreen onComplete={handleSplashComplete} />
      </Suspense>
    )
  }

  return (
    <ToastProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ToastProvider>
  )
}

export default App

