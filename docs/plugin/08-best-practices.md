# 最佳实践与完整示例

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 高级

## 完整插件示例

以下是一个功能完整、生产就绪的插件示例，展示了所有最佳实践。

### plugin.json

```json
{
  "name": "advanced_plugin",
  "version": "2.0.0",
  "author": "XQNEXT",
  "description": "高级插件示例 - 展示所有最佳实践",
  "entry": "main.py",
  "dependencies": [],
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
    "admins": {
      "type": "array",
      "default": [],
      "description": "管理员QQ号列表"
    },
    "max_retry": {
      "type": "number",
      "default": 3,
      "description": "API调用失败时的最大重试次数",
      "min": 1,
      "max": 10
    },
    "cache_ttl": {
      "type": "number",
      "default": 3600,
      "description": "缓存过期时间（秒）",
      "min": 60,
      "max": 86400
    }
  },
  "default_config": {
    "enabled": true,
    "api_key": "",
    "admins": [],
    "max_retry": 3,
    "cache_ttl": 3600
  }
}
```

### main.py

```python
"""高级插件示例

展示所有最佳实践：
- 配置验证
- 数据持久化
- 内存缓存
- 错误处理
- 异步编程
- 权限管理
- 日志记录
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor


class AdvancedPlugin:
    """高级插件类"""
    
    def __init__(self, api, config: Dict[str, Any]):
        """初始化插件
        
        Args:
            api: PluginAPI 对象
            config: 插件配置
        """
        self.api = api
        
        # 验证配置
        self._validate_config(config)
        
        # 读取配置
        self.enabled = config.get('enabled', True)
        self.api_key = config['api_key']  # 必需，已验证
        self.admins = set(config.get('admins', []))
        self.max_retry = config.get('max_retry', 3)
        self.cache_ttl = config.get('cache_ttl', 3600)
        
        # 内存缓存
        self.cache: Dict[str, tuple] = {}  # {key: (value, expire_time)}
        
        # 持久化数据
        self.user_data: Dict[str, Any] = {}
        
        # 线程池（用于CPU密集型任务）
        self.executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="advanced_"
        )
        
        # 定时任务
        self.cleanup_task: Optional[asyncio.Task] = None
    
    def _validate_config(self, config: Dict[str, Any]):
        """验证配置
        
        Args:
            config: 配置字典
            
        Raises:
            ValueError: 配置无效
        """
        # 检查必需字段
        if 'api_key' not in config or not config['api_key']:
            raise ValueError("API密钥不能为空")
        
        # 检查类型和范围
        if 'max_retry' in config:
            max_retry = config['max_retry']
            if not isinstance(max_retry, int) or max_retry < 1 or max_retry > 10:
                raise ValueError("max_retry 必须是 1-10 的整数")
        
        if 'cache_ttl' in config:
            cache_ttl = config['cache_ttl']
            if not isinstance(cache_ttl, int) or cache_ttl < 60:
                raise ValueError("cache_ttl 必须是大于60的整数")
    
    async def on_load(self):
        """插件加载时调用"""
        self.api.log("info", "=" * 50)
        self.api.log("info", "Advanced Plugin 开始加载...")
        
        try:
            # 加载持久化数据
            await self._load_data()
            
            # 启动定时任务
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.api.log("info", f"插件加载成功！配置: enabled={self.enabled}, cache_ttl={self.cache_ttl}")
            self.api.log("info", f"管理员数量: {len(self.admins)}")
            self.api.log("info", f"用户数据数量: {len(self.user_data)}")
            self.api.log("info", "=" * 50)
        except Exception as e:
            self.api.log("error", f"插件加载失败: {e}")
            raise
    
    async def on_unload(self):
        """插件卸载时调用"""
        self.api.log("info", "Advanced Plugin 正在卸载...")
        
        try:
            # 取消定时任务
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # 保存数据
            await self._save_data()
            
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            self.api.log("info", "插件已卸载")
        except Exception as e:
            self.api.log("error", f"插件卸载出错: {e}")
    
    async def on_event(self, event_name: str, data: Dict[str, Any]):
        """处理事件
        
        Args:
            event_name: 事件名称
            data: 事件数据
        """
        # 只处理消息事件
        if event_name == "onebot.message":
            await self.handle_message(data)
    
    async def handle_message(self, event: Dict[str, Any]):
        """处理消息事件
        
        Args:
            event: OneBot 消息事件
        """
        # 检查插件是否启用
        if not self.enabled:
            return
        
        try:
            message_type = event.get('message_type')
            raw_message = event.get('raw_message', '').strip()
            user_id = event['user_id']
            
            # 处理命令
            if raw_message.startswith('/'):
                await self._handle_command(event, raw_message)
        except Exception as e:
            self.api.log("error", f"处理消息失败: {e}")
    
    async def _handle_command(self, event: Dict[str, Any], command: str):
        """处理命令
        
        Args:
            event: 消息事件
            command: 命令字符串
        """
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            await self._cmd_help(event)
        elif cmd == '/stats':
            await self._cmd_stats(event)
        elif cmd == '/cache':
            await self._cmd_cache(event, parts)
        elif cmd == '/admin':
            await self._cmd_admin(event, parts)
    
    async def _cmd_help(self, event: Dict[str, Any]):
        """帮助命令"""
        help_text = """
Advanced Plugin 帮助
━━━━━━━━━━━━━━━━━━━━━━
/help - 显示此帮助
/stats - 显示统计信息
/cache clear - 清空缓存（管理员）
/admin <QQ号> - 添加管理员（需要管理员权限）
━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        await self._send_reply(event, help_text)
    
    async def _cmd_stats(self, event: Dict[str, Any]):
        """统计命令"""
        stats = f"""
插件统计
━━━━━━━━━━━━━━━━━━━━━━
用户数量: {len(self.user_data)}
管理员数量: {len(self.admins)}
缓存项数: {len(self.cache)}
状态: {'启用' if self.enabled else '禁用'}
━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        await self._send_reply(event, stats)
    
    async def _cmd_cache(self, event: Dict[str, Any], parts: List[str]):
        """缓存命令"""
        user_id = event['user_id']
        
        # 检查权限
        if not self._is_admin(user_id):
            await self._send_reply(event, " 权限不足")
            return
        
        if len(parts) < 2 or parts[1] != 'clear':
            await self._send_reply(event, "用法: /cache clear")
            return
        
        # 清空缓存
        count = len(self.cache)
        self.cache.clear()
        await self._send_reply(event, f" 已清空 {count} 个缓存项")
    
    async def _cmd_admin(self, event: Dict[str, Any], parts: List[str]):
        """管理员命令"""
        user_id = event['user_id']
        
        # 检查权限
        if not self._is_admin(user_id):
            await self._send_reply(event, " 权限不足")
            return
        
        if len(parts) < 2:
            await self._send_reply(event, "用法: /admin <QQ号>")
            return
        
        # 添加管理员
        try:
            new_admin = int(parts[1])
            self.admins.add(new_admin)
            
            # 保存到配置
            await self.api.set_config('admins', list(self.admins))
            
            await self._send_reply(event, f" 已添加管理员: {new_admin}")
            self.api.log("info", f"添加管理员: {new_admin} (操作者: {user_id})")
        except ValueError:
            await self._send_reply(event, " QQ号格式错误")
    
    def _is_admin(self, user_id: int) -> bool:
        """检查是否是管理员
        
        Args:
            user_id: QQ 号
            
        Returns:
            是否是管理员
        """
        return user_id in self.admins
    
    async def _send_reply(self, event: Dict[str, Any], message: str):
        """发送回复
        
        Args:
            event: 消息事件
            message: 回复内容
        """
        message_type = event.get('message_type')
        
        if message_type == 'group':
            await self.api.send_group_msg(event['group_id'], message)
        elif message_type == 'private':
            await self.api.send_private_msg(event['user_id'], message)
    
    # ==================== 缓存管理 ====================
    
    def set_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
        """
        if ttl is None:
            ttl = self.cache_ttl
        
        expire_time = datetime.now() + timedelta(seconds=ttl)
        self.cache[key] = (value, expire_time)
    
    def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在或过期则返回 None
        """
        if key not in self.cache:
            return None
        
        value, expire_time = self.cache[key]
        if datetime.now() > expire_time:
            # 过期，删除
            del self.cache[key]
            return None
        
        return value
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expire_time) in self.cache.items()
            if now > expire_time
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self.api.log("debug", f"清理了 {len(expired_keys)} 个过期缓存")
    
    async def _cleanup_loop(self):
        """清理循环（每5分钟执行一次）"""
        while True:
            try:
                await asyncio.sleep(300)  # 5分钟
                self._cleanup_cache()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.api.log("error", f"清理任务出错: {e}")
    
    # ==================== 数据持久化 ====================
    
    async def _load_data(self):
        """加载持久化数据"""
        data_bytes = await self.api.get_storage('user_data')
        if data_bytes:
            try:
                self.user_data = json.loads(data_bytes.decode('utf-8'))
                self.api.log("info", f"已加载 {len(self.user_data)} 个用户数据")
            except Exception as e:
                self.api.log("error", f"加载数据失败: {e}")
                self.user_data = {}
        else:
            self.user_data = {}
    
    async def _save_data(self):
        """保存持久化数据"""
        try:
            data_bytes = json.dumps(self.user_data, ensure_ascii=False).encode('utf-8')
            await self.api.set_storage('user_data', data_bytes)
            self.api.log("info", "数据已保存")
        except Exception as e:
            self.api.log("error", f"保存数据失败: {e}")


# 插件入口点
async def create_plugin(api, config: Dict[str, Any]):
    """创建插件实例
    
    Args:
        api: PluginAPI 对象
        config: 插件配置
        
    Returns:
        插件实例
    """
    plugin = AdvancedPlugin(api, config)
    await plugin.on_load()
    return plugin
```

