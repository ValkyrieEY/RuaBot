export type FieldType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'select'
  | 'textarea'
  | 'array'
  | 'file'
  | 'file_array'
  | 'group'
  | 'object_array'
  | 'table'

export interface FieldOption {
  value: string
  label: string
}

export interface FieldConfig {
  type: FieldType
  default?: any
  description?: string
  label?: string
  required?: boolean
  options?: FieldOption[]
  rows?: number
  min?: number
  max?: number
  items?: { type?: string }
  accept?: string
  fields?: ConfigSchema
  addLabel?: string
}

export interface ConfigSchema {
  [fieldName: string]: FieldConfig
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function resolveFieldValue(config: FieldConfig, value: any): any {
  if (value !== undefined) {
    if (config.type === 'group') {
      return buildDefaultValues(config.fields || {}, isRecord(value) ? value : {})
    }
    if (config.type === 'object_array' || config.type === 'table') {
      const rows = Array.isArray(value) ? value : []
      return rows.map((row) => buildDefaultValues(config.fields || {}, isRecord(row) ? row : {}))
    }
    if (config.type === 'array' || config.type === 'file_array') {
      return Array.isArray(value) ? value : []
    }
    return value
  }

  if (config.default !== undefined) {
    return resolveFieldValue(
      { ...config, default: undefined },
      config.default,
    )
  }

  switch (config.type) {
    case 'number':
      return 0
    case 'boolean':
      return false
    case 'array':
    case 'file_array':
    case 'object_array':
    case 'table':
      return []
    case 'group':
      return buildDefaultValues(config.fields || {}, {})
    case 'file':
      return null
    default:
      return ''
  }
}

export function buildDefaultValues(
  schema: ConfigSchema,
  initialValues: Record<string, any> = {},
): Record<string, any> {
  return Object.entries(schema).reduce((acc, [key, field]) => {
    acc[key] = resolveFieldValue(field, initialValues[key])
    return acc
  }, {} as Record<string, any>)
}
