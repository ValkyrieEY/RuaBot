import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'
import { initPromise } from './i18n'

// 等待 i18n 初始化完成后再渲染应用
initPromise
  .then(() => {
    renderApp()
  })
  .catch((err) => {
    console.error('Failed to initialize i18n:', err)
    // 即使初始化失败也渲染应用，使用回退语言
    renderApp()
  })

function renderApp() {
  const rootElement = document.getElementById('root')
  if (!rootElement) {
    console.error('Root element not found')
    return
  }
  
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

