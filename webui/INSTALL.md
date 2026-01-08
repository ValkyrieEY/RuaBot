# WebUI 安装指南

## 环境要求

### Node.js 版本
- **推荐版本**: Node.js 18.x 或更高版本
- **最低版本**: Node.js 18.x（Next.js 14 要求）
- **推荐使用**: Node.js 20.x LTS（长期支持版本）

### 如何检查 Node.js 版本
```bash
node --version
```

### 如何安装 Node.js
1. **Windows**: 
   - 访问 [Node.js 官网](https://nodejs.org/)
   - 下载并安装 LTS 版本（推荐 20.x）
   - 或使用包管理器：`winget install OpenJS.NodeJS.LTS`

2. **Linux/Mac**:
   ```bash
   # 使用 nvm (推荐)
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   nvm install 20
   nvm use 20
   ```

### npm 版本
- npm 通常随 Node.js 一起安装
- **推荐版本**: npm 9.x 或更高版本
- 检查版本：`npm --version`

## TypeScript 版本

**不需要单独安装 TypeScript！**

TypeScript 会作为项目依赖自动安装（版本：^5.2.2）

当你运行 `npm install` 时，会自动安装：
- TypeScript 5.2.2 或更高版本（在 devDependencies 中）

## 安装步骤

### 1. 确保 Node.js 已安装
```bash
node --version  # 应该显示 v18.x.x 或更高
npm --version   # 应该显示 9.x.x 或更高
```

### 2. 进入 webui 目录
```bash
cd onebot_framework/webui
```

### 3. 安装项目依赖
```bash
npm install
```

这会自动安装所有依赖，包括：
- TypeScript 5.2.2
- Next.js 14.0.4
- React 18.2.0
- 以及其他所有依赖

### 4. 验证安装
```bash
# 检查 TypeScript 版本（通过 npx）
npx tsc --version  # 应该显示 Version 5.2.x

# 检查所有依赖是否安装成功
npm list --depth=0
```

## 开发命令

### 启动开发服务器
```bash
npm run dev
```
访问 http://localhost:3000（Next.js 默认端口）

### 构建生产版本
```bash
npm run build
```
构建产物输出到 `../src/ui/static`

### 预览构建结果
```bash
npm run preview
```

## 常见问题

### Q: 我需要全局安装 TypeScript 吗？
**A: 不需要！** TypeScript 会作为项目依赖自动安装。使用 `npx tsc` 或通过 npm scripts 运行即可。

### Q: Node.js 版本太低怎么办？
**A: 升级 Node.js 到 18+ 版本**。可以使用 nvm 管理多个 Node.js 版本。

### Q: npm install 失败怎么办？
**A: 尝试以下方法：**
1. 清除 npm 缓存：`npm cache clean --force`
2. 删除 node_modules 和 package-lock.json，重新安装
3. 使用国内镜像：`npm config set registry https://registry.npmmirror.com`

### Q: 如何更新依赖？
**A: 使用以下命令：**
```bash
npm update          # 更新到 package.json 允许的最新版本
npm outdated        # 查看过时的包
npm install <package>@latest  # 更新特定包
```

## 版本总结

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| Node.js | 18.x+ (推荐 20.x LTS) | 必需，全局安装 |
| npm | 9.x+ | 随 Node.js 安装 |
| TypeScript | 5.2.2+ | 自动安装，无需全局安装 |
| Next.js | 14.0.4+ | 自动安装 |
| React | 18.2.0+ | 自动安装（Next.js 依赖） |

## 快速开始

```bash
# 1. 检查 Node.js 版本
node --version

# 2. 进入项目目录
cd onebot_framework/webui

# 3. 安装依赖
npm install

# 4. 启动开发服务器
npm run dev
```

完成！现在可以开始开发了 🎉

