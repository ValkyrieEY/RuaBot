# XQNEXT Plugin Development Documentation

{ [Chinese](README_CN.md) | English }

> **Version**: v2.0
> **Last Updated**: 2026-01-23

Welcome to the XQNEXT Plugin Development Documentation! This set of documentation will help you start developing powerful QQ bot plugins from scratch.

---

## Table of Contents

### Getting Started

1. **[Plugin System Overview](01-overview.md)** Beginner
   - Understand core features of XQNEXT plugin system
   - Plugin architecture overview
   - Why choose XQNEXT

2. **[Quick Start](02-quickstart.md)** Beginner | 15 min
   - Create your first plugin
   - Hello World example
   - Echo plugin example
   - FAQ

### In-Depth Understanding

3. **[Plugin System Architecture](03-architecture.md)** Intermediate | 20 min
   - Overall architecture design
   - Process isolation principle
   - Communication mechanism detailed
   - Event flow mechanism
   - Lifecycle management

### API Reference

4. **[Plugin API Reference](04-api-reference.md)** Intermediate | 30 min
   - Complete PluginAPI documentation
   - Message API
   - OneBot API shortcuts
   - Configuration API
   - Storage API
   - Event API
   - Tool API

### Functional Guides

5. **[Configuration & Data Management](05-config-data.md)** Intermediate
   - Three-layer configuration system
   - Configuration definition and validation
   - Data persistence
   - Thread pool usage
   - Caching strategy

6. **[Frontend UI Integration](06-ui-integration.md)** Intermediate
   - Configuration Schema definition
   - Supported field types
   - Frontend form auto-generation
   - Configuration reading and updating

7. **[Advanced Features](07-advanced-features.md)** Advanced
   - Event system deep dive
   - Async programming best practices
   - Error handling and retry
   - Performance optimization
   - Security considerations

8. **[Best Practices & Examples](08-best-practices.md)** Advanced
   - Complete production-grade plugin examples
   - Code quality checklist
   - Common pitfalls to avoid
   - Testing and debugging

---

## Quick Navigation

### I want to...

- **Create my first plugin** → [Quick Start](02-quickstart.md)
- **Understand plugin principles** → [Plugin System Architecture](03-architecture.md)
- **Check API usage** → [Plugin API Reference](04-api-reference.md)
- **Learn best practices** → [Best Practices & Examples](08-best-practices.md)
- **Configure UI interface** → [Frontend UI Integration](06-ui-integration.md)
- **Save plugin data** → [Configuration & Data Management](05-config-data.md)

---

## Learning Path

### Beginner Path

```
1. Plugin System Overview (5 min)
   ↓
2. Quick Start (15 min)
   ↓
3. Plugin API Reference (Browse common APIs)
   ↓
4. Configuration & Data Management
   ↓
5. Frontend UI Integration
```

### Advanced Path

```
Complete Beginner Path
   ↓
6. Plugin System Architecture (Deep understanding)
   ↓
7. Advanced Features (Async, Performance, Security)
   ↓
8. Best Practices & Examples (Production-grade code)
```

---

## Plugin Examples

The framework comes with several example plugins for reference:

| Plugin | Location | Difficulty | Features |
|--------|----------|------------|----------|
| Hello Plugin | `plugins/hello_plugin/` |  | Basic message handling |
| Like Plugin | `plugins/like_plugin/` |  | Data persistence, rate limiting |
| Kawaii Status | `plugins/kawaii_status/` |  | Thread pool, image processing |

---

## Development Tools

### VS Code Recommended Extensions

- **Python** - Basic Python support
- **Pylance** - Type checking and IntelliSense
- **Python Docstring Generator** - Auto-generate docstrings

### Debugging Tips

```python
# Use log for debugging
self.api.log("debug", f"Variable value: {variable}")

# View framework logs
tail -f logs/xqnext.log
```

---

## Get Help

Running into issues? Get help via:

-  Check documentation (You are reading it)
-  Join Discussion Group: QQ Group 615122348
-  Report Bug: [GitHub Issues](https://github.com/ValkyrieEY/RuaBot/issues)
-  Email Support: 2477194503@qq.com

---

## FAQ

### Q: What basics are needed for plugin development?

**A**: Basic Python knowledge and simple asynchronous programming concepts (`async/await`) are required.

### Q: What can plugins do?

**A**:
-  Receive and send messages
-  Group management (kick, mute, etc.)
-  Persist data
-  Scheduled tasks
-  Call external APIs
-  Generate multimedia content like images, voice

### Q: Will plugins affect framework stability?

**A**: No. Plugins run in independent processes; crashes will not affect the framework or other plugins.

### Q: How to debug plugins?

**A**: Use `api.log()` to output logs, view framework log files, or use a Python debugger.

### Q: Can plugins install dependencies?

**A**: Yes. Declare in the `dependencies` field of `plugin.json` or create `requirements.txt`.

---

## Contribution

Found documentation issues or have improvement suggestions? PRs or Issues are welcome!

---

**Start Learning**: [Plugin System Overview →](01-overview.md)

---

<p align="center">
  Made with love by XQNEXT Team
</p>

