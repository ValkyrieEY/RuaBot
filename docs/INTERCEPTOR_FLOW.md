# 拦截器系统完整流程说明

## 📋 目录

1. [系统架构](#系统架构)
2. [拦截器注册流程](#拦截器注册流程)
3. [拦截器获取流程](#拦截器获取流程)
4. [拦截器执行流程](#拦截器执行流程)
5. [完整调用链路](#完整调用链路)
6. [代码示例](#代码示例)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        主进程                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  App (src/core/app.py)                                 │ │
│  │    └─ PluginRuntimeConnector                           │ │
│  │         └─ InterceptorRegistry (拦截器注册表)          │ │
│  │              ├─ _message_interceptors: List            │ │
│  │              └─ _event_interceptors: List              │ │
│  └────────────────────────────────────────────────────────┘ │
│                         ▲                                    │
│                         │ stdio 通信                         │
│                         │                                    │
└─────────────────────────┼─────────────────────────────────────┘
                          │
┌─────────────────────────┼─────────────────────────────────────┐
│                         │  插件进程                            │
│  ┌─────────────────────▼────────────────────────────────────┐│
│  │  PluginRuntime (src/plugins/runtime/main.py)            ││
│  │    └─ _interceptors: Dict[plugin_id, interceptor]       ││
│  └──────────────────────────────────────────────────────────┘│
│                         ▲                                    │
│                         │                                    │
│  ┌─────────────────────┴────────────────────────────────────┐│
│  │  Plugin (plugins/xxx/main.py)                            ││
│  │    └─ 创建并注册拦截器                                    ││
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 拦截器注册流程

### 流程图

```
插件代码 (plugins/xxx/main.py)
    │
    │ 1. 在 on_load() 中创建拦截器
    ▼
class MyInterceptor(MessageInterceptor):
    def __init__(self, plugin_id, priority=50):
        super().__init__(plugin_id, priority)
    
    async def intercept_message(self, action, params, source_plugin):
        # 拦截逻辑
        return InterceptorResult(allow=True)
    │
    │ 2. 注册拦截器
    ▼
self.api.register_message_interceptor(
    MyInterceptor(self.plugin_name, priority=50)
)
    │
    │ 调用 PluginAPI.register_message_interceptor()
    │ (src/plugins/runtime/main.py:1332)
    ▼
┌───────────────────────────────────────────────────┐
│ PluginAPI.register_message_interceptor()          │
│                                                    │
│ 1. 存储拦截器到 runtime._interceptors             │
│    runtime._interceptors[plugin_id] = interceptor │
│                                                    │
│ 2. 发送注册消息到主框架                           │
│    send_message({                                 │
│        'type': 'register_interceptor',            │
│        'data': {                                  │
│            'plugin_id': plugin_id,                │
│            'priority': priority                   │
│        }                                          │
│    })                                             │
└───────────────────────────────────────────────────┘
    │
    │ 通过 stdio 发送到主进程
    ▼
┌───────────────────────────────────────────────────┐
│ PluginRuntimeConnector._handle_runtime_message()  │
│ (src/plugins/runtime/connector.py:635)            │
│                                                    │
│ if msg_type == 'register_interceptor':            │
│     plugin_id = data['plugin_id']                 │
│     priority = data['priority']                   │
│                                                    │
│     # 创建代理拦截器                              │
│     proxy = ProxyMessageInterceptor(              │
│         plugin_id, self, priority                 │
│     )                                             │
│                                                    │
│     # 注册到主框架的注册表                        │
│     self.interceptor_registry                     │
│         .register_message_interceptor(proxy)      │
└───────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────┐
│ InterceptorRegistry.register_message_interceptor()│
│ (src/plugins/interceptor.py:167)                  │
│                                                    │
│ # 添加到列表                                      │
│ self._message_interceptors.append(interceptor)    │
│                                                    │
│ # 按优先级排序                                    │
│ self._message_interceptors.sort(                  │
│     key=lambda x: x.priority                      │
│ )                                                 │
└───────────────────────────────────────────────────┘
    │
    ▼
✅ 注册完成！拦截器已添加到主框架的注册表中
```

### 关键代码位置

1. **插件侧注册** (`src/plugins/runtime/main.py:1332-1355`)
   ```python
   def register_message_interceptor(self, interceptor):
       # 存储在插件进程
       self.runtime._interceptors[self.plugin_id] = interceptor
       
       # 发送消息到主进程
       self.runtime.send_message({
           'type': 'register_interceptor',
           'data': {
               'plugin_id': self.plugin_id,
               'priority': getattr(interceptor, 'priority', 100)
           }
       })
   ```

2. **主框架接收** (`src/plugins/runtime/connector.py:635-645`)
   ```python
   elif msg_type == 'register_interceptor':
       plugin_id = data.get('plugin_id')
       priority = data.get('priority', 100)
       
       # 创建代理拦截器（在主进程中代理插件进程的拦截器）
       proxy_interceptor = ProxyMessageInterceptor(
           plugin_id, self, priority=priority
       )
       self.interceptor_registry.register_message_interceptor(proxy_interceptor)
   ```

3. **注册表添加** (`src/plugins/interceptor.py:167-175`)
   ```python
   def register_message_interceptor(self, interceptor: MessageInterceptor):
       self._message_interceptors.append(interceptor)
       # 按优先级排序（小数字先执行）
       self._message_interceptors.sort(key=lambda x: x.priority)
   ```

---

## 拦截器获取流程

### 如何获取已注册的拦截器

```python
# 方式1: 直接访问注册表
registry = connector.interceptor_registry
message_interceptors = registry.get_message_interceptors()  # 返回副本
event_interceptors = registry.get_event_interceptors()

# 方式2: 查看统计信息
stats = registry.get_stats_summary()
print(f"已注册消息拦截器: {stats['message_interceptors']} 个")
print(f"已注册事件拦截器: {stats['event_interceptors']} 个")

# 方式3: 遍历拦截器
for interceptor in registry.get_message_interceptors():
    print(f"Plugin: {interceptor.plugin_id}, Priority: {interceptor.priority}")
```

### 代码位置

**获取拦截器列表** (`src/plugins/interceptor.py:731-737`)
```python
def get_message_interceptors(self) -> list[MessageInterceptor]:
    """Get all message interceptors."""
    return self._message_interceptors.copy()  # 返回副本，防止外部修改

def get_event_interceptors(self) -> list[EventInterceptor]:
    """Get all event interceptors."""
    return self._event_interceptors.copy()
```

---

## 拦截器执行流程

### 完整执行流程

```
插件发送消息
    │
    │ await api.send_group_msg(group_id=xxx, message="...")
    ▼
┌─────────────────────────────────────────────┐
│ PluginAPI.send_group_msg()                  │
│ (src/plugins/runtime/plugin_api.py)         │
│                                              │
│ 发送 'api_call' 消息到主进程                 │
└─────────────────────────────────────────────┘
    │
    │ stdio 通信
    ▼
┌─────────────────────────────────────────────┐
│ PluginRuntimeConnector.                     │
│ _handle_runtime_message()                   │
│ (src/plugins/runtime/connector.py:769)      │
│                                              │
│ elif msg_type == 'api_call':                │
│     action = 'send_group_msg'               │
│     params = {'group_id': xxx, ...}         │
└─────────────────────────────────────────────┘
    │
    │ 检查是否是消息发送动作
    ▼
┌─────────────────────────────────────────────┐
│ 是否需要拦截？                              │
│                                              │
│ message_actions = [                         │
│     'send_group_msg',                       │
│     'send_private_msg',                     │
│     'send_msg'                              │
│ ]                                           │
│                                              │
│ if action in message_actions: ✅            │
└─────────────────────────────────────────────┘
    │
    │ YES - 需要拦截
    ▼
┌─────────────────────────────────────────────┐
│ 执行拦截器                                  │
│                                              │
│ allow, modified_params =                    │
│     await self.interceptor_registry         │
│         .intercept_message(                 │
│             action, params, source_plugin   │
│         )                                   │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ InterceptorRegistry.intercept_message()                     │
│ (src/plugins/interceptor.py:232)                            │
│                                                              │
│ 1. 按优先级分组                                             │
│    priority_groups = self._group_by_priority(interceptors)  │
│    例如: [(10, [A, B]), (50, [C, D]), (100, [E])]          │
│                                                              │
│ 2. 遍历每个优先级组                                         │
│    for priority, interceptors in priority_groups:           │
│                                                              │
│        a) 判断执行模式                                      │
│           if HYBRID and len(interceptors) > 1:              │
│               并发执行 (同组)                               │
│           else:                                             │
│               串行执行                                      │
│                                                              │
│        b) 执行拦截器                                        │
│           - 检查熔断器状态                                  │
│           - 应用自适应超时                                  │
│           - 记录性能统计                                    │
│                                                              │
│        c) 处理结果                                          │
│           - 如果被阻止: return (False, params)              │
│           - 如果修改: 更新 params                           │
│                                                              │
│ 3. 返回最终结果                                             │
│    return (True, modified_params)                           │
└─────────────────────────────────────────────────────────────┘
    │
    │ 拦截器如何实际执行？(代理模式)
    ▼
┌──────────────────────────────────────────────────────────────┐
│ ProxyMessageInterceptor.intercept_message()                  │
│ (src/plugins/runtime/connector.py:163)                       │
│                                                               │
│ 1. 生成请求ID                                                │
│    request_id = f"interceptor_{plugin_id}_{uuid}"            │
│                                                               │
│ 2. 创建 Future 等待结果                                      │
│    future = asyncio.Future()                                 │
│    connector._interceptor_futures[request_id] = future       │
│                                                               │
│ 3. 发送消息到插件进程                                        │
│    send_message({                                            │
│        'type': 'intercept_message',                          │
│        'data': {                                             │
│            'request_id': request_id,                         │
│            'plugin_id': plugin_id,                           │
│            'action': action,                                 │
│            'params': params,                                 │
│            'source_plugin': source_plugin                    │
│        }                                                     │
│    })                                                        │
│                                                               │
│ 4. 等待插件进程的响应（带超时）                              │
│    result = await asyncio.wait_for(future, timeout=3.0)      │
│                                                               │
│ 5. 返回结果                                                  │
│    return result                                             │
└──────────────────────────────────────────────────────────────┘
    │
    │ stdio 通信到插件进程
    ▼
┌──────────────────────────────────────────────────────────────┐
│ PluginRuntime._handle_main_message()                         │
│ (src/plugins/runtime/main.py:321)                            │
│                                                               │
│ elif msg_type == 'intercept_message':                        │
│     request_id = data['request_id']                          │
│     plugin_id = data['plugin_id']                            │
│                                                               │
│     # 获取插件的拦截器实例                                   │
│     interceptor = self._interceptors.get(plugin_id)          │
│                                                               │
│     if interceptor:                                          │
│         # 调用插件的拦截器方法                               │
│         result = await interceptor.intercept_message(        │
│             action, params, source_plugin                    │
│         )                                                    │
│                                                               │
│         # 发送响应回主进程                                   │
│         send_message({                                       │
│             'type': 'intercept_message_response',            │
│             'data': {                                        │
│                 'request_id': request_id,                    │
│                 'allow': result.allow,                       │
│                 'modified_data': result.modified_data,       │
│                 'block_reason': result.block_reason          │
│             }                                                │
│         })                                                   │
└──────────────────────────────────────────────────────────────┘
    │
    │ stdio 通信回主进程
    ▼
┌──────────────────────────────────────────────────────────────┐
│ PluginRuntimeConnector._handle_runtime_message()             │
│ (src/plugins/runtime/connector.py:655)                       │
│                                                               │
│ elif msg_type == 'intercept_message_response':               │
│     request_id = data['request_id']                          │
│     future = self._interceptor_futures.get(request_id)       │
│                                                               │
│     if future:                                               │
│         result = InterceptorResult(                          │
│             allow=data['allow'],                             │
│             modified_data=data['modified_data'],             │
│             block_reason=data['block_reason']                │
│         )                                                    │
│         future.set_result(result)  # 唤醒等待的 Future      │
└──────────────────────────────────────────────────────────────┘
    │
    │ ProxyMessageInterceptor 的 Future 完成
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 拦截器执行完成                                               │
│                                                               │
│ - 如果 allow=False: 阻止消息，不调用 OneBot API             │
│ - 如果 allow=True: 使用 modified_params 调用 OneBot API     │
└──────────────────────────────────────────────────────────────┘
```

---

## 完整调用链路

### 数据流向

```
┌─────────────┐                      ┌──────────────┐
│  插件进程    │                      │   主进程      │
└─────────────┘                      └──────────────┘

1. 注册阶段:
   Plugin.on_load()
       ↓
   api.register_message_interceptor(interceptor)
       ↓ [存储在插件进程]
   runtime._interceptors[plugin_id] = interceptor
       ↓ [发送注册消息]
   stdio → main process
                                      ↓
                        创建 ProxyMessageInterceptor
                                      ↓
                        registry.register_message_interceptor(proxy)
                                      ↓
                        _message_interceptors.append(proxy)

2. 执行阶段:
   Plugin: api.send_group_msg()
       ↓ [发送 API 调用]
   stdio → main process
                                      ↓
                        检查是否需要拦截
                                      ↓
                        registry.intercept_message()
                                      ↓
                        遍历所有拦截器（按优先级）
                                      ↓
                        ProxyMessageInterceptor.intercept_message()
                                      ↓ [发送拦截请求]
                                  stdio → plugin process
   收到拦截请求
       ↓
   获取实际的拦截器实例
       ↓
   interceptor.intercept_message()
       ↓ [插件的拦截逻辑]
   返回 InterceptorResult
       ↓ [发送响应]
   stdio → main process
                                      ↓
                        ProxyMessageInterceptor 收到响应
                                      ↓
                        registry 收集所有结果
                                      ↓
                        决定是否允许/修改消息
                                      ↓
                        调用 OneBot API（或阻止）
```

---

## 代码示例

### 完整示例：创建并注册拦截器

```python
# plugins/my_plugin/main.py

from src.plugins.interceptor import MessageInterceptor, InterceptorResult
from typing import Dict, Any, Optional

class MyInterceptor(MessageInterceptor):
    """我的消息拦截器"""
    
    def __init__(self, plugin_id: str):
        # 优先级50 - 中等优先级
        super().__init__(plugin_id, priority=50)
        self.blocked_words = ['spam', 'ad']
    
    async def intercept_message(
        self,
        action: str,
        params: Dict[str, Any],
        source_plugin: Optional[str] = None
    ) -> InterceptorResult:
        """拦截消息"""
        
        # 只处理群消息
        if action != 'send_group_msg':
            return InterceptorResult(allow=True)
        
        message = params.get('message', '')
        
        # 检查敏感词
        for word in self.blocked_words:
            if word in message.lower():
                # 阻止消息
                return InterceptorResult(
                    allow=False,
                    block_reason=f"包含敏感词: {word}"
                )
        
        # 修改消息（添加前缀）
        modified_params = params.copy()
        modified_params['message'] = f"[已审核] {message}"
        
        return InterceptorResult(
            allow=True,
            modified_data=modified_params
        )


class MyPlugin:
    """插件类"""
    
    def __init__(self, api, config):
        self.api = api
        self.config = config
        self.plugin_name = "author/my-plugin"
        self.interceptor = None
    
    async def on_load(self):
        """插件加载时调用"""
        # 创建拦截器
        self.interceptor = MyInterceptor(self.plugin_name)
        
        # 注册拦截器
        self.api.register_message_interceptor(self.interceptor)
        
        print(f"✅ 拦截器已注册: {self.plugin_name}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        # 取消注册
        self.api.unregister_message_interceptor()
        
        print(f"❌ 拦截器已取消注册: {self.plugin_name}")


# 插件入口点
async def create_plugin(api, config):
    plugin = MyPlugin(api, config)
    await plugin.on_load()
    return plugin
```

### 查看已注册的拦截器

```python
# 在主进程中

# 获取connector实例（通常在app中）
connector = app.plugin_connector
registry = connector.interceptor_registry

# 方法1: 获取所有拦截器
interceptors = registry.get_message_interceptors()
print(f"已注册 {len(interceptors)} 个消息拦截器:")
for i in interceptors:
    print(f"  - {i.plugin_id} (优先级: {i.priority})")

# 方法2: 获取统计信息
summary = registry.get_stats_summary()
print(f"\n统计信息:")
print(f"  执行模式: {summary['execution_mode']}")
print(f"  消息拦截器: {summary['message_interceptors']}")
print(f"  事件拦截器: {summary['event_interceptors']}")

# 方法3: 查看性能统计
for stat in summary['interceptor_stats']:
    print(f"\n{stat['plugin_id']}:")
    print(f"  调用次数: {stat['total_calls']}")
    print(f"  成功率: {stat['success_rate']:.1f}%")
    print(f"  平均耗时: {stat['avg_execution_time']:.3f}s")
    print(f"  熔断器: {'开启' if stat['circuit_breaker_open'] else '关闭'}")
```

---

## 关键要点

### ✅ 拦截器是如何获取的？

1. **存储位置**:
   - 主进程: `connector.interceptor_registry._message_interceptors` (List)
   - 插件进程: `runtime._interceptors` (Dict)

2. **获取方式**:
   ```python
   # 主进程
   registry.get_message_interceptors()  # 返回List[MessageInterceptor]
   registry.get_stats_summary()         # 返回统计信息Dict
   
   # 插件进程（一般不需要）
   runtime._interceptors.get(plugin_id)  # 返回该插件的拦截器
   ```

### ✅ 拦截器是如何注册的？

1. **插件侧**:
   ```python
   # 1. 创建拦截器类
   class MyInterceptor(MessageInterceptor): ...
   
   # 2. 在on_load()中注册
   self.api.register_message_interceptor(MyInterceptor(...))
   ```

2. **内部流程**:
   - 插件进程存储拦截器实例
   - 发送注册消息到主进程（通过stdio）
   - 主进程创建代理拦截器（ProxyMessageInterceptor）
   - 代理拦截器注册到InterceptorRegistry
   - 按优先级排序

### ✅ 拦截器是如何执行的？

1. **触发时机**: 当插件调用消息发送API时（`send_group_msg`等）

2. **执行流程**:
   - 主进程检测到消息发送API调用
   - 调用 `registry.intercept_message()`
   - 按优先级组执行所有拦截器
   - 代理拦截器通过stdio与插件进程通信
   - 插件进程执行实际的拦截逻辑
   - 结果返回主进程
   - 决定是否允许/修改消息

3. **性能优化**:
   - 同优先级并发执行（HYBRID模式）
   - 自适应超时
   - 熔断器保护
   - 性能统计

---

## 调试技巧

### 查看拦截器是否注册

```bash
# 查看日志
grep "register_interceptor\|Registered message interceptor" logs/onebot_framework.log

# 应该看到类似：
# Registering interceptor for plugin: author/plugin-name, priority: 50
# ✅ 拦截器已注册: author/plugin-name
```

### 查看拦截器执行情况

```bash
# 查看拦截器执行日志
grep "Running interceptors" logs/onebot_framework.log

# 应该看到：
# Running interceptors for send_group_msg from author/plugin-name, registered: 1
```

### 查看拦截器性能

在代码中添加：

```python
# 在主进程中
registry = app.plugin_connector.interceptor_registry
summary = registry.get_stats_summary()

import json
print(json.dumps(summary, indent=2, ensure_ascii=False))
```

---

**文档版本**: v2.0  
**更新日期**: 2026-02-22  
**相关文件**:
- `src/plugins/interceptor.py` - 拦截器注册表和执行逻辑
- `src/plugins/runtime/connector.py` - 主进程连接器和代理
- `src/plugins/runtime/main.py` - 插件进程运行时
- `src/plugins/runtime/plugin_api.py` - 插件API接口

