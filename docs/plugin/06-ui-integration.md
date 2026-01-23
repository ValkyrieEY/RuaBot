# 前端 UI 集成指南

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 中级

## 概述

XQNEXT 插件可以通过 `config_schema` 自动生成前端配置界面，用户可以在 Web UI 中修改插件配置，无需手动编辑文件。

---

## 配置Schema

### 基本结构

在 `plugin.json` 中定义 `config_schema`：

```json
{
  "name": "my_plugin",
  "config_schema": {
    "字段名": {
      "type": "字段类型",
      "default": "默认值",
      "description": "字段描述",
      "label": "显示标签",
      "required": true/false
    }
  }
}
```

---

## 支持的字段类型

### 1. string（字符串）

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API 密钥",
    "label": "API Key",
    "required": true
  }
}
```

**前端显示：** 文本输入框

---

### 2. number（数字）

```json
{
  "timeout": {
    "type": "number",
    "default": 30,
    "description": "超时时间（秒）",
    "min": 1,
    "max": 300
  }
}
```

**前端显示：** 数字输入框

**可选属性：**
- `min`: 最小值
- `max`: 最大值

---

### 3. boolean（布尔值）

```json
{
  "enabled": {
    "type": "boolean",
    "default": true,
    "description": "是否启用插件"
  }
}
```

**前端显示：** 开关按钮

---

### 4. array（数组）

```json
{
  "admins": {
    "type": "array",
    "default": [],
    "description": "管理员QQ号列表（每行一个）"
  }
}
```

**前端显示：** 文本域（多行输入）

**用户输入格式：**
```
123456
789012
345678
```

或

```
123456, 789012, 345678
```

---

### 5. select（下拉选择）

```json
{
  "theme": {
    "type": "select",
    "default": "light",
    "description": "主题",
    "options": [
      {"value": "light", "label": "亮色"},
      {"value": "dark", "label": "暗色"},
      {"value": "auto", "label": "自动"}
    ]
  }
}
```

**前端显示：** 下拉选择框

---

### 6. textarea（多行文本）

```json
{
  "custom_reply": {
    "type": "textarea",
    "default": "",
    "description": "自定义回复内容",
    "rows": 5
  }
}
```

**前端显示：** 多行文本框

**可选属性：**
- `rows`: 行数（默认3）

---

## 完整示例

```json
{
  "name": "weather_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "天气查询插件",
  "config_schema": {
    "api_key": {
      "type": "string",
      "default": "",
      "description": "天气API密钥（在 https://example.com 申请）",
      "label": "API 密钥",
      "required": true
    },
    "default_city": {
      "type": "string",
      "default": "北京",
      "description": "默认查询城市",
      "label": "默认城市"
    },
    "cache_time": {
      "type": "number",
      "default": 3600,
      "description": "缓存时间（秒）",
      "label": "缓存时长",
      "min": 60,
      "max": 86400
    },
    "enabled": {
      "type": "boolean",
      "default": true,
      "description": "是否启用插件",
      "label": "启用"
    },
    "admins": {
      "type": "array",
      "default": [],
      "description": "管理员QQ号列表（每行一个）",
      "label": "管理员列表"
    },
    "unit": {
      "type": "select",
      "default": "metric",
      "description": "温度单位",
      "label": "单位",
      "options": [
        {"value": "metric", "label": "摄氏度 (°C)"},
        {"value": "imperial", "label": "华氏度 (°F)"}
      ]
    },
    "welcome_message": {
      "type": "textarea",
      "default": "欢迎使用天气查询插件！\n发送 /天气 [城市名] 查询天气",
      "description": "欢迎消息",
      "label": "欢迎消息",
      "rows": 3
    }
  },
  "default_config": {
    "api_key": "",
    "default_city": "北京",
    "cache_time": 3600,
    "enabled": true,
    "admins": [],
    "unit": "metric",
    "welcome_message": "欢迎使用天气查询插件！\n发送 /天气 [城市名] 查询天气"
  }
}
```

---

## 前端显示效果

用户在 Web UI 的插件管理页面中，点击"配置"按钮后会看到：

```
┌─────────────────────────────────────┐
│ weather_plugin 配置                 │
├─────────────────────────────────────┤
│ API 密钥 *                          │
│ [____________________________]      │
│ 天气API密钥（在 https://... 申请）  │
│                                     │
│ 默认城市                            │
│ [北京_____________________]        │
│ 默认查询城市                        │
│                                     │
│ 缓存时长                            │
│ [3600] ◀──────▶ (60 ~ 86400)      │
│ 缓存时间（秒）                      │
│                                     │
│ 启用                                │
│ [ON  OFF]                           │
│ 是否启用插件                        │
│                                     │
│ 管理员列表                          │
│ [                              ]    │
│ [                              ]    │
│ [                              ]    │
│ 管理员QQ号列表（每行一个）          │
│                                     │
│ 单位                                │
│ [摄氏度 (°C) ▼]                    │
│ 温度单位                            │
│                                     │
│ 欢迎消息                            │
│ [欢迎使用天气查询插件！        ]    │
│ [发送 /天气 [城市名] 查询天气  ]    │
│ [                              ]    │
│ 欢迎消息                            │
│                                     │
│ [保存]  [取消]                      │
└─────────────────────────────────────┘
```

---

## 从前端获取配置

### 在插件中读取用户配置

```python
class WeatherPlugin:
    def __init__(self, api, config):
        self.api = api
        # 读取配置
        self.api_key = config.get('api_key', '')
        self.default_city = config.get('default_city', '北京')
        self.cache_time = config.get('cache_time', 3600)
        self.enabled = config.get('enabled', True)
        self.admins = config.get('admins', [])
        self.unit = config.get('unit', 'metric')
        self.welcome_message = config.get('welcome_message', '')
        
        # 验证必需配置
        if not self.api_key:
            self.api.log("error", "API密钥未设置！")
