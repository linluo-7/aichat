# 邀请码注册 + 登录隔离（学习分享版）

> 定位：无偿学习分享 / 自带 Key / 自愿赞赏。  
> 注册：先校验邀请码 → 通过后设账号密码 → 完成后可登录。邀请码由站长下发，**一次性**。  
> 本期不做：付费、赞赏收款、管理端网页、开放无码注册。

---

## 1. Goal（验收）

| # | 目标 | 验收标准 |
|---|------|----------|
| G1 | 邀请码注册 | 无码/错码/已用码无法注册；有效码用一次后作废 |
| G2 | 登录鉴权 | 未登录业务 API → 401 |
| G3 | 数据隔离 | 用户互不可见联系人/消息/记忆 |
| G4 | 资料归属 | 每人独立昵称/头像 |
| G5 | BYOK 脱敏 | 接口只返回 api_key 掩码 |
| G6 | 旧数据迁移 | 存量数据归 bootstrap 管理员 |
| G7 | 改密 | 登录用户可改自己密码 |
| G8 | 下发邀请码 | 站长用 CLI 生成邀请码（可批量） |

**非目标**：管理网页、OAuth、计费、内容审核后台。

---

## 2. 注册 / 登录 UX

1. **登录页**：账号 + 密码；链到「注册」。
2. **注册 · 步骤 1**：输入邀请码 → `POST /api/auth/invite/check`。
3. **注册 · 步骤 2**：用户名 + 密码（+ 确认密码）→ `POST /api/auth/register`（再次带上邀请码，服务端原子核销）。
4. 注册成功后自动登录进入主界面（可选强制改密：邀请注册可不强制）。

站长侧：`python -m app.scripts.create_invite [--count N]` 打印明文邀请码。

---

## 3. 数据模型

### `users`【账号】用户表
- id, username(UNIQUE), password_hash, is_admin, is_active, created_at, updated_at

### `invite_codes`【账号】邀请码表
- id
- code（UNIQUE，短码如 8～12 位易读字符）
- created_by_user_id（可空，CLI 创建时挂 admin）
- used_by_user_id（可空）
- used_at（可空）
- created_at
- 约束：`used_by_user_id IS NOT NULL` 即已使用；注册事务内 UPDATE WHERE used_by IS NULL

### `user_profile`：加 `user_id` UNIQUE FK  
### `contacts`：加 `user_id` FK + 索引

---

## 4. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/invite/check` | `{code}` → 是否可用 |
| POST | `/api/auth/register` | `{code, username, password}` 核销+建用户+返回 token |
| POST | `/api/auth/login` | `{username, password}` → token |
| POST | `/api/auth/change-password` | 需登录 |
| GET | `/api/auth/me` | 需登录，当前用户 |

其余业务 API 全部 `Bearer` 鉴权 + `user_id` 过滤。无 `register` 在无码时成功。

Contact 响应：`api_key_masked`，更新时 api_key 可选留空不改。

---

## 5. 其它约定

- JWT Bearer + localStorage；`AUTH_SECRET` 环境变量必填（生产）
- 空库 bootstrap：`BOOTSTRAP_ADMIN_USER` / `BOOTSTRAP_ADMIN_PASSWORD` 建管理员（便于 CLI 记 created_by）
- 登录名：**仅用户名**
- 限流：invite/check、register、login 简单防刷
- 上传：`uploads/{user_id}/...`

---

## 6. 执行顺序

1. 依赖 + 模型 + SQL + 迁移（旧数据 → admin）
2. auth 服务、邀请码核销、路由
3. 业务路由鉴权隔离 + Key 掩码
4. CLI `create_invite`（及可选 `create_user` 给 admin 救急）
5. 前端：登录 / 两步注册 / token 拦截 / 编辑 Key
6. 本地验收 → 按需部署

---

## 7. Tests

- 邀请码：有效 / 无效 / 已用；并发双注册仅一人成功
- 未登录 401；跨用户 contact → 404
- 注册成功后可 login

---

## 8. 已拍板

- 登录名：仅用户名  
- 开户方式：**邀请码一次性注册**（取代「仅 CLI 代开」为主路径；CLI 只负责产码 + bootstrap admin）

## 9. 实现状态

已落地（2026-10-23）：后端鉴权/隔离/掩码、邀请码注册、CLI `create_invite`、前端登录与两步注册、改密与退出。说明见 `AI_FILES/md/auth-invite-users.md`。
