"""
统一 Web 数据服务 — web.py 所有文件读取操作经此发往 umps
"""
import json
import os

import yaml

from mail_tool import _file_lock


def _player_name(qq):
    """从 binding.yml 查玩家名"""
    try:
        with _file_lock:
            with open("./UMPs/binding.yml", "r", encoding="utf-8") as f:
                b = yaml.safe_load(f) or {}
        for name, bound in (b.get("id-qq") or {}).items():
            if str(bound) == str(qq):
                return name
    except Exception:
        pass
    return ""


def _fix_player_data(player):
    """兼容旧字段：buff→buffs, Particle→particles"""
    wd = player.setdefault("web_data", {})
    wd.setdefault("buffs", wd.pop("buff", []))
    wd.setdefault("particles", wd.pop("Particle", []))
    wd.setdefault("effects", [])
    player.setdefault("current_title", None)
    player.setdefault("owned_titles", {})


def _reply(mail, data):
    """构造回信"""
    m = dict(mail)
    m["mailer"], m["Recipient"] = "umps", "web"
    m["umps_mail"] = data
    return m


def player_web(mail):
    """统一入口"""
    if mail.get("mailer") != "web":
        return None
    wm = mail.get("web_mail") or {}
    ptype = wm.get("post_type", "")

    qq = wm.get("qq")
    lid = wm.get("littleskin_id")

    # ── 启动数据 ──
    if ptype == "player_boot" and qq:
        player = {}
        path = f"./UMPs/PlayerData/{qq}.json"
        if os.path.exists(path):
            with _file_lock:
                with open(path, "r", encoding="utf-8") as f:
                    player = json.load(f)
        _fix_player_data(player)

        registry = {}
        if os.path.exists("./static/data/registry.json"):
            with _file_lock:
                with open("./static/data/registry.json", "r", encoding="utf-8") as f:
                    registry = json.load(f)

        return _reply(mail, {
            "player": player,
            "registry": registry,
            "player_name": _player_name(qq),
        })

    # ── 玩家信息 ──
    if ptype == "player_me" and qq:
        data = {"qq": qq, "crystal": 0, "web_data": {}, "vip": {}}
        path = f"./UMPs/PlayerData/{qq}.json"
        if os.path.exists(path):
            with _file_lock:
                with open(path, "r", encoding="utf-8") as f:
                    data.update(json.load(f))
        _fix_player_data(data)
        data["player_name"] = _player_name(qq)
        return _reply(mail, data)

    # ── 称号列表 ──
    if ptype == "player_title_list" and qq:
        path = f"./UMPs/PlayerData/{qq}.json"
        titles = {}
        current = None
        if os.path.exists(path):
            with _file_lock:
                with open(path, "r", encoding="utf-8") as f:
                    pd = json.load(f)
            titles = pd.get("owned_titles", {})
            current = pd.get("current_title")
        return _reply(mail, {"ok": True, "titles": titles, "current": current})

    # ── 玩家验证（LittleSkin→QQ） ──
    if ptype == "verify_player" and lid:
        qq_val = None
        try:
            with _file_lock:
                with open("./UMPs/binding.yml", "r", encoding="utf-8") as f:
                    b = yaml.safe_load(f) or {}
            qq_val = (b.get("littleskinUID-qq") or {}).get(int(lid))
        except Exception:
            pass
        return _reply(mail, {"qq": int(qq_val) if qq_val else None})

    # ── 管理员验证（LittleSkin→QQ→查管理员列表） ──
    if ptype == "verify_admin" and lid:
        qq_val = None
        is_admin = False
        try:
            with _file_lock:
                with open("./UMPs/binding.yml", "r", encoding="utf-8") as f:
                    b = yaml.safe_load(f) or {}
            qq_val = (b.get("littleskinUID-qq") or {}).get(int(lid))
            if qq_val:
                with _file_lock:
                    with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                is_admin = int(qq_val) in cfg.get("管理员列表", [])
        except Exception:
            pass
        return _reply(mail, {"qq": int(qq_val) if qq_val else None, "is_admin": is_admin})

    # ── 管理面板统计 ──
    if ptype == "admin_dashboard":
        reviewed, failed = [], []
        try:
            with _file_lock:
                with open("./UMPs/review.yml", "r", encoding="utf-8") as f:
                    reviewed = yaml.safe_load(f) or []
                with open("./UMPs/Review_failed.yml", "r", encoding="utf-8") as f:
                    failed = yaml.safe_load(f) or []
        except Exception:
            pass
        cheat_count = 0
        try:
            if os.path.exists("./UMPs/CheatRecords"):
                cheat_count = len([f for f in os.listdir("./UMPs/CheatRecords") if f.endswith('.json')])
        except Exception:
            pass
        pending = 0
        try:
            with _file_lock:
                with open("./UMPs/afdian.yml", "r", encoding="utf-8") as f:
                    afd = yaml.safe_load(f) or {}
            pending = len(afd.get("out_trade_no", []))
        except Exception:
            pass
        return _reply(mail, {
            "reviewed_count": len(reviewed), "failed_count": len(failed),
            "cheat_count": cheat_count, "pending_orders": pending,
        })

    # ── 审核记录列表 ──
    if ptype == "admin_reviews_list":
        reviewed, failed = [], []
        try:
            with _file_lock:
                with open("./UMPs/review.yml", "r", encoding="utf-8") as f:
                    reviewed = yaml.safe_load(f) or []
                with open("./UMPs/Review_failed.yml", "r", encoding="utf-8") as f:
                    failed = yaml.safe_load(f) or []
        except Exception:
            pass
        players = []
        for q in reviewed + failed:
            info = {"qq": q, "status": "通过" if q in reviewed else "未通过"}
            rpath = f"./UMPs/Review/{q}.json"
            if os.path.exists(rpath):
                with _file_lock:
                    with open(rpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                info["score"] = f"{data.get('Multiple_choice_question_score',0)}+{data.get('Question_and_answer_score',0)}"
                info["reason"] = data.get("reason", "")
                info["review"] = data.get("review", False)
            players.append(info)
        return _reply(mail, {"players": players})

    # ── 审核详情 ──
    if ptype == "admin_review_detail" and qq:
        rpath = f"./UMPs/Review/{qq}.json"
        if not os.path.exists(rpath):
            return _reply(mail, {"error": "not_found"})
        with _file_lock:
            with open(rpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        return _reply(mail, {"qq": qq, "data": data})

    # ── 违规列表 ──
    if ptype == "admin_cheat_list":
        cheat_dir = "./UMPs/CheatRecords"
        players = []
        if os.path.exists(cheat_dir):
            for fname in os.listdir(cheat_dir):
                if fname.endswith('.json'):
                    with _file_lock:
                        with open(f"{cheat_dir}/{fname}", "r", encoding="utf-8") as f:
                            rec = json.load(f)
                    players.append({
                        "qq": rec.get("qq", fname[:-5]),
                        "player": rec.get("player", "?"),
                        "total_points": rec.get("total_points", 0),
                        "banned": rec.get("banned", False),
                        "record_count": len(rec.get("records", [])),
                    })
        try:
            with _file_lock:
                with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            threshold = (cfg.get("反作弊", {}) or {}).get("违规分阈值", 5)
        except Exception:
            threshold = 5
        return _reply(mail, {"players": players, "threshold": threshold})

    # ── 违规详情 ──
    if ptype == "admin_cheat_detail" and qq:
        cpath = f"./UMPs/CheatRecords/{qq}.json"
        if not os.path.exists(cpath):
            return _reply(mail, {"error": "not_found"})
        with _file_lock:
            with open(cpath, "r", encoding="utf-8") as f:
                rec = json.load(f)
        try:
            with _file_lock:
                with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
            threshold = (cfg.get("反作弊", {}) or {}).get("违规分阈值", 5)
        except Exception:
            threshold = 5
        return _reply(mail, {"qq": qq, "record": rec, "threshold": threshold})

    # ── 赞助订单列表 ──
    if ptype == "admin_sponsor_list":
        try:
            with _file_lock:
                with open("./UMPs/afdian.yml", "r", encoding="utf-8") as f:
                    afd = yaml.safe_load(f) or {}
            orders = [{"id": oid, "sku": afd.get("sku", {}).get(oid, "?"), "count": afd.get("count", {}).get(oid, 1)}
                      for oid in afd.get("out_trade_no", [])]
        except Exception:
            orders = []
        return _reply(mail, {"orders": orders})

    # ── 配置读取 ──
    if ptype == "admin_config_read":
        try:
            with _file_lock:
                with open("./UMPs/config.yml", "r", encoding="utf-8") as f:
                    content = f.read()
        except Exception:
            content = ""
        return _reply(mail, {"content": content})

    # ── 配置写入 ──
    if ptype == "admin_config_write":
        content = wm.get("content", "")
        try:
            yaml.safe_load(content)
            with _file_lock:
                with open("./UMPs/config.yml", "w", encoding="utf-8") as f:
                    f.write(content)
            return _reply(mail, {"ok": True})
        except Exception as e:
            return _reply(mail, {"ok": False, "error": f"格式错误: {e}"})

    return None
