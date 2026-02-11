# GitHub Plugin Installation Guide

> **Version**: v2.0  
> **Updated**: 2026-01-23  
> **Target Audience**: Plugin Developers

This document explains how to prepare a GitHub repository so users can install your plugin directly from GitHub through XQNEXT's Web UI.

---

## Directory Format Requirements

XQNEXT supports two GitHub repository directory formats:

### Format 1: Root Directory as Plugin Directory (Recommended)

**Use Case**: Plugin code is directly in the repository root

```
your-plugin-repo/
├── plugin.json          # Required: Plugin metadata
├── main.py              # Required: Plugin entry file (or file specified in entry)
├── README.md            # Recommended: Plugin documentation
├── requirements.txt     # Optional: Python dependencies
└── ...                  # Other plugin files
```

**Advantages**:
- Simple and clear structure
- Ready to use after installation
- Matches most plugin development habits

**Example Repository Structure**:
```
https://github.com/username/my-plugin
├── plugin.json
├── main.py
├── utils.py
├── config.py
└── README.md
```

---

### Format 2: Plugin in Subdirectory

**Use Case**: Repository contains multiple plugins, or includes other files (docs, tests, etc.)

```
your-plugin-repo/
├── plugin-name/         # Plugin directory (any name)
│   ├── plugin.json      # Required: Plugin metadata
│   ├── main.py          # Required: Plugin entry file
│   └── ...              # Other plugin files
├── README.md            # Repository documentation
├── docs/                # Documentation directory
└── tests/               # Test directory
```

**Advantages**:
- Suitable for multi-plugin repositories
- Can include documentation and test code
- More professional project structure

**Example Repository Structure**:
```
https://github.com/username/plugins-collection
├── weather-plugin/
│   ├── plugin.json
│   ├── main.py
│   └── utils.py
├── music-plugin/
│   ├── plugin.json
│   ├── main.py
│   └── api.py
└── README.md
```

**Note**: If using Format 2, the system will automatically find subdirectories containing `plugin.json`.

---

## Required Files

### 1. `plugin.json` (Required)

Plugin metadata file, must include the following fields:

```json
{
  "name": "my_plugin",           // Required: Plugin name (unique identifier)
  "version": "1.0.0",            // Required: Plugin version
  "author": "YourName",          // Recommended: Author name
  "description": "Plugin description", // Recommended: Plugin functionality description
  "entry": "main.py",            // Optional: Entry file (default: main.py)
  "default_config": {            // Optional: Default configuration
    "key": "value"
  },
  "config_schema": {             // Optional: Configuration UI definition
    "key": {
      "type": "string",
      "default": "value",
      "description": "Configuration description"
    }
  }
}
```

**Complete Example**:
```json
{
  "name": "weather_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "Weather query plugin",
  "entry": "main.py",
  "default_config": {
    "api_key": "",
    "default_city": "Beijing"
  },
  "config_schema": {
    "api_key": {
      "type": "string",
      "default": "",
      "description": "Weather API key"
    },
    "default_city": {
      "type": "string",
      "default": "Beijing",
      "description": "Default query city"
    }
  }
}
```

### 2. Entry File (Required)

Default entry file is `main.py`, or specified by the `entry` field in `plugin.json`.

The entry file must contain a `create_plugin` function:

```python
async def create_plugin(api, config):
    """Plugin entry point
    
    Args:
        api: PluginAPI object
        config: Plugin configuration dictionary
    
    Returns:
        Plugin instance
    """
    # Create and return plugin instance
    plugin = MyPlugin(api, config)
    await plugin.on_load()
    return plugin
```

---

## Installation Process

When users install a plugin from GitHub through the Web UI, the system will:

