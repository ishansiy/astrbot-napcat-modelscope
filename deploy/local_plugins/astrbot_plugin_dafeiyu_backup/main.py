import asyncio,json,os,subprocess,sys,tempfile,uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from croniter import croniter
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent,filter
from astrbot.api.star import Context,Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from .core import key_bytes

NAME='astrbot_plugin_dafeiyu_backup'

class DafeiyuBackup(Star):
    def __init__(self,context:Context,config):
        super().__init__(context);self.config=config;self.timer=None;self.launch_lock=asyncio.Lock()
        self.state_dir=Path(get_astrbot_data_path())/'plugin_data'/NAME;self.state_dir.mkdir(parents=True,exist_ok=True)
        identity=self.state_dir/'installation-id'
        if not identity.exists():identity.write_text(uuid.uuid4().hex,encoding='ascii')
        self.installation_id=identity.read_text().strip()
        for route,handler,methods in [('status',self.api_status,['GET']),('run',self.api_run,['POST']),('resume',self.api_resume,['POST']),('manifest',self.api_manifest,['GET'])]:
            context.register_web_api('/'+NAME+'/'+route,handler,methods,'大肥鱼全量备份（仅登录面板可用）')

    async def initialize(self):
        self.timer=asyncio.create_task(self.scheduler())
        if self.config.get('actions',{}).get('retry_upload_now'):
            self.config['actions']['retry_upload_now']=False;self.config.save_config()
            await self.start(resume=True)
        if self.config.get('actions',{}).get('backup_now'):
            self.config['actions']['backup_now']=False;self.config.save_config()
            await self.start()

    def read_json(self,name):
        path=self.state_dir/name
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}

    def status(self):
        state=self.read_json('state.json')
        if state.get('status') in ('queued','running'):
            try:
                command=Path('/proc')/str(state['pid'])/'cmdline'
                alive=command.is_file() and state['job_id'].encode() in command.read_bytes()
            except (OSError,KeyError):alive=False
            if not alive:state.update(status='interrupted',stage='上次备份进程已停止；已完成的本地/远程备份不受影响')
        schedule=self.config['schedule'];next_run=None
        if schedule['enabled']:
            try:next_run=croniter(schedule['cron'],datetime.now(ZoneInfo(schedule['timezone']))).get_next(datetime).isoformat()
            except Exception:next_run='定时规则或时区配置无效'
        return {'current':state,'last_success':self.read_json('last-success.json'),'next_run':next_run,'scheduled':schedule['enabled'],'webdav_enabled':self.config['webdav']['enabled']}

    async def start(self,resume=False):
        async with self.launch_lock:
            previous=self.status()['current']
            if previous.get('status') in ('queued','running'):return {'started':False,'reason':'已有备份正在进行'}
            config=json.loads(json.dumps(dict(self.config)));key_bytes(config['backup']['encryption_key'])
            if config['webdav']['enabled'] and not config['webdav']['url'].strip():raise ValueError('请先在插件配置中填写 WebDAV 地址')
            config['_installation_id']=self.installation_id
            if resume:
                if not previous.get('local_verified') or not previous.get('local_directory'):raise ValueError('没有可续传的已验证本地副本')
                config['_resume_bundle']=previous['local_directory']
            job_id=uuid.uuid4().hex
            descriptor,path=tempfile.mkstemp(prefix='dafeiyu-backup-settings-',suffix='.json')
            os.chmod(path,0o600)
            with os.fdopen(descriptor,'w',encoding='utf-8') as target:json.dump(config,target,ensure_ascii=False)
            worker=Path(__file__).with_name('worker.py')
            try:
                process=subprocess.Popen([sys.executable,str(worker),'--settings-file',path,'--state-dir',str(self.state_dir),'--job-id',job_id],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                # The worker writes the authoritative running state; retain its PID for reloads.
                self.process=process
                asyncio.create_task(asyncio.to_thread(process.wait))
                await asyncio.sleep(.5)
            except Exception:
                Path(path).unlink(missing_ok=True);raise
            return {'started':True,'job_id':job_id}

    async def api_status(self):return {'status':'ok','data':self.status()}

    async def api_manifest(self):
        current=self.read_json('state.json');directory=current.get('local_directory')
        if not current.get('local_verified') or not directory:return {'status':'error','message':'暂无完整本地副本'}
        directory=Path(directory).resolve();root=Path(self.config['backup']['local_directory']).resolve()
        if not directory.is_relative_to(root):return {'status':'error','message':'本地副本不在当前备份目录内'}
        return {'status':'ok','data':json.loads((directory/'manifest.json').read_text(encoding='utf-8'))}

    async def api_run(self):
        try:return {'status':'ok','data':await self.start()}
        except ValueError as error:return {'status':'error','message':str(error)}

    async def api_resume(self):
        try:return {'status':'ok','data':await self.start(resume=True)}
        except ValueError as error:return {'status':'error','message':str(error)}

    async def scheduler(self):
        while True:
            if not self.config['schedule']['enabled']:
                await asyncio.sleep(30);continue
            try:
                schedule=self.config['schedule'];now=datetime.now(ZoneInfo(schedule['timezone']))
                next_time=croniter(schedule['cron'],now).get_next(datetime)
                await asyncio.sleep(max(1,(next_time-now).total_seconds()))
                await self.start()
            except asyncio.CancelledError:raise
            except Exception:logger.warning('[dafeiyu-backup] 定时备份配置或启动失败；请在面板检查状态。');await asyncio.sleep(60)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command('大肥鱼备份',alias={'全量备份'})
    async def backup_command(self,event:AstrMessageEvent):
        result=await self.start()
        yield event.plain_result('已开始加密全量备份，可用 /备份状态 查询。' if result['started'] else result['reason'])

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command('备份状态')
    async def backup_status(self,event:AstrMessageEvent):
        status=self.status();current=status['current']
        yield event.plain_result('备份状态：'+current.get('status','尚未运行')+'\n阶段：'+current.get('stage','')+'\nWebDAV 已验证：'+str(current.get('remote_verified',False))+'\n下次备份：'+str(status['next_run']))

    async def terminate(self):
        if self.timer:
            self.timer.cancel()
            try:await self.timer
            except asyncio.CancelledError:pass
        # Detached worker intentionally continues through panel configuration reloads.
