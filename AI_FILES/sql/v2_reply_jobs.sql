-- V2：服务端回复流水线 / 模型切换 / 自动消息调度 相关表结构（SQLite）
-- 实际迁移由 backend/app/services/migrate.py 在启动时按“列不存在才添加”的方式执行

-- 【聊天】回复任务表：用户发消息或自动调度时创建，后台 Worker 领取执行
CREATE TABLE IF NOT EXISTS reply_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,              -- 任务ID
    contact_id    INTEGER NOT NULL
                  REFERENCES contacts(id) ON DELETE CASCADE,      -- 联系人ID
    trigger       VARCHAR(16)  NOT NULL DEFAULT 'user',           -- 触发来源：user 用户消息 / auto 自动发消息
    status        VARCHAR(16)  NOT NULL DEFAULT 'pending',        -- 状态：pending 待执行 / running 执行中 / done 完成 / failed 失败
    run_after     DATETIME     NOT NULL,                          -- 最早执行时间（用于合并用户连发）
    attempts      INTEGER      NOT NULL DEFAULT 0,                -- 已尝试次数
    bubbles_json  TEXT,                                           -- 模型返回并解析后的气泡数组（JSON）
    emitted_count INTEGER      NOT NULL DEFAULT 0,                -- 已写入消息表的气泡数（断点续发）
    error         VARCHAR(512),                                   -- 失败原因（展示给用户）
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,-- 创建时间
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

-- 领取到期任务
CREATE INDEX IF NOT EXISTS ix_reply_jobs_status_run_after ON reply_jobs (status, run_after);
-- 判断联系人是否“正在输入”、是否已有待执行任务
CREATE INDEX IF NOT EXISTS ix_reply_jobs_contact_status ON reply_jobs (contact_id, status);

-- 【聊天】联系人表：新增字段
ALTER TABLE contacts ADD COLUMN model_profile VARCHAR(16) NOT NULL DEFAULT 'flash'; -- 模型档位：flash V4.1 Flash / chat deepseek-chat
ALTER TABLE contacts ADD COLUMN auto_message_next_at DATETIME;                     -- 下次自动发消息时间
ALTER TABLE contacts ADD COLUMN auto_message_streak INTEGER NOT NULL DEFAULT 0;    -- 用户未回复期间已连续自动发送条数

-- 【聊天】消息表：按会话分页、取最后一条消息
CREATE INDEX IF NOT EXISTS ix_messages_contact_id_id ON messages (contact_id, id);

-- 连接级设置（每次建立连接时执行）
-- PRAGMA journal_mode = WAL;   -- 允许 Worker 写入与 API 读取并发
-- PRAGMA busy_timeout = 5000;  -- 写锁冲突时最多等待 5 秒
