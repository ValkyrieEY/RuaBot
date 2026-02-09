import { useState, useEffect, useRef } from 'react'
import DynamicFormItemComponent from './DynamicFormItemComponent'

// 支持的类型
export type FieldType = 
  | 'string' 
  | 'number' 
  | 'boolean' 
  | 'select' 
  | 'textarea' 
  | 'array'
  | 'file'
  | 'file_array'

// 字段配置接口
export interface FieldConfig {
  type: FieldType
  default?: any
  description?: string
  label?: string
  required?: boolean
  options?: Array<{ value: string; label: string }>
  rows?: number // for textarea
  min?: number // for number
  max?: number // for number
  items?: { type?: string } // for array
  accept?: string // for file
}

// Schema 格式
export interface ConfigSchema {
  [fieldName: string]: FieldConfig
}

interface DynamicFormComponentProps {
  schema: ConfigSchema
  initialValues?: Record<string, any>
  onSubmit?: (values: Record<string, any>) => void
  onFileUploaded?: (fileKey: string) => void
}

export default function DynamicFormComponent({
  schema,
  initialValues = {},
  onSubmit,
  onFileUploaded,
}: DynamicFormComponentProps) {
  const previousInitialValues = useRef<Record<string, any> | null>(null)

  // 表单值类型
  type FormValues = Record<string, any>

  // 合并初始值和默认值
  const mergeValues = (): FormValues => {
    return Object.entries(schema).reduce(
      (acc, [key, field]) => {
        if (key in initialValues && initialValues[key] !== undefined) {
          acc[key] = initialValues[key]
        } else if (field.default !== undefined) {
          acc[key] = field.default
        } else {
          // 类型默认值
          switch (field.type) {
            case 'number':
              acc[key] = 0
              break
            case 'boolean':
              acc[key] = false
              break
            case 'array':
            case 'file_array':
              acc[key] = []
              break
            default:
              acc[key] = ''
          }
        }
        return acc
      },
      {} as FormValues,
    )
  }

  // 表单值状态
  const [formValues, setFormValues] = useState<FormValues>(() => mergeValues())

  // 监听 initialValues 变化
  useEffect(() => {
    const hasRealChange =
      previousInitialValues.current === null ||
      JSON.stringify(previousInitialValues.current) !== JSON.stringify(initialValues)

    if (hasRealChange) {
      const mergedValues = mergeValues()
      setFormValues(mergedValues)
      previousInitialValues.current = initialValues
    }
  }, [initialValues, schema])

  // 更新表单值
  const updateFieldValue = (key: string, value: any) => {
    const newValues = { ...formValues, [key]: value }
    setFormValues(newValues)
    onSubmit?.(newValues)
  }

  return (
    <div className="space-y-4">
      {Object.entries(schema).map(([key, field]) => (
        <div key={key} className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            {field.label || key}
            {field.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          {field.description && (
            <p className="text-xs text-gray-500 mb-2">{field.description}</p>
          )}
          <DynamicFormItemComponent
            fieldName={key}
            config={field}
            value={formValues[key]}
            onChange={(value) => updateFieldValue(key, value)}
            onFileUploaded={onFileUploaded}
          />
        </div>
      ))}
    </div>
  )
}

