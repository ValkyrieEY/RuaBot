# Configuration & Data Management

{ [Chinese](05-config-data_CN.md) | English }

> **Doc Version**: v2.0
> **Last Updated**: 2026-01-23
> **Difficulty**: Intermediate

## Document Navigation

1. [Plugin System Overview](01-overview.md)
2. [Quick Start](02-quickstart.md)
3. [Plugin System Architecture](03-architecture.md)
4. [Plugin API Reference](04-api-reference.md)
5. [OneBot API Guide](05-onebot-guide.md)
6. **[Configuration & Data Management](05-config-data.md)** ← Current
7. [Frontend UI Integration](06-ui-integration.md)
8. [Advanced Features](07-advanced-features.md)
9. [Best Practices & Examples](08-best-practices.md)

---

## Configuration Management

XQNEXT provides a three-layer configuration system to ensure flexibility and maintainability of plugin configuration.

### 1. Default Configuration (`plugin.json`)

The `default_config` defined in `plugin.json` is the baseline value for configuration.

```json
{
  "default_config": {
    "enabled": true,
    "limit": 10
  }
}
```

### 2. User Configuration (Database)

Configurations modified by users via Web UI or API are stored in the database and have higher priority than default configurations.

### 3. Runtime Configuration (Memory)

Plugins can access the merged configuration using `self.config` at runtime.

### Configuration API Usage

```python
# Get config
value = await api.get_config('key')

# Set config (Automatically persisted to database)
await api.set_config('key', 'new_value')
```

---

## Data Persistence

For non-configuration data (such as statistics, cached images, etc.), you should use the Storage API.

### Storage API Features

- **Key-Value Storage**: Simple and easy to use
- **Binary Support**: Can store arbitrary binary data
- **Auto Compression**: Large data is automatically compressed
- **Plugin Isolation**: Data of different plugins are invisible to each other

### Example: Save User Sign-in Data

```python
import json
import time

class SigninPlugin:
    async def on_load(self):
        # Load data
        data_bytes = await self.api.get_storage('signin_data')
        if data_bytes:
            self.signin_data = json.loads(data_bytes.decode('utf-8'))
        else:
            self.signin_data = {}

    async def save_data(self):
        # Save data
        data_bytes = json.dumps(self.signin_data).encode('utf-8')
        await self.api.set_storage('signin_data', data_bytes)

    async def handle_signin(self, user_id):
        today = time.strftime('%Y-%m-%d')
        if self.signin_data.get(str(user_id)) == today:
            return "You have already signed in today"
        
        self.signin_data[str(user_id)] = today
        await self.save_data()
        return "Sign-in successful"
```

---

## Thread Pool Usage

For CPU-bound or blocking I/O operations, you **MUST** use a thread pool, otherwise the entire plugin process will be blocked.

### Using `run_in_executor`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

class MyPlugin:
    def __init__(self, api, config):
        self.api = api
        # Create thread pool
        self.executor = ThreadPoolExecutor(max_workers=3)

    def cpu_bound_task(self, n):
        # Simulate time-consuming calculation
        time.sleep(1)
        return n * n

    async def handle_message(self, event):
        loop = asyncio.get_event_loop()
        # Execute in thread pool
        result = await loop.run_in_executor(
            self.executor, 
            self.cpu_bound_task, 
            10
        )
        await self.api.send_private_msg(event['user_id'], f"Calculation Result: {result}")
```

---

## Caching Strategy

Rational use of caching can significantly improve plugin performance.

### 1. Memory Cache

Suitable for small data volume and high frequency access.

```python
class CachePlugin:
    def __init__(self, api, config):
        self.cache = {}
        self.cache_ttl = 60  # Expire in 60 seconds

    def get_data(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None

    def set_data(self, key, value):
        self.cache[key] = (value, time.time())
```

### 2. Storage Cache

Suitable for large data volume and data that needs persistence.

```python
async def get_image(self, url):
    # Try to get from Storage
    key = f"img_{hash(url)}"
    data = await self.api.get_storage(key)
    
    if data:
        return data
        
    # Download image
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            # Save to Storage
            await self.api.set_storage(key, data)
            return data
```

---

## Next Steps

- [Frontend UI Integration](06-ui-integration.md)

