# 邀请统计插件文件说明

## 文件结构

```
invite_stats/
├── main.py              # 插件主程序
├── plugin.json          # 插件配置文件
├── README.md            # 插件说明文档
├── USAGE.md             # 使用指南
├── FILES.md             # 文件说明（本文件）
├── test_plugin.py       # 测试脚本
├── .gitignore           # Git忽略文件
└── temp/                # 临时文件目录（存储导出的文件）
```

## 文件详解

### main.py
**功能**：插件的核心代码
**内容**：
- `InviteStatsPlugin` 类：主插件类
- 事件监听：群成员增加/减少事件
- 消息处理：处理查询、清空、导出命令
- 数据管理：统计、排名、导出功能
- `create_plugin` 函数：插件入口点

**主要方法**：
- `on_load()`：插件加载时初始化
- `on_unload()`：插件卸载时保存数据
- `on_event_context()`：处理事件上下文
- `is_group_enabled()`：检查群是否启用此插件（群白名单）
- `handle_notice()`：处理通知事件
- `handle_message()`：处理消息事件
- `handle_member_join()`：处理成员加入
- `handle_member_leave()`：处理成员离开
- `handle_query_invite()`：处理查询请求
- `handle_clear_invite()`：处理清空请求
- `handle_export_stats()`：处理导出请求
- `get_user_rank()`：计算用户排名
- `generate_export_content()`：生成导出内容

### plugin.json
**功能**：插件元数据配置
**内容**：
- 插件名称、版本、作者
- 插件描述和标签
- 默认配置（admin_qq 和 enabled_groups）
- 配置模式定义

**配置项**：
- `admin_qq`：管理员QQ号（字符串类型）
- `enabled_groups`：启用插件的群号列表（数组类型，为空则所有群都启用）

### README.md
**功能**：插件详细说明文档
**内容**：
- 功能介绍
- 主要功能详解
- 排名规则说明
- 配置说明
- 使用示例
- 技术细节
- 数据结构
- 注意事项
- 开发信息

### USAGE.md
**功能**：用户使用指南
**内容**：
- 快速开始指南
- 基本使用方法
- 工作原理
- 命令详解
- 配置说明
- 常见问题解答
- 更新日志

### test_plugin.py
**功能**：插件功能测试脚本
**内容**：
- 数据结构测试
- 统计功能测试
- 排名功能测试
- 导出功能测试

**运行方法**：
```bash
cd plugins/invite_stats
python test_plugin.py
```

### .gitignore
**功能**：Git版本控制忽略文件
**内容**：
- 临时文件目录
- Python缓存文件
- 备份文件

### temp/
**功能**：临时文件存储目录
**用途**：存储导出的统计数据文件
**文件格式**：`invite_stats_YYYYMMDD_HHMMSS.txt`

## 数据存储

插件使用框架的Storage API存储数据，键名为`invite_data`。

**数据格式**：
```json
{
  "group_id": {
    "inviter_qq": {
      "invited_qq": {
        "join_time": "2026年2月12日12时30分15秒",
        "status": "存在",
        "leave_time": null
      }
    }
  }
}
```

## 依赖关系

### 框架依赖
- PluginAPI：框架提供的插件接口
- EventContext：事件上下文系统
- Storage API：数据持久化接口
- OneBot API：QQ机器人API

### Python依赖
- asyncio：异步IO支持
- json：JSON数据处理
- os：文件系统操作
- datetime：时间处理
- typing：类型注解

**注意**：所有依赖都是Python标准库，无需额外安装第三方包。

## 权限说明

### 插件权限
- 监听群成员增减事件
- 发送群消息
- 发送私聊消息
- 获取群成员信息
- 上传文件
- 读写存储数据

### 用户权限
- **所有群成员**：可以查询自己的邀请记录
- **群主**：可以清空本群的邀请记录
- **指定管理员**：可以导出所有统计数据

## 安全性

1. **权限控制**：
   - 清空记录功能通过API验证群主身份
   - 导出功能检查QQ号是否匹配管理员

2. **数据隔离**：
   - 每个群的数据独立存储
   - 不同邀请人的数据分别记录
   - 支持群白名单，只在指定群中工作

3. **数据安全**：
   - 使用框架的Storage API安全存储
   - 定期自动保存数据
   - 支持数据导出备份

## 性能优化

1. **异步处理**：所有IO操作都是异步的，不会阻塞事件循环
2. **延迟保存**：使用`asyncio.create_task`异步保存数据
3. **快速返回**：事件处理快速返回，避免阻塞其他插件
4. **群白名单**：通过`enabled_groups`配置，可以只在特定群中工作，减少不必要的处理

## 版本历史

### v1.0.0 (2026-02-12)
- 首次发布
- 完整实现所有需求功能
- 包含完整的文档和测试

## 开发者信息

- **作者**：XQNEXT
- **版本**：1.0.0
- **协议**：根据框架协议
- **支持**：GitHub Issues

## 贡献指南

如果你想为这个插件做出贡献：

1. Fork项目
2. 创建功能分支
3. 提交改动
4. 发起Pull Request

## 许可证

本插件遵循XQNEXT框架的许可证。

