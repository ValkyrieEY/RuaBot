# GitHub Issues Capture Plugin

GitHub Issues、Commits、PRs 卡片渲染插件，支持获取指定编号或最新的内容并渲染为美观卡片。

## 功能

- 获取 GitHub issue 并渲染为卡片
- 获取 GitHub commit 并渲染为卡片（包含详细 diff）
- 获取 GitHub PR 并渲染为卡片
- 查看 issue/PR 评论
- 搜索 issue/commit/pr
- 仓库统计图表
- 支持指定编号或 `latest`（最新）
- **不需要指令前缀**

## 使用方法

### Issue 命令

```
issue latest          # 获取最新的 issue
issue 123             # 获取编号为 123 的 issue
issue 123 comments    # 查看 issue 123 的评论
```

### Commit 命令

```
commit latest         # 获取最新的 commit
commit abc123def      # 获取指定 SHA 的 commit
```

### PR 命令

```
pr latest             # 获取最新的 PR
pr 123                # 获取编号为 123 的 PR
pr 123 comments       # 查看 PR 123 的评论
```

### 搜索命令

```
search issue "关键词"     # 搜索 issue
search commit "关键词"    # 搜索 commit
search pr "关键词"        # 搜索 PR
```

### 统计命令

```
stats                 # 显示仓库统计图表
statistics            # 同上
统计                  # 同上（中文）
```

## 配置

在插件配置中可以设置：

- `owner`: GitHub 仓库所有者（默认: `SRInternet-Studio`）
- `repo`: GitHub 仓库名称（默认: `Jianer_QQ_bot`）
- `github_token`: GitHub API Token（可选，也可以从环境变量 `GITHUB_TOKEN` 获取）

## 依赖

- `requests`: HTTP 请求库
- `pillow`: 图片处理

## 安装依赖

```bash
pip install requests pillow
```

## 注意事项

1. 如果 GitHub 仓库是私有的，需要配置 `github_token`
2. 渲染卡片可能需要一些时间，请耐心等待
3. 建议配置 GitHub Token 以避免速率限制

