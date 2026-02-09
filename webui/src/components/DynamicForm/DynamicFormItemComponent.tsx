import { X, Plus, Upload } from 'lucide-react'
import { FieldConfig } from './DynamicFormComponent'
import { useState } from 'react'
import { api } from '@/utils/api'

interface DynamicFormItemComponentProps {
  fieldName: string
  config: FieldConfig
  value: any
  onChange: (value: any) => void
  onFileUploaded?: (fileKey: string) => void
}

export default function DynamicFormItemComponent({
  fieldName,
  config,
  value,
  onChange,
  onFileUploaded,
}: DynamicFormItemComponentProps) {
  const [uploading, setUploading] = useState(false)

  const handleFileUpload = async (file: File): Promise<{ file_key: string; mimetype: string } | null> => {
    const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

    if (file.size > MAX_FILE_SIZE) {
      alert('文件大小不能超过 10MB')
      return null
    }

    try {
      setUploading(true)
      const response = await api.uploadPluginConfigFile(file)
      onFileUploaded?.(response.file_key)
      return { file_key: response.file_key, mimetype: file.type }
    } catch (error) {
      alert('文件上传失败: ' + (error as Error).message)
      return null
    } finally {
      setUploading(false)
    }
  }

  switch (config.type) {
    case 'string':
      return (
        <input
          type="text"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="input w-full"
          required={config.required}
        />
      )

    case 'number':
      return (
        <input
          type="number"
          value={value ?? ''}
          min={config.min}
          max={config.max}
          onChange={(e) => {
            const val = e.target.value
            if (val === '') {
              onChange(config.default ?? 0)
            } else {
              const numValue = Number(val)
              if (!isNaN(numValue)) {
                onChange(numValue)
              }
            }
          }}
          className="input w-full"
          required={config.required}
        />
      )

    case 'boolean':
      return (
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={value || false}
            onChange={(e) => onChange(e.target.checked)}
            className="rounded border-gray-300 text-primary-600"
          />
          <span className="text-sm text-gray-600">启用</span>
        </label>
      )

    case 'textarea':
      return (
        <textarea
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          rows={config.rows || 4}
          className="input w-full"
          required={config.required}
        />
      )

    case 'select':
      return (
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="input w-full"
          required={config.required}
        >
          <option value="">请选择</option>
          {config.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )

    case 'array':
      const arrayValue = Array.isArray(value) ? value : []
      return (
        <div className="space-y-2">
          {arrayValue.length === 0 ? (
            <div className="text-sm text-gray-500 py-2 border border-dashed border-gray-300 rounded p-3 text-center">
              暂无项目，点击下方"添加项"按钮添加
            </div>
          ) : (
            arrayValue.map((item: any, index: number) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  type="text"
                  value={item || ''}
                  onChange={(e) => {
                    const newArray = [...arrayValue]
                    newArray[index] = e.target.value
                    onChange(newArray)
                  }}
                  className="input flex-1"
                  placeholder={config.items?.type === 'string' ? '输入值' : '输入值'}
                />
                <button
                  type="button"
                  onClick={() => {
                    const newArray = arrayValue.filter((_: any, i: number) => i !== index)
                    onChange(newArray)
                  }}
                  className="btn btn-secondary px-3 py-1 text-sm hover:bg-red-50 hover:text-red-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))
          )}
          <button
            type="button"
            onClick={() => {
              onChange([...arrayValue, ''])
            }}
            className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
          >
            <Plus className="h-4 w-4" />
            添加项
          </button>
        </div>
      )

    case 'file':
      const fileValue = value as { file_key?: string; mimetype?: string } | null
      return (
        <div className="space-y-2">
          {fileValue?.file_key ? (
            <div className="flex items-center justify-between p-3 border rounded bg-gray-50">
              <div className="flex-1 min-w-0 overflow-hidden">
                <div className="text-sm font-medium truncate" title={fileValue.file_key}>
                  {fileValue.file_key}
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {fileValue.mimetype}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onChange(null)}
                className="btn btn-secondary px-2 py-1 text-sm hover:bg-red-50 hover:text-red-600 ml-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="relative">
              <input
                type="file"
                accept={config.accept}
                disabled={uploading}
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (file) {
                    const fileConfig = await handleFileUpload(file)
                    if (fileConfig) {
                      onChange(fileConfig)
                    }
                  }
                  e.target.value = ''
                }}
                className="hidden"
                id={`file-input-${fieldName}`}
              />
              <button
                type="button"
                disabled={uploading}
                onClick={() =>
                  document.getElementById(`file-input-${fieldName}`)?.click()
                }
                className="btn btn-primary text-sm flex items-center gap-2"
              >
                <Upload className="w-4 h-4" />
                {uploading ? '上传中...' : '选择文件'}
              </button>
            </div>
          )}
        </div>
      )

    case 'file_array':
      const fileArrayValue = Array.isArray(value) ? value : []
      return (
        <div className="space-y-2">
          {fileArrayValue.map((fileConfig: { file_key?: string; mimetype?: string }, index: number) => (
            <div key={index} className="flex items-center justify-between p-3 border rounded bg-gray-50">
              <div className="flex-1 min-w-0 overflow-hidden">
                <div className="text-sm font-medium truncate" title={fileConfig.file_key}>
                  {fileConfig.file_key}
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {fileConfig.mimetype}
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  const newArray = fileArrayValue.filter((_: any, i: number) => i !== index)
                  onChange(newArray)
                }}
                className="btn btn-secondary px-2 py-1 text-sm hover:bg-red-50 hover:text-red-600 ml-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="relative">
            <input
              type="file"
              accept={config.accept}
              disabled={uploading}
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (file) {
                  const fileConfig = await handleFileUpload(file)
                  if (fileConfig) {
                    onChange([...fileArrayValue, fileConfig])
                  }
                }
                e.target.value = ''
              }}
              className="hidden"
              id={`file-array-input-${fieldName}`}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() =>
                document.getElementById(`file-array-input-${fieldName}`)?.click()
              }
              className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
            >
              <Plus className="w-4 h-4" />
              {uploading ? '上传中...' : '添加文件'}
            </button>
          </div>
        </div>
      )

    default:
      // Fallback: 未知类型使用文本输入框
      return (
        <input
          type="text"
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="input w-full"
          placeholder={`类型: ${config.type || 'unknown'}`}
        />
      )
  }
}

