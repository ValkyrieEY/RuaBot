import { Plus, Trash2, Upload, X } from 'lucide-react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/utils/api'
import { useToast } from '@/components/Toast'
import { buildDefaultValues, type ConfigSchema, type FieldConfig } from './types'

interface DynamicFormFieldComponentProps {
  pluginName: string
  fieldName: string
  config: FieldConfig
  value: any
  onChange: (value: any) => void
  onFileUploaded?: (fileKey: string) => void
  compact?: boolean
}

function FieldWrapper({
  fieldName,
  config,
  compact = false,
  children,
}: {
  fieldName: string
  config: FieldConfig
  compact?: boolean
  children: ReactNode
}) {
  if (compact) {
    return <>{children}</>
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        {config.label || fieldName}
        {config.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {config.description && (
        <p className="text-xs text-gray-500 mb-2">{config.description}</p>
      )}
      {children}
    </div>
  )
}

export default function DynamicFormFieldComponent({
  pluginName,
  fieldName,
  config,
  value,
  onChange,
  onFileUploaded,
  compact = false,
}: DynamicFormFieldComponentProps) {
  const { t } = useTranslation()
  const toast = useToast()
  const [uploading, setUploading] = useState(false)

  const nestedSchema: ConfigSchema = config.fields || {}

  const handleFileUpload = async (
    file: File,
  ): Promise<{ file_key: string; mimetype: string } | null> => {
    const MAX_FILE_SIZE = 10 * 1024 * 1024

    if (file.size > MAX_FILE_SIZE) {
      toast.warning(t('dynamicForm.fileTooLarge'))
      return null
    }

    try {
      setUploading(true)
      const response = await api.uploadPluginConfigFile(pluginName, file)
      onFileUploaded?.(response.file_key)
      return { file_key: response.file_key, mimetype: file.type }
    } catch (error) {
      toast.error(t('dynamicForm.uploadError', { message: (error as Error).message }))
      return null
    } finally {
      setUploading(false)
    }
  }

  const renderNestedFields = (
    schema: ConfigSchema,
    nestedValue: Record<string, any>,
    onNestedChange: (nextValue: Record<string, any>) => void,
    nestedCompact = false,
  ) => (
    <div className={nestedCompact ? 'space-y-0' : 'space-y-4'}>
      {Object.entries(schema).map(([nestedKey, nestedField]) => (
        <DynamicFormFieldComponent
          key={nestedKey}
          pluginName={pluginName}
          fieldName={nestedKey}
          config={nestedField}
          value={nestedValue[nestedKey]}
          onChange={(next) => onNestedChange({ ...nestedValue, [nestedKey]: next })}
          onFileUploaded={onFileUploaded}
          compact={nestedCompact}
        />
      ))}
    </div>
  )

  const renderPrimitiveControl = () => {
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
                return
              }
              const numValue = Number(val)
              if (!Number.isNaN(numValue)) {
                onChange(numValue)
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
            <span className="text-sm text-gray-600">{t('dynamicForm.booleanHint')}</span>
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
            <option value="">{t('dynamicForm.selectPlaceholder')}</option>
            {config.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )

      case 'array': {
        const arrayValue = Array.isArray(value) ? value : []
        return (
          <div className="space-y-2">
            {arrayValue.length === 0 ? (
              <div className="text-sm text-gray-500 py-2 border border-dashed border-gray-300 rounded p-3 text-center">
                {t('dynamicForm.emptyArray')}
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
                  />
                  <button
                    type="button"
                    onClick={() => onChange(arrayValue.filter((_: any, i: number) => i !== index))}
                    className="btn btn-secondary px-3 py-1 text-sm hover:bg-red-50 hover:text-red-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))
            )}
            <button
              type="button"
              onClick={() => onChange([...arrayValue, ''])}
              className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
            >
              <Plus className="h-4 w-4" />
              {t('dynamicForm.addItem')}
            </button>
          </div>
        )
      }

      case 'file': {
        const fileValue = value as { file_key?: string; mimetype?: string } | null
        return (
          <div className="space-y-2">
            {fileValue?.file_key ? (
              <div className="flex items-center justify-between p-3 border rounded bg-gray-50">
                <div className="flex-1 min-w-0 overflow-hidden">
                  <div className="text-sm font-medium truncate" title={fileValue.file_key}>
                    {fileValue.file_key}
                  </div>
                  <div className="text-xs text-gray-500 truncate">{fileValue.mimetype}</div>
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
                  onClick={() => document.getElementById(`file-input-${fieldName}`)?.click()}
                  className="btn btn-primary text-sm flex items-center gap-2"
                >
                  <Upload className="w-4 h-4" />
                  {uploading ? t('dynamicForm.uploading') : t('dynamicForm.uploadFile')}
                </button>
              </div>
            )}
          </div>
        )
      }

      case 'file_array': {
        const fileArrayValue = Array.isArray(value) ? value : []
        return (
          <div className="space-y-2">
            {fileArrayValue.map((fileConfig: { file_key?: string; mimetype?: string }, index: number) => (
              <div key={index} className="flex items-center justify-between p-3 border rounded bg-gray-50">
                <div className="flex-1 min-w-0 overflow-hidden">
                  <div className="text-sm font-medium truncate" title={fileConfig.file_key}>
                    {fileConfig.file_key}
                  </div>
                  <div className="text-xs text-gray-500 truncate">{fileConfig.mimetype}</div>
                </div>
                <button
                  type="button"
                  onClick={() => onChange(fileArrayValue.filter((_: any, i: number) => i !== index))}
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
                onClick={() => document.getElementById(`file-array-input-${fieldName}`)?.click()}
                className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
              >
                <Plus className="w-4 h-4" />
                {uploading ? t('dynamicForm.uploading') : t('dynamicForm.addFile')}
              </button>
            </div>
          </div>
        )
      }

      default:
        return (
          <input
            type="text"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            className="input w-full"
            placeholder={t('dynamicForm.unknownField', {
              type: config.type || 'unknown',
            })}
          />
        )
    }
  }

  const renderControl = () => {
    if (config.type === 'group') {
      const groupValue =
        value && typeof value === 'object' && !Array.isArray(value)
          ? value
          : buildDefaultValues(nestedSchema, {})

      return (
        <div className="rounded-lg border border-gray-200 bg-gray-50/60 p-4">
          {renderNestedFields(nestedSchema, groupValue, onChange)}
        </div>
      )
    }

    if (config.type === 'object_array') {
      const rows = Array.isArray(value) ? value : []
      return (
        <div className="space-y-3">
          {rows.length === 0 ? (
            <div className="text-sm text-gray-500 py-3 border border-dashed border-gray-300 rounded p-3 text-center">
              {t('dynamicForm.emptyObjectArray')}
            </div>
          ) : (
            rows.map((row, index) => {
              const rowValue = buildDefaultValues(nestedSchema, row || {})
              return (
                <div key={index} className="rounded-lg border border-gray-200 p-4 space-y-3 bg-white">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">
                      {t('dynamicForm.rowLabel', { index: index + 1 })}
                    </span>
                    <button
                      type="button"
                      onClick={() => onChange(rows.filter((_: any, i: number) => i !== index))}
                      className="btn btn-secondary px-2 py-1 text-sm hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  {renderNestedFields(nestedSchema, rowValue, (nextRow) => {
                    const nextRows = [...rows]
                    nextRows[index] = nextRow
                    onChange(nextRows)
                  })}
                </div>
              )
            })
          )}
          <button
            type="button"
            onClick={() => onChange([...rows, buildDefaultValues(nestedSchema, {})])}
            className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
          >
            <Plus className="h-4 w-4" />
            {config.addLabel || t('dynamicForm.addRow')}
          </button>
        </div>
      )
    }

    if (config.type === 'table') {
      const rows = Array.isArray(value) ? value : []
      const columns = Object.entries(nestedSchema)
      return (
        <div className="space-y-3">
          {rows.length === 0 ? (
            <div className="text-sm text-gray-500 py-3 border border-dashed border-gray-300 rounded p-3 text-center">
              {t('dynamicForm.emptyTable')}
            </div>
          ) : (
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {columns.map(([columnKey, columnConfig]) => (
                      <th
                        key={columnKey}
                        className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wide"
                      >
                        {columnConfig.label || columnKey}
                      </th>
                    ))}
                    <th className="px-3 py-2 w-16" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {rows.map((row, index) => {
                    const rowValue = buildDefaultValues(nestedSchema, row || {})
                    return (
                      <tr key={index}>
                        {columns.map(([columnKey, columnConfig]) => (
                          <td key={columnKey} className="px-3 py-2 align-top min-w-[180px]">
                            <DynamicFormFieldComponent
                              pluginName={pluginName}
                              fieldName={columnKey}
                              config={columnConfig}
                              value={rowValue[columnKey]}
                              onChange={(nextCellValue) => {
                                const nextRows = [...rows]
                                nextRows[index] = { ...rowValue, [columnKey]: nextCellValue }
                                onChange(nextRows)
                              }}
                              onFileUploaded={onFileUploaded}
                              compact
                            />
                          </td>
                        ))}
                        <td className="px-3 py-2 align-top">
                          <button
                            type="button"
                            onClick={() => onChange(rows.filter((_: any, i: number) => i !== index))}
                            className="btn btn-secondary px-2 py-1 text-sm hover:bg-red-50 hover:text-red-600"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <button
            type="button"
            onClick={() => onChange([...rows, buildDefaultValues(nestedSchema, {})])}
            className="btn btn-primary text-sm flex items-center gap-2 w-full justify-center py-2"
          >
            <Plus className="h-4 w-4" />
            {config.addLabel || t('dynamicForm.addRow')}
          </button>
        </div>
      )
    }

    return renderPrimitiveControl()
  }

  return (
    <FieldWrapper fieldName={fieldName} config={config} compact={compact}>
      {renderControl()}
    </FieldWrapper>
  )
}
