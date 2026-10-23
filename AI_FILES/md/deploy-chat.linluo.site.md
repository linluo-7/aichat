# chat.linluo.site 部署说明

## 架构

- 域名：`chat.linluo.site`
- 路径：`/opt/qixiang/`
- 宿主 Nginx `:80` 反代：
  - `/`、`/index.html` 等 → `127.0.0.1:8080`（Docker 前端 nginx）
  - `/api/`、`/uploads/` → `127.0.0.1:8000`（Docker FastAPI）
- 容器仅监听本机，不对外直接暴露 8080/8000。

## 服务器文件

| 路径 | 说明 |
|------|------|
| `/opt/qixiang/docker-compose.yml` | 来自 `deploy/docker-compose.yml` |
| `/opt/qixiang/backend/`、`frontend/` | 源码，Docker 构建 |
| `/etc/nginx/sites-available/chat.linluo.site.conf` | 来自 `deploy/nginx/chat.linluo.site.conf` |

## 常用命令（SSH 到服务器后）

```bash
cd /opt/qixiang
docker compose ps
docker compose logs -f --tail=100
docker compose build && docker compose up -d   # 更新代码后重建（用缓存较快）
# 全量重建（慢）：DEPLOY_NO_CACHE=1 python deploy/remote_deploy.py
nginx -t && systemctl reload nginx
```

## 本地再次部署

```powershell
$env:DEPLOY_SSH_PASSWORD='你的密码'
python deploy/remote_deploy.py
```

可选环境变量：`DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_PATH`。

## HTTPS（已配置）

- 证书：Let's Encrypt（`/etc/letsencrypt/live/chat.linluo.site/`）
- HTTP 自动跳转 HTTPS；证书约每 90 天由 `certbot.timer` 自动续期
- 本地一键（需 `DEPLOY_SSH_PASSWORD`）：

```powershell
$env:DEPLOY_SSH_PASSWORD='你的密码'
python deploy/setup_https.py
```

服务器上手动：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d chat.linluo.site --redirect
```

**注意**：`remote_deploy.py` 在已有证书时**不会**覆盖 Nginx 站点配置，避免冲掉 HTTPS。

## DNS / 防火墙

`chat.linluo.site` A 记录指向 `146.56.251.112`；需放行 **80** 与 **443**（本机 iptables + 云厂商安全组）。
