# 配置与数据管理完全指南

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 中级

## 文档导航

1. [插件系统概述](01-overview.md)
2. [快速开始](02-quickstart.md)
3. [插件系统架构](03-architecture.md)
4. [插件 API 参考](04-api-reference.md)
5. **[配置与数据管理](05-config-data.md)** ← 当前文档
6. [前端 UI 集成](06-ui-integration.md)
7. [高级特性](07-advanced-features.md)
8. [最佳实践与示例](08-best-practices.md)

---

## 配置系统

### 三层配置体系

XQNEXT 插件使用三层配置：

```
1. plugin.json (default_config)    ← 默认配置
   ↓ 合并
2. 数据库配置                       ← 用户修改的配置
   ↓ 合并
3. 运行时配置 (传给 create_plugin)  ← 最终生效的配置
```

### 1. 定义默认配置

在 `plugin.json` 中定义：

```json
{
  "name": "my_plugin",
  "default_config": {
    "enabled": true,
    "api_key": "",
    "max_retry": 3,
    "timeout": 30,
    "admins": []
  },
  "config_schema": {
    "enabled": {
      "type": "boolean",
      "default": true,
      "description": "是否启用插件"
    },
    "api_key": {
      "type": "string",
      "default": "",
      "description": "API 密钥",
      "required": true
    },
    "max_retry": {
      "type": "number",
      "default": 3,
      "description": "最大重试次数",
      "min": 1,
      "max": 10
    },
    "timeout": {
      "type": "number",
      "default": 30,
      "description": "超时时间（秒）"
    },
    "admins": {
      "type": "array",
      "default": [],
      "description": "管理员QQ号列表"
    }
  }
}
```

**配置类型：**

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 字符串 | `"hello"` |
| `number` | 数字 | `123`, `3.14` |
| `boolean` | 布尔值 | `true`, `false` |
| `array` | 数组 | `[1, 2, 3]` |
| `object` | 对象 | `{"key": "value"}` |

**Schema 字段：**

| 字段 | 说明 | 类型 |
|------|------|------|
| `type` | 配置类型 | string |
| `default` | 默认值 | any |
| `description` | 描述（显示在UI） | string |
| `required` | 是否必填 | boolean |
| `min` | 最小值（number） | number |
| `max` | 最大值（number） | number |
| `enum` | 可选值列表 | array |
| `label` | 显示标签 | string |

### 2. 读取配置

**在初始化时读取：**

```python
class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        # 从传入的 config 读取
        self.api_key = config.get('api_key', '')
        self.max_retry = config.get('max_retry', 3)
        self.admins = config.get('admins', [])
```

**运行时读取：**

```python
# 读取单个配置项
api_key = await self.api.get_config('api_key')

# 读取全部配置
config = await self.api.get_config()
api_key = config.get('api_key')
```

### 3. 修改配置

```python
# 设置单个配置项
await self.api.set_config('api_key', 'new_key_12345')

# 设置多个配置项
await self.api.set_config('admins', [123, 456, 789])
await self.api.set_config('max_retry', 5)
```

**注意：**
- 配置自动保存到数据库
- 配置不会立即生效，需要重载插件
- 不支持存储二进制数据（使用存储API）

---

## 数据存储

### 存储类型对比

| 特性 | 配置 API | 存储 API |
|------|----------|----------|
| 用途 | 插件配置 | 任意数据 |
| 格式 | JSON | 二进制 |
| 大小限制 | < 1MB | < 10MB |
| 修改方式 | Web UI / API | API only |
| 典型用例 | API密钥、开关 | 图片、文件、序列化数据 |

### 1. 存储 JSON 数据

```python
import json

class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        self.user_data = {}
    
    async def on_load(self):
        """加载数据"""
        data_bytes = await self.api.get_storage('user_data')
        if data_bytes:
            try:
                self.user_data = json.loads(data_bytes.decode('utf-8'))
                self.api.log("info", f"已加载 {len(self.user_data)} 个用户")
            except Exception as e:
                self.api.log("error", f"加载数据失败: {e}")
                self.user_data = {}
    
    async def on_unload(self):
        """保存数据"""
        try:
            data_bytes = json.dumps(self.user_data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('user_data', data_bytes)
            self.api.log("info", "数据已保存")
        except Exception as e:
            self.api.log("error", f"保存数据失败: {e}")
    
    def add_user(self, user_id: int, data: dict):
        """添加用户数据"""
        self.user_data[str(user_id)] = data
        # 异步保存
        asyncio.create_task(self._save_data())
    
    async def _save_data(self):
        """异步保存"""
        data_bytes = json.dumps(self.user_data, ensure_ascii=False).encode('utf-8')
        await self.api.set_storage('user_data', data_bytes)
```

