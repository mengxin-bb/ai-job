"""
职来 Careerture —— Streamlit Demo 主入口。

结构：主页四大板块（求职陪聊 / 简历诊断 / 投递记录 / 面试邀约），
每个板块点进去是一个独立全屏页面，左上角有「返回主页」。
个人资料不再手填，从上传的简历中自动读取。

运行：
    cp .env.example .env      # 填入 DEEPSEEK_API_KEY
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import uuid
import base64
import json
from datetime import date, time
from urllib.parse import urlencode

import streamlit as st
import extra_streamlit_components as stx

st.set_page_config(page_title="职来 Careerture", page_icon="🌱", layout="centered")

from dotenv import load_dotenv

# 本地：从 .env 读取；部署（Streamlit Cloud）：从 st.secrets 读取。
load_dotenv()
try:
    for _k in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"):
        if _k not in os.environ and _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

from utils import db, resume
from utils.api_client import analyze_resume, chat_turn, extract_resume_profile, generate_job_market_snapshot

# ---- 像素风样式（星露谷调性）-----------------------------------------

BG_PATH = os.path.join(os.path.dirname(__file__), "assets", "ocean-bg.jpg")
if os.path.exists(BG_PATH):
    with open(BG_PATH, "rb") as _bg_file:
        _bg_bytes = _bg_file.read()
        _bg_mime = "image/png" if _bg_bytes.startswith(b"\\x89PNG") else "image/jpeg"
        OCEAN_BG_CSS_URL = (
            f"data:{_bg_mime};base64,"
            + base64.b64encode(_bg_bytes).decode("ascii")
        )
else:
    OCEAN_BG_CSS_URL = ""

ICON_FILES = {
    "chat": "shell-sign.png",
    "resume": "pineapple.png",
    "mail": "snail.png",
    "calendar": "crab.png",
    "task": "starfish.png",
}
ICON_DATA_URLS = {}
for _icon_name, _icon_file in ICON_FILES.items():
    _icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", _icon_file)
    if os.path.exists(_icon_path):
        with open(_icon_path, "rb") as _icon_f:
            ICON_DATA_URLS[_icon_name] = (
                "data:image/png;base64,"
                + base64.b64encode(_icon_f.read()).decode("ascii")
            )

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');
      :root {
        --wood: #2273a9; --wood-dark: #123d79;
        --parch: #eaffcf; --panel: rgba(236, 255, 214, 0.9);
        --green-light: rgba(142, 239, 190, 0.78); --gold: #f8f27d; --ink: #12314f;
        --leaf: #61d871; --leaf-dark: #177c74; --sky: #45d5dc;
        --berry: #7362c9; --paper: #e9fff2;
        --reef-pink: #ff7aa8; --mountain: #5969b2; --foam: #f5fff5;
      }
      .stApp {
        color: var(--ink);
        background:
          linear-gradient(rgba(230, 255, 242, 0.48), rgba(230, 255, 242, 0.56)),
          url("__OCEAN_BG__");
        background-size: cover;
        background-position: center top;
        background-attachment: fixed;
        min-height: 100vh;
      }
      .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background:
          linear-gradient(90deg, rgba(245,255,245,0.32), rgba(245,255,245,0.08) 24%, rgba(245,255,245,0.22)),
          radial-gradient(circle at 50% 18%, rgba(245,255,245,0.38), transparent 34%);
        z-index: 0;
      }
      .stApp::after {
        content: none;
      }
      [data-testid="stAppViewContainer"] > .main {
        position: relative;
        z-index: 1;
      }
      .main .block-container {
        background: linear-gradient(180deg, rgba(236,255,247,0.2), rgba(236,255,247,0.08));
      }
      p, li, label, [data-testid="stMarkdownContainer"] {
        color: var(--ink) !important;
        text-shadow: 1px 1px 0 rgba(245, 255, 245, 0.72);
      }
      [data-testid="stCaptionContainer"],
      [data-testid="stCaptionContainer"] p,
      small {
        color: #154a75 !important;
        text-shadow: 1px 1px 0 rgba(245,255,245,0.9);
        font-weight: 650;
      }
      h1, h2, h3 {
        font-family: 'Press Start 2P', cursive !important;
        color: var(--wood-dark) !important; line-height: 1.6 !important;
        text-shadow: 2px 2px 0 rgba(245, 255, 245, 0.96), 4px 4px 0 rgba(18, 61, 121, 0.16);
      }
      h1 { font-size: 1.4rem !important; }
      [data-testid="stChatMessage"] {
        border: 3px solid var(--wood); border-radius: 0 !important;
        padding: 0.6rem 0.9rem; margin-bottom: 0.6rem;
        box-shadow: 4px 4px 0 rgba(18, 61, 121, 0.22);
      }
      [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: var(--green-light); }
      [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { background: var(--panel); }
      .stButton button, .stFormSubmitButton button, [data-testid="stDownloadButton"] button {
        color: var(--wood-dark) !important;
        background: linear-gradient(180deg, #fffaa1, #78ead5) !important;
        border: 3px solid var(--wood-dark) !important; border-radius: 0 !important;
        box-shadow: 3px 3px 0 rgba(18, 61, 121, 0.72) !important; font-weight: 700 !important;
        transition: transform .05s, box-shadow .05s;
      }
      .stButton button:hover, .stFormSubmitButton button:hover {
        transform: translate(2px, 2px); box-shadow: 1px 1px 0 var(--wood-dark) !important;
      }
      .stTextInput input, [data-baseweb="input"] {
        border: 3px solid var(--wood) !important;
        border-radius: 0 !important;
        background: rgba(245, 255, 245, 0.82) !important;
        color: var(--ink) !important;
      }
      [data-baseweb="base-input"],
      [data-testid="stTextInputRootElement"] {
        background: rgba(245, 255, 245, 0.82) !important;
        border-radius: 0 !important;
      }
      .stTextInput label p {
        color: var(--wood-dark) !important;
        font-weight: 800 !important;
      }
      [data-testid="stChatInput"] { border: 3px solid var(--wood) !important; border-radius: 0 !important; }
      [data-testid="stFileUploaderDropzone"] {
        border: 3px dashed var(--wood) !important;
        border-radius: 0 !important;
        background: rgba(235, 255, 229, 0.82);
        box-shadow: inset 0 0 0 3px rgba(255, 250, 161, 0.42), 4px 4px 0 rgba(18, 61, 121, 0.18);
        min-height: 118px;
      }
      .brand-title {
        display: block;
        text-align: center;
        max-width: 520px;
        margin: 0.45rem auto 0.9rem;
        padding: 0.55rem 0.8rem 0.45rem;
        position: relative;
      }
      .brand-title::after {
        content: "";
        display: block;
        width: min(180px, 42vw);
        height: 4px;
        margin: 0.45rem auto 0;
        background: linear-gradient(90deg, transparent, rgba(245,255,245,0.95), transparent);
      }
      .brand-title h1 {
        margin: 0 !important;
        font-size: clamp(2.05rem, 8vw, 3.6rem) !important;
        line-height: 1.08 !important;
        letter-spacing: 0 !important;
        color: #0f4f8a !important;
        text-shadow: 3px 3px 0 rgba(245,255,245,0.9), 6px 6px 0 rgba(18,61,121,0.16) !important;
      }
      .brand-copy {
        min-width: 0;
      }
      .brand-subtitle {
        margin-top: 0.25rem;
        font-family: 'Press Start 2P', cursive;
        font-size: clamp(0.62rem, 2.25vw, 0.92rem);
        line-height: 1.6;
        letter-spacing: 0.02em;
        color: #176d93;
        text-shadow: 2px 2px 0 rgba(245,255,245,0.9);
      }
      .page-title {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0.4rem 0 0.8rem;
        padding: 0.25rem 0.35rem;
        background: linear-gradient(90deg, rgba(235,255,229,0.72), rgba(235,255,229,0));
      }
      .page-title h1 {
        margin: 0 !important;
      }
      .pixel-icon {
        --icon-main: var(--leaf);
        --icon-dark: var(--leaf-dark);
        --icon-light: var(--gold);
        width: 40px;
        height: 40px;
        flex: 0 0 40px;
        border: 4px solid var(--wood-dark);
        background: var(--icon-main);
        box-shadow: 4px 4px 0 rgba(18, 61, 121, 0.24);
        image-rendering: pixelated;
        position: relative;
      }
      .sprite-icon {
        width: 48px;
        height: 48px;
        flex: 0 0 48px;
        object-fit: contain;
        image-rendering: pixelated;
        filter: drop-shadow(4px 4px 0 rgba(18, 61, 121, 0.28));
      }
      .sprite-icon.task {
        width: 28px;
        height: 28px;
        flex-basis: 28px;
        filter: drop-shadow(2px 2px 0 rgba(18, 61, 121, 0.24));
      }
      .pixel-icon::before,
      .pixel-icon::after {
        content: "";
        position: absolute;
        image-rendering: pixelated;
      }
      .pixel-icon.brand {
        background:
          linear-gradient(var(--icon-light), var(--icon-light)) 14px 5px / 8px 8px no-repeat,
          linear-gradient(var(--icon-main), var(--icon-main)) 10px 13px / 16px 12px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 18px 25px / 5px 8px no-repeat,
          var(--sky);
      }
      .pixel-icon.brand::before {
        left: 7px; top: 24px; width: 22px; height: 5px; background: var(--leaf-dark);
      }
      .pixel-icon.chat {
        --icon-main: #ff8cad; --icon-dark: #7a4d36; --icon-light: #fff7c4;
        background:
          linear-gradient(var(--icon-dark), var(--icon-dark)) 18px 4px / 4px 30px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 13px 7px / 14px 5px no-repeat,
          linear-gradient(var(--icon-main), var(--icon-main)) 10px 12px / 20px 13px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 13px 15px / 5px 4px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 21px 15px / 5px 4px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 13px 25px / 14px 4px no-repeat,
          var(--sky);
      }
      .pixel-icon.resume {
        --icon-main: #f5a142; --icon-dark: #7a4d36; --icon-light: #7bdc65;
        background:
          linear-gradient(var(--icon-light), var(--icon-light)) 14px 3px / 5px 8px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 20px 2px / 6px 10px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 8px 7px / 12px 6px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 11px 12px / 20px 24px no-repeat,
          linear-gradient(var(--icon-main), var(--icon-main)) 9px 14px / 22px 20px no-repeat,
          linear-gradient(#ffd66b, #ffd66b) 13px 17px / 5px 5px no-repeat,
          linear-gradient(#ffd66b, #ffd66b) 22px 22px / 5px 5px no-repeat,
          linear-gradient(#3678cf, #3678cf) 17px 28px / 7px 7px no-repeat,
          var(--sky);
      }
      .pixel-icon.mail {
        --icon-main: #8ee7d5; --icon-dark: #27517a; --icon-light: #ff8cad;
        background:
          linear-gradient(var(--icon-dark), var(--icon-dark)) 10px 25px / 24px 5px no-repeat,
          linear-gradient(var(--icon-main), var(--icon-main)) 11px 15px / 17px 13px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 8px 12px / 12px 12px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 8px 10px / 16px 4px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 27px 11px / 3px 16px no-repeat,
          linear-gradient(#f4fff8, #f4fff8) 18px 16px / 5px 5px no-repeat,
          linear-gradient(#f4fff8, #f4fff8) 26px 16px / 5px 5px no-repeat,
          var(--paper);
      }
      .pixel-icon.calendar {
        --icon-main: #e94c57; --icon-dark: #6e2d40; --icon-light: #ffe37a;
        background:
          linear-gradient(var(--icon-main), var(--icon-main)) 13px 18px / 16px 12px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 9px 21px / 5px 7px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 28px 21px / 5px 7px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 11px 13px / 5px 5px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 26px 13px / 5px 5px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 17px 10px / 8px 7px no-repeat,
          linear-gradient(#7bc9ff, #7bc9ff) 17px 21px / 8px 5px no-repeat,
          var(--sky);
      }
      .pixel-icon.task {
        --icon-main: #ff9e9a; --icon-dark: #7a4d36; --icon-light: #fff5a8;
        width: 24px; height: 24px; flex-basis: 24px; border-width: 3px; box-shadow: 3px 3px 0 rgba(74, 47, 24, 0.25);
        background:
          linear-gradient(var(--icon-dark), var(--icon-dark)) 10px 3px / 4px 18px no-repeat,
          linear-gradient(var(--icon-dark), var(--icon-dark)) 3px 10px / 18px 4px no-repeat,
          linear-gradient(var(--icon-main), var(--icon-main)) 7px 7px / 10px 10px no-repeat,
          linear-gradient(var(--icon-light), var(--icon-light)) 10px 9px / 4px 4px no-repeat,
          var(--sky);
      }
      .pixel-label {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        color: var(--ink);
        text-shadow: 1px 1px 0 rgba(245,255,245,0.86);
      }
      .onboarding-hero {
        border: 4px solid var(--wood-dark);
        background:
          radial-gradient(circle at 78% 18%, rgba(255,255,143,0.7), transparent 22%),
          linear-gradient(90deg, rgba(255,255,255,0.42), rgba(255,255,255,0.06)) 0 0 / 100% 100% no-repeat,
          rgba(235, 255, 229, 0.82);
        box-shadow: 5px 5px 0 rgba(18, 61, 121, 0.24);
        padding: 1rem;
        margin: 0.8rem 0 1rem;
        position: relative;
        overflow: hidden;
      }
      .onboarding-hero::after {
        content: "";
        position: absolute;
        right: -8px;
        bottom: -4px;
        width: 110px;
        height: 48px;
        opacity: 0.6;
        background:
          radial-gradient(ellipse at 14px 32px, #7df081 0 12px, transparent 13px),
          radial-gradient(ellipse at 36px 28px, #49cc78 0 15px, transparent 16px),
          radial-gradient(ellipse at 64px 32px, #98f36c 0 18px, transparent 19px),
          radial-gradient(circle at 88px 20px, #ff7aa8 0 3px, transparent 4px),
          radial-gradient(circle at 98px 28px, #fffaa1 0 3px, transparent 4px);
      }
      .onboarding-hero p {
        margin: 0;
        color: var(--ink);
        line-height: 1.7;
      }
      .step-strip {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0.7rem 0 1rem;
      }
      .step-badge {
        border: 3px solid var(--wood);
        background: rgba(206, 255, 206, 0.74);
        box-shadow: 3px 3px 0 rgba(18, 61, 121, 0.2);
        padding: 0.7rem;
      }
      .step-badge strong {
        display: block;
        color: var(--wood-dark);
        margin-bottom: 0.2rem;
      }
      .step-badge span {
        color: var(--ink);
        font-size: 0.9rem;
      }
      .section-label {
        display: inline-block;
        border: 3px solid var(--wood-dark);
        background: linear-gradient(180deg, #fffaa1, #98f7e8);
        box-shadow: 3px 3px 0 rgba(18, 61, 121, 0.72);
        color: var(--wood-dark);
        font-weight: 800;
        padding: 0.35rem 0.6rem;
        margin: 0.6rem 0 0.45rem;
      }
      .helper-copy {
        color: #123d79;
        font-size: 0.9rem;
        margin: -0.15rem 0 0.55rem;
        display: inline-block;
        padding: 0.12rem 0.35rem;
        background: rgba(245, 255, 245, 0.58);
        box-decoration-break: clone;
        -webkit-box-decoration-break: clone;
        text-shadow: 1px 1px 0 rgba(245,255,245,0.92);
      }
      /* 板块卡片 / 容器边框木框化 */
      [data-testid="stExpander"] details,
      [data-testid="stVerticalBlockBorderWrapper"] {
        border: 3px solid var(--wood) !important; border-radius: 0 !important;
        background: rgba(239, 255, 236, 0.86) !important;
        box-shadow: 4px 4px 0 rgba(18, 61, 121, 0.18);
        backdrop-filter: blur(1.5px);
      }
      /* 主页四大板块卡片等高对齐 */
      .home-card-marker {
        display: none;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-marker),
      [data-testid="stVerticalBlock"]:has(.home-card-marker) {
        min-height: 234px !important;
        height: 234px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-marker) > div {
        width: 100%;
        height: 100%;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-marker) [data-testid="stVerticalBlock"] {
        height: 100%;
        justify-content: space-between;
        gap: 0.5rem;
      }
      [data-testid="stVerticalBlock"]:has(.home-card-marker) [data-testid="stElementContainer"] {
        flex-shrink: 0;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-marker) h3 {
        min-height: 3.4rem;
        margin-bottom: 0 !important;
      }
      [data-testid="stVerticalBlock"]:has(.home-card-marker) h3 {
        min-height: 3.4rem;
        margin-bottom: 0 !important;
      }
      [data-testid="stVerticalBlockBorderWrapper"]:has(.home-card-marker) p,
      [data-testid="stVerticalBlock"]:has(.home-card-marker) p {
        min-height: 3rem;
        margin-bottom: 0 !important;
      }
      img { image-rendering: pixelated; }
      .disclaimer {
        text-align: center;
        color: #123d79;
        font-size: 0.8rem;
        margin-top: 1rem;
        font-weight: 700;
        text-shadow: 1px 1px 0 rgba(245,255,245,0.94);
      }
      @media (max-width: 560px) {
        .brand-title {
          margin-top: 0.25rem;
          margin-bottom: 0.65rem;
        }
        .step-strip {
          grid-template-columns: 1fr;
        }
      }
    </style>
    """.replace("__OCEAN_BG__", OCEAN_BG_CSS_URL),
    unsafe_allow_html=True,
)

