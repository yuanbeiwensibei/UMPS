import yaml



'''
这个工具用于检测littleskinUID，qq有没有被注册过了

函数要接收的数据
{
'content': '',
'type': ''
}
其中type指的是content中的参数类型，包括
qq--QQ号
littleskinUID-皮肤站id



函数会返回以下内容
{
'result': Bool
}

其中如果result的结果为false，那么意味着没有被注册过

'''



def register(ask):
    with open('./UMPs/register_list.yml', 'r', encoding='utf-8') as f:
        registerr = yaml.safe_load(f)


    if ask['type'] == 'qq':
        if ask['content'] in registerr['qq']:
            return True
        else:
            return False

    if ask['type'] == 'littleskinUID':
        if str(ask['content']) in map(str, registerr['littleskin_uuid']):
            return True
        else:
            return False















