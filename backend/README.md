# Backend — AI PR Review 助手

FastAPI 服务 + 分析核心。负责：

- 解析并抓取 GitHub PR 的变更（diff / files / commits）+ 跨文件上下文（head 版完整文件）
- 封装 DeepSeek 客户端（`deepseek-chat` 分诊、`deepseek-reasoner` 深查）
- Review 引擎：变更总结、风险识别（双层分诊 + 复查）、SSE 流式输出
- 评论回写：把分析结果拼成结构化评论发布到 PR
- SQLite 缓存（PR + head_sha 版本键）

## 已实现

- `app/core/config.py`：基于 pydantic-settings 的配置（读取 .env）
- `app/models/github.py`：PR 数据模型（PRRef / PRFile / PRCommit / PullRequest）
- `app/models/llm.py`：LLM 数据模型（ChatMessage / LLMResponse / TokenUsage）
- `app/models/review.py`：接口请求/响应模型（Summary / Risk / Writeback）
- `app/services/github_client.py`：PR URL 解析 + GitHub REST 抓取（含分页、错误处理）+ 评论回写
- `app/services/deepseek_client.py`：DeepSeek 客户端（chat=V3 / reason=R1，含重试）
- `app/services/prompts.py`：prompt 模板与 diff 渲染
- `app/services/json_utils.py`：从模型输出稳健提取 JSON
- `app/services/summary_service.py`：变更总结编排（抓取→prompt→V3→解析）
- `app/services/risk_service.py`：风险识别（V3 全量分诊 → R1 对高危点复查）
- `app/services/review_stream.py`：SSE 编排（stage / summary_delta / summary / risks / done）
- `app/services/writeback_service.py`：复用总结+风险结果拼装评论并回写 GitHub
- `app/services/cache.py`：SQLite 结果缓存（以 PR + head_sha 为版本键）
- `app/api/review.py`：`POST /review/summary`、`POST /review/risks`、`POST /review/writeback`、`GET /review/stream`
- `app/main.py`：FastAPI 入口（含 /health 与 CORS）
- `app/scripts/`：手动验证脚本（fetch_pr / try_deepseek）

## 目录结构

```
backend/
├── app/
│   ├── core/            # 配置
│   ├── models/          # Pydantic 数据模型（github / llm / review）
│   ├── services/        # 抓取、DeepSeek 客户端、总结/风险/流式/回写、缓存
│   ├── api/             # FastAPI 路由（/review/*）
│   └── scripts/         # 手动验证脚本
├── tests/
└── pyproject.toml
```

## 本地开发

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux

# 运行测试
python -m pytest -q

# 手动抓取一个 PR（公开仓库无需 token；私有仓库需在 .env 配置 GITHUB_TOKEN）
python -m app.scripts.fetch_pr https://github.com/octocat/Hello-World/pull/1

# 调一次 DeepSeek（需在 .env 配置 DEEPSEEK_API_KEY）
python -m app.scripts.try_deepseek            # deepseek-chat (V3)
python -m app.scripts.try_deepseek --reason   # deepseek-reasoner (R1)
```

## 运行服务

```bash
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 健康检查
curl http://127.0.0.1:8000/health

# 变更总结（需配置 DEEPSEEK_API_KEY；公开仓库无需 GITHUB_TOKEN）
curl -X POST http://127.0.0.1:8000/review/summary \
  -H "Content-Type: application/json" \
  -d '{"pr_url":"https://github.com/octocat/Hello-World/pull/1"}'

# 风险识别（双层模型：V3 分诊 → R1 复查高危点）
curl -X POST http://127.0.0.1:8000/review/risks \
  -H "Content-Type: application/json" \
  -d '{"pr_url":"https://github.com/octocat/Hello-World/pull/1"}'

# 流式分析（SSE：概述逐字 + 风险整块）
curl -N "http://127.0.0.1:8000/review/stream?pr_url=https://github.com/octocat/Hello-World/pull/1"

# 评论回写（dry_run=true 仅预览；false 真正发布，需 token 对目标仓库有写权限）
curl -X POST http://127.0.0.1:8000/review/writeback \
  -H "Content-Type: application/json" \
  -d '{"pr_url":"https://github.com/owner/repo/pull/1","dry_run":true}'
```

接口文档：启动后访问 http://127.0.0.1:8000/docs
