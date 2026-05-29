# Backend — AI PR Review 助手

FastAPI 服务 + 分析核心。负责：

- 解析并抓取 GitHub PR 的变更（diff / files / commits）
- 封装 DeepSeek 客户端（`deepseek-chat` 分诊、`deepseek-reasoner` 深查）
- Review 引擎：变更总结、风险识别、行级建议生成
- SQLite 缓存

## 已实现

- `app/core/config.py`：基于 pydantic-settings 的配置（读取 .env）
- `app/models/github.py`：PR 数据模型（PRRef / PRFile / PRCommit / PullRequest）
- `app/services/github_client.py`：PR URL 解析 + GitHub REST 抓取（含分页、错误处理）
- `app/scripts/fetch_pr.py`：手动验证脚本

## 目录结构

```
backend/
├── app/
│   ├── core/            # 配置
│   ├── models/          # Pydantic 数据模型
│   ├── services/        # github 抓取（后续：deepseek 客户端、review 引擎）
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
```
