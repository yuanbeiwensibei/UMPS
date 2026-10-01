"""
UMPs 文件结构初始化 — 确保目录和初始 YAML/JSON 齐全
"""
import json
import os
import yaml


# ── 各文件的初始默认值 ──────────────────────────────────────
FILES = {
    "register_list.yml": {"littleskin_uuid": [], "qq": []},
    "review.yml": [],
    "binding.yml": {"uuid-qq": {}, "qq-uuid": {}, "littleskinUID-qq": {}, "littleskinUID-id": {}, "id-qq": {}},
    "ban.yml": {"littleskin_uuid": [], "qq": []},
    "config.yml": {
        "审核群": 594051605,
        "游戏群": [1036440930],
        "管理员群": 920415939,
        "管理员列表": [1772578581],
        "签到": {
            "普通水晶": [10, 15],
            "SVIP水晶": [15, 25],
        },
        "兑换": {
            "每份水晶数": 50,
            "VIP有效期": 30,
        },
        "审核": {
            "选择题及格分": 6,
            "问答题及格分": 10,
        },
        "反作弊": {
            "违规分阈值": 5,
            "免罚窗口小时": 1,
        },
    },
    "Review_failed.yml": [],
    "Unexecuted_instructions.yml": [],
    "afdian.yml": {"out_trade_no": [], "sku": {}, "count": {}, "vip_player": []},
}

DIRS = ["PlayerData", "Review"]


def File_Check():
    os.makedirs("./UMPs", exist_ok=True)

    for name, default in FILES.items():
        path = f"./UMPs/{name}"
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                if name.endswith('.json'):
                    json.dump(default, f, ensure_ascii=False, indent=2)
                else:
                    yaml.dump(default, f, default_flow_style=False, allow_unicode=True)

    for d in DIRS:
        os.makedirs(f"./UMPs/{d}", exist_ok=True)

    # ⚠ 称号 ID 计数器
    if not os.path.exists("./UMPs/title_next_id.txt"):
        with open("./UMPs/title_next_id.txt", "w") as f:
            f.write("1\n")
