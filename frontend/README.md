# Frontend — AI PR Review 助手

Next.js (App Router) + TypeScript + Tailwind CSS v4。

负责：输入 GitHub PR URL，以 SSE 订阅后端 `GET /review/stream`，逐字呈现变更概述、
展示风险概览（按级别/类别聚合与筛选）、行级 diff 高亮与风险定位，并支持把分析结果
回写为 GitHub PR 评论（预览 + 显式确认）。

## 目录结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # 根布局
│   │   ├── page.tsx            # 首页（输入 PR URL + SSE 编排 + 组装各视图）
│   │   └── globals.css         # Tailwind 入口 + 主题
│   ├── components/
│   │   ├── SummaryView.tsx     # 变更总结展示（概述 + 元信息）
│   │   ├── RiskOverview.tsx    # 风险概览（级别/类别计数、筛选、点击定位）
│   │   ├── DiffView.tsx        # 行级 diff 高亮 + 风险标注 + 滚动定位
│   │   └── WritebackPanel.tsx  # 评论回写（预览 / 确认发布）
│   └── lib/
│       ├── api.ts              # 调后端的 fetch + SSE（EventSource）封装
│       ├── types.ts            # 与后端对应的响应类型
│       ├── diff.ts             # unified diff 解析为增删行
│       └── risk.ts             # 风险级别/类别的展示常量与 diff 锚点
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
