import axios, { AxiosInstance, AxiosError } from 'axios'

// Normalize API base URL - ensure it ends with /api but doesn't duplicate
let API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
// Remove trailing /api if present, then add it back to ensure consistency
if (API_BASE_URL.endsWith('/api')) {
  API_BASE_URL = API_BASE_URL.slice(0, -4) // Remove '/api'
}
// Ensure it ends with /api
if (!API_BASE_URL.endsWith('/api')) {
  API_BASE_URL = API_BASE_URL + (API_BASE_URL.endsWith('/') ? 'api' : '/api')
}

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 15000, // 15秒超时
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor to handle errors
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('access_token')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: any): Promise<T> {
    const response = await this.client.get<T>(url, config)
    return response.data
  }

  async post<T = any>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.post<T>(url, data, config)
    return response.data
  }

  // Get image proxy URL
  getImageProxyUrl(imageUrl: string): string {
    return `${API_BASE_URL}/chat/image-proxy?url=${encodeURIComponent(imageUrl)}`
  }

  async put<T = any>(url: string, data?: any, config?: any): Promise<T> {
    const response = await this.client.put<T>(url, data, config)
    return response.data
  }

  async delete<T = any>(url: string, config?: any): Promise<T> {
    const response = await this.client.delete<T>(url, config)
    return response.data
  }

  // Auth
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.client.post<LoginResponse>('/auth/login', credentials)
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token)
    }
    return response.data
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout')
    localStorage.removeItem('access_token')
  }

  async getCurrentUser(): Promise<any> {
    const response = await this.client.get('/auth/me')
    return response.data
  }

  // Plugins
  async getPlugins(): Promise<PluginInfo[]> {
    const response = await this.client.get<PluginInfo[]>('/plugins')
    return response.data
  }

  async getPlugin(name: string): Promise<any> {
    const response = await this.client.get(`/plugins/${name}`)
    return response.data
  }

  async pluginAction(name: string, action: string): Promise<any> {
    const payload: any = { action }
    const response = await this.client.post(`/plugins/${name}/action`, payload)
    return response.data
  }

  async reloadPlugin(name: string): Promise<any> {
    const response = await this.client.post(`/plugins/${name}/action`, { action: 'reload' })
    return response.data
  }

  async deletePlugin(name: string): Promise<any> {
    const response = await this.client.delete(`/plugins/${name}`)
    return response.data
  }

  async updatePluginConfig(name: string, config: any, priority?: number): Promise<any> {
    const payload: any = { config }
    if (priority !== undefined) {
      payload.priority = priority
    }
    const response = await this.client.put(`/plugins/${name}/config`, payload)
    return response.data
  }

  async getPluginConfigSchema(name: string): Promise<any> {
    const response = await this.client.get(`/plugins/${name}/config-schema`)
    return response.data
  }

  async uploadPlugin(file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await this.client.post('/plugins/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  async installPluginFromGitHub(repoUrl: string): Promise<{ task_id: string }> {
    const response = await this.client.post('/plugins/install-from-github', {
      repo_url: repoUrl
    })
    return response.data
  }

  async uploadPluginConfigFile(file: File): Promise<{ file_key: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const response = await this.client.post('/plugins/config-files', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  async deletePluginConfigFile(fileKey: string): Promise<{ deleted: boolean }> {
    const response = await this.client.delete(`/plugins/config-files/${fileKey}`)
    return response.data
  }

  // System
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await this.client.get<SystemStatus>('/system/status')
    return response.data
  }

  async getThreadPoolStats(): Promise<any> {
    const response = await this.client.get('/system/threadpool-stats')
    return response.data
  }

  async getSystemConfig(): Promise<any> {
    const response = await this.client.get('/system/config')
    return response.data
  }

  async updateSystemConfig(config: any): Promise<any> {
    const response = await this.client.post('/system/config', config)
    return response.data
  }

  async resetAdminPassword(data: { password: string }): Promise<any> {
    const response = await this.client.post('/system/reset-admin-password', data)
    return response.data
  }

  // OneBot
  async getOneBotConfig(): Promise<OneBotConfig> {
    const response = await this.client.get<OneBotConfig>('/onebot/config')
    return response.data
  }

  async updateOneBotConfig(config: OneBotConfigUpdate): Promise<any> {
    const response = await this.client.post('/onebot/config', config)
    return response.data
  }

  async reconnectOneBot(): Promise<{ success: boolean; message: string }> {
    const response = await this.client.post('/onebot/reconnect')
    return response.data
  }

  async getLoginInfo(): Promise<any> {
    const response = await this.client.get('/onebot/login-info')
    return response.data
  }

  // Messages
  async getMessageLog(limit?: number): Promise<MessageLog[]> {
    const response = await this.client.get<MessageLog[]>('/messages/log', {
      params: { limit },
    })
    return response.data
  }

  // System Logs
  async getSystemLogs(limit?: number): Promise<any[]> {
    const response = await this.client.get('/system/logs', {
      params: { limit },
    })
    return response.data
  }

  // Chat APIs
  async getChatContacts(): Promise<{ groups: any[], friends: any[] }> {
    const response = await this.client.get('/chat/contacts')
    return response.data
  }

  async sendChatMessage(payload: { type: string, id: string, message: string }): Promise<any> {
    const response = await this.client.post('/chat/send', payload)
    return response.data
  }

  async getChatHistory(chatType: string, chatId: string, limit: number = 50): Promise<any[]> {
    const response = await this.client.get(`/chat/history/${chatType}/${chatId}`, { params: { limit } })
    return response.data
  }

  async getGroupMembers(groupId: string): Promise<{ group_id: string, members: any[], count: number }> {
    const response = await this.client.get(`/chat/groups/${groupId}/members`)
    return response.data
  }

  // AI APIs
  async checkAIAvailability(): Promise<{ available: boolean; message: string; module_path?: string }> {
    const response = await this.client.get('/ai/availability')
    return response.data
  }
  
  async getAIConfig(configType: string, targetId?: string): Promise<any> {
    const response = await this.client.get('/ai/config', { params: { config_type: configType, target_id: targetId } })
    return response.data
  }

  async updateAIConfig(configType: string, targetId: string | undefined, updates: any): Promise<any> {
    const response = await this.client.put('/ai/config', updates, { 
      params: { config_type: configType, target_id: targetId },
      headers: { 'Content-Type': 'application/json' }
    })
    return response.data
  }

  // AI Tools
  async listAITools(): Promise<any[]> {
    const response = await this.client.get('/ai/tools')
    return response.data
  }

  async getEnabledTools(configType: string, targetId?: string): Promise<Record<string, boolean>> {
    const response = await this.client.get('/ai/tools/enabled', {
      params: { config_type: configType, target_id: targetId }
    })
    return response.data
  }

  async updateEnabledTools(configType: string, targetId: string | undefined, enabledTools: Record<string, boolean>): Promise<any> {
    const response = await this.client.put('/ai/tools/enabled', { enabled_tools: enabledTools }, {
      params: { config_type: configType, target_id: targetId }
    })
    return response.data
  }

  async listGroupConfigs(): Promise<any[]> {
    const response = await this.client.get('/ai/groups')
    return response.data
  }

  async batchUpdateGroups(groupIds: string[], updates: any): Promise<any> {
    const response = await this.client.post('/ai/groups/batch', { ...updates, group_ids: groupIds })
    return response.data
  }

  async listModels(): Promise<any[]> {
    const response = await this.client.get('/ai/models')
    return response.data
  }

  async getModel(modelUuid: string): Promise<any> {
    const response = await this.client.get(`/ai/models/${modelUuid}`)
    return response.data
  }

  async createModel(model: any): Promise<any> {
    const response = await this.client.post('/ai/models', model)
    return response.data
  }

  async updateModel(modelUuid: string, updates: any): Promise<any> {
    const response = await this.client.put(`/ai/models/${modelUuid}`, updates)
    return response.data
  }

  async deleteModel(modelUuid: string): Promise<any> {
    const response = await this.client.delete(`/ai/models/${modelUuid}`)
    return response.data
  }

  async listProviders(): Promise<string[]> {
    const response = await this.client.get('/ai/models/providers/list')
    return response.data
  }

  async listPresets(): Promise<any[]> {
    const response = await this.client.get('/ai/presets')
    return response.data
  }

  async getPreset(presetUuid: string): Promise<any> {
    const response = await this.client.get(`/ai/presets/${presetUuid}`)
    return response.data
  }

  async createPreset(preset: any): Promise<any> {
    const response = await this.client.post('/ai/presets', preset)
    return response.data
  }

  async updatePreset(presetUuid: string, updates: any): Promise<any> {
    const response = await this.client.put(`/ai/presets/${presetUuid}`, updates)
    return response.data
  }

  async deletePreset(presetUuid: string): Promise<any> {
    const response = await this.client.delete(`/ai/presets/${presetUuid}`)
    return response.data
  }

  async listMemories(memoryType?: string, targetId?: string): Promise<any[]> {
    const response = await this.client.get('/ai/memories', { params: { memory_type: memoryType, target_id: targetId } })
    return response.data
  }

  async getMemory(memoryUuid: string): Promise<any> {
    const response = await this.client.get(`/ai/memories/${memoryUuid}`)
    return response.data
  }

  async deleteMemory(memoryUuid: string): Promise<any> {
    const response = await this.client.delete(`/ai/memories/${memoryUuid}`)
    return response.data
  }

  async clearMemory(memoryType: string, targetId: string, presetUuid?: string): Promise<any> {
    const response = await this.client.post('/ai/memories/clear', {
      memory_type: memoryType,
      target_id: targetId,
      preset_uuid: presetUuid || null
    })
    return response.data
  }

  async listMCPServers(enabledOnly: boolean = false): Promise<any[]> {
    const response = await this.client.get('/ai/mcp/servers', { params: { enabled_only: enabledOnly } })
    return response.data
  }

  async getMCPServer(serverUuid: string): Promise<any> {
    const response = await this.client.get(`/ai/mcp/servers/${serverUuid}`)
    return response.data
  }

  async createMCPServer(server: any): Promise<any> {
    const response = await this.client.post('/ai/mcp/servers', server)
    return response.data
  }

  async updateMCPServer(serverUuid: string, updates: any): Promise<any> {
    const response = await this.client.put(`/ai/mcp/servers/${serverUuid}`, updates)
    return response.data
  }

  async deleteMCPServer(serverUuid: string): Promise<any> {
    const response = await this.client.delete(`/ai/mcp/servers/${serverUuid}`)
    return response.data
  }

  async connectMCPServer(serverUuid: string): Promise<any> {
    const response = await this.client.post(`/ai/mcp/servers/${serverUuid}/connect`)
    return response.data
  }

  async disconnectMCPServer(serverUuid: string): Promise<any> {
    const response = await this.client.post(`/ai/mcp/servers/${serverUuid}/disconnect`)
    return response.data
  }

  async getMCPServerTools(serverUuid: string): Promise<any[]> {
    const response = await this.client.get(`/ai/mcp/servers/${serverUuid}/tools`)
    return response.data
  }

  async getAllMCPTools(): Promise<any[]> {
    const response = await this.client.get('/ai/mcp/tools')
    return response.data
  }

  // Splash screen APIs
  async checkSplashScreen(): Promise<{ should_show: boolean; reason?: string }> {
    const response = await this.client.get('/splash/check')
    return response.data
  }

  async markSplashScreenShown(): Promise<any> {
    const response = await this.client.post('/splash/mark-shown')
    return response.data
  }

  // NapCat Management API
  async getNapCatSystemInfo(): Promise<any> {
    const response = await this.client.get('/napcat/system/info')
    return response.data
  }

  async getNapCatConfig(): Promise<any> {
    const response = await this.client.get('/napcat/config')
    return response.data
  }

  async updateNapCatConfig(data: any): Promise<any> {
    const response = await this.client.post('/napcat/config', data)
    return response.data
  }

  async deployNapCat(data: any): Promise<any> {
    const response = await this.client.post('/napcat/deploy', data)
    return response.data
  }

  async getNapCatProgress(jobId: string): Promise<any> {
    const response = await this.client.get(`/napcat/progress/${jobId}`)
    return response.data
  }

  async cancelNapCatInstall(data: any): Promise<any> {
    const response = await this.client.post('/napcat/cancel', data)
    return response.data
  }

  async getNapCatStatus(): Promise<any> {
    const response = await this.client.get('/napcat/status')
    return response.data
  }

  async startNapCat(): Promise<any> {
    const response = await this.client.post('/napcat/start')
    return response.data
  }

  async stopNapCat(): Promise<any> {
    const response = await this.client.post('/napcat/stop')
    return response.data
  }

  async getNapCatLogs(): Promise<any> {
    const response = await this.client.get('/napcat/logs')
    return response.data
  }

  async getNapCatWebUIInfo(): Promise<any> {
    const response = await this.client.get('/napcat/webui')
    return response.data
  }

  async setNapCatPath(data: any): Promise<any> {
    const response = await this.client.post('/napcat/path', data)
    return response.data
  }

  async listNapCatDockerContainers(): Promise<any> {
    const response = await this.client.get('/napcat/docker/containers')
    return response.data
  }

  async systemOpenDialog(): Promise<any> {
    const response = await this.client.post('/system/open-dialog')
    return response.data
  }

  async listDirectory(data: any): Promise<any> {
    const response = await this.client.post('/system/list-directory', data)
    return response.data
  }
}

// Types
export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user?: any
}

