# AI Chat · QQ 风格聊天

前后端分离的 AI 聊天平台：**Vue3** 前端（8090）+ **FastAPI** 后端（8091），每个会话对应一个「AI 联系人」（姓名、人设、DeepSeek API Key、头像、独立聊天背景）。

## 快速启动（Docker）

```bash
docker compose up -d --build
```

浏览器打开 [http://localhost:8090](http://localhost:8090)

## 本地开发

详见 [AI_FILES/md/README-project.md](AI_FILES/md/README-project.md)

## 技术栈

- 后端：FastAPI、SQLAlchemy、SQLite、DeepSeek Chat API（流式 SSE）
- 前端：Vue 3、Pinia、Vite
- 部署：Docker Compose + Nginx 反代 API
