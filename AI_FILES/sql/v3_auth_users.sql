-- 【账号】用户表 / 邀请码表 / 资料与联系人归属（V3）

-- 【账号】用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,           -- 登录用户名
    password_hash VARCHAR(255) NOT NULL,            -- 密码哈希
    is_admin INTEGER NOT NULL DEFAULT 0,            -- 是否管理员
    is_active INTEGER NOT NULL DEFAULT 1,           -- 是否启用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 【账号】邀请码表（一次性）
CREATE TABLE IF NOT EXISTS invite_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,               -- 邀请码
    created_by_user_id INTEGER,                    -- 创建人
    used_by_user_id INTEGER,                       -- 使用人（非空=已用）
    used_at DATETIME,                              -- 使用时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- user_profile.user_id / contacts.user_id 由应用轻量迁移添加
CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts (user_id);
