# Xiaoyi_QQ WebUI

现代化的 React + TypeScript Web 管理界面，支持中英文双语。

## 功能特性

- 🎨 现代化 UI 设计，使用 Tailwind CSS
- 🌐 双语支持（中文/英文）
- 📱 响应式设计，支持移动端
- 🔐 完整的身份认证和权限管理
- 🧩 插件管理界面
- 📊 系统状态监控
- 📝 审计日志查看

## 开发

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

开发服务器将在 http://localhost:3000 启动，并代理 API 请求到后端。

### 构建生产版本

```bash
npm run build
```

构建产物将输出到 `../src/ui/static` 目录，由 FastAPI 后端服务。

## 项目结构

```
webui/
├── src/
│   ├── components/     # React 组件
│   ├── pages/          # 页面组件
│   ├── store/          # 状态管理 (Zustand)
│   ├── utils/          # 工具函数
│   ├── i18n/           # 国际化配置
│   └── styles/         # 样式文件
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## 技术栈

- **React 18** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **React Router** - 路由管理
- **Zustand** - 状态管理
- **i18next** - 国际化
- **Tailwind CSS** - 样式框架
- **Axios** - HTTP 客户端
- **Lucide React** - 图标库

## 环境变量

创建 `.env` 文件（可选）：

```env
VITE_API_BASE_URL=http://localhost:8080/api
```

## 语言切换

用户可以通过界面右上角的语言切换按钮在中英文之间切换。语言偏好会保存在本地存储中。

