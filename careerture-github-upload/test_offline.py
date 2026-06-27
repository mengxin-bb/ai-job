"""
无需 DeepSeek Token 的本地基础测试。

覆盖：
- 数据库用户资料保存/读取
- 投递 CRM 增删改查
- 待办完成与重复任务去重逻辑
- 面试邀约保存
- TXT 简历解析

用法：
    python test_offline.py
"""

from __future__ import annotations

import os
import tempfile

from utils import db, resume


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_with_temp_db() -> None:
    original_db_path = db.DB_PATH
    fd, temp_path = tempfile.mkstemp(prefix="careerture-test-", suffix=".db")
    os.close(fd)
    try:
        db.DB_PATH = temp_path
        db.init_db()

        user_id = db.get_or_create_user("offline-test-user")
        db.update_user_profile(
            user_id,
            "小职",
            "示例大学",
            "大三",
            "人力资源管理",
            "互联网",
            "HR 实习生",
            "上海",
        )
        profile = db.get_user(user_id)
        assert_true(profile["nickname"] == "小职", "用户昵称保存失败")
        assert_true(profile["target_city"] == "上海", "目标城市保存失败")

        db.add_application(
            user_id,
            "MiniMax",
            "AI-HR 实习生",
            "秋招",
            "已投递",
            "2026-06-28",
            "官网",
            "https://example.com/jd",
            "学姐A",
            "3天后跟进",
            "重点准备 AI 产品理解",
            "",
        )
        apps = db.get_applications(user_id)
        assert_true(len(apps) == 1, "投递记录新增失败")
        app_id = apps[0]["id"]
        assert_true(apps[0]["channel"] == "官网", "投递渠道保存失败")
        db.update_application_detail(
            app_id,
            "MiniMax",
            "HR 实习生",
            "秋招",
            "面试中",
            "2026-06-28",
            "内推",
            "https://example.com/new-jd",
            "学姐B",
            "准备一面",
            "已收到面试邀约",
            "",
        )
        updated_app = db.get_applications(user_id)[0]
        assert_true(updated_app["status"] == "面试中", "投递状态更新失败")
        assert_true(updated_app["referrer"] == "学姐B", "内推人更新失败")
        db.delete_application(app_id)
        assert_true(len(db.get_applications(user_id)) == 0, "投递记录删除失败")

        task_content = "整理 3 个目标岗位 JD"
        existing = {t["task_content"] for t in db.get_user_tasks(user_id)}
        for item in [task_content, task_content]:
            if item not in existing:
                db.add_task(user_id, item)
                existing.add(item)
        tasks = db.get_user_tasks(user_id)
        assert_true(len(tasks) == 1, "重复任务去重逻辑失败")
        db.mark_task_complete(tasks[0]["id"])
        assert_true(len(db.get_user_tasks(user_id, only_incomplete=True)) == 0, "待办完成失败")

        db.add_interview(
            user_id,
            "腾讯",
            "HR 实习生",
            "2026-07-01 10:00",
            "线上",
            "准备行为面",
            interview_date="2026-07-01",
            interview_clock="10:00",
        )
        interviews = db.get_interviews(user_id)
        assert_true(len(interviews) == 1, "面试邀约新增失败")
        assert_true(interviews[0]["interview_clock"] == "10:00", "面试时间保存失败")

        parsed = resume.extract_text(
            "resume.txt",
            (
                "教育经历：示例大学 人力资源管理 大三\n"
                "项目经历：负责校园招聘活动运营，协同 5 人团队完成候选人沟通与数据整理。\n"
                "目标岗位：AI-HR 实习生，希望投递上海互联网公司。"
            ).encode("utf-8"),
        )
        assert_true("AI-HR 实习生" in parsed, "TXT 简历解析失败")
    finally:
        db.DB_PATH = original_db_path
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    run_with_temp_db()
    print("✅ 离线基础测试通过")