---

## 代码质量检查清单

###  基础要求
- [ ] 实现 `create_plugin` 函数
- [ ] 实现 `on_load` 和 `on_unload` 方法
- [ ] 实现 `on_event` 方法处理事件
- [ ] 所有异步函数使用 `async def`
- [ ] 所有异步调用使用 `await`

###  配置管理
- [ ] 在 `plugin.json` 中定义 `config_schema`
- [ ] 验证配置的类型和范围
- [ ] 提供合理的默认值
- [ ] 缓存常用配置到内存

###  错误处理
- [ ] 使用 try-except 捕获异常
- [ ] 记录详细的错误日志
- [ ] 向用户返回友好的错误信息
- [ ] 防止插件崩溃影响框架

###  数据管理
- [ ] 在 `on_unload` 中保存数据
- [ ] 使用 JSON 序列化数据
- [ ] 处理数据加载失败的情况
- [ ] 考虑数据迁移和向后兼容

###  性能优化
- [ ] 使用内存缓存减少I/O
- [ ] CPU密集型操作使用线程池
- [ ] 避免阻塞事件循环
- [ ] 并发执行独立任务

###  安全性
- [ ] 验证用户输入
- [ ] 检查权限后执行敏感操作
- [ ] 防止注入攻击
- [ ] 不在日志中输出敏感信息

