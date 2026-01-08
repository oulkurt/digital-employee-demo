# Digital Employee Demo

数字员工记忆系统 Demo - 基于 LangGraph + LangMem 的 ReAct Agent，支持长期记忆与 RAG 检索增强。

## 技术栈

- **Agent**: LangGraph ReAct + LangMem
- **LLM**: GLM-4.7 (智谱官方 API)
- **Embedding**: 硅基流动 bge-m3
- **Reranker**: 硅基流动 bge-reranker-v2-m3
- **搜索**: Tavily API
- **存储**: PostgreSQL + pgvector
- **Web UI**: Streamlit

## 快速开始

```bash
# 启动 PostgreSQL
docker-compose up -d

# 安装依赖
uv sync

# 初始化数据库
uv run python -m src.memory.store --init

# 启动应用
uv run streamlit run streamlit_app.py
```

## 环境变量

复制 `.env.example` 到 `.env` 并配置：

- `Chat LLM` - 对话 LLM 配置
- `SILICONFLOW_API_KEY` - Embedding + Reranker
- `TAVILY_API_KEY` - 搜索服务
- `DATABASE_URL` - PostgreSQL 连接串
