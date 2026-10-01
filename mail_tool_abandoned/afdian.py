"""
爱发电订单处理 — 接收 webhook 记录订单到 afdian.yml
"""
import yaml

from mail_tool import _file_lock, log


SKU_MAP = {
    "8c88c58460ca11f183225254001e7c00": "crystal",
    "ae102dca60b911f1955252540025c377": "vip",
    "0e227f6e60ca11f1b47c52540025c377": "svip"
}


def afdian(mail):
    """记录爱发电订单到 YAML"""

    if mail.get("mailer") != "web":
        return None
    if mail.get("web_mail", {}).get("post_type") != "afdian_order":
        return None

    try:
        order = mail["web_mail"]["content"]["data"]["order"]
        out_trade_no = order["out_trade_no"]
        status = order["status"]
        name = order["sku_detail"][0]["name"]
        count = order["sku_detail"][0]["count"]
    except Exception as e:
        log.warning("afdian: 解析订单数据失败 %s", e)
        return None

    if status != 2:
        return None

    if name == "50水晶":
        sku_name = "crystal"
    elif name == "VIP":
        sku_name = "vip"
    elif name == "SVIP":
        sku_name = "svip"
    else:
        sku_name = None

    with _file_lock:
        with open("./UMPs/afdian.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

    data["out_trade_no"].append(out_trade_no)
    data["sku"][out_trade_no] = sku_name
    data["count"][out_trade_no] = count

    with _file_lock:
        with open("./UMPs/afdian.yml", "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    log.info("afdian: 订单已记录 %s sku=%s count=%s", out_trade_no, sku_name, count)
    return None