```

### 运行时更新配置

```python
async def update_cache_time(self, new_time: int):
    """更新缓存时间"""
    # 修改内存中的值
    self.cache_time = new_time
    
    # 保存到数据库
    await self.api.set_config('cache_time', new_time)
    
    # 注意：配置不会立即生效，需要重载插件
    self.api.log("info", f"缓存时间已更新为 {new_time} 秒，请重载插件生效")
```

---

## 高级技巧

### 1. 密码字段

虽然目前没有专门的 `password` 类型，但可以使用 `string` 类型并在描述中提示：

```json
{
  "password": {
    "type": "string",
    "default": "",
    "description": "密码（将以明文存储，请注意安全）",
    "label": "密码"
  }
}
```

### 2. 条件显示

目前不支持条件显示，但可以在插件代码中处理：

```python
def __init__(self, api, config):
    self.mode = config.get('mode', 'simple')
    
    # 根据模式读取不同的配置
    if self.mode == 'advanced':
        self.advanced_option = config.get('advanced_option', '')
```

### 3. 配置组

使用 label 和 description 进行分组：

```json
{
  "_group_basic": {
    "type": "string",
    "default": "=== 基础配置 ===",
    "description": "",
    "label": "基础配置"
  },
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API密钥"
  },
  "_group_advanced": {
    "type": "string",
    "default": "=== 高级配置 ===",
    "description": "",
    "label": "高级配置"
  },
  "timeout": {
    "type": "number",
    "default": 30,
    "description": "超时时间"
  }
}
```

---

## 配置验证

### 在插件中验证配置

```python
class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        
        # 验证配置
        try:
            self._validate_config(config)
        except ValueError as e:
            self.api.log("error", f"配置验证失败: {e}")
            raise
        
        # 读取配置
        self.api_key = config['api_key']
    
    def _validate_config(self, config: dict):
        """验证配置"""
        # 检查必需字段
        if 'api_key' not in config or not config['api_key']:
            raise ValueError("API密钥不能为空")
        
        # 检查类型
        if 'timeout' in config:
            if not isinstance(config['timeout'], (int, float)):
                raise ValueError("超时时间必须是数字")
            if config['timeout'] < 1:
                raise ValueError("超时时间不能小于1秒")
        
        # 检查范围
        if 'admins' in config:
            if not isinstance(config['admins'], list):
                raise ValueError("管理员列表必须是数组")
```

---

## 最佳实践

### 1. 提供清晰的描述

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "在 https://api.example.com 申请API密钥，免费版每天100次请求",
    "label": "API 密钥"
  }
}
```

### 2. 设置合理的默认值

```json
{
  "retry_count": {
    "type": "number",
    "default": 3,
    "description": "失败后的重试次数（建议3-5次）",
    "min": 1,
    "max": 10
  }
}
```

### 3. 使用 label 提升可读性

```json
{
  "max_results": {
    "type": "number",
    "default": 10,
    "description": "每次查询返回的最大结果数",
    "label": "最大结果数"
  }
}
```

### 4. 标记必需字段

```json
{
  "api_key": {
    "type": "string",
    "default": "",
    "description": "API 密钥",
    "required": true
  }
}
```

---

## 常见问题

### Q: 配置修改后何时生效？

配置保存后，需要重载插件才能生效。点击插件页面的"重载"按钮。

### Q: 可以隐藏某些配置吗？

目前不支持隐藏配置。如果不想在前端显示，可以不在 `config_schema` 中定义，只在 `default_config` 中定义。

### Q: 可以自定义UI吗？

目前不支持自定义UI。UI 会根据 `config_schema` 自动生成。

### Q: array 类型如何输入？

用户可以每行输入一个值，或用逗号/空格分隔多个值：

```
123456
789012
```

或

```
123456, 789012, 345678
```

---

**上一篇**: [← 配置与数据管理](05-config-data.md)  
**下一篇**: [高级特性 →](07-advanced-features.md)


