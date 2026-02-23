import { Save, Info } from 'lucide-react'
import { RuaBotConfigProps } from './types'

export default function RuaBotConfig({
  enableRuaBot,
  setEnableRuaBot,
  ruabotDecisionModel,
  setRuabotDecisionModel,
  botName,
  setBotName,
  thinkLevel,
  setThinkLevel,
  enableBrainMode,
  setEnableBrainMode,
  enableLearning,
  setEnableLearning,
  talkValue,
  setTalkValue,
  triggerMode,
  models,
  saving,
  handleSaveGlobal
}: RuaBotConfigProps) {
  
  const isMaxtoken = triggerMode === 'maxtoken'

  return (
    <div className="space-y-6">
      {/* 头部说明与开关卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        {!isMaxtoken && (
          <div className="bg-amber-50 border border-amber-100 text-amber-800 text-sm px-4 py-3 rounded-lg flex items-start gap-3">
            <Info className="w-5 h-5 shrink-0 mt-0.5 text-amber-600" />
            <div>
              <p className="font-medium">功能受限</p>
              <p className="mt-1 text-xs opacity-90">
                当前未启用 MaxToken 模式，RuaBot 的大部分功能将无法生效。
                请在「基础设置」中切换触发模式为 MaxToken 以启用完整功能。
              </p>
            </div>
          </div>
        )}

        <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all duration-300 ${!isMaxtoken ? 'opacity-60 grayscale-[0.5]' : ''}`}>
          <div>
            <h2 className="text-base font-bold text-gray-900">RuaBot 拟人化系统</h2>
            <p className="text-sm text-gray-500 mt-1">具备自主决策、长期记忆和智能规划的高级 AI 代理</p>
          </div>
          <div className="flex items-center gap-4">
            <label className={`flex items-center gap-2 cursor-pointer select-none ${!isMaxtoken ? 'cursor-not-allowed' : ''}`}>
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={enableRuaBot}
                  onChange={(e) => setEnableRuaBot(e.target.checked)}
                  disabled={!isMaxtoken}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
              </div>
              <span className="text-sm font-medium text-gray-700">启用</span>
            </label>
            <button
              onClick={handleSaveGlobal}
              disabled={saving || !isMaxtoken}
              className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </div>

      {/* 核心配置卡片 */}
      <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5 transition-all duration-300 ${(!isMaxtoken || !enableRuaBot) ? 'opacity-60 grayscale-[0.5]' : ''}`}>
        <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
          <div className="w-1 h-5 bg-purple-500 rounded-full"></div>
          <h3 className="text-base font-bold text-gray-900">核心参数</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">RuaBot 决策模型</label>
            <select
              value={ruabotDecisionModel}
              onChange={(e) => setRuabotDecisionModel(e.target.value)}
              disabled={!isMaxtoken || !enableRuaBot}
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2.5"
            >
              <option value="">使用主模型</option>
              {models.map((model) => (
                <option key={model.uuid} value={model.uuid}>
                  {model.name} ({model.provider})
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500">用于判断"是否回复"、"情感分析"等决策，建议使用小模型</p>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">Bot 名称 (自称)</label>
            <input
              type="text"
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
              disabled={!isMaxtoken || !enableRuaBot}
              placeholder="例如：Rua酱"
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-purple-500 focus:ring-purple-500 sm:text-sm py-2.5"
            />
            <p className="text-xs text-gray-500">AI 在对话中对自己的称呼，影响自我认知</p>
          </div>
        </div>
      </div>

      {/* 行为参数卡片 */}
      <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6 transition-all duration-300 ${(!isMaxtoken || !enableRuaBot) ? 'opacity-60 grayscale-[0.5]' : ''}`}>
        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
            <div className="w-1 h-5 bg-pink-500 rounded-full"></div>
            <h3 className="text-base font-bold text-gray-900">活跃度控制</h3>
          </div>
          
          <div className="space-y-4 bg-gray-50 p-5 rounded-xl border border-gray-100">
            <div className="flex justify-between items-center">
              <label className="text-sm font-medium text-gray-900">发言频率 (Talk Value)</label>
              <span className="text-sm font-bold text-purple-600 bg-purple-100 px-3 py-1 rounded-full">{talkValue.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={talkValue}
              onChange={(e) => setTalkValue(parseFloat(e.target.value))}
              disabled={!isMaxtoken || !enableRuaBot}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
            />
            <div className="flex justify-between text-xs text-gray-500 font-medium px-1">
              <span>沉默 (0.0)</span>
              <span>适中 (0.5)</span>
              <span>话痨 (1.0)</span>
            </div>
            <p className="text-xs text-gray-500 pt-2 border-t border-gray-200 mt-2">
              控制 AI 主动插话的概率。值越小越安静，只有被 @ 或感兴趣时才回复。
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4 mt-6">
            <div className="w-1 h-5 bg-indigo-500 rounded-full"></div>
            <h3 className="text-base font-bold text-gray-900">智能特性</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className={`flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors ${(!isMaxtoken || !enableRuaBot) ? 'opacity-60 cursor-not-allowed' : ''}`}>
              <div>
                <div className="text-sm font-bold text-gray-900">Brain Planner (思维链)</div>
                <div className="text-xs text-gray-500 mt-0.5">使用 ReAct 模式进行思考，支持复杂任务规划</div>
              </div>
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={enableBrainMode}
                  onChange={(e) => setEnableBrainMode(e.target.checked)}
                  disabled={!isMaxtoken || !enableRuaBot}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
              </div>
            </label>

            <label className={`flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors ${(!isMaxtoken || !enableRuaBot) ? 'opacity-60 cursor-not-allowed' : ''}`}>
              <div>
                <div className="text-sm font-bold text-gray-900">自主学习 (Active Learning)</div>
                <div className="text-xs text-gray-500 mt-0.5">自动学习群友的说话风格、口癖和新词汇</div>
              </div>
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={enableLearning}
                  onChange={(e) => setEnableLearning(e.target.checked)}
                  disabled={!isMaxtoken || !enableRuaBot}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
              </div>
            </label>
          </div>

          <div className="p-4 bg-gray-50 rounded-xl border border-gray-100">
            <label className="block text-sm font-medium text-gray-900 mb-3">思考深度 (Think Level)</label>
            <div className="flex items-center gap-4">
              <span className={`text-xs font-bold ${thinkLevel === 0 ? 'text-purple-600' : 'text-gray-400'}`}>快速响应</span>
              <input
                type="range"
                min="0"
                max="1"
                step="1"
                value={thinkLevel}
                onChange={(e) => setThinkLevel(parseInt(e.target.value))}
                disabled={!isMaxtoken || !enableRuaBot}
                className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
              />
              <span className={`text-xs font-bold ${thinkLevel === 1 ? 'text-purple-600' : 'text-gray-400'}`}>深度思考</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
