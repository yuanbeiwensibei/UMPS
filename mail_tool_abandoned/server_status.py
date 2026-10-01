"""
服务器状态查询 — "ump在线" / "在线" / "查服" → 在线人数 & 玩家列表
"""
import time
import yaml

from mail_tool.vice_tool.config import config as _cfg

_pending_server = []  # [{group_id, qq, event_type, time}]
_PENDING_TTL = 5


def _read_ban_qqs():
    try:
        with open("./UMPs/ban.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return set(data.get("qq", []))
    except Exception:
        return set()


def _read_reviewed_qqs():
    try:
        with open("./UMPs/review.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return set(data or [])
    except Exception:
        return set()


def _cleanup_pending(now=None):
    if now is None:
        now = time.time()
    global _pending_server
    _pending_server = [c for c in _pending_server if now - c["time"] < _PENDING_TTL]


def _reply(mail, event_type, target, group_id, text):
    """构造 napcat 回复，自动适配群聊/私聊/临时会话"""
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "napcat"
    payload = {"text": text}
    if event_type == "message.group":
        payload["action"], payload["target"] = "send_group_msg", group_id
    elif event_type == "message.private":
        payload["action"], payload["target"] = "send_private_msg", target
    else:
        payload["action"], payload["target"] = "send_msg", target
        payload["group_id"] = group_id
    m["umps_mail"] = payload
    return m


def server_status(mail):

    nm = mail.get("napcat_mail") or {}
    mm = mail.get("minecraft_mail") or {}

    # ====== 入口 A：napcat 查询指令 ======
    if mail.get("mailer") == "napcat":
        msg = (nm.get("message") or "").strip()
        et = nm.get("event_type", "")
        qq = nm["sender_qq"]
        group_id = nm.get("group_id") or 0

        # 触发词过滤
        if msg not in ("ump在线", "在线", "查服"):
            return None

        # 游戏群内才响应（私聊/临时会话无 group_id 也能走）
        if et == "message.group" and group_id not in _cfg("游戏群"):
            return None

        # 封禁 / 未通过审核
        if qq in _read_ban_qqs():
            return _reply(mail, et, qq, group_id, "[查询失败]\n你已被服务器封禁，无法查询")
        if qq not in _read_reviewed_qqs():
            return _reply(mail, et, qq, group_id, "[查询失败]\n你没有通过服务器审核，无法查询")

        # 服务器离线
        if not mail.get("minecraft_online"):
            return _reply(mail, et, qq, group_id, "[服务器状态]\n当前离线")

        _cleanup_pending()
        _pending_server.append({
            "group_id": group_id,
            "qq": qq,
            "event_type": et,
            "time": time.time(),
        })

        if len(_pending_server) == 1:
            return _make_mc_req(mail)
        return None

    # ====== 入口 B：minecraft 响应 ======
    if mail.get("mailer") == "minecraft":
        if mm.get("post_type") != "server_info_result":
            return None

        count = mm.get("online_count", 0)
        players = mm.get("online_players", [])

        text = (
            f"服务器状态\n"
            f"在线人数：{count}\n"
            f"在线玩家：{', '.join(players) if players else '无'}"
        )

        results = []
        while _pending_server:
            ctx = _pending_server.pop(0)
            results.append(_reply(mail, ctx["event_type"], ctx["qq"], ctx["group_id"], text))

        return results if results else None

    return None


def _make_mc_req(mail):
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "minecraft"
    m["umps_mail"] = {"post_type": "get_server_info"}
    return m
