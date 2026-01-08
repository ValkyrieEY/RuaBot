import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
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

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
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
      </Routes>
    </BrowserRouter>
  )
}

export default App

