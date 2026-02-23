import { Save, Info } from 'lucide-react'
import { AIConfigProps } from './types'

export default function BasicConfig({
  globalEnabled,
  setGlobalEnabled,
  globalModel,
  setGlobalModel,
  globalPreset,
  setGlobalPreset,
  globalDecisionModel,
  setGlobalDecisionModel,
  globalTriggerCommand,
  setGlobalTriggerCommand,
  triggerMode,
  setTriggerMode,
  enableStreaming,
  setEnableStreaming,
  toolsEnabled,
  setToolsEnabled,
  models,
  presets,
  saving,
  handleSaveGlobal
}: AIConfigProps) {
  return (
    <div className="space-y-6">
      {/* 功能总开关卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-gray-900">功能总开关</h2>
            <p className="text-sm text-gray-500 mt-1">控制整个 AI 系统的启用状态</p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={globalEnabled}
                  onChange={(e) => setGlobalEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </div>
              <span className="text-sm font-medium text-gray-700">启用</span>
            </label>
            <button
              onClick={handleSaveGlobal}
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </div>

      {/* 核心模型配置卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
        <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
          <div className="w-1 h-5 bg-blue-500 rounded-full"></div>
          <h3 className="text-base font-bold text-gray-900">模型与预设</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">默认对话模型</label>
            <select
              value={globalModel}
              onChange={(e) => setGlobalModel(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5"
            >
              <option value="">未选择</option>
              {models.map((model) => (
                <option key={model.uuid} value={model.uuid}>
                  {model.name} ({model.provider})
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500">主要用于生成回复的 LLM 模型</p>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">默认预设 (Prompt)</label>
            <select
              value={globalPreset}
              onChange={(e) => setGlobalPreset(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5"
            >
              <option value="">未选择</option>
              {presets.map((preset) => (
                <option key={preset.uuid} value={preset.uuid}>
                  {preset.name}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500">定义 AI 的角色和行为设定</p>
          </div>

          <div className="md:col-span-2 space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              决策模型 <span className="text-gray-400 font-normal ml-1">(用于权限判断等轻量级任务)</span>
            </label>
            <select
              value={globalDecisionModel}
              onChange={(e) => setGlobalDecisionModel(e.target.value)}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2.5"
            >
              <option value="">使用主模型</option>
              {models.map((model) => (
                <option key={model.uuid} value={model.uuid}>
                  {model.name} ({model.provider})
                </option>
              ))}
            </select>
            <div className="flex items-center gap-1.5 mt-1.5 text-xs text-gray-500 bg-blue-50 p-2 rounded text-blue-700 border border-blue-100 inline-flex">
              <Info className="w-3.5 h-3.5" />
              建议使用更快速、更便宜的模型 (如 gpt-3.5-turbo, deepseek-chat)
            </div>
          </div>
        </div>
      </div>

      {/* 触发模式配置卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
          <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
          <h3 className="text-base font-bold text-gray-900">触发模式</h3>
        </div>
        
        <div className="space-y-4">
          {/* 指令模式 */}
          <label className={`flex items-start gap-4 p-4 border rounded-xl cursor-pointer transition-all ${
            triggerMode === 'command' ? 'border-purple-200 bg-purple-50 ring-1 ring-purple-200' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}>
            <input
              type="radio"
              name="triggerMode"
              value="command"
              checked={triggerMode === 'command'}
              onChange={(e) => setTriggerMode(e.target.value as 'command' | 'maxtoken')}
              className="mt-1 w-4 h-4 text-purple-600 border-gray-300 focus:ring-purple-500"
            />
            <div className="flex-1">
              <span className="block text-sm font-bold text-gray-900">指令触发模式</span>
              <span className="block text-xs text-gray-500 mt-1 mb-2">只有以指定指令开头的消息才会触发回复</span>
              
              {triggerMode === 'command' && (
                <div className="animate-fadeIn">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={globalTriggerCommand}
                      onChange={(e) => setGlobalTriggerCommand(e.target.value)}
                      placeholder="例如：@AI 或 /chat"
                      className="block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 text-sm py-1.5"
                    />
                    <span className="text-xs text-gray-400">留空则默认需要 @机器人</span>
                  </div>
                </div>
              )}
            </div>
          </label>

          {/* MaxToken 模式 */}
          <label className={`flex items-start gap-4 p-4 border rounded-xl cursor-pointer transition-all ${
            triggerMode === 'maxtoken' ? 'border-purple-200 bg-purple-50 ring-1 ring-purple-200' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}>
            <input
              type="radio"
              name="triggerMode"
              value="maxtoken"
              checked={triggerMode === 'maxtoken'}
              onChange={(e) => setTriggerMode(e.target.value as 'command' | 'maxtoken')}
              className="mt-1 w-4 h-4 text-purple-600 border-gray-300 focus:ring-purple-500"
            />
            <div className="flex-1">
              <span className="block text-sm font-bold text-gray-900">MaxToken 智能模式</span>
              <span className="block text-xs text-gray-500 mt-1">
                所有消息都会上报给 AI，由 AI 自行判断是否需要回复。
                <span className="text-purple-600 font-medium ml-1">请在「RuaBot & Behavior」中配置详细行为</span>
              </span>
            </div>
          </label>
        </div>
      </div>

      {/* 高级功能开关卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
          <div className="w-1 h-5 bg-gray-500 rounded-full"></div>
          <h3 className="text-base font-bold text-gray-900">高级选项</h3>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <label className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors">
            <div>
              <div className="text-sm font-bold text-gray-900">流式传输 (Streaming)</div>
              <div className="text-xs text-gray-500 mt-0.5">模拟打字效果，分段发送长回复</div>
            </div>
            <div className="relative inline-flex items-center">
              <input
                type="checkbox"
                checked={enableStreaming}
                onChange={(e) => setEnableStreaming(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </div>
          </label>

          <label className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors">
            <div>
              <div className="text-sm font-bold text-gray-900">工具调用 (Function Calling)</div>
              <div className="text-xs text-gray-500 mt-0.5">允许 AI 使用搜索、群管理等工具</div>
            </div>
            <div className="relative inline-flex items-center">
              <input
                type="checkbox"
                checked={toolsEnabled}
                onChange={(e) => setToolsEnabled(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </div>
          </label>
        </div>
      </div>
    </div>
  )
}
