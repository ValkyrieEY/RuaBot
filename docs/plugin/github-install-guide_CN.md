# GitHub 插件安装指南

> **版本**: v2.0  
> **更新日期**: 2026-01-23  
> **目标读者**: 插件开发者

本文档说明如何准备 GitHub 仓库，以便用户可以通过 XQNEXT 的 Web UI 直接从 GitHub 安装你的插件。

---

## 目录格式要求

XQNEXT 支持两种 GitHub 仓库目录格式：

### 格式 1：根目录即插件目录（推荐）

**适用场景**：插件代码直接放在仓库根目录

```
your-plugin-repo/
├── plugin.json          # 必需：插件元数据
├── main.py              # 必需：插件入口文件（或 plugin.json 中 entry 指定的文件）
├── README.md            # 推荐：插件说明文档
├── requirements.txt     # 可选：Python 依赖
└── ...                  # 其他插件文件
```

**优点**：
- 结构简单清晰
- 用户安装后直接可用
- 符合大多数插件开发习惯

**示例仓库结构**：
```
https://github.com/username/my-plugin
├── plugin.json
├── main.py
├── utils.py
├── config.py
└── README.md
```

---

### 格式 2：插件在子目录中

**适用场景**：仓库包含多个插件，或包含其他文件（如文档、测试等）

```
your-plugin-repo/
├── plugin-name/         # 插件目录（名称任意）
│   ├── plugin.json      # 必需：插件元数据
│   ├── main.py          # 必需：插件入口文件
│   └── ...              # 其他插件文件
├── README.md            # 仓库说明
├── docs/                # 文档目录
└── tests/               # 测试目录
```

**优点**：
- 适合多插件仓库
- 可以包含文档和测试代码
- 更专业的项目结构

**示例仓库结构**：
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

**注意**：如果使用格式 2，系统会自动查找包含 `plugin.json` 的子目录。

---

## 必需文件

### 1. `plugin.json`（必需）

插件元数据文件，必须包含以下字段：

```json
{
  "name": "my_plugin",           // 必需：插件名称（唯一标识）
  "version": "1.0.0",            // 必需：插件版本
  "author": "YourName",          // 推荐：作者名称
  "description": "插件描述",      // 推荐：插件功能说明
  "entry": "main.py",            // 可选：入口文件（默认 main.py）
  "default_config": {            // 可选：默认配置
    "key": "value"
  },
  "config_schema": {             // 可选：配置界面定义
    "key": {
      "type": "string",
      "default": "value",
      "description": "配置说明"
    }
  }
}
```

**完整示例**：
```json
{
  "name": "weather_plugin",
  "version": "1.0.0",
  "author": "YourName",
  "description": "天气查询插件",
  "entry": "main.py",
  "default_config": {
    "api_key": "",
    "default_city": "北京"
  },
  "config_schema": {
    "api_key": {
      "type": "string",
      "default": "",
      "description": "天气 API 密钥"
    },
    "default_city": {
      "type": "string",
      "default": "北京",
      "description": "默认查询城市"
    }
  }
}
```

### 2. 入口文件（必需）

默认入口文件为 `main.py`，或由 `plugin.json` 的 `entry` 字段指定。

入口文件必须包含 `create_plugin` 函数：

```python
async def create_plugin(api, config):
    """插件入口点
    
    Args:
        api: PluginAPI 对象
        config: 插件配置字典
    
    Returns:
        插件实例
    """
    # 创建并返回插件实例
    plugin = MyPlugin(api, config)
    await plugin.on_load()
    return plugin
```

---

## 安装流程说明

当用户通过 Web UI 从 GitHub 安装插件时，系统会：

1. **下载仓库 ZIP**
   - 从 `main` 分支下载（如果不存在则尝试 `master` 分支）
   - 下载地址：`https://github.com/owner/repo/archive/refs/heads/main.zip`

2. **解压 ZIP 文件**
   - 解压到临时目录
   - 通常解压后会有 `repo-name-main/` 或 `repo-name-master/` 目录

3. **查找插件目录**
   - 首先检查解压后的根目录是否包含 `plugin.json`
   - 如果没有，查找所有子目录，找到第一个包含 `plugin.json` 的目录

4. **复制到插件目录**
   - 将找到的插件目录复制到 `plugins/{plugin_name}/`
   - `plugin_name` 来自 `plugin.json` 的 `name` 字段

