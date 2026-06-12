"""
SQLite 持久化层 —— 校招 Copilot 的“记忆”。

存三类信息：
- users          每个浏览器会话对应一个用户档案（年级/专业/意向行业/意向岗位）
- conversations  对话摘要（便于跨会话回顾）
- tasks          给用户布置的「可马上做的事」，可勾选完成

数据库文件默认放在项目根目录 copilot.db（与 CWD 无关）。
sqlite3 是 Python 标准库，无需额外安装。
"""

from __future__ import annotations  # 兼容 Python 3.9：让 dict|None 等注解延迟解析

import os
import sqlite3

# 数据库文件路径：项目根目录（本文件在 utils/ 下，向上一级即项目根）。
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "copilot.db")


def _connect() -> sqlite3.Connection:
    """打开一个连接。每次调用新开/用完即关，避免 Streamlit 多线程下的共享问题。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果能按列名访问，并方便转成 dict
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表（幂等）。应在应用启动时调用一次。"""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT UNIQUE NOT NULL,
                nickname         TEXT,
                school           TEXT,
                grade            TEXT,
                major            TEXT,
                target_industry  TEXT,
                target_position  TEXT,
                target_city      TEXT,
                created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                summary     TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                task_content  TEXT NOT NULL,
                is_completed  INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                conversation_id  INTEGER,
                is_helpful       INTEGER NOT NULL,      -- 1=有用, 0=没用
                created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE TABLE IF NOT EXISTS applications (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                company       TEXT NOT NULL,
                position      TEXT,
                season        TEXT,        -- 秋招 / 春招
                status        TEXT,        -- 已投递 / 笔试中 / 面试中 / 已 Offer / 未通过
                applied_date  TEXT,        -- 投递日期（ISO 文本）
                created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS interviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                company         TEXT NOT NULL,
                position        TEXT,
                interview_time  TEXT,      -- 面试时间（自由文本，如「3月15日 14:00」）
                method          TEXT,      -- 线上 / 现场 / 电话
                note            TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "nickname" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
        if "school" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN school TEXT")
        if "target_city" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN target_city TEXT")


# ---- users -------------------------------------------------------------

def get_or_create_user(session_id: str) -> int:
    """根据 session_id 查用户；不存在则新建。返回 user_id。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is not None:
            return row["user_id"]

        cur = conn.execute(
            "INSERT INTO users (session_id) VALUES (?)", (session_id,)
        )
        return cur.lastrowid


def get_user(user_id: int) -> dict | None:
    """读取用户档案，返回 dict（含 grade/major/target_industry/target_position 等）。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def update_user_info(
    user_id: int,
    grade: str,
    major: str,
    target_industry: str,
    target_position: str,
) -> None:
    """更新用户档案，并刷新 updated_at。"""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
               SET grade = ?,
                   major = ?,
                   target_industry = ?,
                   target_position = ?,
                   updated_at = datetime('now', 'localtime')
             WHERE user_id = ?
            """,
            (grade, major, target_industry, target_position, user_id),
        )


def update_user_profile(
    user_id: int,
    nickname: str,
    school: str,
    grade: str,
    major: str,
    target_industry: str,
    target_position: str,
    target_city: str = "",
) -> None:
    """更新完整用户档案，并刷新 updated_at。"""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE users
               SET nickname = ?,
                   school = ?,
                   grade = ?,
                   major = ?,
                   target_industry = ?,
                   target_position = ?,
                   target_city = ?,
                   updated_at = datetime('now', 'localtime')
             WHERE user_id = ?
            """,
            (
                nickname,
                school,
                grade,
                major,
                target_industry,
                target_position,
                target_city,
                user_id,
            ),
        )


# ---- conversations -----------------------------------------------------

def save_conversation_summary(user_id: int, summary: str) -> int:
    """保存一条对话摘要（建议 100 字以内）。返回新建 conversation 的 id（供 feedback 关联）。"""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, summary) VALUES (?, ?)",
            (user_id, summary),
        )
        return cur.lastrowid


# ---- tasks -------------------------------------------------------------

def add_task(user_id: int, task_content: str) -> int:
    """新增一条任务，返回 task id。"""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, task_content) VALUES (?, ?)",
            (user_id, task_content),
        )
        return cur.lastrowid


def get_user_tasks(user_id: int, only_incomplete: bool = False) -> list[dict]:
    """
    返回用户的任务列表（每条为 dict）。

    only_incomplete=True 时只返回未完成的任务。按创建时间倒序。
    """
    sql = "SELECT * FROM tasks WHERE user_id = ?"
    params: tuple = (user_id,)
    if only_incomplete:
        sql += " AND is_completed = 0"
    sql += " ORDER BY created_at DESC, id DESC"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def mark_task_complete(task_id: int) -> None:
    """把某条任务标记为已完成。"""
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET is_completed = 1 WHERE id = ?", (task_id,)
        )


# ---- feedback ----------------------------------------------------------

def save_feedback(user_id: int, conversation_id: int | None, is_helpful: bool) -> None:
    """记录一条对 AI 回复的反馈。is_helpful=True 存 1（有用），False 存 0（没用）。"""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO feedback (user_id, conversation_id, is_helpful) VALUES (?, ?, ?)",
            (user_id, conversation_id, 1 if is_helpful else 0),
        )


# ---- applications（投递记录） -----------------------------------------

def add_application(
    user_id: int, company: str, position: str, season: str, status: str, applied_date: str
) -> None:
    """新增一条投递记录。"""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO applications (user_id, company, position, season, status, applied_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, company, position, season, status, applied_date),
        )


def get_applications(user_id: int) -> list[dict]:
    """返回用户的全部投递记录，按投递日期倒序。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE user_id = ? "
            "ORDER BY applied_date DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_application_status(app_id: int, status: str) -> None:
    """更新某条投递记录的状态。"""
    with _connect() as conn:
        conn.execute("UPDATE applications SET status = ? WHERE id = ?", (status, app_id))


def delete_application(app_id: int) -> None:
    """删除某条投递记录。"""
    with _connect() as conn:
        conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))


# ---- interviews（面试邀约） -------------------------------------------

def add_interview(
    user_id: int, company: str, position: str, interview_time: str, method: str, note: str = ""
) -> None:
    """新增一条面试邀约。"""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO interviews (user_id, company, position, interview_time, method, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, company, position, interview_time, method, note),
        )


def get_interviews(user_id: int) -> list[dict]:
    """返回用户的全部面试邀约，最新的在前。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM interviews WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_interview(interview_id: int) -> None:
    """删除某条面试邀约。"""
    with _connect() as conn:
        conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
