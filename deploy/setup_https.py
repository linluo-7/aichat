#!/usr/bin/env python3
"""在服务器上为 chat.linluo.site 申请 Let's Encrypt 证书并启用 HTTPS。"""
from __future__ import annotations

import os
import sys

import paramiko

HOST = os.environ.get("DEPLOY_HOST", "146.56.251.112")
USER = os.environ.get("DEPLOY_USER", "root")
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
EMAIL = os.environ.get("CERTBOT_EMAIL", "admin@linluo.site")
DOMAIN = "chat.linluo.site"


def run(ssh: paramiko.SSHClient, cmd: str, *, check: bool = True) -> str:
    print(f"\n>>> {cmd}")
    _stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    if check and code != 0:
        raise RuntimeError(f"命令失败 ({code}): {cmd}")
    return out


def main() -> None:
    if not PASSWORD:
        print("请设置环境变量 DEPLOY_SSH_PASSWORD", file=sys.stderr)
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {USER}@{HOST}…")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)

    # 本机防火墙放行 80/443（若启用 ufw）
    run(
        ssh,
        "if command -v ufw >/dev/null && ufw status | grep -q 'Status: active'; then "
        "ufw allow 80/tcp; ufw allow 443/tcp; ufw status; "
        "else echo 'ufw 未启用或未安装，跳过'; fi",
        check=False,
    )
    # iptables 放行 443（Oracle 镜像常用）
    run(
        ssh,
        "iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || "
        "iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT; "
        "iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || "
        "iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT; "
        "command -v netfilter-persistent >/dev/null && "
        "netfilter-persistent save || true",
        check=False,
    )

    run(
        ssh,
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -y && "
        "apt-get install -y certbot python3-certbot-nginx",
    )

    # HTTP 可达性（证书申请需要）
    run(ssh, f"curl -sI -m 15 http://{DOMAIN}/ | head -n 5", check=False)

    # 非交互申请；已有证书则尝试续期/重装 nginx 插件配置
    run(
        ssh,
        f"certbot --nginx -d {DOMAIN} "
        f"--non-interactive --agree-tos --email {EMAIL} "
        f"--redirect --keep-until-expiring",
    )

    run(ssh, "nginx -t")
    run(ssh, "systemctl reload nginx")
    run(ssh, "systemctl enable --now certbot.timer || true", check=False)
    run(ssh, "systemctl status certbot.timer --no-pager || true", check=False)

    print("\n验证 HTTPS…")
    run(ssh, f"curl -sI -m 20 https://{DOMAIN}/ | head -n 15", check=False)
    run(ssh, "certbot certificates", check=False)

    ssh.close()
    print(f"\nHTTPS 配置完成：https://{DOMAIN}")
    print(
        "若外网仍打不开 443：请到 Oracle Cloud 安全列表放行 TCP 443（源 0.0.0.0/0）。"
    )


if __name__ == "__main__":
    main()