###  可维护性
- [ ] 代码结构清晰，职责分明
- [ ] 添加适当的注释和文档字符串
- [ ] 使用类型提示
- [ ] 遵循 Python 编码规范（PEP 8）

---

## 常见陷阱

### 1. 忘记 await

```python
#  错误
result = api.send_group_msg(123456, 'test')  # result 是 coroutine，不是结果！

#  正确
result = await api.send_group_msg(123456, 'test')
```

### 2. 阻塞事件循环

```python
#  错误：阻塞5秒
import time
time.sleep(5)

#  正确：异步等待
await asyncio.sleep(5)
```

### 3. 不保存数据

```python
#  错误：数据丢失
def add_user(self, user_id):
    self.users.append(user_id)
    # 没有保存！

#  正确：及时保存
def add_user(self, user_id):
    self.users.append(user_id)
    asyncio.create_task(self._save_data())
```

### 4. 不检查权限

```python
#  错误：任何人都可以执行
async def ban_user(self, event, target_id):
    await self.api.set_group_kick(group_id, target_id)

#  正确：检查权限
async def ban_user(self, event, target_id):
    if not self._is_admin(event['user_id']):
        return "权限不足"
    await self.api.set_group_kick(group_id, target_id)
```

---

**上一篇**: [← 高级特性](07-advanced-features.md)  
**返回目录**: [文档首页](README.md)

: [← 高级特性](07-advanced-features.md)  
**返回目录**: [文档首页](README.md)

