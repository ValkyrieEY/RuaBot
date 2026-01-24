# XQNEXT Plugin System Overview

{ [Chinese](01-overview_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Beginner

## Documentation Navigation

This is the first part of the XQNEXT Plugin Development Series:

1. **[Plugin System Overview](01-overview.md)** ← Current
2. [Quick Start](02-quickstart.md)
3. [Plugin System Architecture](03-architecture.md)
4. [Plugin API Reference](04-api-reference.md)
5. [OneBot API Guide](05-onebot-guide.md)
6. [Configuration & Data Management](06-config-data.md)
7. [Frontend UI Integration](07-ui-integration.md)
8. [Advanced Features](08-advanced-features.md)
9. [Best Practices & Examples](09-best-practices.md)

---

## What is XQNEXT Plugin System

The XQNEXT Plugin System is a **high-performance, isolated, event-driven** plugin architecture that allows developers to extend bot functionality by writing Python plugins.

### Core Features

#### 1. **Process Isolation**
Each plugin runs in an independent process, isolated from others:
- Plugin crashes do not affect the framework.
- Plugins can use their own dependency versions.
- Hot reload does not affect other plugins.

#### 2. **Async First**
Fully adopts `async/await` asynchronous programming:
- High concurrency processing capability.
- Non-blocking I/O operations.
- Built-in thread pool support.

#### 3. **Event Driven**
Responds to messages and status changes via an event system:
- Flexible event subscription mechanism.
- Supports custom events.
- Event priority control.

#### 4. **Complete OneBot API**
Direct access to all OneBot v11 protocol features:
- Send messages, images, voice.
- Group management operations.
- Friend management operations.
- Generic `call_api` to invoke any API.

#### 5. **Data Persistence**
Built-in database support:
- Configuration management.
- Binary storage.
- Automatic serialization.

#### 6. **Web UI Integration**
Plugin configuration can be managed in the Web interface:
- Auto-generate configuration forms.
- Real-time configuration updates.
- Enable/Disable plugins.

---

## Plugin System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    XQNEXT Framework                      │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ OneBot     │  │ Event Bus   │  │  Web UI API     │  │
│  │ Adapter    │  │             │  │                 │  │
│  └──────┬─────┘  └──────┬──────┘  └────────┬────────┘  │
│         │               │                   │            │
│         └───────────────┼───────────────────┘            │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │ Plugin Runtime      │                     │
│              │  Connector          │                     │
│              └──────────┬──────────┘                     │
│            ┌────────────┼──────────────────────────────┐
│            │            │ (stdio IPC)
│  ┌────────▼───────────▼───────────┐
│  │  Plugin Runtime       │
│  │   (Separate Process)  │
│  └───────────┬───────────┘
│              │
│        ┌─────┴─────────────┐
│        │                   │
│  ┌─────▼────┐    ┌────▼─────┐   ┌────▼─────┐
│  │ Plugin A │    │ Plugin B │   │ Plugin C │
│  └──────────┘    └──────────┘   └──────────┘
```

**Communication Methods**:
- **Framework ↔ Plugin Runtime**: stdio (JSON messages)
- **Plugin ↔ Framework**: PluginAPI object
- **Event Flow**: EventBus → Connector → Runtime → Plugins

---

## Plugin Lifecycle

```python
┌──────────────┐
│  Install     │  ← Upload .zip or manually place in plugins/ directory
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Register    │  ← Read plugin.json, write to database
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Load        │  ← Call create_plugin(api, config)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ on_load()    │  ← Initialize resources, load data
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Running     │  ← Receive events, handle messages
│              │
│ on_event()   │  ← Continuous processing
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ on_unload()  │  ← Cleanup resources, save data
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Unload/Reload│
└──────────────┘
```

---

## Plugin Directory Structure

```
plugins/
└── my_plugin/              # Plugin directory
    ├── plugin.json         # Plugin metadata (Required)
    ├── main.py             # Plugin main file (Required)
    ├── config.json         # Runtime config (Auto-generated)
    ├── requirements.txt    # Python dependencies (Optional)
    ├── README.md           # Plugin description (Optional)
    └── ...                 # Other files
```

### `plugin.json` Example

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "An example plugin",
  "entry": "main.py",
  "dependencies": [],
  "default_config": {
    "enabled": true,
    "api_key": ""
  },
  "config_schema": {
    "enabled": {
      "type": "boolean",
      "default": true,
      "description": "Enable Plugin"
    },
    "api_key": {
      "type": "string",
      "default": "",
      "description": "API Key",
      "required": true
    }
  }
}
```

---

## Basic Plugin Example

### Simplest Plugin

```python
# plugins/hello_plugin/main.py

async def create_plugin(api, config):
    """Plugin Entry Point
    
    Args:
        api: PluginAPI object, providing framework interfaces
        config: Plugin configuration dictionary
    
    Returns:
        Plugin instance
    """
    class HelloPlugin:
        def __init__(self, api, config):
            self.api = api
            self.config = config
        
        async def on_load(self):
            """Called when plugin loads"""
            self.api.log("info", "Hello Plugin Loaded!")
        
        async def on_unload(self):
            """Called when plugin unloads"""
            self.api.log("info", "Hello Plugin Unloaded!")
        
        async def on_event(self, event_name, data):
            """Handle Events"""
            if event_name == "onebot.message":
                await self.handle_message(data)
        
        async def handle_message(self, event):
            """Handle Messages"""
            message_type = event.get('message_type')
            raw_message = event.get('raw_message', '')
            
            if raw_message == "hello":
                if message_type == 'group':
                    group_id = event['group_id']
                    await self.api.send_group_msg(group_id, "Hello there!")
                elif message_type == 'private':
                    user_id = event['user_id']
                    await self.api.send_private_msg(user_id, "Hello there!")
    
    plugin = HelloPlugin(api, config)
    await plugin.on_load()
    return plugin
```

---

## What Plugins Can Do

### Message Handling
- Receive group messages, private messages
- Send text, image, voice, video
- Send merged forward messages
- Recall messages

### Group Management
- Kick, mute, set admin
- Change group card, group name
- Get group list, group member list
- Handle join requests

### Data Management
- Save and read configuration
- Store binary data
- Persist plugin state

### Async Tasks
- Scheduled tasks
- Background tasks
- Use thread pool for CPU-bound operations

### Web UI
- Display config options in Web interface
- Dynamic form generation
- Real-time config updates

---

## Why Choose XQNEXT Plugin System

### Comparison with Other Frameworks

| Feature | XQNEXT | NoneBot2 | Mirai |
|---------|--------|----------|-------|
| Process Isolation | Yes | No | No |
| Async Support | Full | Full | Partial |
| Web UI | Built-in | Needs Plugin | 3rd Party |
| Hot Reload | Yes | Yes | Limited |
| Data Persistence | Built-in | Needs Config | Needs Config |
| Thread Pool | Built-in | Manual | Manual |
| Config Management | Database | File | File |

### Performance Advantages

1. **Process Isolation**: Plugin crashes don't affect the framework.
2. **Async High Concurrency**: Supports massive concurrent requests.
3. **Built-in Thread Pool**: CPU-bound tasks don't block.
4. **Database Storage**: Excellent config read/write performance.

### Developer Experience

1. **Easy to Start**: Just implement a few functions.
2. **Complete API**: Framework provides all common features.
3. **Hot Reload**: Code changes take effect immediately.
4. **Web UI**: No need to manually edit config files.

---

## Plugin Development Flow

### 1. Create Plugin Directory

```bash
mkdir -p plugins/my_plugin
cd plugins/my_plugin
```

### 2. Create `plugin.json`

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "My first plugin",
  "default_config": {}
}
```

### 3. Create `main.py`

```python
async def create_plugin(api, config):
    # Your plugin code
    pass
```

### 4. Restart Framework or Hot Reload

- **Hot Reload**: Click "Reload" button in Web UI.
- **Restart**: `python main.py`

### 5. Test Plugin

Send messages to the bot and see if the plugin responds.

---

## Next Steps

Now that you understand the basic concepts of XQNEXT Plugin System, next:

1.  [Quick Start](02-quickstart.md) - Create your first plugin
2.  [Plugin System Architecture](03-architecture.md) - Deep dive into plugin principles
3.  [Plugin API Reference](04-api-reference.md) - View complete API documentation

---

## FAQ

### Q: Can plugins access the file system?
**A**: Yes. Plugins run in independent processes with full file system access. However, it is recommended to use `api.get_storage()` and `api.set_storage()` to persist data.

### Q: Can plugins install their own dependencies?
**A**: Yes. Declare dependencies in the `dependencies` field of `plugin.json`, or create a `requirements.txt` file.

### Q: Will a plugin crash affect the framework?
**A**: No. Plugins run in independent processes. A crash only stops that plugin, not impacting the framework or other plugins.

### Q: How to debug plugins?
**A**: Use `api.log("info", "Debug Info")` to output logs, which will appear in the framework logs.

### Q: Can plugins call other plugins?
**A**: Yes, via the event system (`api.emit_event`) to send custom events that other plugins can listen to.

---

## Get Help

-  View Full Docs: `/docs/plugin/`
-  Join Discussion Group: QQ Group 615122348
-  Report Issues: GitHub Issues
-  Email Support: 2477194503@qq.com

---

**Next**: [Plugin Quick Start →](02-quickstart.md)

