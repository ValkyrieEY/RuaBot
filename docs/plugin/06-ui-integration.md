# Frontend UI Integration Guide

{ [Chinese](06-ui-integration_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Intermediate

## Overview

XQNEXT plugins can automatically generate frontend configuration interfaces through `config_schema`. Users can modify plugin configurations in the Web UI without manually editing files.

---

## Config Schema

### Basic Structure

Define `config_schema` in `plugin.json`:

```json
{
  "name": "my_plugin",
  "config_schema": {
    "field_name": {
      "type": "field_type",
      "default": "default_value",
      "description": "Field Description",
      "label": "Display Label",
      "required": true/false
    }
  }
}
```

---

## Supported Field Types

### 1. string

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API Key",
    "label": "API Key",
    "required": true
  }
}
```

**Frontend Display:** Text Input Box

---

### 2. number

```json
{
  "timeout": {
    "type": "number",
    "default": 30,
    "description": "Timeout (seconds)",
    "min": 1,
    "max": 300
  }
}
```

**Frontend Display:** Number Input Box

**Optional Properties:**
- `min`: Minimum value
- `max`: Maximum value

---

### 3. boolean

```json
{
  "enabled": {
    "type": "boolean",
    "default": true,
    "description": "Enable Plugin"
  }
}
```

**Frontend Display:** Toggle Switch

---

### 4. array

```json
{
  "admins": {
    "type": "array",
    "default": [],
    "description": "Admin QQ ID List (One per line)"
  }
}
```

**Frontend Display:** Text Area (Multi-line input)

**User Input Format:**
```
123456
789012
345678
```

Or

```
123456, 789012, 345678
```

---

### 5. select

```json
{
  "theme": {
    "type": "select",
    "default": "light",
    "description": "Theme",
    "options": [
      {"value": "light", "label": "Light"},
      {"value": "dark", "label": "Dark"},
      {"value": "auto", "label": "Auto"}
    ]
  }
}
```

**Frontend Display:** Dropdown Select Box

---

### 6. textarea

```json
{
  "custom_reply": {
    "type": "textarea",
    "default": "",
    "description": "Custom Reply Content",
    "rows": 5
  }
}
```

**Frontend Display:** Multi-line Text Box

**Optional Properties:**
- `rows`: Number of rows (Default 3)

---

## Complete Example

```json
{
  "name": "weather_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "Weather Plugin",
  "config_schema": {
    "api_key": {
      "type": "string",
      "default": "",
      "description": "Weather API Key (Apply at https://example.com)",
      "label": "API Key",
      "required": true
    },
    "default_city": {
      "type": "string",
      "default": "Beijing",
      "description": "Default Query City",
      "label": "Default City"
    },
    "cache_time": {
      "type": "number",
      "default": 3600,
      "description": "Cache Time (seconds)",
      "label": "Cache Duration",
      "min": 60,
      "max": 86400
    },
    "enabled": {
      "type": "boolean",
      "default": true,
      "description": "Enable Plugin",
      "label": "Enabled"
    },
    "admins": {
      "type": "array",
      "default": [],
      "description": "Admin QQ ID List (One per line)",
      "label": "Admin List"
    },
    "unit": {
      "type": "select",
      "default": "metric",
      "description": "Temperature Unit",
      "label": "Unit",
      "options": [
        {"value": "metric", "label": "Celsius (°C)"},
        {"value": "imperial", "label": "Fahrenheit (°F)"}
      ]
    },
    "welcome_message": {
      "type": "textarea",
      "default": "Welcome to Weather Plugin!\nSend /weather [city] to query weather",
      "description": "Welcome Message",
      "label": "Welcome Message",
      "rows": 3
    }
  },
  "default_config": {
    "api_key": "",
    "default_city": "Beijing",
    "cache_time": 3600,
    "enabled": true,
    "admins": [],
    "unit": "metric",
    "welcome_message": "Welcome to Weather Plugin!\nSend /weather [city] to query weather"
  }
}
```

---

## Frontend Display Effect

When users click the "Config" button on the plugin management page in Web UI, they will see:

```
┌─────────────────────────────────────┐
│ weather_plugin Config               │
├─────────────────────────────────────┤
│ API Key *                           │
│ [____________________________]      │
│ Weather API Key (Apply at...)       │
│                                     │
│ Default City                        │
│ [Beijing__________________]         │
│ Default Query City                  │
│                                     │
│ Cache Duration                      │
│ [3600] ◀──────▶ (60 ~ 86400)      │
│ Cache Time (seconds)                │
│                                     │
│ Enabled                             │
│ [ON  OFF]                           │
│ Enable Plugin                       │
│                                     │
│ Admin List                          │
│ [                              ]    │
│ [                              ]    │
│ [                              ]    │
│ Admin QQ ID List (One per line)     │
│                                     │
│ Unit                                │
│ [Celsius (°C) ▼]                    │
│ Temperature Unit                    │
│                                     │
│ Welcome Message                     │
│ [Welcome to Weather Plugin!      ]  │
│ [Send /weather [city] to query   ]  │
│ [                              ]    │
│ Welcome Message                     │
│                                     │
│ [Save]  [Cancel]                    │
└─────────────────────────────────────┘
```

---

## Getting Config from Frontend

### Reading User Config in Plugin

```python
class WeatherPlugin:
    def __init__(self, api, config):
        self.api = api
        # Read Config
        self.api_key = config.get('api_key', '')
        self.default_city = config.get('default_city', 'Beijing')
        self.cache_time = config.get('cache_time', 3600)
        self.enabled = config.get('enabled', True)
        self.admins = config.get('admins', [])
        self.unit = config.get('unit', 'metric')
        self.welcome_message = config.get('welcome_message', '')
        
        # Validate Required Config
        if not self.api_key:
            self.api.log("error", "API Key not set!")
