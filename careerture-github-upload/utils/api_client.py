"""
DeepSeek API 客户端 —— 校招 Copilot。

DeepSeek 提供 OpenAI 兼容接口，因此用 openai 库 + base_url 接入。
对外暴露两个函数，签名与返回结构保持稳定，app.py / test_local.py 无需改动：
  - call_claude(messages, user_info=None) -> str            纯文本回复
  - chat_turn(messages, user_info, existing_tasks) -> dict  结构化：advice/action_items/summary

环境变量：
  DEEPSEEK_API_KEY   必填
  DEEPSEEK_MODEL     可选，默认 deepseek-chat
  DEEPSEEK_BASE_URL  可选，默认 https://api.deepseek.com
"""

from __future__ import annotations  # 兼容 Python 3.9：让 dict|None 等注解延迟解析

import json
import os

from openai import OpenAI, APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

# ---- 配置 --------------------------------------------------------------

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

MAX_TOKENS = 1000
TEMPERATURE = 0.7

SYSTEM_PROMPT = """\
你是“校招 Copilot”，一个温暖、理性、有行动力的求职陪伴 AI。
你的用户是在校大学生（大一到研三）。
你的任务：
1. 理解用户当前所处的阶段（年级、专业、意向）
2. 给出具体、可执行的建议，而不是空泛的道理
3. 每次回答尽可能包含“一个可以马上做的事”
4. 鼓励用户，而不是制造焦虑
5. 如果是第一次和用户对话，主动询问：年级、专业、目前最困惑的问题
"""

# 结构化输出说明（拼到 system，配合 response_format=json_object 使用）。
STRUCTURED_MAX_TOKENS = 1500

MEMORY_INSTRUCTIONS = """\
此外，你必须只输出一个 JSON 对象（不要任何额外文字、不要 markdown 代码块），包含三个字段：
- advice：字符串，给用户看的回复（即你正常的对话回答，保持上面的人设与风格）
- action_items：字符串数组，本轮建议用户「可以马上做的事」，0-3 条具体可执行任务；不合适就给空数组 []，不要重复下面已布置的任务
- summary：字符串，本轮对话摘要，100 字以内，格式为「用户年级+专业+核心困惑+给出的建议要点」"""


# 进程内复用 client；前端 token 和环境变量 token 分开缓存。
_clients: dict[tuple[str, str], OpenAI] = {}


def _resolve_api_key(api_key: str | None = None) -> str:
    """优先使用前端传入的 token；没有则回退到环境变量。"""
    return (api_key or os.getenv("DEEPSEEK_API_KEY") or "").strip()


def _missing_key_message() -> str:
    return "⚠️ 还没配置 DeepSeek Token。请在页面左侧填写，或通过 URL 参数 deepseek_token 传入。"


def _get_client(api_key: str | None = None) -> OpenAI:
    key = _resolve_api_key(api_key)
    cache_key = (key, BASE_URL)
    if cache_key not in _clients:
        _clients[cache_key] = OpenAI(api_key=key, base_url=BASE_URL)
    return _clients[cache_key]


# ---- 提示词组装 --------------------------------------------------------

def _profile_block(user_info: dict | None) -> str:
    """把已知用户档案渲染成一段提示文本；无信息时返回空串。"""
    if not user_info:
        return ""
    fields = [
        ("grade", "年级"),
        ("major", "专业"),
        ("target_industry", "意向行业"),
        ("target_position", "意向岗位"),
        ("target_city", "目标城市"),
    ]
    lines = [f"- {label}：{user_info[key]}" for key, label in fields if user_info.get(key)]
    if not lines:
        return ""
    return (
        "\n\n【已知用户信息】（来自历史记录，请直接利用，不要重复追问已知项）：\n"
        + "\n".join(lines)
    )


def _tasks_block(existing_tasks: list[str] | None) -> str:
    """把已布置且未完成的任务渲染成提示文本，避免模型重复布置。"""
    if not existing_tasks:
        return ""
    lines = "\n".join(f"- {t}" for t in existing_tasks)
    return f"\n\n【已布置且未完成的任务】（不要重复布置）：\n{lines}"


def _build_system_prompt(user_info: dict | None) -> str:
    """把已知的用户档案拼到 System Prompt 末尾，让模型“记住”用户。"""
    return SYSTEM_PROMPT + _profile_block(user_info)


# ---- 纯文本回复（保留，兼容旧调用） -----------------------------------

