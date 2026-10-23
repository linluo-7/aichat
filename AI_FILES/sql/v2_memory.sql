-- V2：小记忆系统 表结构（SQLite）
-- 实际迁移由 backend/app/services/migrate.py 在启动时按“表/列不存在才创建”的方式执行

-- 【记忆】记忆条目表：每个联系人独立保存的长期记忆
CREATE TABLE IF NOT EXISTS memories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,              -- 记忆ID
    contact_id      INTEGER NOT NULL
                    REFERENCES contacts(id) ON DELETE CASCADE,      -- 联系人ID
    category        VARCHAR(16)  NOT NULL,                          -- 分类：profile 关于你 / relationship 我们之间 / event 往事
    content         VARCHAR(255) NOT NULL,                          -- 记忆内容（≤120字）
    importance      INTEGER      NOT NULL DEFAULT 3,                -- 重要度 1～5
    status          VARCHAR(16)  NOT NULL DEFAULT 'active',         -- 状态：active 有效 / retired 已被替代
    source          VARCHAR(16)  NOT NULL DEFAULT 'ai',             -- 来源：ai 自动整理 / user 用户添加或编辑
    pinned          BOOLEAN      NOT NULL DEFAULT 0,                -- 是否置顶（始终注入上下文）
    superseded_by   INTEGER REFERENCES memories(id)
                    ON DELETE SET NULL,                             -- 被哪条新记忆替代
    from_message_id INTEGER,                                        -- 来源消息起始ID
    to_message_id   INTEGER,                                        -- 来源消息结束ID
    occurred_at     DATE,                                           -- 事件发生日期（事件记忆）
    last_used_at    DATETIME,                                       -- 最近一次注入上下文时间
    use_count       INTEGER      NOT NULL DEFAULT 0,                -- 注入上下文次数
    seen            BOOLEAN      NOT NULL DEFAULT 0,                -- 用户是否已在记忆页查看
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,-- 创建时间
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP -- 更新时间
);

-- 按联系人取有效记忆
CREATE INDEX IF NOT EXISTS ix_memories_contact_status ON memories (contact_id, status);

-- 【记忆】联系人记忆状态表：整理游标、整理结果与“Ta 眼中的你”总结缓存，每个联系人一行
CREATE TABLE IF NOT EXISTS memory_states (
    contact_id                INTEGER PRIMARY KEY
                              REFERENCES contacts(id) ON DELETE CASCADE, -- 联系人ID
    last_extracted_message_id INTEGER  NOT NULL DEFAULT 0,  -- 整理游标：已整理到的消息ID（成功才推进）
    last_run_at               DATETIME,                     -- 最近一次整理时间
    last_added                INTEGER  NOT NULL DEFAULT 0,  -- 最近一次新增条数
    last_retired              INTEGER  NOT NULL DEFAULT 0,  -- 最近一次退役条数
    last_dropped              INTEGER  NOT NULL DEFAULT 0,  -- 最近一次校验丢弃条数
    last_error                VARCHAR(512),                 -- 最近一次整理失败原因
    fail_count                INTEGER  NOT NULL DEFAULT 0,  -- 连续失败次数
    runs_day                  DATE,                         -- 当日计数所属日期（北京时间）
    runs_today                INTEGER  NOT NULL DEFAULT 0,  -- 当日已整理次数
    digest                    TEXT,                         -- “Ta 眼中的你”总结文本
    digest_at                 DATETIME,                     -- 总结生成时间
    digest_stale              BOOLEAN  NOT NULL DEFAULT 1   -- 总结是否过期（记忆变化后置为1）
);

-- 【聊天】联系人表：新增记忆开关
ALTER TABLE contacts ADD COLUMN memory_enabled BOOLEAN NOT NULL DEFAULT 1; -- 是否启用记忆（关闭后不整理、不注入）
