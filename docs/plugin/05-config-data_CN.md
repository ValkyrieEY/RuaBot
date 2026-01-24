# 配置与数据管理

{ Chinese | [English](05-config-data.md) }

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 中级

## 文档导航

1. [插件系统概述](01-overview_CN.md)
2. [快速开始](02-quickstart_CN.md)
3. [插件系统架构](03-architecture_CN.md)
4. [插件 API 参考](04-api-reference_CN.md)
5. [OneBot API 使用](05-onebot-guide_CN.md)
6. **[配置与数据管理](06-config-data_CN.md)** ← 当前文档
7. [前端 UI 集成](07-ui-integration_CN.md)
8. [高级特性](08-advanced-features_CN.md)
9. [最佳实践与示例](09-best-practices_CN.md)

---

## 配置管理

XQNEXT 提供了三层配置体系，确保插件配置的灵活性和可维护性。

### 1. 默认配置 (`plugin.json`)

在 `plugin.json` 中定义的 `default_config` 是配置的基准值。

```json
{
  "default_config": {
    "enabled": true,
    "limit": 10
  }
}
```

### 2. 用户配置 (数据库)

用户通过 Web UI 或 API 修改的配置会存储在数据库中，优先级高于默认配置。

### 3. 运行时配置 (内存)

插件运行时可以使用 `self.config` 访问合并后的配置。

### 配置 API 使用

```python
# 获取配置
value = await api.get_config('key')

# 设置配置（自动持久化到数据库）
await api.set_config('key', 'new_value')
```

---

## 数据持久化

对于非配置类数据（如统计数据、缓存图片等），应使用 Storage API。

### Storage API 特点

- **键值对存储**: 简单易用
- **二进制支持**: 可以存储任意二进制数据
- **自动压缩**: 大数据自动压缩
- **插件隔离**: 不同插件的数据互不可见

### 示例：保存用户签到数据

```python
import json
import time

class SigninPlugin:
    async def on_load(self):
        # 加载数据
        data_bytes = await self.api.get_storage('signin_data')
        if data_bytes:
            self.signin_data = json.loads(data_bytes.decode('utf-8'))
        else:
            self.signin_data = {}

    async def save_data(self):
        # 保存数据
        data_bytes = json.dumps(self.signin_data).encode('utf-8')
        await self.api.set_storage('signin_data', data_bytes)

    async def handle_signin(self, user_id):
        today = time.strftime('%Y-%m-%d')
        if self.signin_data.get(str(user_id)) == today:
            return "今天已经签到过了"
        
        self.signin_data[str(user_id)] = today
        await self.save_data()
        return "签到成功"
```

---

## 线程池使用

对于 CPU 密集型或阻塞型 I/O 操作，**必须**使用线程池，否则会阻塞整个插件进程。

### 使用 `run_in_executor`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=3)

    def cpu_bound_task(self, n):
        # 模拟耗时计算
        time.sleep(1)
        return n * n

    async def handle_message(self, event):
        loop = asyncio.get_event_loop()
        # 在线程池中执行
        result = await loop.run_in_executor(
            self.executor, 
            self.cpu_bound_task, 
            10
        )
        await self.api.send_private_msg(event['user_id'], f"计算结果: {result}")
```

---

## 缓存策略

合理使用缓存可以显著提升插件性能。

### 1. 内存缓存

适合小数据量、高频访问的数据。

```python
class CachePlugin:
    def __init__(self, api, config):
        self.cache = {}
        self.cache_ttl = 60  # 60秒过期

    def get_data(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None

    def set_data(self, key, value):
        self.cache[key] = (value, time.time())
```

### 2. Storage 缓存

适合大数据量、需要持久化的数据。

```python
async def get_image(self, url):
    # 尝试从 Storage 获取
    key = f"img_{hash(url)}"
    data = await self.api.get_storage(key)
    
    if data:
        return data
        
    # 下载图片
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            # 存入 Storage
            await self.api.set_storage(key, data)
            return data
```

---

## 下一步

- [前端 UI 集成](07-ui-integration_CN.md)
