import os
import yaml
import json
"""
用于玩家数据的快捷管理
"""

"""
=====这里是使用说明====

=====
->register_list操作:

查询有无skin_uuid注册
register_list_operate(1,littleskin_uuid)
输出：true->已被注册/false->没有被注册

查询有无qq注册
register_list_operate(2,qq)
输出：Ture->已被注册/false->没有被注册

查询有没有某玩家审核记录
register_list_operate(3,qq)
输出：Ture->已审核/false->未审核

适用于新玩家的审核文件写入
register_list_operate(4,review_data)
输出：Ture->成功/false->失败
review_data = {
        "passed": passed,
        "reason": reason,
        "score_m": score_m,
        "score_q": score_q,
        "qq": qq
    }
    
添加新的人工审核名单
register_list_operate(5,qq)
输出：Ture->成功/false->出错

=====
"""



def register_list_operate(code,content):
    #查询有无skin_uuid注册
    if code == 1 and content != "":
        with open("./UMPs/register_list.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if content in data["littleskin_uuid"]:
                return True
            else:
                return False
    # 查询有无qq注册
    if code == 2 and content != "":
        with open("./UMPs/register_list.yml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if content in data["qq"]:
                return True
            else:
                return False
    #查询有没有审核记录
    if code == 3 and content != "":
        file_path = os.path.join("./UMPs/PlayerData/ReviewData", f"{content}.json")
        if os.path.exists(file_path):
            return True
        else:
            return False

    #向审核文件写入数据
    if code == 4 and content != "":
        qq = content["qq"]
        try:
            with open(f"./UMPs/PlayerData/ReviewData/{qq}.json", "r", encoding="utf-8") as f:
                loaded = json.load(f)
                loaded["passed"] = content["passed"]
                loaded["reason"] = content["reason"]
                loaded["score_m"] = content["score_m"]
                loaded["score_q"] = content["score_q"]
            with open(f"./UMPs/PlayerData/ReviewData/{qq}.json", "w", encoding="utf-8") as f:
                json.dump(loaded, f, ensure_ascii=False, indent=4)
        except:
            return False
        return True

    #添加人工审核QQ
    if code == 5 and content != "":
        qq = content
        try:
            with open("./UMPs/manually_review.yml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            data.append(qq)
            with open('./UMPs/manually_review.yml', 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except:
            return False
        return True