def call_claude(messages: list, user_info: dict | None = None, api_key: str | None = None) -> str:
    """
    调用 DeepSeek，返回完整回复文本。（函数名沿用历史命名，便于兼容。）

    失败时返回 ⚠️ 开头的友好提示，而不是抛异常。
    """
    if not _resolve_api_key(api_key):
        return _missing_key_message()

    try:
        resp = _get_client(api_key).chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            messages=[{"role": "system", "content": _build_system_prompt(user_info)}, *messages],
        )
        return resp.choices[0].message.content or ""
    except AuthenticationError:
        return "⚠️ DeepSeek Token 无效或已过期，请检查页面左侧填写的访问 Token。"
    except RateLimitError:
        return "⚠️ 请求太频繁，触发了限流。请稍等几秒再试。"
    except APIConnectionError:
        return "⚠️ 网络连接出错，请检查网络后重试。"
    except APIStatusError as e:
        return f"⚠️ 调用 DeepSeek 失败（HTTP {e.status_code}）。请稍后重试。"
    except Exception as e:  # noqa: BLE001
        return f"⚠️ 出现未知错误：{e}"


# ---- 结构化：一轮对话 + 记忆维护 --------------------------------------

def _error(advice: str) -> dict:
    """统一的失败返回结构。"""
    return {"advice": advice, "action_items": [], "summary": ""}


def chat_turn(
    messages: list,
    user_info: dict | None = None,
    existing_tasks: list[str] | None = None,
    api_key: str | None = None,
) -> dict:
    """
    一轮对话 + 记忆维护：调用 DeepSeek，用 JSON 模式同时拿到回复、行动项、摘要。

    用 DeepSeek 的 JSON 模式（response_format={"type": "json_object"}）约束输出为 JSON，
    并在 system 里说明字段。比手写分隔符更可靠，且只花一次 API 调用。

    返回 dict:
        {"advice": str, "action_items": list[str], "summary": str}
        调用失败时 advice 为 ⚠️ 开头的友好提示，其余为空。
    """
    if not _resolve_api_key(api_key):
        return _error(_missing_key_message())

    system = (
        SYSTEM_PROMPT
        + _profile_block(user_info)
        + _tasks_block(existing_tasks)
        + "\n\n"
        + MEMORY_INSTRUCTIONS
    )

    try:
        resp = _get_client(api_key).chat.completions.create(
            model=MODEL,
            max_tokens=STRUCTURED_MAX_TOKENS,
            temperature=TEMPERATURE,
            response_format={"type": "json_object"},  # DeepSeek JSON 模式
            messages=[{"role": "system", "content": system}, *messages],
        )
    except AuthenticationError:
        return _error("⚠️ DeepSeek Token 无效或已过期，请检查页面左侧填写的访问 Token。")
    except RateLimitError:
        return _error("⚠️ 请求太频繁，触发了限流。请稍等几秒再试。")
    except APIConnectionError:
        return _error("⚠️ 网络连接出错，请检查网络后重试。")
    except APIStatusError as e:
        return _error(f"⚠️ 调用 DeepSeek 失败（HTTP {e.status_code}）。请稍后重试。")
    except Exception as e:  # noqa: BLE001
        return _error(f"⚠️ 出现未知错误：{e}")

    text = resp.choices[0].message.content or ""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # 拿不到结构化结果：把已有文本当作回复，本轮不记忆。
        return _error(text or "⚠️ 回复解析失败，请重试。")

    items = [t.strip() for t in data.get("action_items", []) if isinstance(t, str) and t.strip()]
    return {
        "advice": (data.get("advice") or "").strip(),
        "action_items": items,
        "summary": (data.get("summary") or "").strip(),
    }


# ---- 简历分析 ----------------------------------------------------------

RESUME_SYSTEM_PROMPT = """\
你是“校招 Copilot”的简历诊断专家，面向在校大学生。
请基于用户提供的简历文本，给出**具体、可落地**的诊断，而不是空泛套话。
要求：
- 先一句话给整体印象（亮点 + 最该改的地方）
- 指出 3-5 个**主要痛点**，每个都引用简历里的具体内容，说明为什么是问题
- 针对每个痛点给出**怎么改**的建议，最好给出改写示例（前→后）
- 结合用户的目标岗位（若已知）做针对性建议
- 语气鼓励，不打击；用 Markdown 分点排版，便于阅读
"""