# ---- 启动：建库 + 跨会话身份 ------------------------------------------

db.init_db()

COOKIE_SESSION_KEY = "careerture_uid"
COOKIE_PROFILE_KEY = "careerture_profile"
PROFILE_FIELDS = (
    "nickname",
    "school",
    "grade",
    "major",
    "target_industry",
    "target_position",
    "target_city",
)

cookie_manager = stx.CookieManager(key="careerture_cookie_manager")


def _safe_cookie_get(key: str) -> str:
    try:
        value = cookie_manager.get(key)
    except Exception:
        return ""
    return value or ""


def _safe_cookie_set(key: str, value: str) -> None:
    try:
        cookie_manager.set(key, value, max_age=60 * 60 * 24 * 365)
    except Exception:
        pass


def _profile_has_required_info(info) -> bool:
    if not info:
        return False
    return any((info.get(k) or "").strip() for k in PROFILE_FIELDS)


def _restore_profile_from_cookie(user_id_to_restore: int) -> None:
    raw_profile = _safe_cookie_get(COOKIE_PROFILE_KEY)
    if not raw_profile:
        return
    try:
        profile = json.loads(raw_profile)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(profile, dict) or not _profile_has_required_info(profile):
        return
    current = db.get_user(user_id_to_restore) or {}
    if _profile_has_required_info(current):
        return
    db.update_user_profile(
        user_id_to_restore,
        profile.get("nickname") or "",
        profile.get("school") or "",
        profile.get("grade") or "",
        profile.get("major") or "",
        profile.get("target_industry") or "",
        profile.get("target_position") or "",
        profile.get("target_city") or "",
    )

