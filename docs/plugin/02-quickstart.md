# 插件快速开始

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 入门
> **预计时间**: 15 分钟

## 文档导航

1. [插件系统概述](01-overview.md)
2. **[快速开始](02-quickstart.md)** ← 当前文档
3. [插件系统架构](03-architecture.md)
4. [插件 API 参考](04-api-reference.md)
5. [OneBot API 使用](05-onebot-guide.md)
6. [配置与数据管理](06-config-data.md)
7. [前端 UI 集成](07-ui-integration.md)
8. [高级特性](08-advanced-features.md)
9. [最佳实践与示例](09-best-practices.md)

---

## 学习目标

通过本教程，你将学会：

-  创建第一个插件
-  处理群消息和私聊消息
-  调用 OneBot API 发送消息
-  使用插件配置
-  保存和读取数据

---

## 前置要求

- Python 3.9+
- XQNEXT 框架已安装并运行
- 基础的 Python 异步编程知识（`async/await`）

---

## 第一个插件：Hello World

### 步骤 1: 创建插件目录

在 XQNEXT 根目录下创建插件目录：

```bash
cd XQNEXT
mkdir -p plugins/hello_plugin
cd plugins/hello_plugin
```

### 步骤 2: 创建 `plugin.json`

创建 `plugin.json` 文件，定义插件元数据：

```json
{
  "name": "hello_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "一个简单的Hello World插件",
  "entry": "main.py",
  "default_config": {
    "greeting": "你好"
  },
  "config_schema": {
    "greeting": {
      "type": "string",
      "default": "你好",
      "description": "问候语"
    }
  }
}
```

**字段说明：**

| 字段 | 说明 | 必需 |
|------|------|------|
| `name` | 插件名称（唯一标识） |  |
| `version` | 插件版本 |  |
| `author` | 作者名称 |  |
| `description` | 插件描述 |  |
| `entry` | 入口文件（默认 `main.py`） |  |
| `default_config` | 默认配置 |  |
| `config_schema` | 配置界面定义 |  |

### 步骤 3: 创建 `main.py`

创建插件主文件 `main.py`：

```python
"""Hello World 插件"""

async def create_plugin(api, config):
    """插件入口点
    
    Args:
        api: PluginAPI 对象，提供框架接口
        config: 插件配置字典
    
    Returns:
        插件实例
    """
    
    class HelloPlugin:
        """Hello World 插件类"""
        
        def __init__(self, api, config):
            self.api = api
            self.config = config
            self.greeting = config.get('greeting', '你好')
        
        async def on_load(self):
            """插件加载时调用"""
            self.api.log("info", f"Hello Plugin 已加载！问候语：{self.greeting}")
        
        async def on_unload(self):
            """插件卸载时调用"""
            self.api.log("info", "Hello Plugin 已卸载！")
        
        async def on_event(self, event_name, data):
            """处理事件
            
            Args:
                event_name: 事件名称
                data: 事件数据
            """
            # 只处理消息事件
            if event_name == "onebot.message":
                await self.handle_message(data)
        
        async def handle_message(self, event):
            """处理消息事件
            
            Args:
                event: OneBot 消息事件
            """
            # 获取消息类型和内容
            message_type = event.get('message_type')  # 'private' 或 'group'
            raw_message = event.get('raw_message', '').strip()
            
            # 检查是否是"你好"消息
            if raw_message in ["你好", "hello", "hi"]:
                # 构建回复消息
                reply = f"{self.greeting}！我是 Hello Plugin"
                
                # 根据消息类型发送回复
                if message_type == 'group':
                    group_id = event['group_id']
                    await self.api.send_group_msg(group_id, reply)
                elif message_type == 'private':
                    user_id = event['user_id']
                    await self.api.send_private_msg(user_id, reply)
    
    # 创建插件实例
    plugin = HelloPlugin(api, config)
    
    # 调用 on_load
    await plugin.on_load()
    
    # 返回插件实例
    return plugin
```

### 步骤 4: 重启框架或热重载

#### 方法 1: 热重载（推荐）

1. 打开 Web UI（默认 `http://localhost:8000`）
2. 进入"插件管理"页面
3. 找到 `hello_plugin`
4. 点击"重载"按钮

