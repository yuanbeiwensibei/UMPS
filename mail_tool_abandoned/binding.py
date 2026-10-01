"""
绑定工具 — 玩家通过 B- 绑定码将 QQ 与 Minecraft 角色关联
"""
import base64
import json
import os

import yaml
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from mail_tool import ENCRYPTION_KEY, _file_lock, log


# ── 不同事件类型对应的 napcat action ──────────────────────────
SEND_ACTIONS = {
    "message.group":      ("send_group_msg",    "group"),
    "message.group_temp": ("send_msg",          "temp"),
    "message.private":    ("send_private_msg",  "private"),
}


def _make_mail(original, recipient, payload):
    """构造一封回信：拷贝 original，设置 mailer/Recipient/umps_mail"""
    m = dict(original)
    m["mailer"] = "umps"
    m["Recipient"] = recipient
    m["umps_mail"] = payload
    return m


def _read_yml(path):
    """线程安全读 YAML"""
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def _write_yml(path, data):
    """线程安全写 YAML"""
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _make_reply(mail, event_type, qq, group_id, text):
    """构造 napcat 回复消息"""
    action, _ = SEND_ACTIONS[event_type]
    payload = {"action": action, "text": text}
    if event_type == "message.group":
        payload["target"] = group_id
    elif event_type == "message.group_temp":
        payload["target"] = qq
        payload["group_id"] = group_id
    else:
        payload["target"] = qq
    return _make_mail(mail, "napcat", payload)


def _do_bind(mail, event_type, qq, group_id, data):
    """
    执行绑定流程 — 写 PlayerData、更新 binding.yml、register_list、
    加白名单（在线时发命令，离线时记待执行队列）。
    返回一封或多封回信。
    """
    role_name = data["role_name"]
    lsid = int(data["littleskin_id"])
    uuid = data["role_uuid"]

    # ── 写 PlayerData ──
    player = {
        "qq": qq,
        "mc_uuid": uuid,
        "crystal": 0,
        "Last_check-in_time": "1997-1-1",
        "vip": {"vip_Expiration_time": "", "vip_type": ""},
        "web_data": {"warehouse": {"buffs": {}, "effects": [], "particles": []}},
        "current_title": None,
        "owned_titles": {},
    }
    with _file_lock:
        os.makedirs("./UMPs/PlayerData", exist_ok=True)
        with open(f"./UMPs/PlayerData/{qq}.json", "w", encoding="utf-8") as f:
            json.dump(player, f, ensure_ascii=False, indent=4)

    # ── 更新 binding.yml 映射 ──
    binding = _read_yml("./UMPs/binding.yml")
    binding["id-qq"][role_name] = qq
    binding["littleskinUID-id"][lsid] = role_name
    binding["littleskinUID-qq"][lsid] = qq
    binding["qq-uuid"][qq] = uuid
    binding["uuid-qq"][uuid] = qq
    _write_yml("./UMPs/binding.yml", binding)

    # ── 更新 register_list ──
    rl = _read_yml("./UMPs/register_list.yml")
    if qq not in rl.get("qq", []):
        rl["qq"].append(qq)
    if lsid not in rl.get("littleskin_uuid", []):
        rl["littleskin_uuid"].append(lsid)
    _write_yml("./UMPs/register_list.yml", rl)

    # ── 服务器在线 → 直接加白名单 ──
    if mail.get("minecraft_online") is True:
        ok_msg = _make_reply(mail, event_type, qq, group_id,
            f"[绑定成功]\n现在你可以使用角色{role_name}进入游戏了")
        cmd_msg = _make_mail(mail, "minecraft", {
            "post_type": "execute_command",
            "request_id": "req_001",
            "command": f"/whitelist add {role_name}",
        })
        return [ok_msg, cmd_msg]

    # ── 服务器不在线 → 记录待执行指令 ──
    pending = _read_yml("./UMPs/Unexecuted_instructions.yml")
    pending.append(f"/whitelist add {role_name}")
    _write_yml("./UMPs/Unexecuted_instructions.yml", pending)

    return _make_reply(mail, event_type, qq, group_id,
        f"[绑定成功]\n现在你可以使用角色{role_name}进入游戏了\n服务器将在开启后自动加入白名单")


