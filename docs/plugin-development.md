# 插件开发指南

## 插件基础

### 什么是插件

插件是 RuaBot 框架的基本扩展单元，通过插件可以扩展框架的功能。每个插件都是独立的模块，拥有自己的目录、配置和生命周期。

### 插件结构

一个标准的插件目录结构如下：

```
plugin_name/
├── plugin.json          # 插件元数据（必需）
├── main.py              # 插件主文件（必需）
├── system.json          # 系统数据（自动生成）
├── data/                # 数据目录
│   └── config.json      # 插件配置（可选）
└── README.md            # 插件说明（可选）
```

### plugin.json

`plugin.json` 是插件的元数据文件，定义了插件的基本信息：

```json
{
  "name": "plugin_name",
  "version": "1.0.0",
  "description": "插件描述",
  "author": "作者名",
  "entry": "main.py",
  "dependencies": [],
  "default_config": {
    "key": "value"
  }
}
```

**字段说明**：
- `name`: 插件名称（必需）
- `version`: 插件版本（必需）
- `description`: 插件描述（可选）
- `author`: 作者名（可选）
- `entry`: 入口文件（可选，默认为 main.py）
- `dependencies`: 依赖的其他插件（可选）
- `default_config`: 默认配置（可选）

## 开发流程

### 1. 创建插件目录

在 `plugins` 目录下创建插件目录：

```bash
mkdir plugins/my_plugin
cd plugins/my_plugin
```

### 2. 创建 plugin.json

创建 `plugin.json` 文件，定义插件元数据。

### 3. 创建主文件

创建插件主文件（通常是 `main.py`），实现插件逻辑。

### 4. 实现插件接口

插件需要实现 `PluginInterface` 接口，至少需要实现以下方法：

```python
from src.plugins.interface import PluginInterface, PluginMetadata

class MyPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self._enabled = False
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            description="我的插件"
        )
    
    async def on_load(self, context: dict):
        """插件加载时调用"""
        pass
    
    async def on_unload(self):
        """插件卸载时调用"""
        pass
    
    async def on_enable(self):
        """插件启用时调用"""
        self._enabled = True
    
    async def on_disable(self):
        """插件禁用时调用"""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        return self._enabled
```

### 5. 订阅事件

插件可以订阅系统事件来处理消息：

```python
async def on_load(self, context: dict):
    event_bus = context.get("event_bus")
    if event_bus:
        await event_bus.subscribe("message.group", self.handle_message)

async def handle_message(self, event: dict):
    """处理群消息"""
    message = event.get("data", {})
    # 处理消息逻辑
```

### 6. 注册能力

插件可以注册能力供其他插件使用：

```python
async def on_load(self, context: dict):
    capability_registry = context.get("capability_registry")
    if capability_registry:
        capability_registry.register(
            provider=self.get_metadata().name,
            capability="my_capability",
            handler=self.my_handler
        )
```

## API 参考

### PluginInterface

插件接口基类，所有插件必须实现此接口。

#### 方法

- `get_metadata() -> PluginMetadata`: 获取插件元数据
- `on_load(context: dict) -> None`: 插件加载时调用
- `on_unload() -> None`: 插件卸载时调用
- `on_enable() -> None`: 插件启用时调用
- `on_disable() -> None`: 插件禁用时调用
- `is_enabled() -> bool`: 检查插件是否启用

### 插件上下文

插件加载时会收到一个上下文字典，包含以下内容：

- `event_bus`: 事件总线实例
- `capability_registry`: 能力注册表实例
- `plugin_manager`: 插件管理器实例
- `plugin_config`: 插件配置
- `adapter`: 适配器实例
- `app`: FastAPI 应用实例（可选）
- `plugin_dir`: 插件目录路径
- `data_dir`: 插件数据目录路径

### 事件总线

事件总线用于发布和订阅事件。

#### 订阅事件

```python
await event_bus.subscribe(event_type, handler)
```

#### 发布事件

```python
await event_bus.publish(event_type, data, source="plugin_name")
```

#### 常见事件类型

- `message.group`: 群消息
- `message.private`: 私聊消息
- `plugin.loaded`: 插件加载
- `plugin.unloaded`: 插件卸载
- `plugin.enabled`: 插件启用
- `plugin.disabled`: 插件禁用