#### 方法 2: 重启框架

```bash
# 停止框架
Ctrl+C

# 重启框架
python main.py
```

### 步骤 5: 测试插件

向机器人发送消息：

```
你: 你好
Bot: 你好！我是 Hello Plugin
```

 恭喜！你的第一个插件已经运行成功！

---

## 进阶示例：回声插件

现在让我们创建一个更复杂的插件，它可以：

- 重复用户发送的消息
- 支持配置前缀
- 记录使用次数

### 创建目录和文件

```bash
mkdir -p plugins/echo_plugin
cd plugins/echo_plugin
```

### `plugin.json`

```json
{
  "name": "echo_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "回声插件 - 重复用户的消息",
  "entry": "main.py",
  "default_config": {
    "prefix": "!echo",
    "max_length": 100
  },
  "config_schema": {
    "prefix": {
      "type": "string",
      "default": "!echo",
      "description": "触发前缀"
    },
    "max_length": {
      "type": "number",
      "default": 100,
      "description": "最大回复长度"
    }
  }
}
```

### `main.py`

```python
"""回声插件 - 重复用户的消息"""

import json

async def create_plugin(api, config):
    """插件入口点"""
    
    class EchoPlugin:
        """回声插件类"""
        
        def __init__(self, api, config):
            self.api = api
            self.config = config
            self.prefix = config.get('prefix', '!echo')
            self.max_length = config.get('max_length', 100)
            self.usage_count = 0
        
        async def on_load(self):
            """插件加载时调用"""
            # 从存储加载使用次数
            data_bytes = await self.api.get_storage('usage_count')
            if data_bytes:
                try:
                    data = json.loads(data_bytes.decode('utf-8'))
                    self.usage_count = data.get('count', 0)
                    self.api.log("info", f"已加载使用次数: {self.usage_count}")
                except Exception as e:
                    self.api.log("error", f"加载数据失败: {e}")
            
            self.api.log("info", f"Echo Plugin 已加载！前缀: {self.prefix}")
        
        async def on_unload(self):
            """插件卸载时调用"""
            # 保存使用次数
            try:
                data = json.dumps({'count': self.usage_count})
                await self.api.set_storage('usage_count', data.encode('utf-8'))
                self.api.log("info", "使用次数已保存")
            except Exception as e:
                self.api.log("error", f"保存数据失败: {e}")
        
        async def on_event(self, event_name, data):
            """处理事件"""
            if event_name == "onebot.message":
                await self.handle_message(data)
        
        async def handle_message(self, event):
            """处理消息事件"""
            message_type = event.get('message_type')
            raw_message = event.get('raw_message', '').strip()
            
            # 检查是否以前缀开头
            if not raw_message.startswith(self.prefix):
                return
            
            # 提取要重复的内容
            content = raw_message[len(self.prefix):].strip()
            
            # 检查内容是否为空
            if not content:
                reply = f"用法: {self.prefix} <消息>"
            elif content == "stats":
                # 显示统计信息
                reply = f"回声插件统计:\n已使用 {self.usage_count} 次"
            else:
                # 截断过长的消息
                if len(content) > self.max_length:
                    content = content[:self.max_length] + "..."
                
                reply = f" {content}"
                
                # 增加使用次数
                self.usage_count += 1
            
            # 发送回复
            if message_type == 'group':
                group_id = event['group_id']
                result = await self.api.send_group_msg(group_id, reply)
            elif message_type == 'private':
                user_id = event['user_id']
                result = await self.api.send_private_msg(user_id, reply)
            
            # 检查发送结果
            if result.get('success'):
                self.api.log("info", f"回复成功，使用次数: {self.usage_count}")
            else:
                self.api.log("error", f"回复失败: {result.get('error')}")
    
    plugin = EchoPlugin(api, config)
    await plugin.on_load()
    return plugin
```

### 测试回声插件

```
你: !echo 你好世界
Bot:  你好世界

你: !echo stats
Bot: 回声插件统计:
     已使用 1 次
```

---

## 代码解析

### 1. 插件入口点

