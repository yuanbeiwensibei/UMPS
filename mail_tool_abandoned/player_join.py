"""
玩家进入事件 — 同步 Minecraft 角色名 ↔ QQ 的绑定关系
MC 每次有玩家进入服务器都会发送 player_joined 事件
uuid↔qq 永久锚定不动，只更新角色名映射
"""
import os

from mail_tool import _file_lock, log

import yaml


def _read_yml(path):
    with _file_lock:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def _write_yml(path, data):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def player_join(mail):
    """收到 MC player_joined → 同步 id-qq / littleskinUID-id 映射"""

    if mail.get("mailer") != "minecraft":
        return None

    mc_mail = mail.get("minecraft_mail") or {}
    if mc_mail.get("post_type") != "player_joined":
        return None

    role_name = mc_mail.get("player")
    uuid = mc_mail.get("uuid")

    if not role_name or not uuid:
        return None

    # ── uuid → qq（永久映射，绑定时锚定，绝不修改） ──
    binding = _read_yml("./UMPs/binding.yml")
    qq = binding.get("uuid-qq", {}).get(uuid)

    if not qq:
        return None  # 未绑定的玩家，跳过

    # ── 检查角色名是否变了 ──
    id_qq = binding.setdefault("id-qq", {})
    old_name = None
    for name, bound_qq in list(id_qq.items()):
        if str(bound_qq) == str(qq):
            old_name = name
            break

    if old_name == role_name:
        return None  # 没变，跳过

    # ── 更新 id-qq ──
    if old_name and old_name in id_qq:
        del id_qq[old_name]
    id_qq[role_name] = qq

    # ── 更新 littleskinUID-id ──
    ls_id = binding.setdefault("littleskinUID-id", {})
    for ls_uid, name in list(ls_id.items()):
        if name == old_name:
            ls_id[ls_uid] = role_name
            break

    _write_yml("./UMPs/binding.yml", binding)

    log.info("player_join: 角色名已同步 uuid=%s %s → %s", uuid, old_name, role_name)
    return None