if "session_id" not in st.session_state:
    sid = st.query_params.get("uid") or _safe_cookie_get(COOKIE_SESSION_KEY)
    if not sid:
        sid = str(uuid.uuid4())
    st.query_params["uid"] = sid
    _safe_cookie_set(COOKIE_SESSION_KEY, sid)
    st.session_state.session_id = sid
if "user_id" not in st.session_state:
    st.session_state.user_id = db.get_or_create_user(st.session_state.session_id)
    _restore_profile_from_cookie(st.session_state.user_id)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback_given" not in st.session_state:
    st.session_state.feedback_given = set()
current_user = db.get_user(st.session_state.user_id) or {}
if "view" not in st.session_state:
    st.session_state.view = "home" if _profile_has_required_info(current_user) else "onboarding"
if "onboarding_done" not in st.session_state:
    st.session_state.onboarding_done = _profile_has_required_info(current_user)
if "deepseek_token" not in st.session_state:
    st.session_state.deepseek_token = (
        st.query_params.get("deepseek_token")
        or st.query_params.get("token")
        or ""
    )

user_id = st.session_state.user_id


def get_deepseek_token() -> str:
    return (
        st.session_state.get("deepseek_token")
        or os.getenv("DEEPSEEK_API_KEY")
        or ""
    ).strip()


