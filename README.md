# Digital Employee Demo

Digital Employee Memory System Demo - LangGraph + LangMem ReAct Agent

## 快速开始

```bash
# 启动 PostgreSQL
docker-compose up -d

# 安装依赖
uv sync

# 初始化数据库
uv run python -m src.memory.store --init

# 启动应用
uv run chainlit run app.py
```

## 环境变量

复制 `.env.example` 到 `.env` 并配置相关 API Key。