### 2. 存储图片/文件

```python
# 保存图片
async def cache_image(self, url: str):
    """下载并缓存图片"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                image_bytes = await response.read()
                # 使用 URL 哈希作为键
                import hashlib
                key = hashlib.md5(url.encode()).hexdigest()
                await self.api.set_storage(f'image_{key}', image_bytes)
                return key

# 读取缓存的图片
async def get_cached_image(self, key: str) -> Optional[bytes]:
    """获取缓存的图片"""
    return await self.api.get_storage(f'image_{key}')
```

### 3. 存储 Pickle 对象

```python
import pickle

# 保存对象
async def save_object(self, key: str, obj: Any):
    """保存 Python 对象"""
    data_bytes = pickle.dumps(obj)
    await self.api.set_storage(key, data_bytes)

# 读取对象
async def load_object(self, key: str) -> Optional[Any]:
    """读取 Python 对象"""
    data_bytes = await self.api.get_storage(key)
    if data_bytes:
        return pickle.loads(data_bytes)
    return None
```

** 警告：** Pickle 有安全风险，不要反序列化不可信的数据！

### 4. 管理存储

```python
# 列出所有存储键
keys = await self.api.list_storage_keys()
for key in keys:
    print(f"存储项: {key}")

# 删除存储
await self.api.delete_storage('user_data')

# 清空所有存储
for key in await self.api.list_storage_keys():
    await self.api.delete_storage(key)
```

---

## 使用线程池

### 为什么需要线程池？

CPU 密集型或阻塞 I/O 操作会阻塞事件循环，影响性能：

```python
#  错误：阻塞事件循环
import time

async def process_image(self, image_bytes):
    # 这会阻塞事件循环 5 秒！
    time.sleep(5)
    return processed_image

#  正确：使用线程池
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def process_image(self, image_bytes):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        self.executor,  # 线程池
        self._process_image_sync,  # 同步函数
        image_bytes  # 参数
    )
    return result

def _process_image_sync(self, image_bytes):
    """在线程池中执行的同步函数"""
    import time
    time.sleep(5)
    return processed_image
```

### 创建线程池

**方法 1：插件自己的线程池（推荐）**

```python
from concurrent.futures import ThreadPoolExecutor
import threading

class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        self.config = config
        # 创建线程池（2-4个线程足够大多数场景）
        self.executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="my_plugin_"
        )
    
    async def on_unload(self):
        """清理线程池"""
        self.executor.shutdown(wait=True)
```

**方法 2：使用框架的线程池**

框架提供了线程池，但目前需要插件自己创建。

### 使用线程池

```python
import asyncio

async def process_cpu_task(self, data):
    """CPU 密集型任务"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        self.executor,
        self._cpu_intensive_work,
        data
    )
    return result

def _cpu_intensive_work(self, data):
    """在线程中执行的CPU密集型工作"""
    import hashlib
    # 模拟 CPU 密集型操作
    for i in range(1000000):
        hashlib.sha256(data.encode()).hexdigest()
    return "done"
```

### 实战示例：图片处理

```python
from PIL import Image
from io import BytesIO

class ImagePlugin:
    def __init__(self, api, config):
        self.api = api
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def compress_image(self, image_bytes: bytes) -> bytes:
        """压缩图片（使用线程池）"""
        loop = asyncio.get_event_loop()
        compressed = await loop.run_in_executor(
            self.executor,
            self._compress_sync,
            image_bytes
        )
        return compressed
    
    def _compress_sync(self, image_bytes: bytes) -> bytes:
        """同步压缩函数（在线程中执行）"""
        # 打开图片
        img = Image.open(BytesIO(image_bytes))
        
        # 压缩
        if img.size[0] > 1920 or img.size[1] > 1080:
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        
        # 保存
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
```

---

## 缓存策略

### 1. 内存缓存

```python
from datetime import datetime, timedelta

class CachePlugin:
    def __init__(self, api, config):
        self.api = api
        self.cache = {}  # {key: (value, expire_time)}
    
    def set_cache(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        expire_time = datetime.now() + timedelta(seconds=ttl)
        self.cache[key] = (value, expire_time)
    
    def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None
        
        value, expire_time = self.cache[key]
        if datetime.now() > expire_time:
            # 过期，删除
            del self.cache[key]
            return None
        
        return value
    
    def clear_expired(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expire_time) in self.cache.items()
            if now > expire_time
        ]
        for key in expired_keys:
            del self.cache[key]
```

