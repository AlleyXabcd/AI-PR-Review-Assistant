# Backend — AI PR Review 助手

FastAPI 服务 + 分析核心。负责：

- 解析并抓取 GitHub PR 的变更（diff / files / commits）
- 封装 DeepSeek 客户端（`deepseek-chat` 分诊、`deepseek-reasoner` 深查）
- Review 引擎：变更总结、风险识别、行级建议生成
- SQLite 缓存

## 计划目录结构

```
backend/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── api/             # 路由层
│   ├── core/            # 配置、设置
│   ├── services/        # github 抓取、deepseek 客户端、review 引擎
│   └── models/          # Pydantic 数据模型
├── tests/
├── pyproject.toml
└── README.md
```

> 具体实现随后续 PR 逐步补充。
