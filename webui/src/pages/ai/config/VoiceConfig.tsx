import { Save, Eye, EyeOff, Mic, Volume2 } from 'lucide-react'
import { VoiceConfigProps } from './types'

export default function VoiceConfig({
  ttsModeEnabled,
  setTtsModeEnabled,
  ttsModeType,
  setTtsModeType,
  tencentSecretId,
  setTencentSecretId,
  tencentSecretKey,
  setTencentSecretKey,
  showTencentKey,
  setShowTencentKey,
  ttsConfigLoaded,
  saving,
  handleSaveGlobal,
  handleSaveTTS
}: VoiceConfigProps) {
  return (
    <div className="space-y-6">
      {/* TTS 模式开关卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-gray-900">自动语音模式</h2>
            <p className="text-sm text-gray-500 mt-1">开启后，AI 的回复将自动转换为语音发送</p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <div className="relative inline-flex items-center">
                <input
                  type="checkbox"
                  checked={ttsModeEnabled}
                  onChange={(e) => setTtsModeEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-600"></div>
              </div>
              <span className="text-sm font-medium text-gray-700">启用</span>
            </label>
            <button
              onClick={handleSaveGlobal}
              disabled={saving}
              className="flex items-center gap-1.5 px-4 py-2 bg-pink-600 text-white text-sm font-medium rounded-lg hover:bg-pink-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </div>

      {/* 语音策略卡片 */}
      <div className={`bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4 transition-all duration-300 ${!ttsModeEnabled ? 'opacity-60 grayscale-[0.5]' : ''}`}>
        <div className="flex items-center gap-2 border-b border-gray-100 pb-4 mb-4">
          <div className="w-1 h-5 bg-pink-500 rounded-full"></div>
          <h3 className="text-base font-bold text-gray-900">发送策略</h3>
        </div>
        
        <div className="space-y-4">
          <label className={`flex items-start gap-4 p-4 border rounded-xl cursor-pointer transition-all ${
            ttsModeType === 'voice_only' ? 'border-pink-200 bg-pink-50 ring-1 ring-pink-200' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}>
            <input
              type="radio"
              name="ttsModeType"
              value="voice_only"
              checked={ttsModeType === 'voice_only'}
              onChange={(e) => setTtsModeType(e.target.value as 'voice_only' | 'text_and_voice')}
              disabled={!ttsModeEnabled}
              className="mt-1 w-4 h-4 text-pink-600 border-gray-300 focus:ring-pink-500"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Mic className="w-4 h-4 text-pink-600" />
                <span className="block text-sm font-bold text-gray-900">纯语音模式</span>
              </div>
              <span className="block text-xs text-gray-500">只发送语音消息，不发送文本。适合纯语音交流场景。</span>
            </div>
          </label>

          <label className={`flex items-start gap-4 p-4 border rounded-xl cursor-pointer transition-all ${
            ttsModeType === 'text_and_voice' ? 'border-pink-200 bg-pink-50 ring-1 ring-pink-200' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}>
            <input
              type="radio"
              name="ttsModeType"
              value="text_and_voice"
              checked={ttsModeType === 'text_and_voice'}
              onChange={(e) => setTtsModeType(e.target.value as 'voice_only' | 'text_and_voice')}
              disabled={!ttsModeEnabled}
              className="mt-1 w-4 h-4 text-pink-600 border-gray-300 focus:ring-pink-500"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Volume2 className="w-4 h-4 text-pink-600" />
                <span className="block text-sm font-bold text-gray-900">文本+语音模式</span>
              </div>
              <span className="block text-xs text-gray-500">同时发送文本和语音消息。适合需要保留文字记录的场景。</span>
            </div>
          </label>
        </div>
      </div>

      {/* 腾讯云配置卡片 */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
        <div className="flex justify-between items-center border-b border-gray-100 pb-4 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-5 bg-gray-500 rounded-full"></div>
            <h3 className="text-base font-bold text-gray-900">腾讯云 TTS 密钥</h3>
          </div>
          <button
            onClick={handleSaveTTS}
            disabled={saving || !tencentSecretId}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-colors shadow-sm"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存密钥'}
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              SecretId <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={tencentSecretId}
              onChange={(e) => setTencentSecretId(e.target.value)}
              placeholder="AKID..."
              className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-gray-500 focus:ring-gray-500 sm:text-sm font-mono py-2.5 px-3"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              SecretKey 
              {ttsConfigLoaded && !showTencentKey && (
                <span className="text-green-600 text-xs ml-2 font-bold bg-green-50 px-2 py-0.5 rounded border border-green-100">已配置</span>
              )}
            </label>
            <div className="relative">
              <input
                type={showTencentKey ? "text" : "password"}
                value={tencentSecretKey}
                onChange={(e) => setTencentSecretKey(e.target.value)}
                placeholder={ttsConfigLoaded ? "留空则不更新..." : "输入 SecretKey..."}
                className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-gray-500 focus:ring-gray-500 sm:text-sm font-mono pr-10 py-2.5 px-3"
              />
              <button
                type="button"
                onClick={() => setShowTencentKey(!showTencentKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
              >
                {showTencentKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="bg-gray-50 px-5 py-4 rounded-xl text-xs text-gray-600 leading-relaxed border border-gray-100 flex items-start gap-3">
            <div className="p-1.5 bg-blue-100 text-blue-600 rounded-full mt-0.5">
              <span className="block w-1.5 h-1.5 bg-blue-600 rounded-full"></span>
            </div>
            <div>
              <p className="font-medium text-gray-900 mb-1">配置说明</p>
              <p>请确保腾讯云账号已开通 TTS (语音合成) 服务并拥有访问权限。</p>
              <a 
                href="https://console.cloud.tencent.com/cam/capi" 
                target="_blank" 
                rel="noreferrer"
                className="text-blue-600 hover:text-blue-700 hover:underline mt-2 inline-flex items-center gap-1 font-medium"
              >
                前往控制台获取密钥 &rarr;
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
