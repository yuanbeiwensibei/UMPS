"""
审核插件 —— 处理 umps 的「开启审核链接」请求，管理审核会话与答题卡提交。

web_tool 插件约定（与 mail_tool 一致）：
  插件入口函数入参是整封 mail，返回 None（不处理）或一封回信 mail。

QQ 贯穿全程：
  - umps 请求开链接时带 qq（open_review_link.qq）
  - web 返回链接时带 qq（review_link_ready.qq）
  - web 交答题卡时带 qq（review_answers.qq）
"""

import secrets
import threading
import time

from web_tool import log, outbox
from web_tool import questions

# ── 配置（web.py 启动时可覆盖）──────────────────────────────
REVIEW_BASE_URL = "http://127.0.0.1"   # 审核链接对外基地址（80 端口默认省略）
REVIEW_LINK_TTL = 30 * 60              # 链接有效期（秒）

# ── 协议消息类型 ────────────────────────────────────────────
OPEN_REVIEW_LINK = "open_review_link"
REVIEW_LINK_READY = "review_link_ready"
REVIEW_ANSWERS = "review_answers"


def _build_mail(mailer, recipient, web_mail, mail_id=""):
    """构造一封标准 mail：只填 web 相关槽位，其余留空。"""
    return {
        "mailer": mailer,
        "Recipient": recipient,
        "web_mail": web_mail,
        "umps_mail": "",
        "ai_mail": "",
        "minecraft_mail": "",
        "napcat_mail": "",
        "need": True,
        "minecraft_online": True,
        "mail_id": mail_id,
    }


# ── 审核会话（link_id -> 会话）───────────────────────────────
_lock = threading.Lock()
_sessions = {}  # link_id -> ReviewSession


class ReviewSession:
    __slots__ = ("qq", "link_id", "created_at", "ttl", "submitted")

    def __init__(self, qq, link_id, created_at, ttl):
        self.qq = qq
        self.link_id = link_id
        self.created_at = created_at
        self.ttl = ttl
        self.submitted = False


def create_session(qq, ttl=None):
    """为一个 QQ 创建审核会话，返回 link_id。"""
    if ttl is None:
        ttl = REVIEW_LINK_TTL
    link_id = secrets.token_urlsafe(24)
    with _lock:
        _sessions[link_id] = ReviewSession(qq, link_id, time.time(), ttl)
    return link_id


def get_session(link_id):
    """按 link_id 取会话；不存在或已过期返回 None（过期顺带清理）。"""
    with _lock:
        s = _sessions.get(link_id)
        if s is None:
            return None
        if (time.time() - s.created_at) > s.ttl:
            _sessions.pop(link_id, None)
            return None
        return s


def mark_submitted(link_id):
    """标记会话已提交。返回 True 表示本次标记成功；重复提交返回 False。"""
    with _lock:
        s = _sessions.get(link_id)
        if s is None or s.submitted:
            return False
        s.submitted = True
        return True


# ── 插件入口 ────────────────────────────────────────────────
def review(mail):
    """处理 umps 发来的 mail。仅处理 open_review_link，其余返回 None。

    注意：ums 发来的内容放在 umps_mail 槽（mailer 填自己的槽，全系统约定），
    因此这里读 umps_mail；web 回信时则填 web_mail 槽（见 _build_mail）。
    """
    if mail.get("Recipient") != "web":
        return None
    wm = mail.get("umps_mail") or {}
    if wm.get("post_type") != OPEN_REVIEW_LINK:
        return None

    qq = wm.get("qq")
    link_id = create_session(qq)
    url = f"{REVIEW_BASE_URL.rstrip('/')}/review/{link_id}/"
    log.info("开启审核链接 qq=%s link_id=%s", qq, link_id)
    return _build_mail(
        "web", "umps",
        {"post_type": REVIEW_LINK_READY, "qq": qq, "link_id": link_id,
         "url": url, "ok": True},
        mail_id=f"review_link_ready_{link_id}",
    )


# ── 答题卡校验与提交（供 Django 视图调用）─────────────────────
def validate_answers(raw):
    """校验答题卡。raw 是 {q<id>: 答案} 字典。返回 (answers, errors)。"""
    answers = []
    errors = []
    for q in questions.QUESTIONS:
        qid = q["id"]
        ans = (raw.get(f"q{qid}") or "").strip()
        if q["type"] == "single":
            if ans not in q["options"]:
                errors.append(f"第 {qid} 题未作答")
            else:
                answers.append({"question_id": qid, "answer": ans})
        else:
            if not ans:
                errors.append(f"第 {qid} 题未作答")
            elif len(ans) < q.get("min_words", 0):
                errors.append(f"第 {qid} 题少于 {q['min_words']} 字")
            else:
                answers.append({"question_id": qid, "answer": ans})
    return answers, errors


def submit_answers(link_id, answers):
    """提交答题卡：防重 → 构造 review_answers 入 outbox。返回 (ok, message)。"""
    session = get_session(link_id)
    if session is None:
        return False, "审核链接无效或已过期"
    if not mark_submitted(link_id):
        return False, "该审核链接已提交过，链接已失效"

    mail = _build_mail(
        "web", "umps",
        {"post_type": REVIEW_ANSWERS, "link_id": link_id,
         "qq": session.qq, "answers": answers},
        mail_id=f"review_answers_{link_id}",
    )
    outbox.put(mail)
    log.info("收到答题卡 qq=%s link_id=%s answers=%d",
             session.qq, link_id, len(answers))
    return True, "已提交"
