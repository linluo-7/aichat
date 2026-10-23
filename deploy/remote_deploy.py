#!/usr/bin/env python3
"""上传项目并在服务器上构建、启动 Docker 与 Nginx 配置。"""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("DEPLOY_HOST", "146.56.251.112")
USER = os.environ.get("DEPLOY_USER", "root")
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
# 无密码时可用密钥：DEPLOY_SSH_KEY，或默认 ~/.ssh/id_rsa_hui
SSH_KEY = os.environ.get(
    "DEPLOY_SSH_KEY",
    str(Path.home() / ".ssh" / "id_rsa_hui"),
)
REMOTE = os.environ.get("DEPLOY_PATH", "/opt/qixiang")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 默认使用 Docker 层缓存；仅当 DEPLOY_NO_CACHE=1 时全量重建（很慢）
NO_CACHE = os.environ.get("DEPLOY_NO_CACHE", "").strip() in ("1", "true", "yes")

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "agent-transcripts",
}
SKIP_SUFFIX = {".pyc", ".pyo"}


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if any(p in SKIP_DIRS for p in parts):
        return True
    if rel.suffix in SKIP_SUFFIX:
        return True
    return False


def build_tarball(tar_path: Path) -> None:
    """打包 backend、frontend 与 deploy 配置。"""
    with tarfile.open(tar_path, "w:gz") as tar:
        for folder in ("backend", "frontend", "deploy"):
            base = PROJECT_ROOT / folder
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_dir():
                    continue
                rel = path.relative_to(PROJECT_ROOT)
                if should_skip(rel):
                    continue
                tar.add(path, arcname=str(rel).replace("\\", "/"))


def run(ssh: paramiko.SSHClient, cmd: str) -> None:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"命令失败 ({code}): {cmd}")


def main() -> None:
    key_path = Path(SSH_KEY).expanduser() if SSH_KEY else None
    use_key = bool(key_path and key_path.is_file())
    if not PASSWORD and not use_key:
        print("请设置 DEPLOY_SSH_PASSWORD，或配置可用的 DEPLOY_SSH_KEY", file=sys.stderr)
        sys.exit(1)

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tar_path = Path(tmp.name)
    try:
        t0 = time.time()
        print("打包项目…")
        build_tarball(tar_path)
        print(f"打包完成 ({time.time() - t0:.1f}s)")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"连接 {USER}@{HOST}…")
        if PASSWORD:
            ssh.connect(HOST, username=USER, password=PASSWORD, timeout=60)
        else:
            print(f"使用密钥 {key_path}")
            ssh.connect(
                HOST,
                username=USER,
                key_filename=str(key_path),
                timeout=60,
                look_for_keys=False,
                allow_agent=False,
            )

        sftp = ssh.open_sftp()
        run(ssh, f"mkdir -p {REMOTE}")
        remote_tar = f"{REMOTE}/aichat-src.tar.gz"
        print(f"上传 {tar_path} -> {remote_tar}")
        sftp.put(str(tar_path), remote_tar)
        sftp.close()

        run(ssh, f"cd {REMOTE} && tar xzf aichat-src.tar.gz && rm -f aichat-src.tar.gz")
        run(ssh, f"cp -f {REMOTE}/deploy/docker-compose.yml {REMOTE}/docker-compose.yml")
        run(
            ssh,
            "export DEBIAN_FRONTEND=noninteractive; "
            "command -v docker >/dev/null || (apt-get update -y && apt-get install -y docker.io docker-compose-v2); "
            "command -v nginx >/dev/null || apt-get install -y nginx",
        )
        build_flag = " --no-cache" if NO_CACHE else ""
        if NO_CACHE:
            print("构建镜像（全量 --no-cache，较慢）…")
        else:
            print("构建镜像（使用 Docker 缓存，通常 1～3 分钟）…")
        t_build = time.time()
        run(ssh, f"cd {REMOTE} && docker compose build{build_flag}")
        print(f"构建完成 ({time.time() - t_build:.1f}s)")
        run(ssh, f"cd {REMOTE} && docker compose up -d")

        nginx_src = f"{REMOTE}/deploy/nginx/chat.linluo.site.conf"
        nginx_dst = "/etc/nginx/sites-available/chat.linluo.site.conf"
        # 已有 Let's Encrypt 证书时不覆盖站点配置，避免冲掉 HTTPS
        run(
            ssh,
            "if [ -d /etc/letsencrypt/live/chat.linluo.site ]; then "
            "echo '跳过 Nginx 覆盖（已有 HTTPS 证书）'; "
            "else "
            f"cp -f {nginx_src} {nginx_dst} && "
            f"ln -sf {nginx_dst} /etc/nginx/sites-enabled/chat.linluo.site.conf; "
            "fi",
        )
        run(ssh, "nginx -t")
        run(ssh, "systemctl reload nginx || systemctl restart nginx")

        run(ssh, f"cd {REMOTE} && docker compose ps")
        ssh.close()
        print(f"\n部署完成，总耗时 {time.time() - t0:.1f}s。请访问 https://chat.linluo.site 或 http://chat.linluo.site")
    finally:
        tar_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
