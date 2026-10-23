-- 【朋友圈】动态 / 图片 / 点赞 / 评论 / 延迟任务（V4）

CREATE TABLE IF NOT EXISTS moment_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                 -- 所属账号
    author_type VARCHAR(16) NOT NULL,         -- user / contact
    contact_id INTEGER,                       -- 联系人作者（可空）
    content TEXT DEFAULT '',                  -- 正文
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS moment_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,                 -- 动态
    url VARCHAR(512) NOT NULL,                -- 图片 URL
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (post_id) REFERENCES moment_posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS moment_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,              -- 点赞联系人
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES moment_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_moment_likes_post_contact ON moment_likes (post_id, contact_id);

CREATE TABLE IF NOT EXISTS moment_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    author_type VARCHAR(16) NOT NULL,         -- user / contact
    contact_id INTEGER,
    parent_id INTEGER,                        -- 父评论
    content VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES moment_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES moment_comments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS moment_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    job_type VARCHAR(32) NOT NULL,            -- like_and_root / reply_user
    target_comment_id INTEGER,
    status VARCHAR(16) DEFAULT 'pending',
    run_after DATETIME NOT NULL,
    attempts INTEGER DEFAULT 0,
    error VARCHAR(512),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- contacts.moment_next_at 由应用轻量迁移添加