5. **自动安装依赖**
   - 扫描 `plugin.json` 的 `dependencies` 字段
   - 扫描 `requirements.txt` 文件
   - 使用 pip 自动安装所有依赖

6. **验证和注册**
   - 验证 `plugin.json` 格式
   - 在数据库中注册插件
   - 自动加载插件

---

## 最佳实践

### 1. 仓库结构建议

**推荐结构**（格式 1）：
```
my-plugin/
├── plugin.json
├── main.py
├── requirements.txt
├── README.md
└── .gitignore
```

### 2. 分支管理

- **主分支**：使用 `main` 或 `master` 作为默认分支
- **稳定版本**：建议使用 Git Tags 标记稳定版本
- **开发分支**：开发中的功能放在其他分支

### 3. 版本管理

在 `plugin.json` 中使用语义化版本号：
- `1.0.0` - 主版本.次版本.修订版本
- 重大更新：主版本号 +1
- 新功能：次版本号 +1
- Bug 修复：修订版本号 +1

### 4. 依赖管理

XQNEXT 框架支持自动安装插件依赖，支持两种方式：

**方式 1**：在 `plugin.json` 中声明（推荐）
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

或者使用简化格式：
```json
{
  "dependencies": [
    "requests>=2.28.0",
    "aiohttp>=3.8.0"
  ]
}
```

**方式 2**：创建 `requirements.txt`
```
requests>=2.28.0
aiohttp>=3.8.0
pillow>=10.0.0
```

**自动安装**：
- 插件安装时，框架会自动检测并安装依赖
- 优先使用 `plugin.json` 中的 `dependencies` 字段
- 如果存在 `requirements.txt`，也会自动安装其中的依赖
- 依赖安装失败不会阻止插件安装，但会在日志中记录警告

### 5. 文档说明

在 `README.md` 中包含：
- 插件功能说明
- 安装方法
- 配置说明
- 使用示例
- 常见问题

---

## 常见问题

### Q1: 我的仓库有多个插件怎么办？

**A**: 使用格式 2，每个插件放在独立的子目录中。用户需要分别安装每个插件。

### Q2: 可以使用其他分支吗？

**A**: 目前系统只支持从 `main` 或 `master` 分支安装。如需安装其他分支，可以：
1. 将其他分支合并到主分支
2. 或提供完整的 ZIP 下载链接

### Q3: 插件安装后找不到 `plugin.json`？

**A**: 检查：
1. `plugin.json` 是否在正确的目录层级
2. 文件名是否正确（区分大小写）
3. 是否在 `.gitignore` 中被忽略

### Q4: 如何测试插件安装？

**A**: 
1. 将插件推送到 GitHub
2. 在 XQNEXT Web UI 中尝试安装
3. 查看日志文件排查问题

### Q5: 插件名称有什么要求？

**A**: 
- 在 `plugin.json` 的 `name` 字段中定义
- 建议使用小写字母、数字和下划线
- 避免使用特殊字符和空格
- 确保唯一性（不同作者可以使用相同名称）

---

## 示例仓库

以下是一些符合规范的示例仓库结构：

### 示例 1：简单插件（格式 1）

```
https://github.com/user/simple-plugin
├── plugin.json
├── main.py
└── README.md
```

### 示例 2：复杂插件（格式 1）

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

### 示例 3：多插件仓库（格式 2）

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

## 检查清单

在发布插件前，请确认：

- [ ] `plugin.json` 存在且格式正确
- [ ] `plugin.json` 包含必需的 `name` 和 `version` 字段
- [ ] 入口文件存在（`main.py` 或 `entry` 指定的文件）
- [ ] 入口文件包含 `create_plugin` 函数
- [ ] 仓库默认分支为 `main` 或 `master`
- [ ] `README.md` 包含使用说明
- [ ] 依赖已正确声明（`dependencies` 或 `requirements.txt`）
- [ ] 代码已测试，可以正常运行

---

## 相关文档

- [插件快速开始](02-quickstart_CN.md) - 学习如何开发插件
- [插件 API 参考](04-api-reference_CN.md) - 查看完整 API 文档
- [最佳实践](08-best-practices_CN.md) - 学习开发最佳实践

---

**需要帮助？** 加入 QQ 群：615122348

