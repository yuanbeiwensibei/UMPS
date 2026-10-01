"""
称号管理 — 接收 web 请求，操作玩家数据 + 发送 MCDR 命令
"""
import json
import os
import re

from mail_tool import _file_lock, log


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with _file_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _next_title_id():
    path = "./UMPs/title_next_id.txt"
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("1\n")
    with _file_lock:
        with open(path, "r") as f:
            n = int(f.read().strip() or "0")
        with open(path, "w") as f:
            f.write(f"{n + 1}\n")
    return n


def _mcmd(mail, cmd):
    """构造 MCDR 执行命令邮件"""
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "minecraft"
    m["umps_mail"] = {
        "post_type": "execute_command",
        "request_id": "title_cmd",
        "command": cmd,
    }
    return m


def _player_name(qq):
    """从 binding.yml 查玩家名"""
    import yaml
    try:
        with open("./UMPs/binding.yml", "r", encoding="utf-8") as f:
            b = yaml.safe_load(f) or {}
        for name, bound in (b.get("id-qq") or {}).items():
            if str(bound) == str(qq):
                return name
    except Exception:
        pass
    return f"qq_{qq}"


def title_handler(mail):
    """称号处理入口"""
    wm = mail.get("web_mail") or {}
    ptype = wm.get("post_type", "")

    if ptype == "title_add":
        qq = wm.get("qq")
        title_text = wm.get("title_text", "").strip()
        buffs = wm.get("buffs", [])
        particles = wm.get("particles", [])
        effects = wm.get("effects", [])

        if not title_text:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "称号不能为空"}
            return mail

        if len(buffs) > 3:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "Buff 最多绑定 3 个"}
            return mail

        if not mail.get("minecraft_online"):
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "服务器离线，请稍后重试"}
            return mail

        pd = _read_json(f"./UMPs/PlayerData/{qq}.json")
        if not pd:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "玩家数据不存在"}
            return mail

        tid = _next_title_id()
        new_title = {
            "id": tid,
            "text": title_text,
            "buffs": buffs,
            "particles": particles,
            "effects": effects,
        }
        pd.setdefault("owned_titles", {})[str(tid)] = new_title
        _write_json(f"./UMPs/PlayerData/{qq}.json", pd)

        pname = _player_name(qq)
        results = []
        results.append({
            "mailer": "umps", "Recipient": "web",
            "umps_mail": {"ok": True, "title_id": tid},
            "web_mail": {}, "ai_mail": {}, "minecraft_mail": {}, "napcat_mail": {},
            "need": False, "minecraft_online": True, "mail_id": mail.get("mail_id", ""),
        })
        results.append(_mcmd(mail, f"/lpv user {pname} meta set display-name {title_text}"))
        return results

    if ptype == "title_del":
        qq = wm.get("qq")
        tid = wm.get("title_id")

        pd = _read_json(f"./UMPs/PlayerData/{qq}.json")
        if not pd:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "玩家数据不存在"}
            return mail

        titles = pd.get("owned_titles", {})
        tid_str = str(tid)
        if tid_str in titles:
            del titles[tid_str]

        if str(pd.get("current_title")) == tid_str:
            pd["current_title"] = None

        _write_json(f"./UMPs/PlayerData/{qq}.json", pd)

        mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": True}
        return mail

    if ptype == "title_use":
        qq = wm.get("qq")
        tid = wm.get("title_id")

        pd = _read_json(f"./UMPs/PlayerData/{qq}.json")
        if not pd:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "玩家数据不存在"}
            return mail

        found = pd.get("owned_titles", {}).get(tid_str)
        if not found:
            mail["mailer"], mail["Recipient"], mail["umps_mail"] = "umps", "web", {"ok": False, "reason": "没有这个称号"}
            return mail

        pd["current_title"] = tid
        _write_json(f"./UMPs/PlayerData/{qq}.json", pd)

        pname = _player_name(qq)
        results = [{
            "mailer": "umps", "Recipient": "web",
            "umps_mail": {"ok": True},
            "web_mail": {}, "ai_mail": {}, "minecraft_mail": {}, "napcat_mail": {},
            "need": False, "minecraft_online": True, "mail_id": mail.get("mail_id", ""),
        }]
        results.append(_mcmd(mail, f"/lpv user {pname} meta set display-name {found['text']}"))
        return results

    return None
