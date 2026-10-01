"""
进群审核工具 (Entry Gate Review) — 自动审批加群请求
"""
from mail_tool.vice_tool.config import config
import yaml


def E_G_R(mail):
    """处理加群请求：自动审批或拒绝"""

    if mail.get("mailer") != "napcat" or mail.get("napcat_mail", {}).get("event_type") != "request.group_add":
        return None

    nm = mail["napcat_mail"]
    group_id = nm["group_id"]
    sender_qq = nm["sender_qq"]
    flag = nm["flag"]

    with open("./UMPs/ban.yml", "r", encoding="utf-8") as f:
        ban_qq = (yaml.safe_load(f) or {}).get("qq", [])
    with open("./UMPs/review.yml", "r", encoding="utf-8") as f:
        review_qq = yaml.safe_load(f) or []

    review_group = config("审核群")
    game_groups = config("游戏群")
    admin_group = config("管理员群")

    # ── 审核群 ──
    if group_id == review_group:
        if sender_qq in ban_qq:
            return _make_results(mail, [
                {"action": "set_group_add_request", "flag": flag, "sub_type": "add", "approve": False,
                 "reason": "你已被服务器封禁"},
                {"action": "send_group_msg", "target": group_id,
                 "text": f"[处理结果]\n拒绝了来自{sender_qq}的加群申请\n理由：被封禁的玩家不能加入"},
            ], admin_text=f"[加群审批] 审核群\n拒绝了 {sender_qq}\n理由：被封禁的玩家")
        else:
            return _make_result(mail, {
                "action": "set_group_add_request", "flag": flag, "sub_type": "add", "approve": True,
            })

    # ── 游戏群 ──
    if group_id in game_groups:
        if sender_qq in ban_qq:
            return _make_results(mail, [
                {"action": "set_group_add_request", "flag": flag, "sub_type": "add", "approve": False,
                 "reason": "你已被服务器封禁"},
                {"action": "send_group_msg", "target": group_id,
                 "text": f"[处理结果]\n拒绝了来自{sender_qq}的加群申请\n理由：被封禁的玩家不能加入"},
            ], admin_text=f"[加群审批] 游戏群\n拒绝了 {sender_qq}\n理由：被封禁的玩家")

        if sender_qq not in review_qq:
            return _make_results(mail, [
                {"action": "set_group_add_request", "flag": flag, "sub_type": "add", "approve": False,
                 "reason": "你没有通过审核或者正在被审核，审核期间无法加入群聊"},
                {"action": "send_group_msg", "target": group_id,
                 "text": f"[处理结果]\n拒绝了来自{sender_qq}的加群申请\n理由：没有通过审核或者正在被审核"},
            ], admin_text=f"[加群审批] 游戏群\n拒绝了 {sender_qq}\n理由：未通过审核")

        # 通过审核 → 放行
        return _make_result(mail, {
            "action": "set_group_add_request", "flag": flag, "sub_type": "add", "approve": True,
        })

    return None


def _make_result(mail, payload):
    """返回单封回信"""
    r = dict(mail)
    r["mailer"], r["Recipient"], r["umps_mail"] = "umps", "napcat", payload
    return r


def _make_results(mail, payloads, admin_text=None):
    """返回多封回信，可选管理员群通知"""
    results = []
    for p in payloads:
        r = dict(mail)
        r["mailer"], r["Recipient"], r["umps_mail"] = "umps", "napcat", p
        results.append(r)
    if admin_text:
        r = dict(mail)
        r["mailer"], r["Recipient"], r["umps_mail"] = "umps", "napcat", {
            "action": "send_group_msg",
            "target": config("管理员群"),
            "text": admin_text,
        }
        results.append(r)
    return results
