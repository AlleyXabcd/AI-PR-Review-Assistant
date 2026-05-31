# AI PR Review 助手

一个以 AI 辅助分析为核心的代码评审工具。用户指定 GitHub Pull Request，系统自动获取代码变更并智能分析，辅助开发者发现问题、提升 Review 效率与质量。

> 七牛云 1024 创意马拉松 · 题目三作品

## 核心能力

- **PR 变更总结**：自动概括本次 PR 改动的意图、关键改动与潜在影响。
- **风险代码识别**：按 安全 / 性能 / 正确性 / 可维护性 分类，标注严重级别与置信度。
- **双层模型分析**：DeepSeek-V3 快速分诊全量改动 → DeepSeek-R1 对高风险点深度复查，确认 / 驳回误报 / 修正级别，兼顾速度与质量。
- **跨文件上下文理解**：不止读 diff，还按变更量补充被改文件在 head 版本的完整内容，降低误报与漏报。
- **风险概览与定位**：按严重级别 / 类别聚合计数与筛选，点击任一风险即可滚动到 diff 对应行并高亮。
- **行级 diff 高亮**：解析 unified diff 渲染增删行，把风险点叠加到对应代码行下方。
- **流式输出体验**：基于 SSE，变更概述逐字打字机式呈现，风险分析就绪后整块到达。
- **评论回写 GitHub**：把分析结果拼成结构化评论回写到 PR 对话区，默认预览、显式确认后才发布。
- **结果缓存**：以 PR + head_sha 为版本键缓存分析结果，未改动的 PR 二次分析直接命中、不重复调用模型。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.11+ + FastAPI + httpx + Pydantic v2 |
| LLM | DeepSeek（`deepseek-chat` / `deepseek-reasoner`，OpenAI 兼容接口，复用 openai SDK） |
| 前端 | Next.js 15（App Router）+ React 19 + TypeScript + Tailwind CSS v4 |
| 流式 | Server-Sent Events（后端手写 text/event-stream，前端原生 EventSource） |
| 存储 | SQLite（标准库 sqlite3，缓存分析结果） |
| GitHub 接入 | REST API + Personal Access Token |

> 前端组件为手写实现（未使用 UI 组件库），样式基于 Tailwind v4。

## 目录结构

```
.
├── backend/    # FastAPI 服务 + 分析核心（GitHub 抓取、DeepSeek 客户端、Review 引擎、缓存、回写）
├── frontend/   # Next.js 前端（输入 PR URL，展示总结、风险概览、行级 diff，回写评论）
└── docs/       # 题目与设计文档
```

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env   # 填入 DEEPSEEK_API_KEY 与 GITHUB_TOKEN

# 2. 后端（Python 3.11+）
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 3. 前端（另开一个终端）
cd frontend && pnpm install && pnpm dev   # http://localhost:3000
```

打开 http://localhost:3000，粘贴一个 GitHub PR 地址即可分析。

> **关于 GITHUB_TOKEN 权限**：分析公开仓库的 PR 无需 token；分析私有仓库需 token 具备 repo 读权限。
> **评论回写**额外要求 token 对目标仓库具备**写权限**，因此回写只能作用于你有权限的仓库。

## 设计思路

### 模型选择
采用 **DeepSeek 双层模型**，按任务难度分配算力：
- `deepseek-chat`（V3）：快、便宜，负责变更总结与对全量改动的风险分诊，覆盖面广。
- `deepseek-reasoner`（R1）：推理强，仅对 V3 标记为「高危」的风险点做深度复查，确认 / 驳回误报 / 修正级别。

这样既保证响应速度与成本可控，又把更强的推理能力集中用在最需要谨慎判断的高风险点上，降低误报。

### 上下文获取方式
不止把 diff 喂给模型，还会：
- 解析 PR 的 files / commits，把 unified diff 与 PR 元信息一并构建进 prompt；
- 按变更量挑选前若干个被改文件，拉取其在 head 版本的**完整内容**作为跨文件上下文，帮助模型理解被引用符号与改动的真实影响，从而降低漏报与误报；
- 对超大 / 二进制文件做截断与跳过，控制请求体量与延迟。

### 未来扩展方向
- **行级 inline 评论回写**：当前回写为 PR 级总结评论；可进一步把每个风险点作为 inline review 评论贴到 diff 具体行（需精确的 commit_id + path + line 映射）。
- **CLI 工具**：复用后端分析核心，提供 `pr-review <github-pr-url>` 的终端评审（彩色报告 / JSON 输出），便于接入 CI。
- **更多代码托管平台**：抽象 GitHub 抓取层，扩展 GitLab / Gitee。
- **Review 建议采纳闭环**：结合 PR 讨论与采纳情况持续优化 prompt 与阈值。

## 依赖与原创说明

### 第三方库
后端（`backend/pyproject.toml`）：
- `fastapi` / `uvicorn`：Web 框架与 ASGI 服务
- `httpx`：异步 HTTP 客户端（调用 GitHub REST API）
- `pydantic` / `pydantic-settings`：数据模型与配置
- `openai`：复用其 SDK 调用 DeepSeek 的 OpenAI 兼容接口
- `python-dotenv`：加载 .env
- 开发依赖：`pytest` / `pytest-asyncio` / `respx`（HTTP mock）

前端（`frontend/package.json`）：
- `next` / `react` / `react-dom`：框架与运行时
- `tailwindcss` / `@tailwindcss/postcss`：样式
- `typescript` 及相关 `@types/*`：类型

存储使用 Python 标准库 `sqlite3`，SSE 为后端手写（未引入额外 SSE 库）。

### 原创部分
分析编排与核心逻辑均为原创，包括：双层模型分诊 + 复查流程、跨文件上下文采集策略、两段式总结输出（正文 + 元信息 JSON）与流式逐字解析、风险按行号归组与 diff 行级标注、PR + head_sha 版本化缓存、评论回写的预览 / 确认双段机制。

## 开发约定

- 基于 PR 增量开发，每个 PR 只做一件事，描述含：标题 / 功能描述 / 实现思路 / 测试方式。
- 每个 PR 合并后主分支保持可运行。
- 后端改动需通过 `cd backend && python -m pytest -q`；前端改动需通过 `cd frontend && npm run build`。

## Demo 视频

> 视频链接：[https://www.bilibili.com/video/BV1gRV76iEL2](https://www.bilibili.com/video/BV1gRV76iEL2)

视频覆盖以下核心模块的实际效果：

1. 粘贴 GitHub PR 地址，发起分析。
2. 变更概述 SSE 逐字呈现 → 结构化总结（意图 / 关键改动 / 影响）到达。
3. 风险概览：按 安全 / 性能 / 正确性 / 可维护性 与严重级别聚合、筛选。
4. 点击任一风险，滚动到 diff 对应行并高亮，查看行级标注。
5. 评论回写：预览生成的评论正文 → 显式确认后发布到 GitHub PR。

