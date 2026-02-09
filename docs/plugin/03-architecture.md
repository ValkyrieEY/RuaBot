# Plugin System Architecture

{ [Chinese](03-architecture_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Advanced
> **Read Time**: 20 Minutes

## Document Navigation

1. [Plugin System Overview](01-overview.md)
2. [Quick Start](02-quickstart.md)
3. **[Plugin System Architecture](03-architecture.md)** ← Current
4. [Plugin API Reference](04-api-reference.md)
5. [OneBot API Guide](05-onebot-guide.md)
6. [Configuration & Data Management](06-config-data.md)
7. [Frontend UI Integration](07-ui-integration.md)
8. [Advanced Features](08-advanced-features.md)
9. [Best Practices & Examples](09-best-practices.md)

---

## Learning Objectives

By the end of this chapter, you will understand:

-  Overall architecture design of the plugin system
-  Implementation principle of process isolation
-  Communication methods between plugins and framework
-  Event flow mechanism
-  Plugin loading and lifecycle management

---

## Overall Architecture Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                        XQNEXT Framework                       │
│                                                               │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │   OneBot    │   │  Event Bus   │   │   Web UI / API     │  │
│  │   Adapter   │   │              │   │                    │  │
│  │             │   │  - Publish   │   │  - Manage Plugins  │  │
│  │  - HTTP     │   │  - Subscribe │   │  - Manage Config   │  │
│  │  - WS       │   │  - Route     │   │  - Monitor Status  │  │
│  └──────┬──────┘   └───────┬──────┘   └──────────┬─────────┘  │
│         │                  │                      │           │
│         └──────────────────┼──────────────────────┘           │
│                            │                                  │
│              ┌─────────────▼──────────────┐                   │
│              │  Plugin Runtime Connector  │                   │
│              │                            │                   │
│              │  - Process Mgmt            │                   │
│              │  - stdio Comm              │                   │
│              │  - Event Forward           │                   │
│              │  - API Bridge              │                   │
│              │  - Interceptor Reg         │                   │
│              └─────────────┬──────────────┘                   │
│            ┌───────────────┼──────────────────────────────────┘
│            │               │ (stdio - JSON over pipes)
│  ┌─────────▼───────────────▼────────────┐
│  │  Plugin Runtime                      │
│  │  (Independent Python Process)        │
│  │                                      │
│  │  - Plugin Loader                     │
│  │  - Event Dispatcher                  │
│  │  - API Proxy                         │
│  │  - Plugin Isolation                  │
│  └───────────┬──────────────────────────┘
│              │
│        ┌─────┴────────────┐
│        │                  │
│  ┌─────▼─────┐      ┌─────▼─────┐      ┌────▼──────┐
│  │ Plugin A  │      │ Plugin B  │      │ Plugin C  │
│  │           │      │           │      │           │
│  │ PluginAPI │      │ PluginAPI │      │ PluginAPI │
│  └───────────┘      └───────────┘      └───────────┘
```

---

## Core Components Detail

### 1. OneBot Adapter

**Responsibilities:**
- Connect to OneBot implementation (go-cqhttp, Lagrange, etc.)
- Receive and parse OneBot events
- Send OneBot API requests
- Support multiple connection methods (HTTP, WebSocket, Reverse WebSocket)

**Code Location:** `src/protocol/onebot.py`

```python
class OneBotAdapter:
    """OneBot Protocol Adapter"""
    
    async def start(self):
        """Start Adapter"""
        # Establish connection
        # Register event handlers
    
    async def call_api(self, action: str, params: dict):
        """Call OneBot API"""
        # Build request
        # Send request
        # Return result
    
    def on_event(self, handler):
        """Register Event Handler"""
        self.event_handler = handler
```

**Event Flow:**

```
OneBot Impl → OneBot Adapter → Event Bus → Plugin Runtime → Plugins
```

---

### 2. Event Bus

**Responsibilities:**
- Event publishing and subscription
- Event routing
- Event priority management
- Asynchronous event distribution

**Code Location:** `src/core/event_bus.py`

```python
class EventBus:
    """Event Bus"""
    
    def subscribe(self, event_name: str, handler: Callable):
        """Subscribe to Event"""
        # Register event handler
    
    async def emit(self, event_name: str, data: dict):
        """Emit Event"""
        # Call all subscribers
    
    async def publish(self, event_name: str, payload: dict, source: str):
        """Publish Event (with metadata)"""
        # Create Event object
        # Call emit
```

**Event Types:**

| Event Name | Description | Data Format |
|------------|-------------|-------------|
| `onebot.message` | Message Event | OneBot Message Event Format |
| `onebot.notice` | Notice Event | OneBot Notice Event Format |
| `onebot.request` | Request Event | OneBot Request Event Format |
| `plugin.<name>.*` | Plugin Custom Event | Plugin Defined |

---

### 3. Plugin Runtime Connector

**Responsibilities:**
- Start and manage plugin runtime process
- stdio communication (Standard Input/Output)
- Message serialization/deserialization
- API request proxying
- Plugin lifecycle management

**Code Location:** `src/plugins/runtime/connector.py`

#### 3.1 Process Management

```python
class PluginRuntimeConnector:
    """Plugin Runtime Connector"""
    
    async def _start_runtime_process(self):
        """Start Plugin Runtime Process"""
        self.runtime_process = await asyncio.create_subprocess_exec(
            sys.executable,  # Python Interpreter
            str(self.runtime_script),  # runtime/main.py
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        # Start read task
        self.runtime_task = asyncio.create_task(self._read_runtime_output())
```

#### 3.2 stdio Communication Protocol

**Message Format:**

```json
{
  "type": "message_type",
  "data": {
    // Message Data
  }
}
```

**Message Types (Framework → Runtime):**

| Type | Description | Data |
|------|-------------|------|
| `init_plugins` | Initialize Plugins | Plugin list and config |
| `reload_plugin` | Reload Plugin | Plugin name and config |
| `unload_plugin` | Unload Plugin | Plugin name |
| `event` | Forward Event | Event name and data |
| `heartbeat` | Heartbeat Check | Empty |
| `api_response` | API Response | Request ID and result |

**Message Types (Runtime → Framework):**

| Type | Description | Data |
|------|-------------|------|
| `log` | Log Message | Level, message, plugin |
| `event` | Send Event | Event name and data |
| `heartbeat` | Heartbeat Response | Empty |
| `api_call` | API Request | Request ID, action, params |

#### 3.3 Example Communication Flow

**Plugin sends group message:**

```
Plugin                Runtime              Connector            OneBot
  │                     │                      │                   │
  ├─ send_group_msg ───→│                      │                   │
  │                     ├─ api_call ──────────→│                   │
  │                     │  {                   │                   │
  │                     │    type: "api_call", │                   │
  │                     │    data: {           │                   │
  │                     │      request_id: ...,│                   │
  │                     │      action: "...",  │                   │
  │                     │      params: {...}   │                   │
  │                     │    }                 │                   │
  │                     │  }                   ├─ call_api ───────→│
  │                     │                      │                   │
  │                     │                      │←─ response ───────┤
  │                     │←─ api_response ──────┤                   │
  │←─ result ───────────┤                      │                   │
```

---

### 4. Plugin Runtime

**Responsibilities:**
- Load and manage plugin instances
- Event dispatch
- API proxy
- Plugin isolation

**Code Location:** `src/plugins/runtime/main.py`

#### 4.1 Plugin Loading Flow

```python
class PluginRuntime:
    """Plugin Runtime"""
    
    async def init_plugins(self, plugins: List[Dict]):
        """Initialize Plugins"""
        for plugin_config in plugins:
            # 1. Read plugin.json
            plugin_metadata = self._read_plugin_json(plugin_name)
            
            # 2. Load Python Module
            module = self._load_plugin_module(plugin_name, entry_file)
            
            # 3. Create PluginAPI Wrapper
            plugin_api = PluginAPI(self, plugin_id)
            
            # 4. Merge Config
            config = {**default_config, **db_config}
            
            # 5. Call create_plugin
            if hasattr(module, 'create_plugin'):
                plugin_instance = await module.create_plugin(plugin_api, config)
            
            # 6. Store Plugin Instance
            self.plugins[plugin_id] = plugin_instance
```

#### 4.2 Event Dispatch

```python
async def handle_event(self, data: Dict):
    """Handle Event"""
    event_name = data.get('event')
    event_data = data.get('data', {})
    
    # Dispatch to all plugins
    for plugin_id, plugin_instance in self.plugins.items():
        try:
            if hasattr(plugin_instance, 'on_event'):
                await plugin_instance.on_event(event_name, event_data)
        except Exception as e:
            self.log("error", f"Plugin {plugin_id} error handling event: {e}")
```

---

### 5. PluginAPI

**Responsibilities:**
- Provide unified API interface
- Encapsulate common operations
- Handle errors and retries
- Data format conversion

**Code Location:** `src/plugins/runtime/plugin_api.py` (Framework side)

**Main API Categories:**

```python
class PluginAPI:
    """Plugin API Interface"""
    
    # ==================== OneBot API ====================
    async def call_api(self, action: str, params: dict) -> dict:
        """Call arbitrary OneBot API"""
    
    async def send_message(self, message_type: str, target_id: int, message: str):
        """Send message (Generic)"""
    
    async def send_group_msg(self, group_id: int, message: str):
        """Send group message (Shortcut)"""
    
    async def send_private_msg(self, user_id: int, message: str):
        """Send private message (Shortcut)"""
    
    # ==================== Config API ====================
    async def get_config(self, key: str = None) -> Any:
        """Get plugin config"""
    
    async def set_config(self, key: str, value: Any) -> bool:
        """Set plugin config"""
    
    # ==================== Storage API ====================
    async def get_storage(self, key: str) -> Optional[bytes]:
        """Get binary storage"""
    
    async def set_storage(self, key: str, value: bytes) -> bool:
        """Set binary storage"""
    
    # ==================== Event API ====================
    async def emit_event(self, event_name: str, data: dict):
        """Emit custom event"""
    
    # ==================== Utility API ====================
    def log(self, level: str, message: str, **kwargs):
        """Log message"""
```

---

## Process Isolation Principle

### Why Process Isolation?

1. **Stability**: Plugin crashes do not affect the framework.
2. **Security**: Limit plugin permission scope.
3. **Isolation**: Plugins do not interfere with each other.
4. **Flexibility**: Support different dependency versions.

### Implementation

```python
# Start independent process
process = await asyncio.create_subprocess_exec(
    sys.executable,         # Python Interpreter
    'runtime/main.py',      # Runtime script
    stdin=PIPE,            # Standard Input (Send messages)
    stdout=PIPE,           # Standard Output (Receive messages)
    stderr=PIPE,           # Standard Error (Error logs)
)
```

### Communication Mechanism

**stdin/stdout JSON Protocol:**

```python
# Send message to plugin runtime
def _send_to_runtime(self, message: dict):
    json_str = json.dumps(message)
    self.runtime_process.stdin.write(json_str.encode() + b'\n')

# Read message from plugin runtime
async def _read_runtime_output(self):
    async for line in self.runtime_process.stdout:
        message = json.loads(line.decode())
        await self._handle_runtime_message(message)
```

---

## Event Flow Detail

### Complete Event Flow

```
┌────────────┐
│  QQ Msg    │
└─────┬──────┘
      │
      ▼
┌─────────────────┐
│ OneBot Impl     │  (go-cqhttp / Lagrange)
└────────┬────────┘
         │ HTTP/WebSocket
         ▼
┌─────────────────┐
│ OneBot Adapter  │
│                 │
│ - Recv Event    │
│ - Parse Format  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Event Bus       │
│                 │
│ - Pub Event     │
│ - Route Event   │
└────────┬────────┘
         │
         ├──────────────┐
         │              │
         ▼              ▼
┌─────────────────┐  ┌─────────────────┐
│ AI Handler      │  │ Plugin Runtime  │
│ (Optional)      │  │  Connector      │
└─────────────────┘  └────────┬────────┘
                              │ stdio
                              ▼
                     ┌─────────────────┐
                     │ Plugin Runtime  │
                     │                 │
                     │ - Recv Event    │
                     │ - Dispatch      │
                     └────────┬────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │Plugin A  │        │Plugin B  │        │Plugin C  │
    │          │        │          │        │          │
    │on_event()│        │on_event()│        │on_event()│
    └──────────┘        └──────────┘        └──────────┘
```

### Event Object Structure

**OneBot Message Event:**

```python
{
  'time': 1640000000,
  'self_id': 123456,
  'post_type': 'message',
  'message_type': 'group',  # or 'private'
  'sub_type': 'normal',
  'message_id': 12345,
  'user_id': 987654,
  'group_id': 111222,  # Only group message
  'message': [  # Message Segment Array
    {'type': 'text', 'data': {'text': 'Hello'}},
    {'type': 'at', 'data': {'qq': '123456'}}
  ],
  'raw_message': 'Hello[CQ:at,qq=123456]',  # Raw message
  'font': 0,
  'sender': {
    'user_id': 987654,
    'nickname': 'Nickname',
    'card': 'Group Card',  # Only group message
    'role': 'member'   # Only group message: owner/admin/member
  }
}
```

---

## Plugin Lifecycle Management

### State Transition Diagram

```
     [Not Installed]
        │
        │ install/upload
        ▼
     [Installed]
        │
        │ enable
        ▼
     [Loading]
        │
        │ create_plugin()
        ▼
     [Loaded]
        │
        │ on_load()
        ▼
     [Running] ◄────┐
        │          │
        │ reload   │
        ├──────────┘
        │
        │ disable
        ▼
   [Unloading]
        │
        │ on_unload()
        ▼
   [Disabled]
        │
        │ uninstall
        ▼
   [Uninstalled]
```

### Lifecycle Hooks

| Hook | Timing | Purpose |
|------|--------|---------|
| `create_plugin(api, config)` | When creating plugin instance | Initialize plugin object |
| `on_load()` | When plugin loads | Load resources, subscribe to events |
| `on_event(event_name, data)` | When receiving event | Handle event |
| `on_unload()` | When plugin unloads | Clean resources, save data |

### Reload Mechanism

**Hot Reload Flow:**

```python
async def reload_plugin(self, plugin_name: str):
    """Reload Plugin"""
    
    # 1. Unload old instance
    if plugin_id in self.plugins:
        old_instance = self.plugins[plugin_id]
        if hasattr(old_instance, 'on_unload'):
            await old_instance.on_unload()
        del self.plugins[plugin_id]
    
    # 2. Delete module from sys.modules
    module_name = f"plugin_{plugin_name}"
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # 3. Reload module
    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    
    # 4. Create new instance
    plugin_api = PluginAPI(self, plugin_id)
    plugin_instance = await module.create_plugin(plugin_api, config)
    
    # 5. Store new instance
    self.plugins[plugin_id] = plugin_instance
```

---

## Performance Optimization

### 1. Async I/O

All I/O operations use `async/await`:

```python
#  Wrong: Blocking I/O
with open('file.txt', 'r') as f:
    data = f.read()

#  Correct: Async I/O
import aiofiles
async with aiofiles.open('file.txt', 'r') as f:
    data = await f.read()
```

### 2. Thread Pool

Use thread pool for CPU-bound tasks:

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# Execute in thread pool
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(executor, cpu_intensive_task, args)
```

### 3. Event Loop

- Use single event loop to handle all async tasks.
- Avoid blocking event loop.
- Use `asyncio.create_task` for long-running tasks.

### 4. Database Connection Pool

```python
# Use connection pool
engine = create_async_engine(
    database_url,
    pool_size=10,      # Pool size
    max_overflow=20,   # Max overflow connections
)
```

---

## Security Design

### 1. Process Isolation

- Plugins run in independent processes.
- Limit plugin system permissions.
- Prevent plugins from directly accessing framework resources.

### 2. API Permission Control

```python
# Sensitive API needs permission verification
async def call_sensitive_api(self, action: str, params: dict):
    if not self.has_permission(action):
        raise PermissionError(f"Plugin has no permission for {action}")
    return await self._call_api(action, params)
```

### 3. Data Isolation

- Each plugin has independent configuration space.
- Plugin data stored in independent namespace.
- Prevent plugins from accessing other plugins' data.

### 4. Input Validation

```python
# Validate plugin config
def validate_config(config: dict, schema: dict):
    for key, field_schema in schema.items():
        if field_schema.get('required') and key not in config:
            raise ValueError(f"Missing required config: {key}")
        # Validate type, range, etc.
```

---

## Extensibility

### 1. Protocol Adapter

Supports multiple chat protocols:

- OneBot v11 (Current implementation)
- OneBot v12 (Future)
- QQ Official API (Future)

### 2. Event Extension

Supports custom event types:

```python
# Plugin A sends custom event
await api.emit_event("custom_event", {"data": "value"})

# Plugin B listens to custom event
async def on_event(self, event_name, data):
    if event_name == "plugin.plugin_a.custom_event":
        # Handle custom event
```

---

## Fault Handling

### 1. Plugin Crash

```python
try:
    await plugin_instance.on_event(event_name, event_data)
except Exception as e:
    logger.error(f"Plugin {plugin_id} crashed: {e}")
    # Plugin crash does not affect other plugins
```

### 2. Runtime Process Crash

```python
# Monitor runtime process
if self.runtime_process.returncode is not None:
    logger.error("Runtime process crashed, restarting...")
    await self._start_runtime_process()
    await self._reload_all_plugins()
```

### 3. Communication Timeout

```python
# API Call Timeout Handling
try:
    result = await asyncio.wait_for(
        self._call_api(action, params),
        timeout=10.0  # 10 seconds timeout
    )
except asyncio.TimeoutError:
    logger.error(f"API Call Timeout: {action}")
    return {'success': False, 'error': 'Timeout'}
```

---

## Summary

Core design features of XQNEXT Plugin System:

1. **Process Isolation**: Stability and security
2. **Async First**: High performance and high concurrency
3. **Event Driven**: Flexible message processing
4. **Loose Coupling**: Decoupling plugin and framework
5. **Extensible**: Supports multiple extension methods

---

## Next Steps

Now you understand the plugin system architecture, next you can:

1.  [View complete API Reference](04-api-reference.md)
2.  [Learn OneBot API Usage](05-onebot-guide.md)
3.  [Master Configuration & Data Management](06-config-data.md)

---

**Previous**: [← Quick Start](02-quickstart.md)  
**Next**: [Plugin API Reference →](04-api-reference.md)

