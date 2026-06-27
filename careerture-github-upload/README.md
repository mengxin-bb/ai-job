# 职来 Careerture

一个面向在校大学生的 **AI 求职陪伴** 应用：温暖、理性、有行动力。
基于 **Streamlit + DeepSeek API** 构建，支持求职陪聊、简历诊断、投递记录、面试邀约和日程看板等场景。

## ✨ 功能

- **对话陪伴**：以"职来 Careerture"人设给出具体、可执行的求职建议
- **记忆**：用 SQLite 保存用户资料、对话摘要、待办任务
- **行动项闭环**：AI 回复时同步产出行动项 → 自动入库 → 侧边栏 checkbox 勾选完成
- **简历诊断**：上传 PDF / DOCX / TXT 简历，生成针对性优化建议
- **面试日历**：记录面试邀约，并生成可放大的日程看板
- **内容归档**：将 AI 回复按求职策略、简历优化、面试准备等类别收藏

## 🗂️ 项目结构

```
ai-job-companion/
├── app.py                 # Streamlit 主入口（UI + 交互逻辑）
├── requirements.txt       # 依赖
├── .env.example           # 环境变量示例
├── .gitignore
└── utils/
    ├── api_client.py      # DeepSeek API 封装（建议 + 行动项 + 摘要）
    ├── db.py              # SQLite 持久化（用户 / 对话 / 任务 / 面试 / 归档）
    └── resume.py          # 简历文本解析
```

## 🔑 环境变量

本项目使用 **DeepSeek API**（OpenAI 兼容接口）。

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek API key，从 <https://platform.deepseek.com/> 获取 |
| `DEEPSEEK_MODEL` | 否 | 覆盖默认模型；不填则用 `deepseek-chat` |
| `DEEPSEEK_BASE_URL` | 否 | 覆盖接口地址；不填则用 `https://api.deepseek.com` |

> ⚠️ 不要把真实 key 提交到 git。`.env` 已在 `.gitignore` 中忽略。

## 💻 本地运行

```bash
# 1) 安装依赖（建议先建虚拟环境）
pip install -r requirements.txt

# 2) 配置 key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 3) 启动
streamlit run app.py
```

浏览器打开 <http://localhost:8501> 即可使用。
数据会写入项目根目录的 `copilot.db`（首次运行自动创建）。

## ☁️ 部署到 Streamlit Cloud

1. 把项目推到一个 **GitHub 仓库**（确认 `.env` 和 `*.db` 未被提交）。
2. 登录 <https://share.streamlit.io>，点击 **New app**。
3. 选择你的仓库、分支，**Main file path** 填 `app.py`。
4. 展开 **Advanced settings → Secrets**，填入 key（TOML 格式）：
   ```toml
   DEEPSEEK_API_KEY = "sk-xxxxxxxx"
   # 可选：
   # DEEPSEEK_MODEL = "deepseek-chat"
   ```
   应用通过 `st.secrets` 读取，无需 `.env`。
5. 点击 **Deploy**，等待构建完成即可访问公开链接。

> **数据持久化提示**：Streamlit Cloud 的文件系统是临时的，重启后 `copilot.db` 会被清空。
> 用于 Demo 足够；若需长期保存，请改用托管数据库（如 Postgres / Supabase）。

## ⚠️ 免责声明

应用中的建议由 AI 生成，**仅供参考**，不构成任何专业意见。
