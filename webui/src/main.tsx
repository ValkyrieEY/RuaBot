import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'
import { initPromise } from './i18n'

//  i18n 
initPromise
  .then(() => {
    renderApp()
  })
  .catch((err) => {
    console.error('Failed to initialize i18n:', err)
    // 
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