def analyze_resume(resume_text: str, user_info: dict | None = None, api_key: str | None = None) -> str:
    """
    分析简历文本，返回 Markdown 格式的诊断报告（痛点 + 修改建议）。

    失败时返回 ⚠️ 开头的友好提示。
    """
    if not _resolve_api_key(api_key):
        return _missing_key_message()

    system = RESUME_SYSTEM_PROMPT + _profile_block(user_info)
    user_msg = f"以下是我的简历内容，请帮我诊断痛点并给出修改建议：\n\n{resume_text}"

    try:
        resp = _get_client(api_key).chat.completions.create(
            model=MODEL,
            max_tokens=2000,  # 诊断报告较长，给足空间
            temperature=TEMPERATURE,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        return resp.choices[0].message.content or "⚠️ 未生成内容，请重试。"
    except AuthenticationError:
        return "⚠️ DeepSeek Token 无效或已过期，请检查页面左侧填写的访问 Token。"
    except RateLimitError:
        return "⚠️ 请求太频繁，触发了限流。请稍等几秒再试。"
    except APIConnectionError:
        return "⚠️ 网络连接出错，请检查网络后重试。"
    except APIStatusError as e:
        return f"⚠️ 调用 DeepSeek 失败（HTTP {e.status_code}）。请稍后重试。"
    except Exception as e:  # noqa: BLE001
        return f"⚠️ 出现未知错误：{e}"


RESUME_PROFILE_SYSTEM = """\
你是信息抽取器。请从用户的简历文本中提取基本信息，只输出一个 JSON 对象（不要任何额外文字）：
{"grade": "", "major": "", "target_industry": "", "target_position": ""}
说明：grade 是年级（如「大三」「研二」，没有就空字符串）；major 是专业；
target_industry 是意向行业；target_position 是意向岗位。
任何字段无法从简历判断时，给空字符串，不要编造。"""


def extract_resume_profile(resume_text: str, api_key: str | None = None) -> dict:
    """
    从简历文本中尽力提取 {grade, major, target_industry, target_position}。
    任何失败都返回空 dict（best-effort，不阻塞主流程）。
    """
    if not _resolve_api_key(api_key):
        return {}
    try:
        resp = _get_client(api_key).chat.completions.create(
            model=MODEL,
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RESUME_PROFILE_SYSTEM},
                {"role": "user", "content": resume_text},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001
        return {}
    keys = ("grade", "major", "target_industry", "target_position")
    return {k: (data.get(k) or "").strip() for k in keys}


JOB_MARKET_SYSTEM = """\
你是“职来 Careerture”的求职市场研究助手。
请根据用户给出的目标城市、目标行业、目标岗位，生成一份帮助学生理解岗位的简明市场快照。
注意：你不能声称自己正在实时联网搜索；如果没有实时来源，请明确写“以下为基于常见招聘信息特征的参考示例”。

输出要求：
- 用 Markdown
- 先给一句“岗位理解”
- 给 2-3 份相关岗位 JD 示例，每份包含：岗位名称、适合公司类型、核心职责、常见要求、适合学生补强点
- 给目标城市的大概薪资水平，按“实习/校招”分别估算区间；如果不确定要写“约”
- 最后给 3 条下一步行动建议
- 语气具体、务实，不制造焦虑
"""


def generate_job_market_snapshot(user_info: dict | None, api_key: str | None = None) -> str:
    """根据目标城市/行业/岗位生成岗位 JD 与薪资参考。"""
    if not user_info:
        return ""
    city = (user_info.get("target_city") or "").strip()
    industry = (user_info.get("target_industry") or "").strip()
    position = (user_info.get("target_position") or "").strip()
    if not (city and industry and position):
        return ""
    if not _resolve_api_key(api_key):
        return (
            "⚠️ 已保存目标城市/行业/岗位。配置 DeepSeek Token 后，"
            "我可以为你生成 2-3 份岗位 JD 示例和薪资参考。"
        )

    user_msg = (
        f"目标城市：{city}\n"
        f"目标行业：{industry}\n"
        f"目标岗位：{position}\n"
        "请生成岗位市场快照。"
    )
    try:
        resp = _get_client(api_key).chat.completions.create(
            model=MODEL,
            max_tokens=1800,
            temperature=0.4,
            messages=[
                {"role": "system", "content": JOB_MARKET_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
        return resp.choices[0].message.content or ""
    except AuthenticationError:
        return "⚠️ DeepSeek Token 无效或已过期，请检查页面左侧填写的访问 Token。"
    except RateLimitError:
        return "⚠️ 请求太频繁，触发了限流。请稍等几秒再试。"
    except APIConnectionError:
        return "⚠️ 网络连接出错，请检查网络后重试。"
    except APIStatusError as e:
        return f"⚠️ 调用 DeepSeek 失败（HTTP {e.status_code}）。请稍后重试。"
    except Exception as e:  # noqa: BLE001
        return f"⚠️ 出现未知错误：{e}"
