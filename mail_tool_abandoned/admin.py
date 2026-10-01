"""
管理员配置工具 — "管理员 添加/删除 <QQ号>" → 修改 config.yml 管理员列表
"""
import re

from mail_tool import _file_lock
from mail_tool.vice_tool.config import config as _cfg


def _read_config():
    import yaml
    try:
        with _file_lock:
            with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _write_config(data):
    import yaml
    try:
        with _file_lock:
            with open("./UMPs/config.yml", "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception:
        return False


def _reply(mail, event_type, qq, group_id, text):
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "napcat"
    payload = {"text": text}
    if event_type == "message.group":
        payload["action"], payload["target"] = "send_group_msg", group_id
    elif event_type == "message.private":
        payload["action"], payload["target"] = "send_private_msg", qq
    else:
        payload["action"], payload["target"] = "send_msg", qq
        payload["group_id"] = group_id
    m["umps_mail"] = payload
    return m


def admin(mail):
    """管理员命令入口"""

    if mail.get("mailer") != "napcat":
        return None

    nm = mail.get("napcat_mail") or {}
    msg = (nm.get("message") or "").strip()
    et = nm.get("event_type", "")
    qq = nm["sender_qq"]
    group_id = nm.get("group_id") or 0

    m = re.match(r"^管理员\s+(添加|删除)\s+(\d+)$", msg)
    if m:
        return _handle_admin_add_del(mail, et, qq, group_id, m.group(1), int(m.group(2)))

    return None


def _check_admin(qq, cfg, *, allow_empty=False):
    """allow_empty=True 时列表为空也允许（仅用于首次添加管理员）"""
    admins = cfg.get("管理员列表", [])
    if allow_empty and not admins:
        return True
    if admins and qq not in admins:
        return False
    return True


def _handle_admin_add_del(mail, et, qq, group_id, action, target):
    if target < 10000:
        return _reply(mail, et, qq, group_id, f"[管理员]\n{target} 不是有效的QQ号")

    try:
        cfg = _read_config()
    except Exception:
        return _reply(mail, et, qq, group_id, "[管理员]\n读取配置文件失败")

    if not _check_admin(qq, cfg, allow_empty=(action == "添加")):
        return _reply(mail, et, qq, group_id, "[管理员]\n你没有管理员权限")

    admins = cfg.get("管理员列表", [])

    if action == "添加":
        if target in admins:
            return _reply(mail, et, qq, group_id, f"[管理员]\n{target} 已经是管理员了")
        admins.append(target)
        if not _write_config(cfg):
            return _reply(mail, et, qq, group_id, "[管理员]\n写入配置文件失败")
        return _reply(mail, et, qq, group_id, f"[管理员]\n已添加管理员: {target}")

    if action == "删除":
        if target not in admins:
            return _reply(mail, et, qq, group_id, f"[管理员]\n{target} 不是管理员，无需删除")
        if target == qq and len(admins) == 1:
            return _reply(mail, et, qq, group_id, "[管理员]\n不能删除最后一个管理员")
        admins.remove(target)
        if not _write_config(cfg):
            return _reply(mail, et, qq, group_id, "[管理员]\n写入配置文件失败")
        return _reply(mail, et, qq, group_id, f"[管理员]\n已移除管理员: {target}")

    return None