### 能力注册表

能力注册表用于注册和查询插件能力。

#### 注册能力

```python
capability_registry.register(
    provider="plugin_name",
    capability="capability_name",
    handler=handler_function
)
```

#### 查询能力

```python
handler = capability_registry.get("capability_name")
```

## 示例代码

### 简单回复插件

```python
from src.plugins.interface import PluginInterface, PluginMetadata

class ReplyPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self._enabled = False
        self._config = {}
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="reply_plugin",
            version="1.0.0",
            description="简单回复插件"
        )
    
    async def on_load(self, context: dict):
        self._config = context.get("plugin_config", {})
        event_bus = context.get("event_bus")
        if event_bus:
            await event_bus.subscribe("message.group", self.handle_message)
    
    async def on_unload(self):
        pass
    
    async def on_enable(self):
        self._enabled = True
    
    async def on_disable(self):
        self._enabled = False
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    async def handle_message(self, event: dict):
        if not self._enabled:
            return
        
        message = event.get("data", {})
        content = message.get("message", "")
        
        # 简单回复逻辑
        if "你好" in content:
            # 发送回复
            await self.send_reply(message, "你好！")
    
    async def send_reply(self, original_message: dict, reply: str):
        # 通过事件总线发送回复
        event_bus = self._context.get("event_bus")
        if event_bus:
            await event_bus.publish(
                "send_message",
                {
                    "group_id": original_message.get("group_id"),
                    "message": reply
                },
                source=self.get_metadata().name
            )
```

### 配置管理插件

```python
import json
from pathlib import Path
from src.plugins.interface import PluginInterface, PluginMetadata

class ConfigPlugin(PluginInterface):
    def __init__(self):
        super().__init__()
        self._enabled = False
        self._config = {}
        self._config_file = None
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="config_plugin",
            version="1.0.0",
            description="配置管理插件"
        )
    
    async def on_load(self, context: dict):
        self._config = context.get("plugin_config", {})
        data_dir = context.get("data_dir")
        if data_dir:
            self._config_file = Path(data_dir) / "config.json"
            await self.load_config()
    
    async def load_config(self):
        """加载配置"""
        if self._config_file and self._config_file.exists():
            with open(self._config_file, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                self._config.update(saved_config)
    
    async def save_config(self):
        """保存配置"""
        if self._config_file:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def get_config(self, key: str, default=None):
        """获取配置值"""
        return self._config.get(key, default)
    
    async def set_config(self, key: str, value):
        """设置配置值"""
        self._config[key] = value
        await self.save_config()
```

## 最佳实践

### 1. 错误处理

始终使用 try-except 处理可能的错误：

```python
async def handle_message(self, event: dict):
    try:
        # 处理逻辑
        pass
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
```

### 2. 异步操作

所有 I/O 操作都应该使用异步方式：

```python
async def read_file(self, path: Path):
    async with aiofiles.open(path, 'r') as f:
        return await f.read()
```

### 3. 配置管理

使用插件的数据目录存储配置和数据：

```python
data_dir = context.get("data_dir")
config_file = Path(data_dir) / "config.json"
```

### 4. 日志记录

使用框架的日志系统：

```python
from src.core.logger import get_logger

logger = get_logger(__name__)
logger.info("插件已加载")
```

### 5. 资源清理

在 `on_unload` 中清理资源：

```python
async def on_unload(self):
    # 取消事件订阅
    event_bus = self._context.get("event_bus")
    if event_bus:
        await event_bus.unsubscribe("message.group", self.handle_message)
    
    # 清理其他资源
    pass
```

### 6. 依赖管理

在 `plugin.json` 中声明依赖：

```json
{
  "dependencies": [
    {
      "name": "other_plugin",
      "version": "1.0.0",
      "required": true
    }
  ]
}
```

## 调试技巧

### 1. 查看日志

插件日志会记录在框架日志中，查看 `logs/` 目录下的日志文件。

### 2. 使用 Web UI

通过 Web UI 可以查看插件状态、启用/禁用插件、查看插件配置。

### 3. 热重载

修改插件代码后，可以通过 Web UI 或 API 重载插件，无需重启框架。

