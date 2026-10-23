# AI 聊天平台（QQ 风格）

## 访问地址

| 服务 | 端口 |
|------|------|
| 前端 Web | http://localhost:8090 |
| 后端 API | http://localhost:8091 |

## Docker 一键启动

```bash
docker compose up -d --build
```

## 本地开发

**后端**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8091
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

## 功能说明

- 新建会话 = 创建「AI 联系人」：昵称、角色设定、DeepSeek API Key、头像
- 聊天界面仿 QQ：左侧列表、气泡（自己绿色 / 对方白色）、流式回复
- 每个联系人可单独设置聊天背景图

## 安全提示

API Key 当前保存在 SQLite 中，仅供自用/内网部署。生产环境请加密存储并限制访问。