```python
async def create_plugin(api, config):
    """插件必须提供这个函数"""
    # 创建插件实例
    plugin = MyPlugin(api, config)
    # 调用初始化
    await plugin.on_load()
    # 返回实例
    return plugin
```

**关键点：**
- 函数名必须是 `create_plugin`
- 接收两个参数：`api` 和 `config`
- 必须是 `async` 函数
- 返回插件实例

### 2. 插件生命周期方法

```python
async def on_load(self):
    """插件加载时调用（可选）"""
    pass

async def on_unload(self):
    """插件卸载时调用（可选）"""
    pass

async def on_event(self, event_name, data):
    """处理事件（必需）"""
    pass
```

### 3. 事件处理

```python
async def on_event(self, event_name, data):
    """处理事件
    
    常见事件：
    - onebot.message: 消息事件
    - onebot.notice: 通知事件
    - onebot.request: 请求事件
    """
    if event_name == "onebot.message":
        await self.handle_message(data)
```

### 4. 消息处理

```python
async def handle_message(self, event):
    """处理消息
    
    event 字段：
    - message_type: 'private' 或 'group'
    - raw_message: 原始消息文本
    - user_id: 发送者 QQ 号
    - group_id: 群号（群消息才有）
    """
    message_type = event.get('message_type')
    raw_message = event.get('raw_message', '')
    user_id = event['user_id']
    
    if message_type == 'group':
        group_id = event['group_id']
        # 处理群消息
    elif message_type == 'private':
        # 处理私聊消息
```

### 5. 发送消息

```python
# 发送群消息
await self.api.send_group_msg(group_id, "消息内容")

# 发送私聊消息
await self.api.send_private_msg(user_id, "消息内容")

# 发送带 CQ 码的消息
await self.api.send_group_msg(group_id, "[CQ:at,qq=123456]你好")
```

### 6. 数据持久化

```python
# 保存数据
data = json.dumps({'key': 'value'})
await self.api.set_storage('my_data', data.encode('utf-8'))

# 读取数据
data_bytes = await self.api.get_storage('my_data')
if data_bytes:
    data = json.loads(data_bytes.decode('utf-8'))
```

### 7. 日志记录

```python
self.api.log("info", "信息日志")
self.api.log("warning", "警告日志")
self.api.log("error", "错误日志")
self.api.log("debug", "调试日志")
```

---

## 常见问题

### Q1: 为什么我的插件没有响应？

**检查清单：**
1.  `plugin.json` 和 `main.py` 是否在正确的目录？
2.  `create_plugin` 函数是否正确定义？
3.  `on_event` 方法是否正确实现？
4.  事件名称是否正确（`onebot.message`）？
5.  查看框架日志是否有错误信息

### Q2: 如何调试插件？

```python
# 使用日志输出调试信息
self.api.log("debug", f"收到消息: {event}")

# 查看框架日志
tail -f logs/xqnext.log
```

### Q3: 插件可以访问配置吗？

```python
# 在 __init__ 中获取配置
def __init__(self, api, config):
    self.api = api
    self.greeting = config.get('greeting', '默认值')

# 运行时读取配置
current_config = await self.api.get_config()
```

### Q4: 如何处理异常？

```python
async def handle_message(self, event):
    try:
        # 你的代码
        pass
    except Exception as e:
        self.api.log("error", f"处理消息失败: {e}")
```

### Q5: 插件可以调用其他插件吗？

```python
# 通过事件系统发送自定义事件
await self.api.emit_event("my_event", {"data": "value"})
```

---

## 下一步

现在你已经掌握了基本的插件开发，接下来可以：

1.  [深入了解插件系统架构](03-architecture.md)
2.  [查看完整的 API 参考](04-api-reference.md)
3.  [学习 OneBot API 使用](05-onebot-guide.md)
4.  [掌握配置与数据管理](06-config-data.md)

---

## 完整示例下载

你可以在以下位置找到更多完整示例：

- `plugins/like_plugin/` - QQ 点赞插件
- `plugins/kawaii_status/` - 服务器状态插件
- `plugins/so_good/` - 趣味回复插件

---

**上一篇**: [← 插件系统概述](01-overview.md)  
**下一篇**: [插件系统架构 →](03-architecture.md)