### 4. 测试插件

创建测试脚本测试插件功能：

```python
import asyncio
from my_plugin import MyPlugin

async def test():
    plugin = MyPlugin()
    context = {
        "event_bus": get_event_bus(),
        "capability_registry": get_capability_registry(),
    }
    await plugin.on_load(context)
    await plugin.on_enable()
    # 测试逻辑
    await plugin.on_disable()
    await plugin.on_unload()
```

## 常见问题

### 1. 插件无法加载

**问题**: 插件加载失败，提示找不到模块。

**解决方案**:
- 检查 `plugin.json` 文件是否存在且格式正确
- 检查入口文件路径是否正确
- 检查插件目录结构是否符合要求

### 2. 事件订阅不生效

**问题**: 订阅了事件但没有收到事件通知。

**解决方案**:
- 确认事件类型名称正确
- 确认插件已启用
- 检查事件处理函数签名是否正确
- 查看日志确认事件是否被发布

### 3. 配置无法保存

**问题**: 修改配置后无法保存。

**解决方案**:
- 确认 `data` 目录存在且有写权限
- 检查配置文件路径是否正确
- 确认使用异步方式保存配置

### 4. 依赖插件未加载

**问题**: 依赖的插件未加载导致当前插件无法工作。

**解决方案**:
- 检查依赖插件是否已安装
- 确认依赖插件版本是否正确
- 查看插件加载顺序

### 5. 热重载失败

**问题**: 修改代码后热重载失败。

**解决方案**:
- 检查代码语法错误
- 确认没有循环导入
- 查看日志获取详细错误信息
- 尝试完全卸载后重新加载

## 高级主题

### 插件适配器

RuaBot 支持多种插件适配器，适配器决定了插件的加载方式和运行环境。

#### 使用适配器

在 Web UI 中为插件选择适配器，或通过 API 设置：

```python
plugin_manager.set_plugin_adapter("plugin_name", "adapter_name")
```

#### 自定义适配器

可以开发自定义适配器来支持特殊的插件类型，详见适配器开发文档。

### 插件间通信

插件可以通过事件总线或能力注册表进行通信。

#### 通过事件总线通信

```python
# 插件 A 发布事件
await event_bus.publish("custom_event", {"data": "value"})

# 插件 B 订阅事件
await event_bus.subscribe("custom_event", self.handle_custom_event)
```

#### 通过能力注册表通信

```python
# 插件 A 注册能力
capability_registry.register(
    provider="plugin_a",
    capability="process_data",
    handler=self.process_handler
)

# 插件 B 使用能力
handler = capability_registry.get("process_data")
result = await handler(data)
```

### 插件权限管理

插件可以定义自己的权限需求：

```python
from src.plugins.interface import PluginPermission

def get_permissions(self) -> List[PluginPermission]:
    return [
        PluginPermission(
            name="send_message",
            description="发送消息权限"
        )
    ]
```

### 插件配置验证

可以在插件中验证配置：

```python
async def on_load(self, context: dict):
    config = context.get("plugin_config", {})
    if not self.validate_config(config):
        raise ValueError("配置验证失败")
    
def validate_config(self, config: dict) -> bool:
    required_keys = ["api_key", "api_url"]
    return all(key in config for key in required_keys)
```

## 发布插件

### 准备发布

1. **完善文档**: 编写清晰的 README.md
2. **测试插件**: 确保插件功能正常
3. **版本号**: 更新 `plugin.json` 中的版本号
4. **许可证**: 添加许可证文件

### 发布清单

- [ ] 插件功能完整
- [ ] 文档完善
- [ ] 代码注释清晰
- [ ] 错误处理完善
- [ ] 配置说明清楚
- [ ] 依赖关系明确

## 参考资源

- [插件接口文档](../src/plugins/interface.py)
- [事件总线文档](../src/core/event_bus.py)
- [示例插件](../plugins/)
- [API 文档](../docs/api-reference.md)

## 获取帮助

如果遇到问题，可以通过以下方式获取帮助：

- 查看框架日志文件
- 提交 Issue 到项目仓库
- 参考示例插件代码
- 查阅 API 文档

---

祝您开发愉快！