# XQNEXT 插件开发文档

{ Chinese | [English](README.md) }

> **版本**: v2.0  
> **更新日期**: 2026-01-23

欢迎来到 XQNEXT 插件开发文档！这套文档将帮助你从零开始开发功能强大的 QQ 机器人插件。

---

## 文档目录

### 入门教程

1. **[插件系统概述](01-overview_CN.md)** 入门
   - 了解 XQNEXT 插件系统的核心特点
   - 插件架构概览
   - 为什么选择 XQNEXT

2. **[快速开始](02-quickstart_CN.md)** 入门 | 15分钟
   - 创建第一个插件
   - Hello World 示例
   - 回声插件示例
   - 常见问题解答

### 深入理解

3. **[插件系统架构](03-architecture_CN.md)** 进阶 | 20分钟
   - 整体架构设计
   - 进程隔离原理
   - 通信机制详解
   - 事件流转机制
   - 生命周期管理

### API 参考

4. **[插件 API 参考](04-api-reference_CN.md)** 中级 | 30分钟
   - 完整的 PluginAPI 文档
   - 消息 API
   - OneBot API 快捷方法
   - 配置 API
   - 存储 API
   - 事件 API
   - 工具 API

### 功能指南

5. **[配置与数据管理](05-config-data_CN.md)** 中级
   - 三层配置体系
   - 配置定义与验证
   - 数据持久化
   - 线程池使用
   - 缓存策略

6. **[前端 UI 集成](06-ui-integration_CN.md)** 中级
   - 配置 Schema 定义
   - 支持的字段类型
   - 前端表单自动生成
   - 配置读取与更新

7. **[高级特性](07-advanced-features_CN.md)** 高级
   - 事件系统深入
   - 异步编程最佳实践
   - 错误处理与重试
   - 性能优化
   - 安全性考虑

8. **[最佳实践与示例](08-best-practices_CN.md)** 高级
   - 完整的生产级插件示例
   - 代码质量检查清单
   - 常见陷阱避免
   - 测试与调试

---

## 快速导航

### 我想...

- **创建第一个插件** → [快速开始](02-quickstart_CN.md)
- **了解插件原理** → [插件系统架构](03-architecture_CN.md)
- **查API用法** → [插件 API 参考](04-api-reference_CN.md)
- **学习最佳实践** → [最佳实践与示例](08-best-practices_CN.md)
- **配置UI界面** → [前端 UI 集成](06-ui-integration_CN.md)
- **保存插件数据** → [配置与数据管理](05-config-data_CN.md)

---

## 学习路径

### 初学者路径

```
1. 插件系统概述 (5分钟)
   ↓
2. 快速开始 (15分钟)
   ↓
3. 插件 API 参考 (浏览常用API)
   ↓
4. 配置与数据管理
   ↓
5. 前端 UI 集成
```

### 进阶路径

```
完成初学者路径
   ↓
6. 插件系统架构 (深入理解)
   ↓
7. 高级特性 (异步、性能、安全)
   ↓
8. 最佳实践与示例 (生产级代码)
```

---

## 插件示例

框架自带了几个示例插件，可以作为参考：

| 插件 | 位置 | 难度 | 特性 |
|------|------|------|------|
| Hello Plugin | `plugins/hello_plugin/` |  | 基础消息处理 |
| Like Plugin | `plugins/like_plugin/` |  | 数据持久化、限流 |
| Kawaii Status | `plugins/kawaii_status/` |  | 线程池、图片处理 |

---

## 开发工具

### VS Code 推荐插件

- **Python** - 基础 Python 支持
- **Pylance** - 类型检查和智能提示
- **Python Docstring Generator** - 自动生成文档字符串

### 调试技巧

```python
# 使用日志调试
self.api.log("debug", f"变量值: {variable}")

# 查看框架日志
tail -f logs/xqnext.log
```

---

## 获取帮助

遇到问题？可以通过以下方式获取帮助：

-  查看文档（当前正在阅读）
-  加入讨论群：QQ群 615122348
-  报告 Bug：[GitHub Issues](https://github.com/ValkyrieEY/RuaBot/issues)
-  邮件支持：2477194503@qq.com

---

## 常见问题

### Q: 插件开发需要什么基础？

**A**: 需要基础的 Python 知识和简单的异步编程概念（`async/await`）。

### Q: 插件可以做什么？

**A**: 
-  接收和发送消息
-  群管理（踢人、禁言等）
-  持久化数据
-  定时任务
-  调用外部 API
-  生成图片、语音等多媒体内容

### Q: 插件会影响框架稳定性吗？

**A**: 不会。插件运行在独立进程中，崩溃不会影响框架和其他插件。

### Q: 如何调试插件？

**A**: 使用 `api.log()` 输出日志，查看框架日志文件，或使用 Python 调试器。

### Q: 插件可以安装依赖吗？

**A**: 可以。在 `plugin.json` 的 `dependencies` 字段中声明，或创建 `requirements.txt`。

---

## 贡献

发现文档问题或有改进建议？欢迎提交 PR 或 Issue！

---

**开始学习**: [插件系统概述 →](01-overview_CN.md)

---

<p align="center">
  Made with love by XQNEXT Team
</p>
