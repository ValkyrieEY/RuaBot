# 插件 API 参考

{ Chinese | [English](04-api-reference.md) }

> **文档版本**: v2.0  
> **更新日期**: 2026-01-23  
> **难度等级**: 中级
> **阅读时间**: 30 分钟

## 文档导航

1. [插件系统概述](01-overview_CN.md)
2. [快速开始](02-quickstart_CN.md)
3. [插件系统架构](03-architecture_CN.md)
4. **[插件 API 参考](04-api-reference_CN.md)** ← 当前文档
5. [OneBot API 使用](05-onebot-guide_CN.md)
6. [配置与数据管理](06-config-data_CN.md)
7. [前端 UI 集成](07-ui-integration_CN.md)
8. [高级特性](08-advanced-features_CN.md)
9. [最佳实践与示例](09-best-practices_CN.md)

---

## API 概览

PluginAPI 提供以下分类的方法：

| 分类 | 说明 | 方法数 |
|------|------|--------|
| [消息API](#消息-api) | 发送消息、图片、语音等 | 10+ |
| [OneBot API](#onebot-api) | 调用任意 OneBot API | 40+ |
| [配置API](#配置-api) | 读写插件配置 | 2 |
| [存储API](#存储-api) | 二进制数据持久化 | 4 |
| [事件API](#事件-api) | 发送自定义事件 | 1 |
| [工具API](#工具-api) | 日志、获取插件信息 | 2 |

---

## 消息 API

### send_message()

发送消息（通用方法）。

```python
async def send_message(
    message_type: str,
    target_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `message_type` | str | 消息类型：`'private'` 或 `'group'` |  |
| `target_id` | int | 目标 ID（QQ 号或群号） |  |
| `message` | str | 消息内容（支持 CQ 码） |  |
| `auto_escape` | bool | 是否转义 CQ 码（默认 False） |  |

**返回值：**

```python
{
  'success': True,          # 是否成功
  'data': {
    'message_id': 12345     # 消息 ID
  }
}
```

**示例：**

```python
# 发送群消息
result = await api.send_message('group', 123456, '你好')

# 发送私聊消息
result = await api.send_message('private', 789, '你好')

# 发送带 CQ 码的消息
result = await api.send_message('group', 123456, '[CQ:at,qq=789]你好')
```

---

### send_group_msg()

发送群消息（快捷方法）。

```python
async def send_group_msg(
    group_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `group_id` | int | 群号 |  |
| `message` | str | 消息内容（支持 CQ 码） |  |
| `auto_escape` | bool | 是否转义 CQ 码（默认 False） |  |

**示例：**

```python
# 发送纯文本
await api.send_group_msg(123456, '你好世界')

# 发送图片
await api.send_group_msg(123456, '[CQ:image,file=https://example.com/image.jpg]')

# @ 某人
await api.send_group_msg(123456, '[CQ:at,qq=789]你好')

# 回复某条消息
await api.send_group_msg(123456, '[CQ:reply,id=12345]收到')
```

---

### send_private_msg()

发送私聊消息（快捷方法）。

```python
async def send_private_msg(
    user_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `user_id` | int | QQ 号 |  |
| `message` | str | 消息内容（支持 CQ 码） |  |
| `auto_escape` | bool | 是否转义 CQ 码（默认 False） |  |

**示例：**

```python
# 发送纯文本
await api.send_private_msg(789, '你好')

# 发送图片
await api.send_private_msg(789, '[CQ:image,file=xxx.jpg]')
```

---

### send_forward_msg()

发送合并转发消息。

```python
async def send_forward_msg(
    message_type: str,
    target_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `message_type` | str | 消息类型：`'private'` 或 `'group'` |  |
| `target_id` | int | 目标 ID |  |
| `nodes` | List[Dict] | 转发节点列表 |  |

**节点格式：**

```python
{
  "type": "node",
  "data": {
    "name": "发送者名称",    # 显示的昵称
    "uin": "10001",        # 显示的 QQ 号
    "content": "消息内容"   # 消息内容（支持CQ码）
  }
}
```

**示例：**

```python
# 创建节点列表
nodes = [
    {
        "type": "node",
        "data": {
            "name": "小明",
            "uin": "10001",
            "content": "今天天气真好"
        }
    },
    {
        "type": "node",
        "data": {
            "name": "小红",
            "uin": "10002",
            "content": "是啊，我们去爬山吧"
        }
    }
]

# 发送到群
await api.send_forward_msg('group', 123456, nodes)

# 发送到私聊
await api.send_forward_msg('private', 789, nodes)
```

---

### send_group_forward_msg()

发送群合并转发（快捷方法）。

```python
async def send_group_forward_msg(
    group_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

---

### send_private_forward_msg()

发送私聊合并转发（快捷方法）。

```python
async def send_private_forward_msg(
    user_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

---

### delete_msg()

撤回消息。

```python
async def delete_msg(message_id: int) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `message_id` | int | 消息 ID |  |

**示例：**

```python
# 发送消息
result = await api.send_group_msg(123456, '这是一条测试消息')
message_id = result['data']['message_id']

# 撤回消息
await api.delete_msg(message_id)
```

---

### get_msg()

获取消息详情。

```python
async def get_msg(message_id: int) -> Dict[str, Any]
```

**返回值：**

```python
{
  'success': True,
  'data': {
    'time': 1640000000,
    'message_type': 'group',
    'message_id': 12345,
    'real_id': 12345,
    'sender': {
      'user_id': 789,
      'nickname': '昵称',
      'card': '群名片'
    },
    'message': [...]  # 消息段数组
  }
}
```

---

## OneBot API

### call_api()

调用任意 OneBot API（万能方法）。

```python
async def call_api(
    action: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `action` | str | API 动作名称 |  |
| `params` | Dict | API 参数字典 |  |

**返回值：**

```python
{
  'success': True,      # 是否成功
  'data': {...}         # API 返回的数据
}
```

**示例：**

```python
# 获取群列表
result = await api.call_api('get_group_list')
groups = result['data']

# 获取群成员列表
result = await api.call_api('get_group_member_list', {
    'group_id': 123456
})
members = result['data']

# 禁言群成员
result = await api.call_api('set_group_ban', {
    'group_id': 123456,
    'user_id': 789,
    'duration': 600  # 10分钟
})
```

---

### 快捷 API 方法

以下方法是常用 OneBot API 的快捷封装。

#### get_group_list()

获取群列表。

```python
async def get_group_list() -> Dict[str, Any]
```

**示例：**

```python
result = await api.get_group_list()
if result['success']:
    for group in result['data']:
        print(f"群号: {group['group_id']}, 群名: {group['group_name']}")
```

---

#### get_group_info()

获取群信息。

```python
async def get_group_info(
    group_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

**返回数据：**

```python
{
  'group_id': 123456,
  'group_name': '群名',
  'member_count': 100,
  'max_member_count': 500
}
```

---

#### get_group_member_list()

获取群成员列表。

```python
async def get_group_member_list(group_id: int) -> Dict[str, Any]
```

**返回数据：**

```python
[
  {
    'user_id': 789,
    'nickname': '昵称',
    'card': '群名片',
    'role': 'member',  # owner/admin/member
    'join_time': 1640000000,
    'last_sent_time': 1640000000
  },
  ...
]
```

---

#### get_group_member_info()

获取群成员信息。

```python
async def get_group_member_info(
    group_id: int,
    user_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

---

#### get_friend_list()

获取好友列表。

```python
async def get_friend_list() -> Dict[str, Any]
```

---

#### get_stranger_info()

获取陌生人信息。

```python
async def get_stranger_info(
    user_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

---

#### send_like()

给好友点赞。

```python
async def send_like(
    user_id: int,
    times: int = 1
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 | 范围 |
|------|------|------|------|
| `user_id` | int | QQ 号 | - |
| `times` | int | 点赞次数 | 1-10 |

**示例：**

```python
# 点赞 10 次
await api.send_like(789, times=10)
```

---

#### set_group_kick()

踢出群成员。

```python
async def set_group_kick(
    group_id: int,
    user_id: int,
    reject_add_request: bool = False
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `group_id` | int | 群号 |
| `user_id` | int | 要踢的 QQ 号 |
| `reject_add_request` | bool | 是否拒绝再次申请 |

---

#### set_group_ban()

禁言群成员。

```python
async def set_group_ban(
    group_id: int,
    user_id: int,
    duration: int = 1800
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `group_id` | int | 群号 |
| `user_id` | int | QQ 号 |
| `duration` | int | 禁言时长（秒），0 表示取消禁言 |

**示例：**

```python
# 禁言 10 分钟
await api.set_group_ban(123456, 789, duration=600)

# 取消禁言
await api.set_group_ban(123456, 789, duration=0)
```

---

#### set_group_whole_ban()

全员禁言。

```python
async def set_group_whole_ban(
    group_id: int,
    enable: bool = True
) -> Dict[str, Any]
```

---

#### set_group_admin()

设置群管理员。

```python
async def set_group_admin(
    group_id: int,
    user_id: int,
    enable: bool = True
) -> Dict[str, Any]
```

---

#### set_group_card()

设置群名片。

```python
async def set_group_card(
    group_id: int,
    user_id: int,
    card: str = ""
) -> Dict[str, Any]
```

---

#### set_group_name()

设置群名。

```python
async def set_group_name(
    group_id: int,
    group_name: str
) -> Dict[str, Any]
```

---

#### set_group_leave()

退出群。

```python
async def set_group_leave(
    group_id: int,
    is_dismiss: bool = False
) -> Dict[str, Any]
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `group_id` | int | 群号 |
| `is_dismiss` | bool | 是否解散（仅群主可用） |

---

#### get_login_info()

获取登录号信息。

```python
async def get_login_info() -> Dict[str, Any]
```

**返回数据：**

```python
{
  'user_id': 123456,
  'nickname': 'Bot昵称'
}
```

---

#### get_status()

获取运行状态。

```python
async def get_status() -> Dict[str, Any]
```

---

#### get_version_info()

获取版本信息。

```python
async def get_version_info() -> Dict[str, Any]
```

---

## 配置 API

### get_config()

获取插件配置。

```python
async def get_config(key: Optional[str] = None) -> Any
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `key` | str | 配置键（为 None 时返回全部配置） |  |

**返回值：**

- 如果指定 `key`：返回对应的配置值，不存在则返回 `None`
- 如果不指定 `key`：返回完整的配置字典

**示例：**

```python
# 获取完整配置
config = await api.get_config()
print(config)  # {'api_key': 'xxx', 'enabled': True}

# 获取单个配置项
api_key = await api.get_config('api_key')
print(api_key)  # 'xxx'

# 获取不存在的配置
value = await api.get_config('non_exist')
print(value)  # None
```

---

### set_config()

设置插件配置。

```python
async def set_config(key: str, value: Any) -> bool
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `key` | str | 配置键 |  |
| `value` | Any | 配置值（可序列化为 JSON） |  |

**返回值：**

- `True`: 设置成功
- `False`: 设置失败

**示例：**

```python
# 设置字符串
await api.set_config('api_key', 'new_api_key')

# 设置数字
await api.set_config('max_count', 100)

# 设置布尔值
await api.set_config('enabled', True)

# 设置列表
await api.set_config('admins', [123, 456, 789])

# 设置字典
await api.set_config('settings', {
    'theme': 'dark',
    'language': 'zh-CN'
})
```

**注意事项：**

1. 配置会自动保存到数据库
2. 配置值必须可序列化为 JSON
3. 不支持存储二进制数据（请使用存储 API）

---

## 存储 API

存储 API 用于持久化二进制数据（如图片、文件等）。

### get_storage()

获取二进制存储。

```python
async def get_storage(key: str) -> Optional[bytes]
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `key` | str | 存储键 |  |

**返回值：**

- 成功：返回二进制数据（`bytes`）
- 失败或不存在：返回 `None`

**示例：**

```python
# 读取数据
data_bytes = await api.get_storage('user_data')
if data_bytes:
    import json
    data = json.loads(data_bytes.decode('utf-8'))
    print(data)
else:
    print("数据不存在")
```

---

### set_storage()

设置二进制存储。

```python
async def set_storage(key: str, value: bytes) -> bool
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `key` | str | 存储键 |  |
| `value` | bytes | 二进制数据 |  |

**返回值：**

- `True`: 存储成功
- `False`: 存储失败

**示例：**

```python
# 存储 JSON 数据
import json
data = {'count': 100, 'users': [123, 456]}
data_bytes = json.dumps(data).encode('utf-8')
await api.set_storage('user_data', data_bytes)

# 存储图片
with open('image.jpg', 'rb') as f:
    image_bytes = f.read()
await api.set_storage('cached_image', image_bytes)
```

**注意事项：**

1. 推荐单个存储项不超过 10MB
2. 数据会自动压缩存储
3. 支持任意二进制数据

---

### delete_storage()

删除二进制存储。

```python
async def delete_storage(key: str) -> bool
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `key` | str | 存储键 |  |

**返回值：**

- `True`: 删除成功
- `False`: 删除失败或不存在

**示例：**

```python
# 删除数据
success = await api.delete_storage('user_data')
if success:
    print("删除成功")
```

---

### list_storage_keys()

列出所有存储键。

```python
async def list_storage_keys() -> List[str]
```

**返回值：**

存储键列表（`List[str]`）

**示例：**

```python
# 列出所有键
keys = await api.list_storage_keys()
print(f"共有 {len(keys)} 个存储项:")
for key in keys:
    print(f"- {key}")
```

---

## 事件 API

### emit_event()

发送自定义事件。

```python
async def emit_event(event_name: str, data: Dict[str, Any])
```

**参数：**

| 参数 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `event_name` | str | 事件名称（会自动加前缀） |  |
| `data` | Dict | 事件数据 |  |

**事件命名：**

实际发送的事件名称为：`plugin.<plugin_name>.<event_name>`

例如：插件 `my_plugin` 发送事件 `data_updated`，实际事件名为 `plugin.my_plugin.data_updated`

**示例：**

```python
# 插件 A 发送事件
await api.emit_event('user_joined', {
    'user_id': 789,
    'group_id': 123456
})

# 插件 B 监听事件
async def on_event(self, event_name, data):
    if event_name == 'plugin.plugin_a.user_joined':
        user_id = data['user_id']
        group_id = data['group_id']
        # 处理事件
```

---

## 工具 API

### log()

记录日志。

```python
def log(level: str, message: str, **kwargs)
```

**参数：**

| 参数 | 类型 | 说明 | 可选值 |
|------|------|------|--------|
| `level` | str | 日志级别 | `'debug'`, `'info'`, `'warning'`, `'error'` |
| `message` | str | 日志消息 | - |
| `**kwargs` | Any | 额外的上下文信息 | - |

**示例：**

```python
# 信息日志
api.log('info', '插件已启动')

# 警告日志
api.log('warning', f'用户 {user_id} 尝试非法操作')

# 错误日志
api.log('error', f'API 调用失败: {error}')

# 调试日志（带上下文）
api.log('debug', '处理消息', user_id=789, group_id=123456)
```

---

### get_plugin_name()

获取插件名称。

```python
def get_plugin_name() -> str
```

**返回值：**

插件名称（格式：`author/name`）

**示例：**

```python
plugin_name = api.get_plugin_name()
print(f"当前插件: {plugin_name}")  # 输出：当前插件: XQNEXT/my_plugin
```

---

## API 最佳实践

### 1. 错误处理

始终检查 API 返回值：

```python
result = await api.send_group_msg(group_id, message)
if result['success']:
    message_id = result['data']['message_id']
    api.log('info', f'消息发送成功: {message_id}')
else:
    error = result.get('error', 'Unknown error')
    api.log('error', f'消息发送失败: {error}')
```

### 2. 使用快捷方法

优先使用快捷方法而不是 `call_api`：

```python
#  推荐：使用快捷方法
await api.send_group_msg(group_id, message)

#  不推荐：使用 call_api
await api.call_api('send_group_msg', {'group_id': group_id, 'message': message})
```

### 3. 配置缓存

缓存常用配置避免频繁读取：

```python
class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        self.api_key = config.get('api_key')  # 从初始配置获取
    
    async def on_load(self):
        # 如果需要最新配置，再从数据库读取
        fresh_config = await self.api.get_config()
        self.api_key = fresh_config.get('api_key')
```

### 4. 存储数据序列化

使用 JSON 序列化复杂数据：

```python
import json

# 保存
data = {'users': [123, 456], 'count': 100}
await api.set_storage('data', json.dumps(data).encode('utf-8'))

# 读取
data_bytes = await api.get_storage('data')
if data_bytes:
    data = json.loads(data_bytes.decode('utf-8'))
```

### 5. 日志分级

根据重要程度选择日志级别：

```python
# debug: 调试信息
api.log('debug', f'处理消息: {raw_message}')

# info: 普通信息
api.log('info', '插件已初始化')

# warning: 警告（不影响运行）
api.log('warning', '配置项缺失，使用默认值')

# error: 错误（影响功能）
api.log('error', f'API 调用失败: {error}')
```

---

## 下一步

现在你已经掌握了所有插件 API，接下来可以：

1.  [学习 OneBot API 的详细使用](05-onebot-guide_CN.md)
2.  [深入了解配置与数据管理](06-config-data_CN.md)
3.  [学习前端 UI 集成](07-ui-integration_CN.md)

---

**上一篇**: [← 插件系统架构](03-architecture_CN.md)  
**下一篇**: [OneBot API 使用 →](05-onebot-guide_CN.md)
