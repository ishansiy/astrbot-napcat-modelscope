"""Idempotent first-run provisioning. Never overwrite existing user settings."""
import asyncio, copy, hashlib, json, os, secrets, shutil, sys
from pathlib import Path
sys.path.insert(0,'/AstrBot')

def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.chmod(0o600)
    tmp.replace(path)

def link_directory(link, target):
    target.mkdir(parents=True,exist_ok=True)
    if link.is_symlink():
        if link.resolve()!=target.resolve():
            raise RuntimeError(f'Refusing to redirect existing data link: {link}')
        return
    if link.exists():
        # Image defaults may exist again after a container rebuild. Only copy
        # missing paths; the persistent version always wins.
        for item in link.rglob('*'):
            dest=target/item.relative_to(link)
            if item.is_dir():
                dest.mkdir(parents=True,exist_ok=True)
            elif not dest.exists():
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(item,dest)
        shutil.rmtree(link)
    link.parent.mkdir(parents=True,exist_ok=True)
    link.symlink_to(target,target_is_directory=True)

def seed_plugins(data):
    from astrbot.core.config.default import DEFAULT_VALUE_MAP
    plugins=data/'plugins'
    plugins.mkdir(exist_ok=True)
    specs=json.loads(Path('/opt/dafeiyu/plugins.lock.json').read_text())
    from fetch_plugins import fetch_plugin
    for spec in specs:
        target=plugins/spec['name']
        seed=Path('/opt/plugin-seeds')/spec['name']
        if spec.get('runtime_download') and not target.exists() and not seed.exists():
            fetch_plugin(spec,seed)
    newly_installed=[]
    for source in Path('/opt/plugin-seeds').iterdir():
        target=plugins/source.name
        if not target.exists():
            shutil.copytree(source,target)
            newly_installed.append(source.name)
    config=data/'config'
    config.mkdir(exist_ok=True)
    for spec in specs:
        name=spec['name']
        path=config/(name+'_config.json')
        if path.exists(): continue
        schema_file=plugins/name/'_conf_schema.json'
        if not schema_file.exists():continue
        schema=json.loads(schema_file.read_text(encoding='utf-8'))
        def defaults(items):
            return {k:defaults(v.get('items',{})) if v.get('type')=='object' else copy.deepcopy(v.get('default',DEFAULT_VALUE_MAP.get(v.get('type')))) for k,v in items.items()}
        value=defaults(schema)
        if name.endswith('livingmemory'):
            # The exact key is resolved from the pinned schema rather than guessed.
            for section in value.values():
                if isinstance(section,dict) and 'memory_scope_mode' in section:
                    section['memory_scope_mode']='session'
            value['session_manager']['enable_full_group_capture']=False
            value['provider_settings']['embedding_provider_id']=os.environ.get('EMBEDDING_PROVIDER_ID','')
        elif name.endswith('proactive_chat'):
            value['friend_settings']['enable']=False
            value['group_settings']['enable']=False
            value['web_admin']['enabled']=False
            value['friend_settings']['schedule_settings'].update(min_interval_minutes=120,max_interval_minutes=240,quiet_hours='23-8',max_unanswered_times=1)
        write_json(path,value)
    return [spec['name'] for spec in specs if spec['name'] in newly_installed and spec.get('enabled_on_install') is False]

async def seed_persona(data, disabled_plugins=None):
    from astrbot.core.db.sqlite import SQLiteDatabase
    db=SQLiteDatabase(str(data/'data_v4.db'))
    try:
        await db.initialize()
        if disabled_plugins:
            current=await db.get_preference('global','global','inactivated_plugins')
            value=copy.deepcopy(current.value.get('val',[]) if current else [])
            for name in disabled_plugins:
                module='data.plugins.'+name+'.main'
                if module not in value:value.append(module)
            await db.insert_preference_or_update('global','global','inactivated_plugins',{'val':value})
        if await db.get_persona_by_id('大肥鱼') is None:
            prompt=Path('/opt/dafeiyu/persona/dafeiyu.md').read_text(encoding='utf-8')
            await db.insert_persona('大肥鱼',prompt)
    finally:
        await db.engine.dispose()