def _check_registered(lsid):
    """检查 littleskin_id 是否已被注册"""
    rl = _read_yml("./UMPs/register_list.yml")
    return lsid in rl.get("littleskin_uuid", [])


# ── 主入口 ──────────────────────────────────────────────────────

def binding(mail):
    """绑定主函数：收到 B- 绑定码后执行绑定流程"""
    try:
        # 过滤：只处理 napcat 消息
        if mail.get("mailer") != "napcat":
            return None

        event = mail.get("napcat_mail") or {}
        event_type = event.get("event_type", "")
        if event_type not in ("message.group", "message.private", "message.group_temp"):
            return None

        message = event.get("message")
        # ── Crash 1 修复：message 可能为 None（非文字消息） ──
        if message is None or len(message) < 10:
            return None
        if message.startswith("绑定 "):
            message = message[3:].lstrip()
        if not message.startswith("B- "):
            return None

        qq = event["sender_qq"]
        group_id = event.get("group_id", 0)

        # ── 群聊消息 → 引导私聊 ──
        if event_type == "message.group":
            return [
                _make_mail(mail, "napcat", {
                    "action": "delete_msg",
                    "target": event["message_id"],
                }),
                _make_mail(mail, "napcat", {
                    "action": "send_group_msg",
                    "target": group_id,
                    "text": f"[无法绑定]\n[CQ:at,qq={qq}]请将绑定码私聊发送给我",
                }),
            ]

        # ── 这里开始是临时会话/私聊 ──

        # 检查是否已绑定
        if os.path.exists(f"./UMPs/PlayerData/{qq}.json"):
            return _make_reply(mail, event_type, qq, group_id,
                "[绑定失败]\n你已经绑定过了，无法换绑或者绑定其他角色")

        # 解密绑定码
        decrypt_data = Decrypt(message[3:])
        if decrypt_data is False:
            return _make_reply(mail, event_type, qq, group_id,
                "[绑定失败]\n不正确或已被修改的绑定码\n前往utopiasmp.top/binding重新获取")

        # 检查 littleskin 是否已被绑定
        if _check_registered(int(decrypt_data["littleskin_id"])):
            return _make_reply(mail, event_type, qq, group_id,
                f"[绑定失败]\nid为{decrypt_data['littleskin_id']}的littleskin账户已经被绑定过了")

        # 执行绑定
        return _do_bind(mail, event_type, qq, group_id, decrypt_data)

    except Exception as e:
        log.exception(f"binding() 异常 qq={mail.get('napcat_mail', {}).get('sender_qq')}")
        # 尝试发错误消息，不行就算了
        try:
            evt = mail.get("napcat_mail") or {}
            return _make_reply(mail,
                evt.get("event_type", "message.private"),
                evt.get("sender_qq", 0),
                evt.get("group_id", 0),
                "[出错]\n绑定过程出现异常，请联系管理员解决")
        except Exception:
            return None


# ── 解密函数 ────────────────────────────────────────────────────

def Decrypt(binding_code):
    """
    解密绑定凭证。成功返回 dict，失败返回 False。
    """
    try:
        if isinstance(binding_code, str):
            binding_code = binding_code.removeprefix("B- ").removeprefix("B-")
            binding_code = "".join(binding_code.split())

        combined = base64.b64decode(binding_code)
        if len(combined) < 17:
            log.warning("Decrypt: 数据长度不足 %d", len(combined))
            return False

        iv = combined[:16]
        ciphertext = combined[16:]

        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        data = json.loads(plaintext.decode("utf-8"))

        required = ["minecraft_id", "littleskin_id", "role_uuid", "role_name", "timestamp", "nonce"]
        if not all(k in data for k in required):
            log.warning("Decrypt: 缺少必需字段")
            return False

        return data

    except Exception as e:
        log.warning("Decrypt: 解密失败 %s", e)
        return False