### 2. LRU 缓存

```python
from functools import lru_cache

class MyPlugin:
    # 使用 Python 内置的 LRU 缓存
    @lru_cache(maxsize=128)
    def expensive_calculation(self, n: int) -> int:
        """昂贵的计算（带缓存）"""
        # 这个结果会被缓存
        return sum(i ** 2 for i in range(n))
```

### 3. 持久化缓存

```python
class PersistentCache:
    def __init__(self, api):
        self.api = api
        self.memory_cache = {}
    
    async def get(self, key: str, fetch_func=None):
        """获取缓存（内存 → 存储 → 获取）"""
        # 1. 检查内存缓存
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # 2. 检查持久化缓存
        cache_key = f"cache_{key}"
        data_bytes = await self.api.get_storage(cache_key)
        if data_bytes:
            import json
            data = json.loads(data_bytes.decode('utf-8'))
            self.memory_cache[key] = data
            return data
        
        # 3. 调用获取函数
        if fetch_func:
            data = await fetch_func()
            await self.set(key, data)
            return data
        
        return None
    
    async def set(self, key: str, value: Any):
        """设置缓存"""
        # 写入内存
        self.memory_cache[key] = value
        
        # 写入存储
        import json
        cache_key = f"cache_{key}"
        data_bytes = json.dumps(value).encode('utf-8')
        await self.api.set_storage(cache_key, data_bytes)
```

---

## 最佳实践

### 1. 配置验证

```python
def validate_config(config: dict) -> bool:
    """验证配置"""
    # 检查必需字段
    required_fields = ['api_key', 'timeout']
    for field in required_fields:
        if field not in config or not config[field]:
            raise ValueError(f"缺少必需的配置项: {field}")
    
    # 检查类型
    if not isinstance(config['timeout'], (int, float)):
        raise ValueError("timeout 必须是数字")
    
    # 检查范围
    if config['timeout'] < 1 or config['timeout'] > 300:
        raise ValueError("timeout 必须在 1-300 之间")
    
    return True
```

### 2. 定期保存

```python
class AutoSavePlugin:
    def __init__(self, api, config):
        self.api = api
        self.data = {}
        self.last_save_time = datetime.now()
        self.save_interval = 300  # 5分钟
    
    async def on_load(self):
        """启动自动保存任务"""
        asyncio.create_task(self._auto_save_loop())
    
    async def _auto_save_loop(self):
        """自动保存循环"""
        while True:
            await asyncio.sleep(self.save_interval)
            await self._save_data()
    
    async def _save_data(self):
        """保存数据"""
        try:
            import json
            data_bytes = json.dumps(self.data).encode('utf-8')
            await self.api.set_storage('data', data_bytes)
            self.api.log("info", "数据已自动保存")
        except Exception as e:
            self.api.log("error", f"自动保存失败: {e}")
```

### 3. 数据迁移

```python
async def migrate_data(self):
    """数据迁移（版本升级）"""
    version = await self.api.get_config('data_version')
    
    if version is None or version < 2:
        # 从版本1迁移到版本2
        self.api.log("info", "开始数据迁移 v1 -> v2")
        
        old_data = await self.api.get_storage('old_data')
        if old_data:
            # 转换数据格式
            new_data = self._convert_v1_to_v2(old_data)
            await self.api.set_storage('data', new_data)
            
            # 删除旧数据
            await self.api.delete_storage('old_data')
        
        # 更新版本号
        await self.api.set_config('data_version', 2)
        self.api.log("info", "数据迁移完成")
```

---

## 常见问题

### Q: 配置修改后如何生效？

配置修改后，需要重载插件才能生效。在 Web UI 中点击"重载"按钮。

### Q: 存储和配置如何选择？

- **配置**：用于设置项（如API密钥、开关）
- **存储**：用于运行时数据（如用户数据、缓存）

### Q: 数据会自动保存吗？

不会。你需要在 `on_unload` 中保存数据，或实现自动保存机制。

### Q: 线程池应该创建多少线程？

通常 2-4 个线程足够。过多线程会增加内存开销，并不会提升性能。

---

**上一篇**: [← 插件 API 参考](04-api-reference.md)  
**下一篇**: [前端 UI 集成 →](06-ui-integration.md)
