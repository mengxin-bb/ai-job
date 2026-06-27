"""
职来 Careerture —— Streamlit Demo 主入口。

结构：主页四大板块（求职陪聊 / 简历诊断 / 投递记录 / 面试邀约），
每个板块点进去是一个独立全屏页面，左上角有「返回主页」。
个人资料可从简历读取，也可在「我的资料」里随时维护。

运行：
    cp .env.example .env      # 填入 DEEPSEEK_API_KEY
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import uuid
import base64
import json
import csv
import io
from datetime import date, time

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
from utils.api_client import (
    analyze_resume,
    chat_turn,
    extract_resume_profile,
    generate_job_market_snapshot,
    rewrite_resume_bullets,
)

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
        overflow-x: hidden;
      }
      html, body, [data-testid="stAppViewContainer"], .main {
        overflow-x: hidden !important;
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
        max-width: 920px;
        padding-left: max(1rem, env(safe-area-inset-left)) !important;
        padding-right: max(1rem, env(safe-area-inset-right)) !important;
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
        font-size: clamp(1.85rem, 7vw, 3.2rem) !important;
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
        .main .block-container {
          padding-left: 0.85rem !important;
          padding-right: 0.85rem !important;
        }
        .brand-title {
          margin-top: 0.25rem;
          margin-bottom: 0.65rem;
        }
        .brand-title h1 {
          font-size: 2rem !important;
        }
        h1 {
          font-size: 1.05rem !important;
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
PROFILE_REQUIRED_FIELDS = ("nickname", "school", "grade", "major", "target_industry", "target_position", "target_city")

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
    return all((info.get(k) or "").strip() for k in PROFILE_REQUIRED_FIELDS)


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
    st.session_state.view = "home"
elif st.session_state.view == "onboarding":
    st.session_state.view = "home"
if "onboarding_done" not in st.session_state:
    st.session_state.onboarding_done = True
if "deepseek_token" not in st.session_state:
    st.session_state.deepseek_token = ""

user_id = st.session_state.user_id


def get_deepseek_token() -> str:
    return (
        st.session_state.get("deepseek_token")
        or os.getenv("DEEPSEEK_API_KEY")
        or ""
    ).strip()


def rows_to_csv(rows: list[dict]) -> bytes:
    """把查询结果转成带 BOM 的 CSV，方便 Excel 直接打开中文。"""
    if not rows:
        return "\ufeff".encode("utf-8")
    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def render_backup_panel() -> None:
    with st.sidebar:
        st.markdown("### 数据备份")
        st.caption("Streamlit Cloud 重启后，本地 SQLite 可能清空。认真使用前建议定期导出 CSV。")
        st.download_button(
            "导出投递记录 CSV",
            data=rows_to_csv(db.get_all_applications()),
            file_name="careerture_applications.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "导出待办 CSV",
            data=rows_to_csv(db.get_user_tasks(user_id)),
            file_name="careerture_tasks.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "导出面试 CSV",
            data=rows_to_csv(db.get_all_interviews()),
            file_name="careerture_interviews.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption("长期稳定版本建议接 Supabase / Postgres，避免云端临时文件丢失。")


def render_token_config() -> None:
    with st.sidebar:
        if st.button("我的资料", use_container_width=True):
            st.session_state.view = "profile"
            st.rerun()
        st.caption("修改学校、目标城市、目标岗位后，陪聊和岗位快照会更准确。")
        st.divider()
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
            st.caption("此 Token 仅保存在当前浏览器会话，不会写入数据库。")
        elif has_cloud_token:
            st.success("已使用部署端 Token，朋友可直接体验")
            st.caption("如需换成自己的 Token，也可以在这里填写。")
        else:
            st.info("未检测到部署端 Token。请在 Streamlit Secrets 配置，或仅自己测试时手动填写。")


render_token_config()
render_backup_panel()


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
APP_CHANNELS = ["官网", "Boss直聘", "猎聘", "牛客", "校园招聘会", "内推", "公众号", "其他"]
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


def _format_interview_day(day: str) -> str:
    try:
        return date.fromisoformat(day).strftime("%m月%d日")
    except (TypeError, ValueError):
        return day or "待定"


def render_calendar_board(compact: bool = True) -> None:
    interviews = db.get_interviews(user_id)
    scheduled = [iv for iv in interviews if iv.get("interview_date")]
    unscheduled = [iv for iv in interviews if not iv.get("interview_date")]

    title = "面试日历挂表" if compact else "日程安排"
    st.markdown(f"### {title}")
    if not interviews:
        with st.container(border=True):
            st.caption("还没有面试邀约。添加后会在这里自动形成日历挂表。")
        return

    grouped = {}
    for iv in scheduled:
        grouped.setdefault(iv["interview_date"], []).append(iv)

    next_items = []
    for day in sorted(grouped):
        for iv in sorted(grouped[day], key=lambda item: item.get("interview_clock") or ""):
            next_items.append(iv)

    if compact:
        with st.container(border=True):
            if next_items:
                st.markdown("**近期面试**")
                for iv in next_items[:3]:
                    clock = iv.get("interview_clock") or "时间待定"
                    st.markdown(
                        f"<div class='pixel-label'><strong>{_format_interview_day(iv.get('interview_date'))} {clock}</strong>"
                        f"｜{iv['company']} · {iv.get('position') or '—'}</div>",
                        unsafe_allow_html=True,
                    )
            if unscheduled:
                st.caption(f"还有 {len(unscheduled)} 个邀约待确认时间")
            if st.button("放大查看日程安排", use_container_width=True):
                go("calendar")
        return

    if grouped:
        for day in sorted(grouped):
            with st.container(border=True):
                st.markdown(f"**{_format_interview_day(day)}**")
                for iv in sorted(grouped[day], key=lambda item: item.get("interview_clock") or ""):
                    clock = iv.get("interview_clock") or "时间待定"
                    st.markdown(
                        f"**{clock}**｜{iv['company']} · {iv.get('position') or '—'} · {iv.get('method') or ''}"
                    )
                    if iv.get("note"):
                        st.caption(iv["note"])

    if unscheduled:
        with st.expander(f"待确认时间（{len(unscheduled)}）", expanded=True):
            for iv in unscheduled:
                st.markdown(
                    f"**{iv['company']}** · {iv.get('position') or '—'}  \n"
                    f"{iv.get('interview_time') or '时间待定'} · {iv.get('method') or ''}"
                )


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
            go("home")

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
    profile_col, _ = st.columns([1, 2])
    with profile_col:
        if st.button("我的资料", use_container_width=True):
            go("profile")
    render_calendar_board(compact=True)

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
# 我的资料：主动编辑目标与基础信息
# ====================================================================

def render_profile() -> None:
    back_button()
    render_page_title("我的资料", "task")

    info = db.get_user(user_id) or {}
    st.caption("这些资料会用于求职陪聊、简历诊断和目标城市岗位快照。之后目标变化，也可以随时回来修改。")

    with st.form("profile_edit_form"):
        f1, f2 = st.columns(2)
        nickname = f1.text_input("昵称", value=info.get("nickname") or "")
        school = f2.text_input("学校", value=info.get("school") or "")
        f3, f4 = st.columns(2)
        grade = f3.text_input("年级", value=info.get("grade") or "", placeholder="如：大三 / 研二")
        major = f4.text_input("专业", value=info.get("major") or "")
        f5, f6, f7 = st.columns(3)
        target_industry = f5.text_input(
            "目标行业",
            value=info.get("target_industry") or "",
            placeholder="如：互联网 / 金融 / 快消",
        )
        target_position = f6.text_input(
            "目标岗位",
            value=info.get("target_position") or "",
            placeholder="如：产品经理 / 数据分析",
        )
        target_city = f7.text_input(
            "目标城市",
            value=info.get("target_city") or "",
            placeholder="如：上海 / 杭州",
        )
        submitted = st.form_submit_button("保存资料", use_container_width=True)

    if submitted:
        save_profile_from_form(
            nickname,
            school,
            grade,
            major,
            target_industry,
            target_position,
            target_city,
        )
        st.success("已保存。之后打开网站会继续记住这些资料。")
        if target_industry.strip() and target_position.strip() and target_city.strip():
            with st.spinner("正在更新目标城市岗位快照…"):
                st.session_state.job_market_snapshot = generate_job_market_snapshot(
                    db.get_user(user_id),
                    api_key=get_deepseek_token(),
                )

    if st.session_state.get("job_market_snapshot"):
        with st.expander("目标城市岗位快照", expanded=True):
            st.caption("岗位快照为 AI 生成的参考示例，不代表实时招聘数据或真实在招岗位；建议结合招聘网站/JD 原文核对。")
            st.markdown(st.session_state.job_market_snapshot)
    else:
        st.info("补全目标城市、目标行业和目标岗位后，我会为你生成岗位 JD 示例与薪资参考。")

    c1, c2 = st.columns(2)
    if c1.button("进入求职陪聊", use_container_width=True):
        go("chat")
    if c2.button("回到四大板块", use_container_width=True):
        go("home")


# ====================================================================
# 板块 1：求职陪聊
# ====================================================================

def render_chat() -> None:
    back_button()
    render_page_title("求职陪聊", "chat")

    if st.session_state.get("job_market_snapshot"):
        with st.expander("目标城市岗位快照", expanded=True):
            st.caption("岗位快照为 AI 生成的参考示例，不代表实时招聘数据或真实在招岗位；建议结合招聘网站/JD 原文核对。")
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
            st.session_state.resume_text = resume_text
            st.session_state.resume_rewrite = None
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
        if st.button("生成可复制改写版", use_container_width=True):
            resume_text = st.session_state.get("resume_text")
            if not resume_text:
                st.warning("请先重新上传简历，再生成改写版。")
            else:
                with st.spinner("正在生成 STAR 改写和可复制 bullet points…"):
                    st.session_state.resume_rewrite = rewrite_resume_bullets(
                        resume_text,
                        user_info=db.get_user(user_id),
                        api_key=get_deepseek_token(),
                    )
                st.rerun()
        if st.session_state.get("resume_rewrite"):
            with st.expander("可复制改写版", expanded=True):
                st.markdown(st.session_state.resume_rewrite)
                st.code(st.session_state.resume_rewrite, language="markdown")
        if st.button("进入求职陪聊", use_container_width=True):
            go("chat")
        if st.button("清除诊断结果"):
            st.session_state.resume_report = None
            st.session_state.resume_rewrite = None
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
        a6, a7, a8 = st.columns(3)
        channel = a6.selectbox("投递渠道", APP_CHANNELS)
        referrer = a7.text_input("内推人", placeholder="没有可留空")
        next_step = a8.text_input("下一步提醒", placeholder="如：3天后跟进")
        jd_link = st.text_input("JD 链接", placeholder="https://...")
        note = st.text_area("备注", placeholder="岗位要求、准备方向、沟通记录等", height=90)
        fail_reason = st.text_input("失败原因", placeholder="未通过时可记录原因，便于复盘")
        if st.form_submit_button("📩 加入 CRM（添加记录）"):
            if company.strip():
                db.add_application(
                    user_id, company.strip(), position.strip(),
                    season, status, applied.isoformat(),
                    channel, jd_link.strip(), referrer.strip(),
                    next_step.strip(), note.strip(), fail_reason.strip(),
                )
                st.rerun()
            else:
                st.warning("请至少填写公司名称。")

    apps = db.get_applications(user_id)
    if not apps:
        st.caption("📭 邮箱还空着 —— 投了第一家就来记一笔吧！")
    else:
        status_counts = {s: 0 for s in APP_STATUS}
        for item in apps:
            if item.get("status") in status_counts:
                status_counts[item["status"]] += 1
        st.caption(f"📬 CRM 里共有 {len(apps)} 条投递")
        stat_cols = st.columns(len(APP_STATUS))
        for col, status_name in zip(stat_cols, APP_STATUS):
            col.metric(status_name, status_counts[status_name])
        for a in apps:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.markdown(
                    f"**{a['company']}** · {a['position'] or '—'}  \n"
                    f"<small>{a['season']} · {a.get('channel') or '渠道未填'} · 投于 {a['applied_date'] or '—'}</small>",
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
                if c3.button("删除", key=f"del_app_{a['id']}"):
                    db.delete_application(a["id"])
                    st.rerun()

                detail_bits = []
                if a.get("next_step"):
                    detail_bits.append(f"下一步：{a['next_step']}")
                if a.get("referrer"):
                    detail_bits.append(f"内推人：{a['referrer']}")
                if a.get("fail_reason"):
                    detail_bits.append(f"失败原因：{a['fail_reason']}")
                if detail_bits:
                    st.caption("｜".join(detail_bits))
                if a.get("jd_link"):
                    st.markdown(f"[查看 JD 链接]({a['jd_link']})")
                if a.get("note"):
                    st.markdown(f"备注：{a['note']}")

                with st.expander("编辑详情", expanded=False):
                    with st.form(f"edit_app_form_{a['id']}"):
                        e1, e2 = st.columns(2)
                        edit_company = e1.text_input("公司", value=a["company"], key=f"edit_company_{a['id']}")
                        edit_position = e2.text_input("岗位", value=a.get("position") or "", key=f"edit_position_{a['id']}")
                        e3, e4, e5 = st.columns(3)
                        edit_season = e3.selectbox(
                            "批次",
                            ["秋招", "春招"],
                            index=0 if a.get("season") != "春招" else 1,
                            key=f"edit_season_{a['id']}",
                        )
                        edit_status = e4.selectbox(
                            "状态",
                            APP_STATUS,
                            index=APP_STATUS.index(a["status"]) if a.get("status") in APP_STATUS else 0,
                            key=f"edit_status_{a['id']}",
                        )
                        try:
                            applied_value = date.fromisoformat(a.get("applied_date") or "")
                        except ValueError:
                            applied_value = date.today()
                        edit_applied = e5.date_input("投递日期", value=applied_value, key=f"edit_applied_{a['id']}")
                        e6, e7, e8 = st.columns(3)
                        channel_value = a.get("channel") or "官网"
                        edit_channel = e6.selectbox(
                            "投递渠道",
                            APP_CHANNELS,
                            index=APP_CHANNELS.index(channel_value) if channel_value in APP_CHANNELS else 0,
                            key=f"edit_channel_{a['id']}",
                        )
                        edit_referrer = e7.text_input("内推人", value=a.get("referrer") or "", key=f"edit_referrer_{a['id']}")
                        edit_next_step = e8.text_input("下一步提醒", value=a.get("next_step") or "", key=f"edit_next_{a['id']}")
                        edit_jd_link = st.text_input("JD 链接", value=a.get("jd_link") or "", key=f"edit_jd_{a['id']}")
                        edit_note = st.text_area("备注", value=a.get("note") or "", height=90, key=f"edit_note_{a['id']}")
                        edit_fail_reason = st.text_input(
                            "失败原因",
                            value=a.get("fail_reason") or "",
                            key=f"edit_fail_{a['id']}",
                        )
                        if st.form_submit_button("保存修改", use_container_width=True):
                            if not edit_company.strip():
                                st.warning("公司名称不能为空。")
                            else:
                                db.update_application_detail(
                                    a["id"],
                                    edit_company.strip(),
                                    edit_position.strip(),
                                    edit_season,
                                    edit_status,
                                    edit_applied.isoformat(),
                                    edit_channel,
                                    edit_jd_link.strip(),
                                    edit_referrer.strip(),
                                    edit_next_step.strip(),
                                    edit_note.strip(),
                                    edit_fail_reason.strip(),
                                )
                                st.success("已保存")
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
    render_calendar_board(compact=False)
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


def render_calendar() -> None:
    back_button()
    render_page_title("日程安排", "calendar")
    render_calendar_board(compact=False)
    if st.button("添加新的面试邀约", use_container_width=True):
        go("interviews")


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
    "calendar": render_calendar,
    "profile": render_profile,
}
VIEWS.get(st.session_state.view, render_home)()
