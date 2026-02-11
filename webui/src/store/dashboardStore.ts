import { create } from 'zustand'

interface Rates {
  events: number
  received: number
  sent: number
}

interface ThreadPoolHistoryItem {
  time: string
  tasks: number
  timestamp: number
}

interface ThreadPoolHistory {
  ai: ThreadPoolHistoryItem[]
  plugin: ThreadPoolHistoryItem[]
}

interface DashboardState {
  lastStatus: any | null
  lastTime: number
  rates: Rates
  threadPoolHistory: ThreadPoolHistory
  setDashboardState: (status: any, time: number, rates: Rates) => void
  setThreadPoolHistory: (history: ThreadPoolHistory) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  lastStatus: null,
  lastTime: Date.now(),
  rates: { events: 0, received: 0, sent: 0 },
  threadPoolHistory: { ai: [], plugin: [] },
  setDashboardState: (status, time, rates) => set({ 
    lastStatus: status, 
    lastTime: time, 
    rates 
  }),
  setThreadPoolHistory: (history) => set({ threadPoolHistory: history }),
}))

