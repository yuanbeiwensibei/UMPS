'''
UMPs总文件夹
----register_list.yml  注册文件,已经注册过的QQ号和littleskinUID
----binding.yml uuid-qq的绑定查询文件
----ban.yml 封禁用户littleskinUID,QQ
----config.yml 设置文件
----PlayerData  玩家数据文件夹
--------[QQ].json  玩家数据
----review.yml  审核文件-被移出
----Review_failed.yml  审核失败记录-被移出
----Unexecuted_instructions.yml  未执行指令
----afdian.yml  爱发电记录
----Review  审核相关文件夹
'''


def File_Check():
    import os
    import yaml
    import json

    # 配置文件初始数据（空结构）
    data = {
        "管理员列表": [],
        "审核群": [],
        "游戏群": []
    }

    # ── 目录不存在时，一次性建好 ──────────────────────────
    if os.path.exists("./UMPs"):
        pass
    else:
        os.makedirs('./UMPs', exist_ok=True)

        with open('./UMPs/register_list.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"littleskin_uuid": [], "qq": []}, f, default_flow_style=False, allow_unicode=True)
        with open('./UMPs/binding.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"uuid-qq": {}, "qq-uuid": {}, "littleskinUID-qq": {}, "littleskinUID-id": {}, "id-qq": {}}, f, default_flow_style=False, allow_unicode=True)
        with open('./UMPs/ban.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"littleskin_uuid": [], "qq": []}, f, default_flow_style=False, allow_unicode=True)
        with open('./UMPs/config.yml', 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        """
        with open('./UMPs/review.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)
        with open('./UMPs/Review_failed.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)
        """
        with open('./UMPs/Unexecuted_instructions.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)
        with open('./UMPs/afdian.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"out_trade_no": [], "sku": {}, "count": {}, "vip_player": []}, f, default_flow_style=False, allow_unicode=True)

        os.makedirs('./UMPs/PlayerData', exist_ok=True)
        os.makedirs('./UMPs/PlayerData/PlayerData', exist_ok=True)
        os.makedirs('./UMPs/PlayerData/ReviewData', exist_ok=True)
        os.makedirs('./UMPs/Review', exist_ok=True)

    # ── 逐个文件检查，缺哪个补哪个 ────────────────────────

    if os.path.exists("./UMPs/register_list.yml"):
        pass
    else:
        with open('./UMPs/register_list.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"littleskin_uuid": [], "qq": []}, f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/binding.yml"):
        pass
    else:
        with open('./UMPs/binding.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"uuid-qq": {}, "qq-uuid": {}, "littleskinUID-qq": {}, "littleskinUID-id": {}, "id-qq": {}}, f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/ban.yml"):
        pass
    else:
        with open('./UMPs/ban.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"littleskin_uuid": [], "qq": []}, f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/config.yml"):
        pass
    else:
        with open('./UMPs/config.yml', 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/review.yml"):
        pass
    else:
        with open('./UMPs/review.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/Review_failed.yml"):
        pass
    else:
        with open('./UMPs/Review_failed.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/Unexecuted_instructions.yml"):
        pass
    else:
        with open('./UMPs/Unexecuted_instructions.yml', 'w', encoding='utf-8') as f:
            yaml.dump([], f, default_flow_style=False, allow_unicode=True)

    if os.path.exists("./UMPs/afdian.yml"):
        pass
    else:
        with open('./UMPs/afdian.yml', 'w', encoding='utf-8') as f:
            yaml.dump({"out_trade_no": [], "sku": {}, "count": {}, "vip_player": []}, f, default_flow_style=False, allow_unicode=True)

    # ── 目录检查 ──────────────────────────────────────────

    if os.path.exists("./UMPs/PlayerData"):
        pass
    else:
        os.makedirs('./UMPs/PlayerData', exist_ok=True)

    if os.path.exists("./UMPs/Review"):
        pass
    else:
        os.makedirs('./UMPs/Review', exist_ok=True)