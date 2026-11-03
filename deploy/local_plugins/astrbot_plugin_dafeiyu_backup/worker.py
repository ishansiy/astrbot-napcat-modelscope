"""Detached, resumable worker for encrypted snapshots and verified WebDAV uploads."""
import argparse,fcntl,hashlib,json,os,re,shutil,sys,tempfile,uuid
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from core import FORMAT,build_archive,encrypt_archive,decrypt_archive,split_archive,digest,key_bytes
from webdav import WebDAV,DavError
import httpx

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.chmod(0o600);temporary.replace(path)

def prepare_bundle(config,installation,update):
    key=config['backup']['encryption_key'];local_root=Path(config['backup']['local_directory']).resolve()
    if config.get('_resume_bundle'):
        bundle=Path(config['_resume_bundle']).resolve()
        if not bundle.is_relative_to(local_root) or bundle==local_root:raise ValueError('续传目录必须位于当前本地备份目录内')
        manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format')!=FORMAT or manifest.get('installation_id')!=installation or manifest.get('id')!=bundle.name:raise ValueError('续传副本不属于本次安装')
        if manifest['key_hint']!=hashlib.sha256(key_bytes(key)).hexdigest()[:12]:raise ValueError('当前恢复密钥与上次副本不匹配，请使用原密钥或新建备份')
        update(stage='校验已有本地副本，准备续传')
        for part in manifest['parts']:
            if not re.fullmatch(r'part-\d{4}\.bin',part['name']):raise ValueError('无效的分片名称')
            if (bundle/part['name']).stat().st_size!=part['size'] or digest(bundle/part['name'])!=part['sha256']:raise ValueError('续传副本校验失败')
        manifest['verification_mode']=config['webdav'].get('verification_mode','full')
        atomic_json(bundle/'manifest.json',manifest)
        return bundle,manifest
    source=Path(config['backup']['source_root']).resolve()
    if any(local_root.is_relative_to(source/name) for name in ('astrbot','desktop','napcat','qq','ollama')):raise ValueError('本地备份目录不能放在备份范围内，以免循环打包')
    folder='dafeiyu-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix='dafeiyu-backup-') as temporary:
        temporary=Path(temporary);archive=temporary/'backup.zip';encrypted=temporary/'backup.dfyb';bundle=temporary/'bundle';bundle.mkdir()
        update(stage='创建文件与 SQLite 一致性快照')
        details=build_archive(source,config['scope'],archive,temporary)
        update(stage='加密并验证备份',file_count=len(details['entries']),sqlite_databases=len(details['sqlite_snapshots']),scopes=details['scopes'],database_recoveries=details['database_recoveries'])
        encrypt_archive(archive,encrypted,key)
        checked=temporary/'verification.zip';decrypt_archive(encrypted,checked,key)
        archive_hash=digest(archive)
        if digest(checked)!=archive_hash:raise ValueError('加密恢复验证失败')
        checked.unlink();archive.unlink()
        parts=split_archive(encrypted,bundle,max(8,min(256,int(config['backup']['part_size_mb'])))*1024*1024)
        manifest={'format':FORMAT,'id':folder,'installation_id':installation,'created_at':datetime.now(timezone.utc).isoformat(),'archive_sha256':archive_hash,'encrypted_sha256':digest(encrypted),'encrypted_size':encrypted.stat().st_size,'encryption':'AES-256-GCM','key_hint':hashlib.sha256(key_bytes(key)).hexdigest()[:12],'parts':parts,'scopes':details['scopes'],'file_count':len(details['entries']),'sqlite_databases':len(details['sqlite_snapshots']),'database_recoveries':details['database_recoveries'],'verification_mode':config['webdav'].get('verification_mode','full')}
        atomic_json(bundle/'manifest.json',manifest);encrypted.unlink()
        update(stage='保存本地持久化副本',backup_id=folder,size_bytes=manifest['encrypted_size'],total_parts=len(parts))
        local_root.mkdir(parents=True,exist_ok=True);pending=local_root/(folder+'.pending')
        shutil.copytree(bundle,pending)
        for part in parts:
            if digest(pending/part['name'])!=part['sha256']:raise ValueError('本地持久化副本校验失败')
        pending.rename(local_root/folder)
    return local_root/folder,manifest

def run(settings_file,state_dir,job_id):
    config=json.loads(Path(settings_file).read_text(encoding='utf-8'));Path(settings_file).unlink()
    state_dir=Path(state_dir);state_dir.mkdir(parents=True,exist_ok=True)
    lock=(state_dir/'backup.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:lock.close();return
    state={'job_id':job_id,'pid':os.getpid(),'status':'running','stage':'检查配置','started_at':datetime.now(timezone.utc).isoformat(),'remote_verified':False}
    dav=None
    def update(**values):state.update(values);atomic_json(state_dir/'state.json',state)
    update()
    try:
        key_bytes(config['backup']['encryption_key']);installation=config['_installation_id']
        if config['webdav']['enabled']:dav=WebDAV(config['webdav']);dav.ensure_collection()
        bundle,manifest=prepare_bundle(config,installation,update)
        update(local_directory=str(bundle),local_verified=True,backup_id=manifest['id'],size_bytes=manifest['encrypted_size'],file_count=manifest['file_count'],sqlite_databases=manifest['sqlite_databases'],scopes=manifest['scopes'],database_recoveries=manifest.get('database_recoveries',[]),total_parts=len(manifest['parts']),verification_mode=manifest['verification_mode'])
        if dav:
            update(stage='上传 WebDAV 并校验分片',verified_parts=0)
            dav.upload_bundle(bundle,manifest,lambda done,total:update(verified_parts=done,total_parts=total),resume=bool(config.get('_resume_bundle')))
            update(remote_verified=True,stage='应用保留份数');dav.cleanup(installation,int(config['schedule']['remote_keep']))
        owned=[];local_root=Path(config['backup']['local_directory']).resolve()
        for candidate in sorted(local_root.glob('dafeiyu-*')):
            metadata=candidate/'manifest.json'
            if candidate.is_symlink() or not candidate.is_dir() or not metadata.is_file() or candidate.name.endswith('.pending'):continue
            info=json.loads(metadata.read_text(encoding='utf-8'))
            if info.get('format')==FORMAT and info.get('installation_id')==installation:owned.append(candidate)
        for candidate in owned[:-max(1,int(config['schedule']['local_keep']))]:shutil.rmtree(candidate)
        update(status='succeeded',stage='备份完成（源库损坏已在备份副本中恢复，原始快照同时保留）' if manifest.get('database_recoveries') else '备份完成',finished_at=datetime.now(timezone.utc).isoformat())
        atomic_json(state_dir/'last-success.json',state)
    except Exception as error:
        if isinstance(error,(ValueError,DavError)):message=str(error)
        elif isinstance(error,httpx.HTTPError):message='WebDAV 网络请求失败（'+type(error).__name__+'）'
        else:message='备份失败（'+type(error).__name__+'）'
        update(status='failed',stage='备份失败',error=message,finished_at=datetime.now(timezone.utc).isoformat())
    finally:
        if dav:dav.close()
        fcntl.flock(lock,fcntl.LOCK_UN);lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--settings-file',required=True);parser.add_argument('--state-dir',required=True);parser.add_argument('--job-id',required=True)
    args=parser.parse_args();run(args.settings_file,args.state_dir,args.job_id)
