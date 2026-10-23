# 邀请码注册与开号说明

## 用户侧

1. 打开站点 → **用邀请码注册**
2. 输入站长下发的邀请码 → 下一步
3. 设置用户名、密码 → 完成并自动登录
4. 之后用用户名密码登录；在「我的资料」可改密、退出

每个邀请码**只能用一次**。

## 站长侧：生成邀请码

在后端容器或本机 `backend` 目录：

```bash
# 生成 1 个
python -m app.scripts.create_invite

# 生成多个
python -m app.scripts.create_invite --count 5
```

Docker 示例：

```bash
docker compose exec backend python -m app.scripts.create_invite --count 3
```

把打印出的码发给好友即可。

## 默认管理员（空库首次启动）

环境变量（可选，有默认值）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `BOOTSTRAP_ADMIN_USER` | `lxy` | 首个管理员用户名 |
| `BOOTSTRAP_ADMIN_PASSWORD` | （见部署配置） | 首个管理员密码 |
| `AUTH_SECRET` | `dev-only-change-me` | JWT 密钥，**生产务必改成随机长串** |
| `AUTH_TOKEN_DAYS` | `30` | 登录有效天数 |

生产建议在 `.env` / compose 中设置强 `AUTH_SECRET`，并用管理员账号登录后修改密码。

## 数据隔离

联系人、消息、记忆、上传文件均按用户隔离；接口返回的 API Key 仅为掩码。
