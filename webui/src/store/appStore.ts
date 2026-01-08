import { create } from 'zustand'

interface AppState {
  language: 'zh' | 'en'
  setLanguage: (lang: 'zh' | 'en') => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
}

// Initialize sidebar state based on screen size
const getInitialSidebarState = (): boolean => {
  if (typeof window === 'undefined') return false
  // On desktop (lg and above), sidebar is open by default
  // On mobile, sidebar is closed by default
  return window.innerWidth >= 1024 // lg breakpoint
}

export const useAppStore = create<AppState>((set) => ({
  language: (localStorage.getItem('language') as 'zh' | 'en') || 'zh',
  setLanguage: (lang) => {
    localStorage.setItem('language', lang)
    set({ language: lang })
    window.location.reload() // Reload to apply language change
  },
  sidebarOpen: getInitialSidebarState(),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))

