# AI PR Review 助手

一个以 AI 辅助分析为核心的代码评审工具。用户指定 GitHub Pull Request，系统自动获取代码变更并智能分析，辅助开发者发现问题、提升 Review 效率与质量。

> 七牛云 1024 创意马拉松 · 题目三作品

## 核心能力

- **PR 变更总结**：自动概括本次 PR 改动的意图、范围与影响。
- **风险代码识别**：按 安全 / 性能 / 正确性 / 可维护性 分类，标注严重级别与置信度。
- **Review 建议生成**：定位到具体文件与行号，给出可执行的修改建议。
- **跨文件上下文理解**：不止读 diff，还按需补充被引用符号的上下文，降低误报与漏报。
- **双层模型分析**：DeepSeek-V3 快速分诊 → DeepSeek-R1 对高风险点深度复查，兼顾速度与质量。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.12 + FastAPI |
| LLM | DeepSeek（`deepseek-chat` / `deepseek-reasoner`，OpenAI 兼容接口） |
| 前端 | Next.js + TypeScript + Tailwind CSS + shadcn/ui |
| CLI | Python + Typer |
| 存储 | SQLite（缓存 PR 抓取与分析结果） |
| GitHub 接入 | Personal Access Token |

## 目录结构

```
.
├── backend/    # FastAPI 服务 + 分析核心（GitHub 抓取、DeepSeek 客户端、Review 引擎）
├── frontend/   # Next.js 前端（输入 PR URL，展示总结、风险与行级建议）
├── cli/        # Typer 命令行工具，复用后端分析核心
└── docs/       # 题目与设计文档
```

## 快速开始

> 详细步骤将随各模块 PR 逐步完善，此处为占位说明。

```bash
# 1. 配置环境变量
cp .env.example .env   # 填入 DEEPSEEK_API_KEY 与 GITHUB_TOKEN

# 2. 后端
cd backend && uvicorn app.main:app --reload

# 3. 前端
cd frontend && pnpm install && pnpm dev

# 4. CLI
cd cli && pr-review <github-pr-url>
```

## 设计思路

模型选择、上下文获取方式、未来扩展方向将在项目完成后于本节详述。

## 依赖与原创说明

本项目使用的第三方库与框架将在各模块 README 与本节统一列明；原创功能部分会单独标注。

## 开发约定

- 基于 PR 增量开发，每个 PR 只做一件事，描述含：标题 / 功能描述 / 实现思路 / 测试方式。
- 每个 PR 合并后主分支保持可运行。
