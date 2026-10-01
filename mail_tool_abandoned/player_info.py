"""
查询玩家信息工具

触发词（游戏群聊）：
- "看我的" / "我的信息" / "查询" → 查自己
- "查询 <QQ号>" / "查询 <游戏ID>" → 查别人

数据流：
  napcat 消息 → QQ↔ID 查表 → 发 get_player_info 给 minecraft
  → minecraft 返回 player_info_result → 拼装卡片 → 发回玩家
"""

import re
import time
import yaml
import json
import os

from mail_tool.vice_tool.query import query as _id_query

# ── 查询状态池：{game_id: {qq, group_id, event_type, time, target_name}} ──
_pending = {}

_PENDING_TTL = 30  # 30 秒超时清理


def _read_ban_qqs():
    """读取封禁 QQ 列表"""
    try:
        with open("./UMPs/ban.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return set(data.get("qq", []))
    except Exception:
        return set()


def _read_crystal(qq):
    """读取玩家水晶数量"""
    try:
        path = f"./UMPs/PlayerData/{qq}.json"
        if not os.path.exists(path):
            return 0
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("crystal", 0)
    except Exception:
        return 0


def _cleanup_expired(now=None):
    if now is None:
        now = time.time()
    expired = [k for k, v in _pending.items() if now - v.get("time", 0) > _PENDING_TTL]
    for k in expired:
        del _pending[k]


def _qq_to_id(qq):
    """QQ → 游戏 ID"""
    r = _id_query({"type": "qq", "target_type": "id", "content": qq})
    return r.get("content") if r.get("result") else None


def _id_to_qq(game_id):
    """游戏 ID → QQ"""
    r = _id_query({"type": "id", "target_type": "qq", "content": game_id})
    try:
        return int(r["content"]) if r.get("result") else None
    except (ValueError, TypeError):
        return None


def _reply(mail, event_type, qq, group_id, text):
    """构造 napcat 回复，适配群聊/私聊/临时会话"""
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "napcat"
    payload = {"text": text}
    if event_type == "message.private":
        payload["action"], payload["target"] = "send_private_msg", qq
    elif event_type == "message.group":
        payload["action"], payload["target"] = "send_group_msg", group_id
    else:
        payload["action"], payload["target"] = "send_msg", qq
        payload["group_id"] = group_id
    m["umps_mail"] = payload
    return m


def _reply_text(player_id, qq, online, money, crystal):
    """拼装个人信息卡片"""
    lines = [
        "玩家ID：" + str(player_id or "未知"),
        "QQ：" + str(qq or "未知"),
    ]

    if online:
        lines.append("在线时间：" + online.get("total_formatted", "0s"))
    else:
        lines.append("在线时间：暂无")

    if money is not None:
        if isinstance(money, dict):
            lines.append("金币：" + money.get("formatted", str(money.get("balance", 0))))
        else:
            lines.append("金币：" + str(money))
    else:
        lines.append("金币：暂无")

    lines.append("水晶：" + str(crystal) if crystal is not None else "水晶：暂无")
    return "\n".join(lines)


# ── 主入口 ───────────────────────────────────────────────────────

def player_info(mail):
    _cleanup_expired()

    nm = mail.get("napcat_mail") or {}
    mm = mail.get("minecraft_mail") or {}

    # ====== 入口 A：napcat 查询指令 ======
    if mail.get("mailer") == "napcat":
        event_type = nm.get("event_type", "")
        group_id = nm.get("group_id") or 0
        msg = (nm.get("message") or "").strip()
        qq = nm["sender_qq"]

        # ── 查自己 ──
        if msg in ("看我的", "我的信息", "查询"):
            if qq in _read_ban_qqs():
                return _reply(mail, event_type, qq, group_id,
                    f"[查询失败]\n你已被服务器封禁，无法查询")

            game_id = _qq_to_id(qq)
            if not game_id:
                return _reply(mail, event_type, qq, group_id,
                    "[查询失败]\n你没有绑定游戏账号")

            _pending[game_id.lower()] = {
                "qq": qq, "group_id": group_id, "event_type": event_type, "time": time.time(),
            }
            m = dict(mail)
            m["mailer"], m["Recipient"] = "umps", "minecraft"
            m["umps_mail"] = {"post_type": "get_player_info", "player": game_id}
            return m

        # ── 查询 xxx ──
        m = re.match(r"^查询\s+(.+)$", msg)
        if m:
            target = m.group(1).strip()
            if not target or len(target) > 64:
                return _reply(mail, event_type, qq, group_id,
                    "[查询失败]\n请输入有效的QQ号或游戏ID")

            game_id = None
            target_qq = None
            target_banned = False

            if target.isdigit():
                target_qq = int(target)
                if target_qq in _read_ban_qqs():
                    target_banned = True
                else:
                    game_id = _qq_to_id(target)
            if not game_id and not target_banned:
                game_id = target
                target_qq = _id_to_qq(target)
                if target_qq and target_qq in _read_ban_qqs():
                    target_banned = True

            if target_banned:
                return _reply(mail, event_type, qq, group_id,
                    "[查询失败]\n该玩家已被服务器封禁")

            if not game_id:
                return _reply(mail, event_type, qq, group_id,
                    f"[查询失败]\n未找到玩家 {target}（可能未注册或输入有误）")

            _pending[game_id.lower()] = {
                "qq": target_qq or qq,
                "group_id": group_id,
                "event_type": event_type,
                "time": time.time(),
                "target_name": target,
            }
            m = dict(mail)
            m["mailer"], m["Recipient"] = "umps", "minecraft"
            m["umps_mail"] = {"post_type": "get_player_info", "player": game_id}
            return m

        return None

    # ====== 入口 B：minecraft 查询结果 ======
    if mail.get("mailer") == "minecraft":
        post_type = mm.get("post_type", "")
        if post_type != "player_info_result":
            return None

        player = (mm.get("player") or "").lower()
        ctx = _pending.pop(player, None)
        if not ctx:
            return None  # 无人等待该玩家结果

        # MCDR 返回失败
        if not mm.get("success"):
            text = f"[查询失败]\n查询 {mm.get('player', '玩家')} 时出错"
        else:
            crystal = _read_crystal(ctx["qq"])
            text = _reply_text(
                player_id=mm.get("player"),
                qq=ctx["qq"],
                online=mm.get("online_time"),
                money={"balance": mm.get("money"), "formatted": mm.get("money_formatted")}
                if mm.get("money") is not None else None,
                crystal=crystal,
            )

        return _reply(mail, ctx.get("event_type", "message.group"), ctx["qq"], ctx["group_id"], text)

    return None
