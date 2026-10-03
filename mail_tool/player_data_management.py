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

    if code == 3 and content != "":
        file_path = os.path.join("./UMPs/PlayerData/ReviewData", f"{content}.txt")
        if os.path.exists(file_path):
            return True
        else:
            return False






