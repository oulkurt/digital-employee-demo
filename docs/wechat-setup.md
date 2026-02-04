# 企业微信配置指南

## 1. 获取企业微信凭证

### 1.1 CorpID
1. 登录 [企业微信管理后台](https://work.weixin.qq.com/)
2. 进入「我的企业」→「企业信息」
3. 复制「企业ID」

### 1.2 创建应用
1. 进入「应用管理」→「自建」→「创建应用」
2. 填写应用名称、Logo
3. 设置可见范围（选择可使用该应用的部门/成员）
4. 记录「AgentId」和「Secret」

### 1.3 配置消息接收
1. 进入应用详情 →「接收消息」→「设置API接收」
2. 配置项：
   - **URL**: `http://<服务器公网IP>:36060/com_wechat/callback`
   - **Token**: 自定义字符串（32字符以内）
   - **EncodingAESKey**: 点击「随机生成」

3. 点击保存，企业微信会向该 URL 发送验证请求

### 1.4 配置可信IP
1. 进入应用详情 →「企业可信IP」
2. 添加服务器的公网 IP 地址

---

## 2. 环境变量配置

将以下内容添加到 `.env` 文件：

```bash
# WeCom App (Enterprise WeChat)
WECOM_CORP_ID=ww-your-corp-id
WECOM_AGENT_ID=1000002
WECOM_SECRET=your-app-secret
WECOM_TOKEN=your-custom-token
WECOM_ENCODING_AES_KEY=your-encoding-aes-key
```

| 变量 | 来源 |
|------|------|
| `WECOM_CORP_ID` | 企业信息页面的「企业ID」 |
| `WECOM_AGENT_ID` | 应用详情页的「AgentId」 |
| `WECOM_SECRET` | 应用详情页的「Secret」 |
| `WECOM_TOKEN` | 接收消息配置的「Token」 |
| `WECOM_ENCODING_AES_KEY` | 接收消息配置的「EncodingAESKey」 |

---

## 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f musebot
```

启动后会运行 4 个容器：
- `digital-employee-pg` - PostgreSQL 数据库
- `digital-employee-calendar` - 日历 API (8000)
- `digital-employee-chat` - Chat API (8080)
- `digital-employee-musebot` - MuseBot 网关 (36060)

---

## 4. 验证

### 4.1 检查服务状态
```bash
# 健康检查
curl http://localhost:8080/health

# 直接测试 Chat API
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "你好"}]}'
```

### 4.2 测试企业微信
1. 打开企业微信 App
2. 搜索并进入你创建的应用
3. 发送消息，例如「你好」或「帮我预订明天下午3点的会议室」
4. 确认收到 Agent 回复

### 4.3 查看日志排查问题
```bash
# MuseBot 日志
docker logs digital-employee-musebot

# Chat API 日志
docker logs digital-employee-chat
```

---

## 5. 常见问题

### Q: 企业微信验证失败
**A**: 检查以下项：
- 服务器公网 IP 是否正确配置
- 端口 36060 是否开放（防火墙/安全组）
- Token 和 EncodingAESKey 是否与 .env 一致

### Q: 收不到回复
**A**: 检查：
- `docker logs digital-employee-musebot` 是否有请求日志
- `docker logs digital-employee-chat` 是否有处理日志
- PostgreSQL 是否正常运行

### Q: 回复很慢
**A**: Agent 调用 LLM 需要时间，首次回复可能需要 5-10 秒。如果超过 30 秒，检查：
- `OPENROUTER_API_KEY` 是否有效
- 网络是否能访问 OpenRouter API

---

## 6. 架构说明

```
企业微信用户
    │
    │ 发送消息
    ▼
企业微信服务器
    │
    │ HTTP 回调
    ▼
MuseBot (:36060)
    │
    │ CUSTOM_URL 转发
    ▼
Chat API (:8080/api/chat)
    │
    │ 调用 LangGraph Agent
    ▼
LangGraph ReAct Agent
    │
    ├──▶ 检索用户记忆 (PostgreSQL + pgvector)
    ├──▶ 调用工具 (日历/搜索)
    └──▶ 生成回复
    │
    ▼
返回给 MuseBot → 企业微信用户
```
