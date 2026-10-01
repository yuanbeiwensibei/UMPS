import yaml

'''
这个工具是用来查询对应绑定关系的

函数要接收的数据
{
‘type’: '',
'content': '',
'target_type': ''
}
其中type指的是content中的参数类型，包括
qq--QQ号
littleskinUID-皮肤站id
id-mcid
uuid-mcuuid

其中target_type是需要获得的类型
也包括上面四类

函数
会返回以下内容
{
'result': Bool
'content': ''
}

其中如果result的结果为false，那么意味没有找到对象
content为目标内容


'''





def query(ask):
    with open('./UMPs/binding.yml', 'r', encoding='utf-8') as f:
        binding = yaml.safe_load(f) or {}


    '''
    id -> qq
    '''
    if ask['type'] == 'id' and ask['target_type'] == 'qq':
        if (binding.get('id-qq') or {}).get(ask['content']) is not None:
            return {'result': True, 'content': binding['id-qq'][ask['content']]}
        else:
            return {'result': False, 'content': None}


    '''
    qq -> id
    '''
    if ask['type'] == 'qq' and ask['target_type'] == 'id':
        qq = ask['content']
        # qq → role_name：反向查 id-qq（兼容 str/int）
        for name, bound in (binding.get('id-qq') or {}).items():
            if str(bound) == str(qq):
                return {'result': True, 'content': name}
        return {'result': False, 'content': None}


    '''
    littleskinUID -> qq
    '''
    if ask['type'] == 'littleskinUID' and ask['target_type'] == 'qq':
        if (binding.get('littleskinUID-qq') or {}).get(str(ask['content'])) is not None:
            return {'result': True, 'content': binding['littleskinUID-qq'][str(ask['content'])]}
        else:
            return {'result': False, 'content': None}