def render_token_config() -> None:
    with st.sidebar:
        st.markdown("### DeepSeek Token")
        has_cloud_token = bool(os.getenv("DEEPSEEK_API_KEY"))
        token = st.text_input(
            "访问 Token",
            value=st.session_state.get("deepseek_token", ""),
            type="password",
            placeholder="sk-...",
            help="可选。留空时会使用部署端已配置的 Token；手动填写仅保存在当前浏览器会话中。",
        )
        st.session_state.deepseek_token = token.strip()
        if token.strip():
            st.success("Token 已配置")
            params = {
                "uid": st.session_state.session_id,
                "deepseek_token": get_deepseek_token(),
            }
            share_url = "http://127.0.0.1:8501/?" + urlencode(params)
            st.caption("带 Token 的分享链接会暴露密钥，只适合短期私下测试。")
            st.code(share_url, language="text")
        elif has_cloud_token:
            st.success("已使用部署端 Token，朋友可直接体验")
            st.caption("如需换成自己的 Token，也可以在这里填写。")
        else:
            st.info("也可以用 URL 参数 deepseek_token 自动配置。")


render_token_config()


def go(view: str) -> None:
    """切换板块并刷新。"""
    st.session_state.view = view
    st.rerun()


def back_button() -> None:
    """各板块左上角的返回按钮。"""
    if st.button("← 返回主页"):
        go("home")