1. **Download Repository ZIP**
   - Download from `main` branch (or `master` if `main` doesn't exist)
   - Download URL: `https://github.com/owner/repo/archive/refs/heads/main.zip`

2. **Extract ZIP File**
   - Extract to temporary directory
   - Usually creates `repo-name-main/` or `repo-name-master/` directory

3. **Find Plugin Directory**
   - First check if root directory contains `plugin.json`
   - If not, search all subdirectories for the first one containing `plugin.json`

4. **Copy to Plugin Directory**
   - Copy found plugin directory to `plugins/{plugin_name}/`
   - `plugin_name` comes from the `name` field in `plugin.json`

5. **Auto-install Dependencies**
   - Scan `dependencies` field in `plugin.json`
   - Scan `requirements.txt` file
   - Automatically install all dependencies using pip

6. **Validate and Register**
   - Validate `plugin.json` format
   - Register plugin in database
   - Automatically load plugin

---

## Best Practices

### 1. Repository Structure Recommendation

**Recommended Structure** (Format 1):
```
my-plugin/
├── plugin.json
├── main.py
├── requirements.txt
├── README.md
└── .gitignore
```

### 2. Branch Management

- **Main Branch**: Use `main` or `master` as default branch
- **Stable Versions**: Use Git Tags to mark stable versions
- **Development Branch**: Keep work-in-progress features in other branches

### 3. Version Management

Use semantic versioning in `plugin.json`:
- `1.0.0` - Major.Minor.Patch
- Major updates: increment major version
- New features: increment minor version
- Bug fixes: increment patch version

### 4. Dependency Management

XQNEXT framework supports automatic dependency installation. Two methods are supported:

**Method 1**: Declare in `plugin.json` (Recommended)
```json
{
  "dependencies": [
    {
      "name": "requests",
      "version": ">=2.28.0",
      "required": true
    },
    {
      "name": "aiohttp",
      "version": ">=3.8.0"
    }
  ]
}
```

Or use simplified format:
```json
{
  "dependencies": [
    "requests>=2.28.0",
    "aiohttp>=3.8.0"
  ]
}
```

**Method 2**: Create `requirements.txt`
```
requests>=2.28.0
aiohttp>=3.8.0
pillow>=10.0.0
```

**Automatic Installation**:
- Dependencies are automatically detected and installed during plugin installation
- Framework prioritizes `dependencies` field in `plugin.json`
- If `requirements.txt` exists, dependencies from it are also installed
- Installation failures don't block plugin installation, but warnings are logged

### 5. Documentation

Include in `README.md`:
- Plugin functionality description
- Installation method
- Configuration instructions
- Usage examples
- FAQ

---

## FAQ

### Q1: What if my repository has multiple plugins?

**A**: Use Format 2, with each plugin in a separate subdirectory. Users need to install each plugin separately.

### Q2: Can I use other branches?

**A**: Currently, the system only supports installation from `main` or `master` branch. To install from other branches:
1. Merge the branch into main branch, or
2. Provide a complete ZIP download link

### Q3: Plugin installed but `plugin.json` not found?

**A**: Check:
1. Is `plugin.json` at the correct directory level?
2. Is the filename correct (case-sensitive)?
3. Is it ignored in `.gitignore`?

### Q4: How to test plugin installation?

**A**: 
1. Push plugin to GitHub
2. Try installing in XQNEXT Web UI
3. Check log files for issues

### Q5: What are the requirements for plugin names?

**A**: 
- Defined in the `name` field of `plugin.json`
- Recommended: lowercase letters, numbers, and underscores
- Avoid special characters and spaces
- Ensure uniqueness (different authors can use the same name)

---

## Example Repositories

Here are some example repository structures that follow the specifications:

### Example 1: Simple Plugin (Format 1)

```
https://github.com/user/simple-plugin
├── plugin.json
├── main.py
└── README.md
```

### Example 2: Complex Plugin (Format 1)

```
https://github.com/user/advanced-plugin
├── plugin.json
├── main.py
├── utils/
│   ├── __init__.py
│   └── helpers.py
├── config.py
├── requirements.txt
└── README.md
```

### Example 3: Multi-Plugin Repository (Format 2)

```
https://github.com/user/plugins-collection
├── plugin-a/
│   ├── plugin.json
│   └── main.py
├── plugin-b/
│   ├── plugin.json
│   └── main.py
└── README.md
```

---

## Checklist

Before publishing your plugin, confirm:

- [ ] `plugin.json` exists and is correctly formatted
- [ ] `plugin.json` contains required `name` and `version` fields
- [ ] Entry file exists (`main.py` or file specified in `entry`)
- [ ] Entry file contains `create_plugin` function
- [ ] Repository default branch is `main` or `master`
- [ ] `README.md` includes usage instructions
- [ ] Dependencies are correctly declared (`dependencies` or `requirements.txt`)
- [ ] Code is tested and runs correctly

---

## Related Documentation

- [Quick Start](02-quickstart.md) - Learn how to develop plugins
- [API Reference](04-api-reference.md) - View complete API documentation
- [Best Practices](08-best-practices.md) - Learn development best practices

---

**Need Help?** Join QQ Group: 615122348

