import { create } from 'zustand'
import { api } from '@/utils/api'

interface User {
  username: string
  [key: string]: any
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

const getStorageItem = (key: string): string | null => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(key)
}

const setStorageItem = (key: string, value: string): void => {
  if (typeof window === 'undefined') return
  localStorage.setItem(key, value)
}

const removeStorageItem = (key: string): void => {
  if (typeof window === 'undefined') return
  localStorage.removeItem(key)
}

// Initialize state safely for SSR
const getInitialState = () => {
  if (typeof window === 'undefined') {
    return {
      user: null,
      token: null,
      isAuthenticated: false,
    }
  }
  const userStr = getStorageItem('user')
  const token = getStorageItem('access_token')
  return {
    user: userStr ? JSON.parse(userStr) : null,
    token,
    isAuthenticated: !!token,
  }
}

export const useAuthStore = create<AuthState>((set) => {
  const initialState = getInitialState()
  return {
    ...initialState,

  login: async (username: string, password: string) => {
    const response = await api.login({ username, password })
    const token = response.access_token
    setStorageItem('access_token', token)
    
    const user = await api.getCurrentUser()
    setStorageItem('user', JSON.stringify(user))
    set({ token, user, isAuthenticated: true })
  },

  logout: async () => {
    try {
      await api.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      set({ user: null, token: null, isAuthenticated: false })
      removeStorageItem('access_token')
      removeStorageItem('user')
    }
  },

  checkAuth: async () => {
    const token = getStorageItem('access_token')
    if (!token) {
      set({ user: null, token: null, isAuthenticated: false })
      return
    }

    try {
      const user = await api.getCurrentUser()
      setStorageItem('user', JSON.stringify(user))
      set({ token, user, isAuthenticated: true })
    } catch (error) {
      set({ user: null, token: null, isAuthenticated: false })
      removeStorageItem('access_token')
      removeStorageItem('user')
    }
  },
  }
})