def save_profile_from_form(
    nickname: str,
    school: str,
    grade: str,
    major: str,
    target_industry: str,
    target_position: str,
    target_city: str,
) -> None:
    db.update_user_profile(
        user_id,
        nickname.strip(),
        school.strip(),
        grade.strip(),
        major.strip(),
        target_industry.strip(),
        target_position.strip(),
        target_city.strip(),
    )
    st.session_state.onboarding_done = True
    profile = {
        "nickname": nickname.strip(),
        "school": school.strip(),
        "grade": grade.strip(),
        "major": major.strip(),
        "target_industry": target_industry.strip(),
        "target_position": target_position.strip(),
        "target_city": target_city.strip(),
    }
    _safe_cookie_set(COOKIE_PROFILE_KEY, json.dumps(profile, ensure_ascii=False))


def pixel_icon(kind: str, label: str = "") -> str:
    aria = f" aria-label='{label}'" if label else ""
    if kind in ICON_DATA_URLS:
        alt = label or kind
        return f"<img class='sprite-icon {kind}' src='{ICON_DATA_URLS[kind]}' alt='{alt}' />"
    return f"<span class='pixel-icon {kind}'{aria}></span>"


def render_page_title(title: str, icon: str) -> None:
    st.markdown(
        f"<div class='page-title'>{pixel_icon(icon, title)}<h1>{title}</h1></div>",
        unsafe_allow_html=True,
    )


APP_STATUS = ["已投递", "笔试中", "面试中", "已 Offer", "未通过"]
ARCHIVE_FOLDERS = ["求职策略", "简历优化", "面试准备", "岗位信息", "行动计划", "灵感收藏"]


def archive_chat_message(message_key: str, content: str) -> None:
    """渲染单条 AI 回复的归档控件。"""
    with st.expander("← 左滑归档 / 收进档案", expanded=False):
        c1, c2 = st.columns([2, 3])
        folder = c1.selectbox(
            "归档到",
            ARCHIVE_FOLDERS,
            key=f"archive_folder_{message_key}",
            label_visibility="collapsed",
        )
        title = c2.text_input(
            "标题",
            value=(content.strip().splitlines()[0][:24] if content.strip() else "AI 建议"),
            key=f"archive_title_{message_key}",
            label_visibility="collapsed",
        )
        if st.button("收进档案", key=f"archive_btn_{message_key}", use_container_width=True):
            db.add_chat_archive(user_id, folder, title.strip() or folder, content)
            st.success(f"已归档到「{folder}」")


def render_archive_drawer() -> None:
    archives = db.get_chat_archives(user_id)
    with st.expander(f"我的档案库（{len(archives)}）", expanded=False):
        if not archives:
            st.caption("还没有归档内容。看到有用的 AI 建议时，可以收进这里。")
            return
        folder_filter = st.selectbox(
            "查看档案",
            ["全部"] + ARCHIVE_FOLDERS,
            key="archive_filter",
        )
        shown = archives if folder_filter == "全部" else [a for a in archives if a["folder"] == folder_filter]
        for item in shown:
            with st.container(border=True):
                h1, h2 = st.columns([6, 1])
                h1.markdown(f"**{item['title'] or item['folder']}**  \n<small>{item['folder']} · {item['created_at']}</small>", unsafe_allow_html=True)
                if h2.button("删除", key=f"del_archive_{item['id']}"):
                    db.delete_chat_archive(item["id"])
                    st.rerun()
                st.markdown(item["content"])


# ====================================================================
# 新手流程：上传简历 / 填基本信息
# ====================================================================

