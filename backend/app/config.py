"""应用配置：数据库路径、上传目录、DeepSeek 默认地址。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Chat QQ"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    upload_dir: Path = Path("./uploads")
    deepseek_base_url: str = "https://api.deepseek.com"
    # DeepSeek V4 Flash（官方名 deepseek-flash；旧名 deepseek-v4-flash 也可）
    deepseek_model: str = "deepseek-flash"
    cors_origins: str = "http://localhost:8090,http://127.0.0.1:8090"
    # 自动发消息：用户未回复时最多连续主动条数
    auto_message_streak_max: int = 3
    # 用户连发合并等待秒数
    reply_merge_seconds: int = 2
    # 记忆整理：新增消息条数触发阈值
    memory_extract_message_threshold: int = 12
    # 记忆整理：空闲分钟数触发
    memory_extract_idle_minutes: int = 10
    # 每个联系人每日最多整理次数
    memory_extract_daily_max: int = 24
    # 有效记忆上限
    memory_active_max: int = 150
    # 是否模拟打字停顿（测试可设为 false）
    reply_typing_enabled: bool = True
    # 全站默认开启网页搜索/抓取（flash + Search/Fetch API）
    web_tools_enabled: bool = True
    # JWT 签名密钥（生产必须用环境变量覆盖）
    auth_secret: str = "dev-only-change-me"
    # JWT 有效期（天）
    auth_token_days: int = 30
    # 空库时自动创建管理员（用户名/密码）；生产创建后请改密
    bootstrap_admin_user: str = "lxy"
    bootstrap_admin_password: str = "change-me"


settings = Settings()