export interface PluginInfo {
  name: string
  enabled: boolean
  metadata?: {
    name: string
    version: string
    author: string
    description: string
    category?: string
    tags?: string[]
    dependencies?: string[]
    homepage?: string
    repository?: string
    documentation?: string
    [key: string]: any
  }
  // Legacy fields for backward compatibility
  version?: string
  description?: string
  author?: string
  system_data?: any
}

export interface SystemStatus {
  status: string
  uptime?: string
  event_bus: {
    total_events?: number
    history_size?: number
    [key: string]: any
  }
  plugins: {
    total: number
    enabled: number
  }
  online_users?: number
}

export interface OneBotConfig {
  onebot_enabled: boolean
  onebot_version: string
  onebot_connection_type: string
  onebot_ws_url?: string
  onebot_ws_reverse_host?: string
  onebot_ws_reverse_port?: number
  onebot_http_url?: string
  onebot_access_token?: string
}

export interface OneBotConfigUpdate {
  onebot_enabled?: boolean
  onebot_version?: string
  onebot_connection_type?: string
  onebot_ws_url?: string
  onebot_ws_reverse_host?: string
  onebot_ws_reverse_port?: number
  onebot_http_url?: string
  onebot_access_token?: string
}

export interface MessageLog {
  id?: string
  time: string
  message_type: string
  user_id: string | number
  group_id?: string | number
  sender: {
    user_id: string | number
    nickname?: string
    [key: string]: any
  }
  message: string
  raw_message?: string
  [key: string]: any
}


export const api = new ApiClient()
