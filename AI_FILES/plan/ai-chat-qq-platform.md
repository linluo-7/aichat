# Goal
搭建 QQ 风格 AI 聊天平台：FastAPI 后端(8091) + Vue3 前端(8090)，Docker Compose 一键部署；联系人含姓名/设定/DeepSeek API Key/头像，支持聊天背景。

# Files
- backend/app/* — API、DeepSeek 调用、SQLite
- frontend/src/* — QQ 风格 UI
- docker-compose.yml, README.md

# Steps
1. 后端：模型、联系人 CRUD、流式聊天、静态文件（头像/背景）
2. 前端：联系人列表、创建表单、聊天页、背景设置
3. Docker Compose + Nginx 反代

# Tests
- 手动：docker compose up，创建联系人并发送消息

# Risks
- API Key 明文存库（文档说明生产需加密）