def main():
    base=Path(os.environ.get('STACK_DATA_DIR','/mnt/workspace/dafeiyu')).resolve()
    data=base/'astrbot'
    link_directory(Path('/AstrBot/data'),data)
    link_directory(Path('/app/napcat/config'),base/'napcat')
    link_directory(Path('/app/.config/QQ'),base/'qq')
    credentials=base/'bootstrap-credentials.json'
    if credentials.exists():
        creds=json.loads(credentials.read_text())
    else:
        creds={name:os.environ.get(env) or ('Df9'+secrets.token_urlsafe(24)) for name,env in [('dashboard_password','ASTRBOT_ADMIN_PASSWORD'),('napcat_token','NAPCAT_WEBUI_TOKEN'),('onebot_token','ONEBOT_TOKEN')]}
        write_json(credentials,creds)
    path=data/'cmd_config.json'
    fresh=not path.exists()
    if fresh:
        # Importing astrbot.core initializes its global configuration. Seed a valid
        # password first so upstream does not generate/log a different password.
        salt=secrets.token_hex(16)
        digest=hashlib.pbkdf2_hmac('sha256',creds['dashboard_password'].encode(),bytes.fromhex(salt),600000).hex()
        write_json(path,{'dashboard':{'password':hashlib.md5(creds['dashboard_password'].encode()).hexdigest(),'pbkdf2_password':f'pbkdf2_sha256$600000${salt}${digest}','password_storage_upgraded':True,'password_change_required':False}})
    from astrbot.core.config.default import DEFAULT_CONFIG
    from astrbot.core.utils.auth_password import hash_dashboard_password
    if fresh:
        cfg=copy.deepcopy(DEFAULT_CONFIG)
        cfg['dashboard'].update(host='127.0.0.1',port=6185,username='astrbot',password=hashlib.md5(creds['dashboard_password'].encode()).hexdigest(),pbkdf2_password=hash_dashboard_password(creds['dashboard_password']),password_storage_upgraded=True,password_change_required=False,jwt_secret=secrets.token_urlsafe(48))
        cfg['platform']=[dict(id='qq',type='aiocqhttp',enable=True,ws_reverse_host='127.0.0.1',ws_reverse_port=6199,ws_reverse_token=creds['onebot_token'])]
        owner=os.environ.get('OWNER_QQ','').strip()
        cfg['admins_id']=[owner] if owner else []
        # AstrBot treats an empty whitelist as allow-all. A sentinel blocks IM until setup.
        cfg['platform_settings'].update(enable_id_white_list=True,id_whitelist=[f'qq:FriendMessage:{owner}'] if owner else ['SET_OWNER_QQ_BEFORE_USE'],no_permission_reply=False)
        cfg['wake_prefix']=['/','大肥鱼']
        cfg['agent_runner']['config']['persona']['persona_id']='大肥鱼'
        key=os.environ.get('DEEPSEEK_API_KEY','')
        cfg['provider_sources']=[dict(id='deepseek',provider='deepseek',type='openai_chat_completion',provider_type='chat_completion',enable=bool(key),key=[key] if key else [],api_base=os.environ.get('DEEPSEEK_API_BASE','https://api.deepseek.com/v1'),timeout=120,proxy='',custom_headers={})]
        cfg['provider']=[dict(id='deepseek-chat',provider_source_id='deepseek',model=os.environ.get('DEEPSEEK_MODEL','deepseek-chat'),modalities=['text'],custom_extra_body={},enable=bool(key))]
        cfg['agent_runner']['config']['model']['provider_id']='deepseek-chat' if key else ''
        write_json(path,cfg)
    webui=base/'napcat/webui.json'
    if not webui.exists(): write_json(webui,dict(host='127.0.0.1',prefix='/napcat',port=6099,token=creds['napcat_token'],loginRate=3))
    onebot=base/'napcat/onebot11.json'
    if not onebot.exists():
        write_json(onebot,{'network':{'httpServers':[],'httpSseServers':[],'httpClients':[],'websocketServers':[],'websocketClients':[{'name':'astrbot','enable':True,'url':'ws://127.0.0.1:6199/ws','messagePostFormat':'array','reportSelfMessage':False,'token':creds['onebot_token'],'debug':False,'heartInterval':30000,'reconnectInterval':5000}]},'musicSignUrl':'','enableLocalFile2Url':True,'parseMultMsg':False})
    disabled_plugins=seed_plugins(data)
    asyncio.run(seed_persona(data,disabled_plugins))
    (data/'home').mkdir(exist_ok=True)
    (base/'ollama').mkdir(exist_ok=True)
    from desktop_setup import setup_desktop
    setup_desktop(base,creds,credentials)
    print('[stack] Persistent data and initial configuration ready. Credentials are supplied via Secrets; no passwords are logged.')

if __name__=='__main__': main()
