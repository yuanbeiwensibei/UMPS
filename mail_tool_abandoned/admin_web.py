"""
Web 管理员操作处理器 — 接收来自 /admin 网页的请求
"""
from mail_tool.vice_tool.config import config as _cfg
from mail_tool import _file_lock


def admin_web(mail):
    if mail.get("mailer") != "web":
        return None

    wm = mail.get("web_mail") or {}
    ptype = wm.get("post_type", "")

    if ptype == "admin_redeem":
        import yaml
        order_id = wm.get("order_id", "")
        target_qq = wm.get("qq", 0)

        # 读订单
        with _file_lock:
            with open("./UMPs/afdian.yml", "r", encoding="utf-8") as f:
                afd = yaml.safe_load(f) or {}

        if order_id not in afd.get("out_trade_no", []):
            return None

        sku_type = afd.get("sku", {}).get(order_id, "")
        count = afd.get("count", {}).get(order_id, 1)

        # 写入水晶 — VIP/SVIP 需完整 exchange 逻辑，web 侧暂只支持水晶
        if sku_type == "crystal":
            import os as _os, json as _json
            CRYSTAL = _cfg("兑换", "每份水晶数", default=50)
            path = f"./UMPs/PlayerData/{target_qq}.json"
            if not _os.path.exists(path):
                return None
            with _file_lock:
                with open(path, "r", encoding="utf-8") as f:
                    pd = _json.load(f)
            pd["crystal"] = pd.get("crystal", 0) + CRYSTAL * count
            with _file_lock:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(pd, f, ensure_ascii=False, indent=4)

        # 标记使用
        afd["out_trade_no"].remove(order_id)
        with _file_lock:
            with open("./UMPs/afdian.yml", "w", encoding="utf-8") as f:
                yaml.dump(afd, f, default_flow_style=False, allow_unicode=True)

        return None

    return None
