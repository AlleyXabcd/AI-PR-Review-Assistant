# Frontend — AI PR Review 助手

Next.js (App Router) + TypeScript + Tailwind CSS v4。

负责：输入 GitHub PR URL，调用后端 `POST /review/summary`，展示变更总结、
PR 元信息与变更文件列表。

## 目录结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx       # 根布局
│   │   ├── page.tsx         # 首页（输入 PR URL + 触发分析）
│   │   └── globals.css      # Tailwind 入口 + 主题
│   ├── components/
│   │   └── SummaryView.tsx  # 总结结果展示
│   └── lib/
│       ├── api.ts           # 调后端的 fetch 封装
│       └── types.ts         # 与后端对应的响应类型
├── package.json
└── tsconfig.json
```

## 本地开发

```bash
cd frontend
pnpm install

# 可选：自定义后端地址（默认 http://127.0.0.1:8000）
cp .env.local.example .env.local

pnpm dev      # http://localhost:3000
pnpm build    # 生产构建（含类型检查）
```

> 需先启动后端（见 ../backend/README.md），并在后端 .env 配置 DEEPSEEK_API_KEY。
