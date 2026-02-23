import { GroupConfigProps } from './types'

export default function GroupConfig({
  groupConfigs,
  models,
  presets,
  selectedGroups,
  saving,
  handleBatchUpdate,
  toggleGroupSelection,
  toggleAllGroups
}: GroupConfigProps) {
  return (
    <div className="space-y-6">
      {/* 头部说明 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-2">
        <div>
          <h2 className="text-base font-semibold text-gray-900">群组管理</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            共 {groupConfigs.length} 个群组，已选 {selectedGroups.size} 个
          </p>
        </div>
      </div>

      {/* 批量操作工具栏 */}
      <div className="flex flex-col sm:flex-row gap-3 bg-gray-50 p-3 rounded-lg border border-gray-200">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={selectedGroups.size === groupConfigs.length && groupConfigs.length > 0}
              onChange={toggleAllGroups}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 border-gray-300"
            />
            <span className="text-sm font-medium text-gray-700">全选</span>
          </label>
          <div className="h-4 w-px bg-gray-300 hidden sm:block"></div>
        </div>

        <div className="flex flex-wrap gap-2 flex-1">
          <button
            onClick={() => handleBatchUpdate(true)}
            disabled={selectedGroups.size === 0 || saving}
            className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-medium rounded hover:bg-gray-50 hover:text-green-700 disabled:opacity-50 transition-colors"
          >
            批量开启
          </button>
          <button
            onClick={() => handleBatchUpdate(false)}
            disabled={selectedGroups.size === 0 || saving}
            className="px-3 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs font-medium rounded hover:bg-gray-50 hover:text-red-700 disabled:opacity-50 transition-colors"
          >
            批量关闭
          </button>
          
          <select
            onChange={(e) => {
              if (e.target.value) {
                handleBatchUpdate(undefined, e.target.value, undefined)
                e.target.value = ''
              }
            }}
            disabled={selectedGroups.size === 0 || saving}
            className="px-2 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs rounded hover:border-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 min-w-[120px]"
          >
            <option value="">批量设置模型...</option>
            {models.map((model) => (
              <option key={model.uuid} value={model.uuid}>
                {model.name}
              </option>
            ))}
          </select>

          <select
            onChange={(e) => {
              if (e.target.value) {
                handleBatchUpdate(undefined, undefined, e.target.value)
                e.target.value = ''
              }
            }}
            disabled={selectedGroups.size === 0 || saving}
            className="px-2 py-1.5 bg-white border border-gray-300 text-gray-700 text-xs rounded hover:border-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 min-w-[120px]"
          >
            <option value="">批量设置预设...</option>
            {presets.map((preset) => (
              <option key={preset.uuid} value={preset.uuid}>
                {preset.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 群组列表 - 移除外层圆角和阴影，更贴合移动端 */}
      <div className="overflow-x-auto -mx-4 sm:mx-0">
        <div className="inline-block min-w-full align-middle">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="w-12 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider pl-6 sm:pl-4">
                  选
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  群组
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  状态
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden md:table-cell">
                  模型
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                  预设
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider pr-6 sm:pr-4">
                  统计
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {groupConfigs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-500">
                    暂无群组数据，请确保已连接 OneBot 适配器
                  </td>
                </tr>
              ) : (
                groupConfigs.map((config) => (
                  <tr 
                    key={config.target_id} 
                    className={`hover:bg-gray-50 transition-colors ${config.is_left ? 'opacity-60 bg-gray-50' : ''}`}
                  >
                    <td className="px-4 py-3 whitespace-nowrap pl-6 sm:pl-4">
                      <input
                        type="checkbox"
                        checked={selectedGroups.has(config.target_id)}
                        onChange={() => toggleGroupSelection(config.target_id)}
                        disabled={config.is_left}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 border-gray-300"
                      />
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="h-9 w-9 flex-shrink-0">
                          <img
                            className="h-9 w-9 rounded-full bg-gray-100 object-cover"
                            src={config.avatar || `http://p.qlogo.cn/gh/${config.target_id}/${config.target_id}/640/`}
                            alt=""
                            onError={(e) => {
                              e.currentTarget.src = `data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0yMCAxMkMxNS41ODIyIDEyIDEyIDE1LjU4MjIgMTIgMjBDMTIgMjQuNDE3OCAxNS41ODIyIDI4IDIwIDI4QzI0LjQxNzggMjggMjggMjQuNDE3OCAyOCAyMEMyOCAxNS41ODIyIDI0LjQxNzggMTIgMjAgMTJaIiBmaWxsPSIjOUI5QkE1Ii8+Cjwvc3ZnPg==`
                            }}
                          />
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-gray-900 max-w-[120px] sm:max-w-[200px] truncate">
                            {config.group_name || `群 ${config.target_id}`}
                          </div>
                          <div className="text-xs text-gray-500">{config.target_id}</div>
                          {config.is_left && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-800 mt-0.5">
                              已退出
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {config.enabled ? (
                        <div className="flex items-center">
                          <div className="h-2 w-2 rounded-full bg-green-500 mr-2"></div>
                          <span className="text-xs text-gray-700">启用</span>
                        </div>
                      ) : (
                        <div className="flex items-center">
                          <div className="h-2 w-2 rounded-full bg-gray-300 mr-2"></div>
                          <span className="text-xs text-gray-500">禁用</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500 hidden md:table-cell">
                      {models.find(m => m.uuid === config.model_uuid)?.name || '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500 hidden lg:table-cell">
                      {presets.find(p => p.uuid === config.preset_uuid)?.name || '-'}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500 pr-6 sm:pr-4 font-mono">
                      {config.message_count}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
