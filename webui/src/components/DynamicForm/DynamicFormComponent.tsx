import { useEffect, useRef, useState } from 'react'
import DynamicFormFieldComponent from './DynamicFormFieldComponent'
import { buildDefaultValues, type ConfigSchema } from './types'

interface DynamicFormComponentProps {
  pluginName: string
  schema: ConfigSchema
  initialValues?: Record<string, any>
  onSubmit?: (values: Record<string, any>) => void
  onFileUploaded?: (fileKey: string) => void
}

export type { ConfigSchema, FieldConfig, FieldType } from './types'

export default function DynamicFormComponent({
  pluginName,
  schema,
  initialValues = {},
  onSubmit,
  onFileUploaded,
}: DynamicFormComponentProps) {
  const previousInitialValues = useRef<Record<string, any> | null>(null)
  const [formValues, setFormValues] = useState<Record<string, any>>(() =>
    buildDefaultValues(schema, initialValues),
  )

  useEffect(() => {
    const hasRealChange =
      previousInitialValues.current === null ||
      JSON.stringify(previousInitialValues.current) !== JSON.stringify(initialValues)

    if (hasRealChange) {
      const mergedValues = buildDefaultValues(schema, initialValues)
      setFormValues(mergedValues)
      previousInitialValues.current = initialValues
    }
  }, [initialValues, schema])

  const updateFieldValue = (key: string, value: any) => {
    const newValues = { ...formValues, [key]: value }
    setFormValues(newValues)
    onSubmit?.(newValues)
  }

  return (
    <div className="space-y-4">
      {Object.entries(schema).map(([key, field]) => (
        <DynamicFormFieldComponent
          key={key}
          pluginName={pluginName}
          fieldName={key}
          config={field}
          value={formValues[key]}
          onChange={(value) => updateFieldValue(key, value)}
          onFileUploaded={onFileUploaded}
        />
      ))}
    </div>
  )
}
