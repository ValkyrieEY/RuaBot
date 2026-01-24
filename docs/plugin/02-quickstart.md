# Plugin Quick Start

{ [Chinese](02-quickstart_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Beginner
> **Estimated Time**: 15 Minutes

## Document Navigation

1. [Plugin System Overview](01-overview.md)
2. **[Quick Start](02-quickstart.md)** ← Current
3. [Plugin System Architecture](03-architecture.md)
4. [Plugin API Reference](04-api-reference.md)
5. [OneBot API Guide](05-onebot-guide.md)
6. [Configuration & Data Management](06-config-data.md)
7. [Frontend UI Integration](07-ui-integration.md)
8. [Advanced Features](08-advanced-features.md)
9. [Best Practices & Examples](09-best-practices.md)

---

## Learning Objectives

By the end of this tutorial, you will learn how to:

-  Create your first plugin
-  Handle group and private messages
-  Call OneBot API to send messages
-  Use plugin configuration
-  Save and read data

---

## Prerequisites

- Python 3.9+
- XQNEXT Framework installed and running
- Basic Python asynchronous programming knowledge (`async/await`)

---

## First Plugin: Hello World

### Step 1: Create Plugin Directory

Create a plugin directory under the XQNEXT root directory:

```bash
cd XQNEXT
mkdir -p plugins/hello_plugin
cd plugins/hello_plugin
```

### Step 2: Create `plugin.json`

Create a `plugin.json` file to define plugin metadata:

```json
{
  "name": "hello_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "A simple Hello World plugin",
  "entry": "main.py",
  "default_config": {
    "greeting": "Hello"
  },
  "config_schema": {
    "greeting": {
      "type": "string",
      "default": "Hello",
      "description": "Greeting message"
    }
  }
}
```

**Field Description:**

| Field | Description | Required |
|-------|-------------|----------|
| `name` | Plugin name (unique identifier) | Yes |
| `version` | Plugin version | Yes |
| `author` | Author name | Yes |
| `description` | Plugin description | Yes |
| `entry` | Entry file (default `main.py`) | No |
| `default_config` | Default configuration | No |
| `config_schema` | Config UI definition | No |

### Step 3: Create `main.py`

Create the plugin main file `main.py`:

```python
"""Hello World Plugin"""

async def create_plugin(api, config):
    """Plugin Entry Point
    
    Args:
        api: PluginAPI object, providing framework interfaces
        config: Plugin configuration dictionary
    
    Returns:
        Plugin instance
    """
    
    class HelloPlugin:
        """Hello World Plugin Class"""
        
        def __init__(self, api, config):
            self.api = api
            self.config = config
            self.greeting = config.get('greeting', 'Hello')
        
        async def on_load(self):
            """Called when plugin loads"""
            self.api.log("info", f"Hello Plugin Loaded! Greeting: {self.greeting}")
        
        async def on_unload(self):
            """Called when plugin unloads"""
            self.api.log("info", "Hello Plugin Unloaded!")
        
        async def on_event(self, event_name, data):
            """Handle Events
            
            Args:
                event_name: Event name
                data: Event data
            """
            # Only handle message events
            if event_name == "onebot.message":
                await self.handle_message(data)
        
        async def handle_message(self, event):
            """Handle Message Events
            
            Args:
                event: OneBot message event
            """
            # Get message type and content
            message_type = event.get('message_type')  # 'private' or 'group'
            raw_message = event.get('raw_message', '').strip()
            
            # Check if it is a "hello" message
            if raw_message in ["Hello", "hello", "hi"]:
                # Build reply message
                reply = f"{self.greeting}! I am Hello Plugin"
                
                # Send reply based on message type
                if message_type == 'group':
                    group_id = event['group_id']
                    await self.api.send_group_msg(group_id, reply)
                elif message_type == 'private':
                    user_id = event['user_id']
                    await self.api.send_private_msg(user_id, reply)
    
    # Create plugin instance
    plugin = HelloPlugin(api, config)
    
    # Call on_load
    await plugin.on_load()
    
    # Return plugin instance
    return plugin
```

### Step 4: Restart Framework or Hot Reload

#### Method 1: Hot Reload (Recommended)

1. Open Web UI (Default `http://localhost:8000`)
2. Go to "Plugin Management" page
3. Find `hello_plugin`
4. Click "Reload" button

#### Method 2: Restart Framework

```bash
# Stop Framework
Ctrl+C

# Restart Framework
python main.py
```

### Step 5: Test Plugin

Send a message to the bot:

```
You: hello
Bot: Hello! I am Hello Plugin
```

Congratulations! Your first plugin is running successfully!

---

## Advanced Example: Echo Plugin

Now let's create a more complex plugin that can:

- Repeat user messages
- Support configurable prefix
- Record usage count

### Create Directory and Files

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
  "description": "Echo Plugin - Repeats user messages",
  "entry": "main.py",
  "default_config": {
    "prefix": "!echo",
    "max_length": 100
  },
  "config_schema": {
    "prefix": {
      "type": "string",
      "default": "!echo",
      "description": "Trigger Prefix"
    },
    "max_length": {
      "type": "number",
      "default": 100,
      "description": "Max Reply Length"
    }
  }
}
```

### `main.py`

```python
"""Echo Plugin - Repeats user messages"""

import json

async def create_plugin(api, config):
    """Plugin Entry Point"""
    
    class EchoPlugin:
        """Echo Plugin Class"""
        
        def __init__(self, api, config):
            self.api = api
            self.config = config
            self.prefix = config.get('prefix', '!echo')
            self.max_length = config.get('max_length', 100)
            self.usage_count = 0
        
        async def on_load(self):
            """Called when plugin loads"""
            # Load usage count from storage
            data_bytes = await self.api.get_storage('usage_count')
            if data_bytes:
                try:
                    data = json.loads(data_bytes.decode('utf-8'))
                    self.usage_count = data.get('count', 0)
                    self.api.log("info", f"Loaded usage count: {self.usage_count}")
                except Exception as e:
                    self.api.log("error", f"Failed to load data: {e}")
            
            self.api.log("info", f"Echo Plugin Loaded! Prefix: {self.prefix}")
        
        async def on_unload(self):
            """Called when plugin unloads"""
            # Save usage count
            try:
                data = json.dumps({'count': self.usage_count})
                await self.api.set_storage('usage_count', data.encode('utf-8'))
                self.api.log("info", "Usage count saved")
            except Exception as e:
                self.api.log("error", f"Failed to save data: {e}")
        
        async def on_event(self, event_name, data):
            """Handle Events"""
            if event_name == "onebot.message":
                await self.handle_message(data)
        
        async def handle_message(self, event):
            """Handle Message Events"""
            message_type = event.get('message_type')
            raw_message = event.get('raw_message', '').strip()
            
            # Check if starts with prefix
            if not raw_message.startswith(self.prefix):
                return
            
            # Extract content to repeat
            content = raw_message[len(self.prefix):].strip()
            
            # Check if content is empty
            if not content:
                reply = f"Usage: {self.prefix} <message>"
            elif content == "stats":
                # Show stats
                reply = f"Echo Plugin Stats:\nUsed {self.usage_count} times"
            else:
                # Truncate long messages
                if len(content) > self.max_length:
                    content = content[:self.max_length] + "..."
                
                reply = f" {content}"
                
                # Increment usage count
                self.usage_count += 1
            
            # Send reply
            if message_type == 'group':
                group_id = event['group_id']
                result = await self.api.send_group_msg(group_id, reply)
            elif message_type == 'private':
                user_id = event['user_id']
                result = await self.api.send_private_msg(user_id, reply)
            
            # Check result
            if result.get('success'):
                self.api.log("info", f"Reply success, usage count: {self.usage_count}")
            else:
                self.api.log("error", f"Reply failed: {result.get('error')}")
    
    plugin = EchoPlugin(api, config)
    await plugin.on_load()
    return plugin
```

### Testing Echo Plugin

```
You: !echo Hello World
Bot:  Hello World

You: !echo stats
Bot: Echo Plugin Stats:
     Used 1 times
```

---

## Code Breakdown

### 1. Plugin Entry Point

```python
async def create_plugin(api, config):
    """Plugin must provide this function"""
    # Create plugin instance
    plugin = MyPlugin(api, config)
    # Call initialization
    await plugin.on_load()
    # Return instance
    return plugin
```

**Key Points:**
- Function name must be `create_plugin`.
- Receives two arguments: `api` and `config`.
- Must be an `async` function.
- Returns plugin instance.

### 2. Plugin Lifecycle Methods

```python
async def on_load(self):
    """Called when plugin loads (Optional)"""
    pass

async def on_unload(self):
    """Called when plugin unloads (Optional)"""
    pass

async def on_event(self, event_name, data):
    """Handle Events (Required)"""
    pass
```

### 3. Event Handling

```python
async def on_event(self, event_name, data):
    """Handle Events
    
    Common Events:
    - onebot.message: Message event
    - onebot.notice: Notice event
    - onebot.request: Request event
    """
    if event_name == "onebot.message":
        await self.handle_message(data)
```

### 4. Message Handling

```python
async def handle_message(self, event):
    """Handle Message
    
    event fields:
    - message_type: 'private' or 'group'
    - raw_message: Original message text
    - user_id: Sender QQ ID
    - group_id: Group ID (only for group messages)
    """
    message_type = event.get('message_type')
    raw_message = event.get('raw_message', '')
    user_id = event['user_id']
    
    if message_type == 'group':
        group_id = event['group_id']
        # Handle group message
    elif message_type == 'private':
        # Handle private message
```

### 5. Sending Messages

```python
# Send group message
await self.api.send_group_msg(group_id, "Message Content")

# Send private message
await self.api.send_private_msg(user_id, "Message Content")

# Send message with CQ code
await self.api.send_group_msg(group_id, "[CQ:at,qq=123456]Hello")
```

### 6. Data Persistence

```python
# Save data
data = json.dumps({'key': 'value'})
await self.api.set_storage('my_data', data.encode('utf-8'))

# Read data
data_bytes = await self.api.get_storage('my_data')
if data_bytes:
    data = json.loads(data_bytes.decode('utf-8'))
```

### 7. Logging

```python
self.api.log("info", "Info Log")
self.api.log("warning", "Warning Log")
self.api.log("error", "Error Log")
self.api.log("debug", "Debug Log")
```

---

## FAQ

### Q1: Why is my plugin not responding?

**Checklist:**
1.  Are `plugin.json` and `main.py` in the correct directory?
2.  Is `create_plugin` function defined correctly?
3.  Is `on_event` method implemented correctly?
4.  Is the event name correct (`onebot.message`)?
5.  Check framework logs for errors.

### Q2: How to debug plugins?

```python
# Use log to output debug info
self.api.log("debug", f"Received message: {event}")

# View framework logs
tail -f logs/xqnext.log
```

### Q3: Can plugins access configuration?

```python
# Get config in __init__
def __init__(self, api, config):
    self.api = api
    self.greeting = config.get('greeting', 'Default Value')

# Read config at runtime
current_config = await self.api.get_config()
```

### Q4: How to handle exceptions?

```python
async def handle_message(self, event):
    try:
        # Your code
        pass
    except Exception as e:
        self.api.log("error", f"Failed to handle message: {e}")
```

### Q5: Can plugins call other plugins?

```python
# Send custom event via event system
await self.api.emit_event("my_event", {"data": "value"})
```

---

## Next Steps

Now you have mastered basic plugin development, next you can:

1.  [Deep dive into Plugin System Architecture](03-architecture.md)
2.  [View complete API Reference](04-api-reference.md)
3.  [Learn OneBot API Usage](05-onebot-guide.md)
4.  [Master Configuration & Data Management](06-config-data.md)

---

## Full Example Download

You can find more complete examples at:

- `plugins/like_plugin/` - QQ Like Plugin
- `plugins/kawaii_status/` - Server Status Plugin
- `plugins/so_good/` - Fun Reply Plugin

---

**Previous**: [← Plugin System Overview](01-overview.md)  
**Next**: [Plugin System Architecture →](03-architecture.md)

