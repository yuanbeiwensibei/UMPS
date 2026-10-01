"""
签到功能 — 每日签到获得水晶
非 SVIP: 10-15 随机水晶，SVIP: 15-25 随机水晶
"""
import datetime
import json
import os
import random

import yaml

from mail_tool import _file_lock
from mail_tool.vice_tool.config import config as _cfg


def _read_ban_qqs():
    try:
        with open("./UMPs/ban.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return set(data.get("qq", []))
    except Exception:
        return set()


def _read_player(qq):
    path = f"./UMPs/PlayerData/{qq}.json"
    if not os.path.exists(path):
        return None
    try:
        with _file_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None


def _write_player(qq, data):
    import os as _os
    _os.makedirs("./UMPs/PlayerData", exist_ok=True)
    with _file_lock:
        with open(f"./UMPs/PlayerData/{qq}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def _reply(mail, event_type, qq, group_id, text):
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


def checkin(mail):

    if mail.get("mailer") != "napcat":
        return None

    nm = mail.get("napcat_mail") or {}
    msg = (nm.get("message") or "").strip()
    if msg not in ("签到", "打卡"):
        return None
    et = nm.get("event_type", "")
    qq = nm["sender_qq"]
    gid = nm.get("group_id") or 0

    if qq in _read_ban_qqs():
        return _reply(mail, et, qq, gid, "[签到失败]\n你已被服务器封禁，无法签到")

    pd = _read_player(qq)
    if not pd:
        return _reply(mail, et, qq, gid, "[签到失败]\n你还没有绑定游戏账号")

    today = datetime.date.today().isoformat()
    last = pd.get("Last_check-in_time", "")

    if last == today:
        return _reply(mail, et, qq, gid, "[签到失败]\n你今天已经签到过了，明天再来吧")

    r_normal = _cfg("签到", "普通水晶", default=[10, 15])
    r_svip = _cfg("签到", "SVIP水晶", default=[15, 25])
    is_svip = (pd.get("vip", {}).get("vip_type") == "svip")
    amount = random.randint(*r_svip) if is_svip else random.randint(*r_normal)
    pd["crystal"] = pd.get("crystal", 0) + amount
    pd["Last_check-in_time"] = today
    _write_player(qq, pd)

    tag = "[SVIP]" if is_svip else ""
    return _reply(mail, et, qq, gid,
        f"[签到成功] {tag}\n你获得了 {amount} 个水晶\n当前水晶: {pd['crystal']}")
