# 高级特性

{ Chinese | [English](07-advanced-features.md) }

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 高级

## 事件系统

### 事件类型

| 事件名 | 触发时机 | 数据格式 |
|--------|----------|----------|
| `onebot.message` | 收到消息 | OneBot 消息事件 |
| `onebot.notice` | 收到通知 | OneBot 通知事件 |
| `onebot.request` | 收到请求 | OneBot 请求事件 |
| `plugin.<name>.*` | 插件自定义事件 | 自定义 |

### 发送自定义事件

```python
# 插件 A 发送事件
await self.api.emit_event('user_banned', {
    'user_id': 789,
    'group_id': 123456,
    'reason': '违规'
})

# 插件 B 监听事件
async def on_event(self, event_name, data):
    if event_name == 'plugin.plugin_a.user_banned':
        user_id = data['user_id']
        # 处理事件
```

---

## 异步编程最佳实践

### 1. 正确使用 async/await

```python
#  正确
async def fetch_data(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

#  错误：忘记 await
async def fetch_data(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return response.json()  # 返回的是 coroutine，不是数据！
```

### 2. 并发执行多个任务

```python
import asyncio

async def process_multiple_users(self, user_ids):
    """并发处理多个用户"""
    tasks = [self.process_user(uid) for uid in user_ids]
    results = await asyncio.gather(*tasks)
    return results
```

### 3. 定时任务

```python
class MyPlugin:
    async def on_load(self):
        """启动定时任务"""
        asyncio.create_task(self._periodic_task())
    
    async def _periodic_task(self):
        """每小时执行一次的任务"""
        while True:
            try:
                await self._do_work()
            except Exception as e:
                self.api.log("error", f"定时任务出错: {e}")
            
            # 等待1小时
            await asyncio.sleep(3600)
```

---

## 错误处理

### 1. 捕获异常

```python
async def handle_message(self, event):
    try:
        # 你的代码
        result = await self.process(event)
    except ValueError as e:
        # 处理特定异常
        self.api.log("warning", f"输入错误: {e}")
        await self.send_error_message(event, "输入格式错误")
    except Exception as e:
        # 处理未知异常
        self.api.log("error", f"处理失败: {e}")
        await self.send_error_message(event, "处理失败，请稍后重试")
```

### 2. 超时控制

```python
import asyncio

async def call_api_with_timeout(self, url):
    """带超时的 API 调用"""
    try:
        async with asyncio.timeout(10.0):  # 10秒超时
            return await self.call_api(url)
    except asyncio.TimeoutError:
        self.api.log("error", "API 调用超时")
        return None
```

### 3. 重试机制

```python
async def call_api_with_retry(self, action, params, max_retry=3):
    """带重试的 API 调用"""
    for attempt in range(max_retry):
        try:
            result = await self.api.call_api(action, params)
            if result['success']:
                return result
            
            # 失败但没有异常，等待后重试
            if attempt < max_retry - 1:
                wait_time = 2 ** attempt  # 指数退避
                self.api.log("warning", f"API 调用失败，{wait_time}秒后重试")
                await asyncio.sleep(wait_time)
        except Exception as e:
            self.api.log("error", f"API 调用异常: {e}")
            if attempt < max_retry - 1:
                await asyncio.sleep(2 ** attempt)
    
    return {'success': False, 'error': 'Max retries exceeded'}
```

---

## 性能优化

### 1. 减少数据库访问

```python
#  每次都读数据库
async def is_admin(self, user_id):
    config = await self.api.get_config()
    return user_id in config.get('admins', [])

#  缓存到内存
class MyPlugin:
    def __init__(self, api, config):
        self.admins = set(config.get('admins', []))
    
    def is_admin(self, user_id):
        return user_id in self.admins
```

### 2. 批量操作

```python
#  逐个发送
for user_id in user_ids:
    await self.api.send_private_msg(user_id, message)
    await asyncio.sleep(1)  # 避免限流

#  并发发送
tasks = [
    self.api.send_private_msg(uid, message)
    for uid in user_ids
]
await asyncio.gather(*tasks)
```

---

## 安全性

### 1. 输入验证

```python
def validate_qq_number(self, qq: str) -> bool:
    """验证 QQ 号格式"""
    if not qq.isdigit():
        return False
    qq_num = int(qq)
    return 10000 <= qq_num <= 9999999999

async def handle_command(self, message):
    qq = message.split()[1]
    if not self.validate_qq_number(qq):
        return "QQ号格式错误"
```

### 2. 权限检查

```python
async def handle_admin_command(self, event):
    """处理管理员命令"""
    user_id = event['user_id']
    
    # 检查是否是管理员
    if user_id not in self.admins:
        await self.api.send_group_msg(
            event['group_id'],
            " 权限不足"
        )
        return
    
    # 执行管理员操作
    await self.do_admin_action(event)
```

---

## 测试

### 单元测试示例

```python
import unittest
from unittest.mock import AsyncMock, MagicMock

class TestMyPlugin(unittest.IAsyncioTestCase):
    async def asyncSetUp(self):
        """测试初始化"""
        self.api = MagicMock()
        self.api.log = MagicMock()
        self.api.send_group_msg = AsyncMock(return_value={'success': True})
        
        self.config = {
            'api_key': 'test_key',
            'enabled': True
        }
        
        self.plugin = MyPlugin(self.api, self.config)
        await self.plugin.on_load()
    
    async def test_handle_message(self):
        """测试消息处理"""
        event = {
            'message_type': 'group',
            'group_id': 123456,
            'raw_message': '/test'
        }
        
        await self.plugin.handle_message(event)
        
        # 验证是否调用了 send_group_msg
        self.api.send_group_msg.assert_called_once()
```

---

**上一篇**: [← 前端 UI 集成](06-ui-integration_CN.md)  
**下一篇**: [最佳实践与示例 →](08-best-practices_CN.md)
