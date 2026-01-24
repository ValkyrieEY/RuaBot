# Plugin API Reference

{ [Chinese](04-api-reference_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Intermediate
> **Read Time**: 30 Minutes

## Document Navigation

1. [Plugin System Overview](01-overview.md)
2. [Quick Start](02-quickstart.md)
3. [Plugin System Architecture](03-architecture.md)
4. **[Plugin API Reference](04-api-reference.md)** ← Current
5. [OneBot API Guide](05-onebot-guide.md)
6. [Configuration & Data Management](06-config-data.md)
7. [Frontend UI Integration](07-ui-integration.md)
8. [Advanced Features](08-advanced-features.md)
9. [Best Practices & Examples](09-best-practices.md)

---

## API Overview

PluginAPI provides methods in the following categories:

| Category | Description | Methods |
|----------|-------------|---------|
| [Message API](#message-api) | Send message, image, voice, etc. | 10+ |
| [OneBot API](#onebot-api) | Call arbitrary OneBot API | 40+ |
| [Config API](#config-api) | Read/Write plugin config | 2 |
| [Storage API](#storage-api) | Binary data persistence | 4 |
| [Event API](#event-api) | Emit custom events | 1 |
| [Utility API](#utility-api) | Log, Get plugin info | 2 |

---

## Message API

### send_message()

Send message (Generic method).

```python
async def send_message(
    message_type: str,
    target_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `message_type` | str | Message Type: `'private'` or `'group'` | Yes |
| `target_id` | int | Target ID (QQ ID or Group ID) | Yes |
| `message` | str | Message Content (Support CQ Code) | Yes |
| `auto_escape` | bool | Auto Escape CQ Code (Default False) | No |

**Returns:**

```python
{
  'success': True,          # Success or not
  'data': {
    'message_id': 12345     # Message ID
  }
}
```

**Example:**

```python
# Send group message
result = await api.send_message('group', 123456, 'Hello')

# Send private message
result = await api.send_message('private', 789, 'Hello')

# Send message with CQ Code
result = await api.send_message('group', 123456, '[CQ:at,qq=789]Hello')
```

---

### send_group_msg()

Send group message (Shortcut).

```python
async def send_group_msg(
    group_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `group_id` | int | Group ID | Yes |
| `message` | str | Message Content (Support CQ Code) | Yes |
| `auto_escape` | bool | Auto Escape CQ Code (Default False) | No |

**Example:**

```python
# Send text
await api.send_group_msg(123456, 'Hello World')

# Send image
await api.send_group_msg(123456, '[CQ:image,file=https://example.com/image.jpg]')

# At someone
await api.send_group_msg(123456, '[CQ:at,qq=789]Hello')

# Reply to a message
await api.send_group_msg(123456, '[CQ:reply,id=12345]Received')
```

---

### send_private_msg()

Send private message (Shortcut).

```python
async def send_private_msg(
    user_id: int,
    message: str,
    auto_escape: bool = False
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `user_id` | int | QQ ID | Yes |
| `message` | str | Message Content (Support CQ Code) | Yes |
| `auto_escape` | bool | Auto Escape CQ Code (Default False) | No |

**Example:**

```python
# Send text
await api.send_private_msg(789, 'Hello')

# Send image
await api.send_private_msg(789, '[CQ:image,file=xxx.jpg]')
```

---

### send_forward_msg()

Send merged forward message.

```python
async def send_forward_msg(
    message_type: str,
    target_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `message_type` | str | Message Type: `'private'` or `'group'` | Yes |
| `target_id` | int | Target ID | Yes |
| `nodes` | List[Dict] | Forward Nodes List | Yes |

**Node Format:**

```python
{
  "type": "node",
  "data": {
    "name": "Sender Name",    # Display Nickname
    "uin": "10001",           # Display QQ ID
    "content": "Message"      # Message Content (Support CQ Code)
  }
}
```

**Example:**

```python
# Create node list
nodes = [
    {
        "type": "node",
        "data": {
            "name": "Alice",
            "uin": "10001",
            "content": "Nice weather today"
        }
    },
    {
        "type": "node",
        "data": {
            "name": "Bob",
            "uin": "10002",
            "content": "Yeah, let's go hiking"
        }
    }
]

# Send to group
await api.send_forward_msg('group', 123456, nodes)

# Send to private
await api.send_forward_msg('private', 789, nodes)
```

---

### send_group_forward_msg()

Send group merged forward message (Shortcut).

```python
async def send_group_forward_msg(
    group_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

---

### send_private_forward_msg()

Send private merged forward message (Shortcut).

```python
async def send_private_forward_msg(
    user_id: int,
    nodes: List[Dict[str, Any]]
) -> Dict[str, Any]
```

---

### delete_msg()

Recall a message.

```python
async def delete_msg(message_id: int) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `message_id` | int | Message ID | Yes |

**Example:**

```python
# Send message
result = await api.send_group_msg(123456, 'Test Message')
message_id = result['data']['message_id']

# Recall message
await api.delete_msg(message_id)
```

---

### get_msg()

Get message details.

```python
async def get_msg(message_id: int) -> Dict[str, Any]
```

**Returns:**

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
      'nickname': 'Nickname',
      'card': 'Group Card'
    },
    'message': [...]  # Message Segment Array
  }
}
```

---

## OneBot API

### call_api()

Call arbitrary OneBot API (Universal method).

```python
async def call_api(
    action: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `action` | str | API Action Name | Yes |
| `params` | Dict | API Parameters Dictionary | No |

**Returns:**

```python
{
  'success': True,      # Success or not
  'data': {...}         # API Return Data
}
```

**Example:**

```python
# Get group list
result = await api.call_api('get_group_list')
groups = result['data']

# Get group member list
result = await api.call_api('get_group_member_list', {
    'group_id': 123456
})
members = result['data']

# Ban group member
result = await api.call_api('set_group_ban', {
    'group_id': 123456,
    'user_id': 789,
    'duration': 600  # 10 minutes
})
```

---

### Shortcut API Methods

The following methods are shortcut wrappers for common OneBot APIs.

#### get_group_list()

Get group list.

```python
async def get_group_list() -> Dict[str, Any]
```

**Example:**

```python
result = await api.get_group_list()
if result['success']:
    for group in result['data']:
        print(f"ID: {group['group_id']}, Name: {group['group_name']}")
```

---

#### get_group_info()

Get group info.

```python
async def get_group_info(
    group_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

**Return Data:**

```python
{
  'group_id': 123456,
  'group_name': 'Group Name',
  'member_count': 100,
  'max_member_count': 500
}
```

---

#### get_group_member_list()

Get group member list.

```python
async def get_group_member_list(group_id: int) -> Dict[str, Any]
```

**Return Data:**

```python
[
  {
    'user_id': 789,
    'nickname': 'Nickname',
    'card': 'Card',
    'role': 'member',  # owner/admin/member
    'join_time': 1640000000,
    'last_sent_time': 1640000000
  },
  ...
]
```

---

#### get_group_member_info()

Get group member info.

```python
async def get_group_member_info(
    group_id: int,
    user_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

---

#### get_friend_list()

Get friend list.

```python
async def get_friend_list() -> Dict[str, Any]
```

---

#### get_stranger_info()

Get stranger info.

```python
async def get_stranger_info(
    user_id: int,
    no_cache: bool = False
) -> Dict[str, Any]
```

---

#### send_like()

Send like to friend.

```python
async def send_like(
    user_id: int,
    times: int = 1
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description | Range |
|-----------|------|-------------|-------|
| `user_id` | int | QQ ID | - |
| `times` | int | Times | 1-10 |

**Example:**

```python
# Like 10 times
await api.send_like(789, times=10)
```

---

#### set_group_kick()

Kick group member.

```python
async def set_group_kick(
    group_id: int,
    user_id: int,
    reject_add_request: bool = False
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `group_id` | int | Group ID |
| `user_id` | int | QQ ID to kick |
| `reject_add_request` | bool | Reject join request again |

---

#### set_group_ban()

Ban group member.

```python
async def set_group_ban(
    group_id: int,
    user_id: int,
    duration: int = 1800
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `group_id` | int | Group ID |
| `user_id` | int | QQ ID |
| `duration` | int | Duration (seconds), 0 to lift ban |

**Example:**

```python
# Ban for 10 minutes
await api.set_group_ban(123456, 789, duration=600)

# Lift ban
await api.set_group_ban(123456, 789, duration=0)
```

---

#### set_group_whole_ban()

Ban whole group.

```python
async def set_group_whole_ban(
    group_id: int,
    enable: bool = True
) -> Dict[str, Any]
```

---

#### set_group_admin()

Set group admin.

```python
async def set_group_admin(
    group_id: int,
    user_id: int,
    enable: bool = True
) -> Dict[str, Any]
```

---

#### set_group_card()

Set group card.

```python
async def set_group_card(
    group_id: int,
    user_id: int,
    card: str = ""
) -> Dict[str, Any]
```

---

#### set_group_name()

Set group name.

```python
async def set_group_name(
    group_id: int,
    group_name: str
) -> Dict[str, Any]
```

---

#### set_group_leave()

Leave group.

```python
async def set_group_leave(
    group_id: int,
    is_dismiss: bool = False
) -> Dict[str, Any]
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `group_id` | int | Group ID |
| `is_dismiss` | bool | Dismiss group (Owner only) |

---

#### get_login_info()

Get login info.

```python
async def get_login_info() -> Dict[str, Any]
```

**Return Data:**

```python
{
  'user_id': 123456,
  'nickname': 'Bot Nickname'
}
```

---

#### get_status()

Get status.

```python
async def get_status() -> Dict[str, Any]
```

---

#### get_version_info()

Get version info.

```python
async def get_version_info() -> Dict[str, Any]
```

---

## Config API

### get_config()

Get plugin config.

```python
async def get_config(key: Optional[str] = None) -> Any
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `key` | str | Config Key (None returns all) | No |

**Returns:**

- If `key` specified: Config value, `None` if not exists
- If `key` not specified: Complete config dict

**Example:**

```python
# Get full config
config = await api.get_config()
print(config)  # {'api_key': 'xxx', 'enabled': True}

# Get single config item
api_key = await api.get_config('api_key')
print(api_key)  # 'xxx'

# Get non-existent config
value = await api.get_config('non_exist')
print(value)  # None
```

---

### set_config()

Set plugin config.

```python
async def set_config(key: str, value: Any) -> bool
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `key` | str | Config Key | Yes |
| `value` | Any | Config Value (JSON serializable) | Yes |

**Returns:**

- `True`: Success
- `False`: Failed

**Example:**

```python
# Set string
await api.set_config('api_key', 'new_api_key')

# Set number
await api.set_config('max_count', 100)

# Set boolean
await api.set_config('enabled', True)

# Set list
await api.set_config('admins', [123, 456, 789])

# Set dict
await api.set_config('settings', {
    'theme': 'dark',
    'language': 'en-US'
})
```

**Notes:**

1. Config is automatically saved to database.
2. Value must be JSON serializable.
3. Binary data not supported (Use Storage API).

---

## Storage API

Storage API is used for persisting binary data (like images, files).

### get_storage()

Get binary storage.

```python
async def get_storage(key: str) -> Optional[bytes]
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `key` | str | Storage Key | Yes |

**Returns:**

- Success: Binary data (`bytes`)
- Failed or Not Exists: `None`

**Example:**

```python
# Read data
data_bytes = await api.get_storage('user_data')
if data_bytes:
    import json
    data = json.loads(data_bytes.decode('utf-8'))
    print(data)
else:
    print("Data not found")
```

---

### set_storage()

Set binary storage.

```python
async def set_storage(key: str, value: bytes) -> bool
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `key` | str | Storage Key | Yes |
| `value` | bytes | Binary Data | Yes |

**Returns:**

- `True`: Success
- `False`: Failed

**Example:**

```python
# Store JSON data
import json
data = {'count': 100, 'users': [123, 456]}
data_bytes = json.dumps(data).encode('utf-8')
await api.set_storage('user_data', data_bytes)

# Store image
with open('image.jpg', 'rb') as f:
    image_bytes = f.read()
await api.set_storage('cached_image', image_bytes)
```

**Notes:**

1. Recommended single item size < 10MB.
2. Data is automatically compressed.
3. Supports arbitrary binary data.

---

### delete_storage()

Delete binary storage.

```python
async def delete_storage(key: str) -> bool
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `key` | str | Storage Key | Yes |

**Returns:**

- `True`: Success
- `False`: Failed or Not Exists

**Example:**

```python
# Delete data
success = await api.delete_storage('user_data')
if success:
    print("Deleted successfully")
```

---

### list_storage_keys()

List all storage keys.

```python
async def list_storage_keys() -> List[str]
```

**Returns:**

List of storage keys (`List[str]`)

**Example:**

```python
# List all keys
keys = await api.list_storage_keys()
print(f"Total {len(keys)} items:")
for key in keys:
    print(f"- {key}")
```

---

## Event API

### emit_event()

Emit custom event.

```python
async def emit_event(event_name: str, data: Dict[str, Any])
```

**Parameters:**

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `event_name` | str | Event Name (Auto-prefixed) | Yes |
| `data` | Dict | Event Data | Yes |

**Event Naming:**

Actual emitted event name: `plugin.<plugin_name>.<event_name>`

Example: Plugin `my_plugin` emits `data_updated`, actual name is `plugin.my_plugin.data_updated`.

**Example:**

```python
# Plugin A emits event
await api.emit_event('user_joined', {
    'user_id': 789,
    'group_id': 123456
})

# Plugin B listens event
async def on_event(self, event_name, data):
    if event_name == 'plugin.plugin_a.user_joined':
        user_id = data['user_id']
        group_id = data['group_id']
        # Handle event
```

---

## Utility API

### log()

Log message.

```python
def log(level: str, message: str, **kwargs)
```

**Parameters:**

| Parameter | Type | Description | Values |
|-----------|------|-------------|--------|
| `level` | str | Log Level | `'debug'`, `'info'`, `'warning'`, `'error'` |
| `message` | str | Log Message | - |
| `**kwargs` | Any | Extra Context | - |

**Example:**

```python
# Info Log
api.log('info', 'Plugin started')

# Warning Log
api.log('warning', f'User {user_id} tried illegal operation')

# Error Log
api.log('error', f'API call failed: {error}')

# Debug Log (With context)
api.log('debug', 'Handling message', user_id=789, group_id=123456)
```

---

### get_plugin_name()

Get plugin name.

```python
def get_plugin_name() -> str
```

**Returns:**

Plugin name (Format: `author/name`)

**Example:**

```python
plugin_name = api.get_plugin_name()
print(f"Current Plugin: {plugin_name}")  # Output: Current Plugin: XQNEXT/my_plugin
```

---

## API Best Practices

### 1. Error Handling

Always check API return values:

```python
result = await api.send_group_msg(group_id, message)
if result['success']:
    message_id = result['data']['message_id']
    api.log('info', f'Message sent: {message_id}')
else:
    error = result.get('error', 'Unknown error')
    api.log('error', f'Message failed: {error}')
```

### 2. Use Shortcut Methods

Prefer shortcut methods over `call_api`:

```python
#  Recommended: Use shortcut
await api.send_group_msg(group_id, message)

#  Not Recommended: Use call_api
await api.call_api('send_group_msg', {'group_id': group_id, 'message': message})
```

### 3. Cache Configuration

Cache frequently used config to avoid frequent reads:

```python
class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        self.api_key = config.get('api_key')  # Get from initial config
    
    async def on_load(self):
        # If fresh config needed, read from DB
        fresh_config = await self.api.get_config()
        self.api_key = fresh_config.get('api_key')
```

### 4. Serialize Storage Data

Use JSON to serialize complex data:

```python
import json

# Save
data = {'users': [123, 456], 'count': 100}
await api.set_storage('data', json.dumps(data).encode('utf-8'))

# Read
data_bytes = await api.get_storage('data')
if data_bytes:
    data = json.loads(data_bytes.decode('utf-8'))
```

### 5. Log Levels

Choose log level based on importance:

```python
# debug: Debugging info
api.log('debug', f'Handling message: {raw_message}')

# info: Normal info
api.log('info', 'Plugin initialized')

# warning: Warning (Non-blocking)
api.log('warning', 'Config missing, using default')

# error: Error (Functionality affected)
api.log('error', f'API call failed: {error}')
```

---

## Next Steps

Now you have mastered all Plugin APIs, next you can:

1.  [Learn OneBot API Usage in detail](05-onebot-guide.md)
2.  [Deep dive into Configuration & Data Management](06-config-data.md)
3.  [Learn Frontend UI Integration](07-ui-integration.md)

---

**Previous**: [← Plugin System Architecture](03-architecture.md)  
**Next**: [OneBot API Guide →](05-onebot-guide.md)