def render_onboarding() -> None:
    st.markdown(
        f"""
        <div class='brand-title'>
          <div class='brand-copy'>
            <h1>职来</h1>
            <div class='brand-subtitle'>Careerture</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class='onboarding-hero'>
          <p><strong>先认识你一点点。</strong>上传简历可以直接进入诊断；暂时没有简历，也能填完基础信息后马上开始求职陪聊。</p>
        </div>
        <div class='step-strip'>
          <div class='step-badge'><strong>1 上传简历</strong><span>可选，有简历会先生成诊断报告</span></div>
          <div class='step-badge'><strong>2 完善信息</strong><span>让建议更贴合你的学校、年级和目标</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    info = db.get_user(user_id) or {}

    st.markdown("<div class='section-label'>简历入口</div>", unsafe_allow_html=True)
    st.markdown("<div class='helper-copy'>支持 PDF / DOCX / TXT；没有也没关系，可以先跳过。</div>", unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "上传简历（可选，支持 PDF / DOCX / TXT，≤ 5MB）",
        type=["pdf", "docx", "txt"],
        key="onboarding_resume",
        label_visibility="collapsed",
    )

    st.markdown("<div class='section-label'>基础信息</div>", unsafe_allow_html=True)
    st.markdown("<div class='helper-copy'>这些信息只用于让求职建议更具体，之后也可以继续补充。</div>", unsafe_allow_html=True)
    with st.form("onboarding_profile_form"):
        f1, f2 = st.columns(2)
        nickname = f1.text_input("昵称", value=info.get("nickname") or "")
        school = f2.text_input("学校", value=info.get("school") or "")
        f3, f4 = st.columns(2)
        grade = f3.text_input("年级", value=info.get("grade") or "", placeholder="如：大三 / 研二")
        major = f4.text_input("专业", value=info.get("major") or "")
        f5, f6, f7 = st.columns(3)
        target_industry = f5.text_input(
            "目标行业", value=info.get("target_industry") or "", placeholder="如：互联网 / 金融 / 快消"
        )
        target_position = f6.text_input(
            "目标岗位", value=info.get("target_position") or "", placeholder="如：产品经理 / 数据分析"
        )
        target_city = f7.text_input(
            "目标城市", value=info.get("target_city") or "", placeholder="如：上海 / 杭州"
        )

        submit_label = "保存并诊断简历" if uploaded is not None else "保存并进入求职陪聊"
        submitted = st.form_submit_button(submit_label, use_container_width=True)

    st.markdown("<div class='helper-copy'>想先体验也可以直接跳过，稍后再上传简历或补资料。</div>", unsafe_allow_html=True)
    if st.button("暂时跳过，直接进入求职陪聊", use_container_width=True):
        _safe_cookie_set(COOKIE_SESSION_KEY, st.session_state.session_id)
        st.session_state.onboarding_done = True
        go("chat")

    if submitted:
        save_profile_from_form(
            nickname, school, grade, major,
            target_industry, target_position, target_city,
        )
        if target_industry.strip() and target_position.strip() and target_city.strip():
            with st.spinner("正在生成目标城市岗位快照…"):
                st.session_state.job_market_snapshot = generate_job_market_snapshot(
                    db.get_user(user_id),
                    api_key=get_deepseek_token(),
                )
        if uploaded is None:
            go("chat")

        try:
            resume_text = resume.extract_text(uploaded.name, uploaded.getvalue())
        except resume.ResumeParseError as e:
            st.error(str(e))
            return

        with st.spinner("正在读取简历并生成诊断…"):
            extracted = extract_resume_profile(resume_text, api_key=get_deepseek_token())
            if extracted:
                cur = db.get_user(user_id) or {}
                db.update_user_profile(
                    user_id,
                    cur.get("nickname") or "",
                    cur.get("school") or "",
                    extracted.get("grade") or cur.get("grade") or "",
                    extracted.get("major") or cur.get("major") or "",
                    extracted.get("target_industry") or cur.get("target_industry") or "",
                    extracted.get("target_position") or cur.get("target_position") or "",
                    cur.get("target_city") or "",
                )
            st.session_state.resume_report = analyze_resume(
                resume_text,
                user_info=db.get_user(user_id),
                api_key=get_deepseek_token(),
            )
        go("resume")


# ====================================================================
# 主页：四大板块
# ====================================================================

def render_home() -> None:
    st.markdown(
        f"""
        <div class='brand-title'>
          <div class='brand-copy'>
            <h1>职来</h1>
            <div class='brand-subtitle'>Careerture</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("温暖、理性、有行动力的求职陪伴 —— 选择一个板块开始")

    # 各板块当前数量，做成小提示
    n_app = len(db.get_applications(user_id))
    n_iv = len(db.get_interviews(user_id))
    n_task = len(db.get_user_tasks(user_id, only_incomplete=True))

    boards = [
        ("求职陪聊", f"和 AI 聊求职，拆成可执行小步（{n_task} 个待办）", "chat", "chat"),
        ("简历诊断", "上传简历，挑痛点给建议，并自动读取你的信息", "resume", "resume"),
        ("投递记录", f"记录秋招/春招每一笔投递（已记 {n_app} 笔）", "applications", "mail"),
        ("面试邀约", f"管理近期面试时间与安排（{n_iv} 个邀约）", "interviews", "calendar"),
    ]

    cols = [st.columns(2), st.columns(2)]
    for i, (title, desc, key, icon) in enumerate(boards):
        col = cols[i // 2][i % 2]
        with col:
            with st.container(border=True):
                st.markdown("<div class='home-card-marker'></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='pixel-label'>{pixel_icon(icon, title)}<h3>{title}</h3></div>",
                    unsafe_allow_html=True,
                )
                st.write(desc)
                if st.button("进入 ▶", key=f"go_{key}", use_container_width=True):
                    go(key)

    st.markdown("<div class='disclaimer'>以上建议由 AI 生成，仅供参考</div>", unsafe_allow_html=True)


# ====================================================================
# 板块 1：求职陪聊
# ====================================================================

def render_chat() -> None:
    back_button()
    render_page_title("求职陪聊", "chat")

    if st.session_state.get("job_market_snapshot"):
        with st.expander("目标城市岗位快照", expanded=True):
            st.markdown(st.session_state.job_market_snapshot)

    # 待办 + 新建对话
    with st.container(border=True):
        incomplete = db.get_user_tasks(user_id, only_incomplete=True)
        if incomplete:
            st.markdown(
                f"<div class='pixel-label'>{pixel_icon('task', '待办')}<strong>你的待办</strong>（勾选即完成）</div>",
                unsafe_allow_html=True,
            )
            for t in incomplete:
                if st.checkbox(t["task_content"], key=f"task_{t['id']}"):
                    db.mark_task_complete(t["id"])
                    st.rerun()
        else:
            st.caption("暂无待办，聊聊我会给你布置「可以马上做的事」。")
        if st.button("🆕 新建对话（清空当前对话）"):
            st.session_state.messages = []
            st.rerun()

    render_archive_drawer()

    # 历史消息 + 反馈按钮
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            cid = msg.get("conversation_id")
            if msg["role"] == "assistant" and cid is not None:
                archive_chat_message(f"history_{cid}_{idx}", msg["content"])
                if cid in st.session_state.feedback_given:
                    st.caption("感谢反馈 🙏")
                else:
                    c1, c2, _ = st.columns([1, 1, 6])
                    if c1.button("👍 有用", key=f"fb_up_{cid}"):
                        db.save_feedback(user_id, cid, True)
                        st.session_state.feedback_given.add(cid)
                        st.rerun()
                    if c2.button("👎 没用", key=f"fb_down_{cid}"):
                        db.save_feedback(user_id, cid, False)
                        st.session_state.feedback_given.add(cid)
                        st.rerun()

    if not st.session_state.messages:
        pending = db.get_user_tasks(user_id, only_incomplete=True)
        with st.chat_message("assistant"):
            if pending:
                st.markdown(
                    f"欢迎回来 👋 你上次有 **{len(pending)}** 个任务还没完成，"
                    "需要我帮你调整计划吗？"
                )
            else:
                st.markdown(
                    "你好，我是职来 Careerture。说说你的情况，"
                    "我们一起把求职这件事拆成可执行的小步。"
                )

    if prompt := st.chat_input("输入你的问题，回车发送…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        incomplete = db.get_user_tasks(user_id, only_incomplete=True)
        with st.chat_message("assistant"):
            with st.spinner("思考中…"):
                result = chat_turn(
                    st.session_state.messages,
                    user_info=db.get_user(user_id),
                    existing_tasks=[t["task_content"] for t in incomplete],
                    api_key=get_deepseek_token(),
                )
            content = result["advice"]
            if result["action_items"]:
                todo = "\n".join(f"- ☐ {t}" for t in result["action_items"])
                content += "\n\n**📌 建议的行动项**\n" + todo + "\n\n*（已加入上方待办，可勾选完成）*"
            st.markdown(content)
            archive_chat_message(f"draft_{len(st.session_state.messages)}", content)

        assistant_msg = {"role": "assistant", "content": content}
        if not result["advice"].startswith("⚠️"):
            cid = db.save_conversation_summary(user_id, result["summary"])
            assistant_msg["conversation_id"] = cid
            if result["action_items"]:
                existing = {t["task_content"] for t in db.get_user_tasks(user_id)}
                for item in result["action_items"]:
                    if item not in existing:
                        db.add_task(user_id, item)
                        existing.add(item)
        st.session_state.messages.append(assistant_msg)
        st.rerun()


# ====================================================================
# 板块 2：简历诊断（并自动读取个人信息）
# ====================================================================

def render_resume() -> None:
    back_button()
    render_page_title("简历诊断", "resume")

    # 展示当前已读到的个人信息（来自上次上传的简历）
    info = db.get_user(user_id) or {}
    if any(info.get(k) for k in ("nickname", "school", "grade", "major", "target_industry", "target_position", "target_city")):
        st.caption(
            "已记录： "
            f"昵称 {info.get('nickname') or '—'}｜学校 {info.get('school') or '—'}｜"
            f"年级 {info.get('grade') or '—'}｜专业 {info.get('major') or '—'}｜"
            f"意向行业 {info.get('target_industry') or '—'}｜意向岗位 {info.get('target_position') or '—'}｜"
            f"目标城市 {info.get('target_city') or '—'}"
        )

    uploaded = st.file_uploader(
        "上传简历（支持 PDF / DOCX / TXT，≤ 5MB）",
        type=["pdf", "docx", "txt"], key="resume_uploader",
    )
    if st.button("🔍 开始诊断", disabled=uploaded is None):
        try:
            resume_text = resume.extract_text(uploaded.name, uploaded.getvalue())
        except resume.ResumeParseError as e:
            st.error(str(e))
        else:
            # 1) 从简历提取个人信息并写库（仅覆盖非空字段，保留已有）
            with st.spinner("正在读取你的个人信息…"):
                extracted = extract_resume_profile(resume_text, api_key=get_deepseek_token())
            if extracted:
                cur = db.get_user(user_id) or {}
                db.update_user_profile(
                    user_id,
                    cur.get("nickname") or "",
                    cur.get("school") or "",
                    extracted.get("grade") or cur.get("grade") or "",
                    extracted.get("major") or cur.get("major") or "",
                    extracted.get("target_industry") or cur.get("target_industry") or "",
                    extracted.get("target_position") or cur.get("target_position") or "",
                    cur.get("target_city") or "",
                )
            # 2) 生成诊断报告
            with st.spinner("正在逐行阅读你的简历…"):
                st.session_state.resume_report = analyze_resume(
                    resume_text,
                    user_info=db.get_user(user_id),
                    api_key=get_deepseek_token(),
                )
            st.rerun()

    if st.session_state.get("resume_report"):
        st.divider()
        st.markdown(st.session_state.resume_report)
        if st.button("进入求职陪聊", use_container_width=True):
            go("chat")
        if st.button("清除诊断结果"):
            st.session_state.resume_report = None
            st.rerun()


# ====================================================================
# 板块 3：投递记录
# ====================================================================

def render_applications() -> None:
    back_button()
    render_page_title("投递记录", "mail")

    with st.form("add_app_form", clear_on_submit=True):
        a1, a2 = st.columns(2)
        company = a1.text_input("公司")
        position = a2.text_input("岗位")
        a3, a4, a5 = st.columns(3)
        season = a3.selectbox("批次", ["秋招", "春招"])
        status = a4.selectbox("状态", APP_STATUS)
        applied = a5.date_input("投递日期")
        if st.form_submit_button("📩 投进邮箱（添加记录）"):
            if company.strip():
                db.add_application(
                    user_id, company.strip(), position.strip(),
                    season, status, applied.isoformat(),
                )
                st.rerun()
            else:
                st.warning("请至少填写公司名称。")

    apps = db.get_applications(user_id)
    if not apps:
        st.caption("📭 邮箱还空着 —— 投了第一家就来记一笔吧！")
    else:
        st.caption(f"📬 邮箱里共有 {len(apps)} 封投递")
        for a in apps:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(
                f"**{a['company']}** · {a['position'] or '—'}  \n"
                f"<small>{a['season']} · 投于 {a['applied_date'] or '—'}</small>",
                unsafe_allow_html=True,
            )
            idx = APP_STATUS.index(a["status"]) if a["status"] in APP_STATUS else 0
            new_status = c2.selectbox(
                "状态", APP_STATUS, index=idx,
                key=f"app_status_{a['id']}", label_visibility="collapsed",
            )
            if new_status != a["status"]:
                db.update_application_status(a["id"], new_status)
                st.rerun()
            if c3.button("🗑", key=f"del_app_{a['id']}"):
                db.delete_application(a["id"])
                st.rerun()


# ====================================================================
# 板块 4：面试邀约
# ====================================================================

def render_interview_calendar(interviews: list[dict]) -> None:
    scheduled = [iv for iv in interviews if iv.get("interview_date")]
    unscheduled = [iv for iv in interviews if not iv.get("interview_date")]

    st.markdown("### 面试日历看板")
    if not scheduled and not unscheduled:
        st.caption("添加面试邀约后，这里会自动生成日历看板。")
        return

    grouped: dict[str, list[dict]] = {}
    for iv in scheduled:
        grouped.setdefault(iv["interview_date"], []).append(iv)

    if grouped:
        for day in sorted(grouped):
            try:
                day_label = date.fromisoformat(day).strftime("%m月%d日")
            except ValueError:
                day_label = day
            with st.container(border=True):
                st.markdown(f"**{day_label}**")
                for iv in sorted(grouped[day], key=lambda item: item.get("interview_clock") or ""):
                    clock = iv.get("interview_clock") or "时间待定"
                    st.markdown(
                        f"<div class='pixel-label'><strong>{clock}</strong> "
                        f"{iv['company']} · {iv.get('position') or '—'} · {iv.get('method') or ''}</div>",
                        unsafe_allow_html=True,
                    )
                    if iv.get("note"):
                        st.caption(iv["note"])

    if unscheduled:
        with st.expander(f"待确认时间（{len(unscheduled)}）", expanded=False):
            for iv in unscheduled:
                st.markdown(
                    f"**{iv['company']}** · {iv.get('position') or '—'}  \n"
                    f"{iv.get('interview_time') or '时间待定'} · {iv.get('method') or ''}"
                )


def render_interviews() -> None:
    back_button()
    render_page_title("面试邀约", "calendar")

    with st.form("add_iv_form", clear_on_submit=True):
        i1, i2 = st.columns(2)
        iv_company = i1.text_input("公司")
        iv_position = i2.text_input("岗位")
        i3, i4, i5 = st.columns(3)
        iv_date = i3.date_input("面试日期")
        iv_clock = i4.time_input("面试时间", value=time(9, 0))
        iv_method = i5.selectbox("形式", ["线上", "现场", "电话"])
        iv_note = st.text_input("备注", placeholder="如：二面 / 腾讯会议 / 带简历")
        if st.form_submit_button("➕ 添加面试邀约"):
            if iv_company.strip():
                iv_time_text = f"{iv_date.isoformat()} {iv_clock.strftime('%H:%M')}"
                db.add_interview(
                    user_id, iv_company.strip(), iv_position.strip(),
                    iv_time_text, iv_method, iv_note.strip(),
                    interview_date=iv_date.isoformat(),
                    interview_clock=iv_clock.strftime("%H:%M"),
                )
                st.rerun()
            else:
                st.warning("请至少填写公司名称。")

    interviews = db.get_interviews(user_id)
    render_interview_calendar(interviews)
    st.divider()
    if not interviews:
        st.caption("还没有面试邀约 —— 加油，邀约会来的！")
    else:
        st.caption(f"📌 共 {len(interviews)} 个面试邀约")
        for iv in interviews:
            c1, c2 = st.columns([6, 1])
            time_label = (
                f"{iv.get('interview_date') or ''} {iv.get('interview_clock') or ''}".strip()
                or iv["interview_time"]
                or "时间待定"
            )
            line = (
                f"**{iv['company']}** · {iv['position'] or '—'}  \n"
                f"🕒 {time_label} · {iv['method'] or ''}"
            )
            if iv["note"]:
                line += f"  \n📝 {iv['note']}"
            c1.markdown(line)
            if c2.button("🗑", key=f"del_iv_{iv['id']}"):
                db.delete_interview(iv["id"])
                st.rerun()


# ====================================================================
# 路由
# ====================================================================

VIEWS = {
    "onboarding": render_onboarding,
    "home": render_home,
    "chat": render_chat,
    "resume": render_resume,
    "applications": render_applications,
    "interviews": render_interviews,
}
VIEWS.get(st.session_state.view, render_home)()