```

### Runtime Config Update

```python
async def update_cache_time(self, new_time: int):
    """Update Cache Time"""
    # Modify value in memory
    self.cache_time = new_time
    
    # Save to database
    await self.api.set_config('cache_time', new_time)
    
    # Note: Config won't take effect immediately until reload
    self.api.log("info", f"Cache time updated to {new_time}s, please reload plugin to take effect")
```

---

## Advanced Tips

### 1. Password Field

Although currently there is no dedicated `password` type, you can use `string` type and prompt in the description:

```json
{
  "password": {
    "type": "string",
    "default": "",
    "description": "Password (Stored in plain text, please be careful)",
    "label": "Password"
  }
}
```

### 2. Conditional Display

Conditional display is currently not supported, but can be handled in plugin code:

```python
def __init__(self, api, config):
    self.mode = config.get('mode', 'simple')
    
    # Read different config based on mode
    if self.mode == 'advanced':
        self.advanced_option = config.get('advanced_option', '')
```

### 3. Config Grouping

Use label and description for grouping:

```json
{
  "_group_basic": {
    "type": "string",
    "default": "=== Basic Config ===",
    "description": "",
    "label": "Basic Config"
  },
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API Key"
  },
  "_group_advanced": {
    "type": "string",
    "default": "=== Advanced Config ===",
    "description": "",
    "label": "Advanced Config"
  },
  "timeout": {
    "type": "number",
    "default": 30,
    "description": "Timeout"
  }
}
```

---

## Configuration Validation

### Validating Config in Plugin

```python
class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        
        # Validate Config
        try:
            self._validate_config(config)
        except ValueError as e:
            self.api.log("error", f"Config validation failed: {e}")
            raise
        
        # Read Config
        self.api_key = config['api_key']
    
    def _validate_config(self, config: dict):
        """Validate Config"""
        # Check required fields
        if 'api_key' not in config or not config['api_key']:
            raise ValueError("API Key cannot be empty")
        
        # Check type
        if 'timeout' in config:
            if not isinstance(config['timeout'], (int, float)):
                raise ValueError("Timeout must be a number")
            if config['timeout'] < 1:
                raise ValueError("Timeout cannot be less than 1 second")
        
        # Check range
        if 'admins' in config:
            if not isinstance(config['admins'], list):
                raise ValueError("Admin list must be an array")
```

---

## Best Practices

### 1. Provide Clear Description

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "Apply API Key at https://api.example.com, free version 100 requests/day",
    "label": "API Key"
  }
}
```

### 2. Set Reasonable Default Values

```json
{
  "retry_count": {
    "type": "number",
    "default": 3,
    "description": "Retry count after failure (Suggested 3-5)",
    "min": 1,
    "max": 10
  }
}
```

### 3. Use Label to Improve Readability

```json
{
  "max_results": {
    "type": "number",
    "default": 10,
    "description": "Max results returned per query",
    "label": "Max Results"
  }
}
```

### 4. Mark Required Fields

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API Key",
    "required": true
  }
}
```

---

## FAQ

### Q: When does config modification take effect?

After saving the configuration, you need to reload the plugin to take effect. Click the "Reload" button on the plugin page.

### Q: Can I hide certain configurations?

Currently hiding configurations is not supported. If you don't want to display it on the frontend, you can define it only in `default_config` instead of `config_schema`.

### Q: Can I customize UI?

Currently customizing UI is not supported. UI is automatically generated based on `config_schema`.

### Q: How to input array type?

Users can input one value per line, or separate multiple values with comma/space:

```
123456
789012
```

Or

```
123456, 789012, 345678
```

---

**Previous**: [← Configuration & Data Management](05-config-data.md)  
**Next**: [Advanced Features →](07-advanced-features.md)

