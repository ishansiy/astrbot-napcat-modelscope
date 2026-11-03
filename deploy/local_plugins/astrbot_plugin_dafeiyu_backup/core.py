"""Consistent file/SQLite snapshots and authenticated streaming encryption."""
import base64, hashlib, json, os, shutil, sqlite3, stat, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

FORMAT='dafeiyu-stack-backup-v1'
MAGIC=b'DFYBAK01'
BLOCK=1024*1024

def key_bytes(value):
    try:key=base64.urlsafe_b64decode(value.strip()+'='*(-len(value.strip())%4))
    except Exception:raise ValueError('备份加密密钥格式无效') from None
    if len(key)!=32:raise ValueError('备份加密密钥必须是 32 字节的 URL-safe Base64')
    return key

def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(BLOCK),b''):result.update(block)
    return result.hexdigest()

def sqlite_file(path):
    with path.open('rb') as source:return source.read(16)==b'SQLite format 3\0'

def snapshot_database(source,target):
    deadline=time.monotonic()+90
    def progress(*args):
        if time.monotonic()>deadline:raise TimeoutError('SQLite 快照等待超时')
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)) as origin:
        with closing(sqlite3.connect(target)) as snapshot:
            origin.backup(snapshot,pages=256,progress=progress,sleep=.05)
            if snapshot.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('SQLite 快照完整性校验失败')

def excluded(scope,relative):
    parts=relative.parts
    if any(x in ('__pycache__','.git','node_modules','.venv') for x in parts):return True
    if relative.name.endswith(('.pyc','.sock')):return True
    if scope=='astrbot' and parts and parts[0] in ('backups','temp','tmp','cache'):return True
    if scope=='desktop' and parts and parts[0]=='.cache':return True
    if scope=='desktop' and parts[:3]==('.local','share','Trash'):return True
    if scope in ('desktop','qq') and any(x in ('cache2','Cache','GPUCache','shader-cache','startupCache','Crash Reports') for x in parts):return True
    if relative.name in ('.parentlock','parent.lock','lock','SingletonLock','SingletonSocket','SingletonCookie'):return True
    return False

def build_archive(root,scopes,target,workspace):
    root=Path(root).resolve();workspace=Path(workspace)
    if not root.is_dir():raise ValueError('备份数据根目录不存在')
    entries=[];directories=[];skipped=[];databases=[]
    selected=[name for name in ('astrbot','desktop','napcat','qq','ollama') if scopes.get(name,False)]
    if not selected:raise ValueError('至少选择一个备份范围')
    roots=[(name,root/name) for name in selected]
    credentials=root/'bootstrap-credentials.json'
    if credentials.is_file():roots.append(('',credentials))
    with zipfile.ZipFile(target,'w',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for scope,source_root in roots:
            if not source_root.exists():continue
            if source_root.is_dir():
                info=source_root.stat()
                directories.append({'path':scope,'mode':stat.S_IMODE(info.st_mode),'uid':getattr(info,'st_uid',0),'gid':getattr(info,'st_gid',0),'mtime_ns':info.st_mtime_ns})
                archive.writestr(scope+'/',b'')
            candidates=[source_root] if source_root.is_file() else source_root.rglob('*')
            for source in candidates:
                relative=source.relative_to(source_root) if source_root.is_dir() else Path(source.name)
                if excluded(scope,relative):continue
                name=(Path(scope)/relative).as_posix() if scope else relative.as_posix()
                if source.is_symlink():
                    skipped.append({'path':name,'reason':'symlink'});continue
                info=source.stat()
                if stat.S_ISDIR(info.st_mode):
                    item=zipfile.ZipInfo(name.rstrip('/')+'/');item.external_attr=(info.st_mode&0xffff)<<16
                    archive.writestr(item,b'');directories.append({'path':name,'mode':stat.S_IMODE(info.st_mode),'uid':getattr(info,'st_uid',0),'gid':getattr(info,'st_gid',0),'mtime_ns':info.st_mtime_ns});continue
                if not stat.S_ISREG(info.st_mode):
                    skipped.append({'path':name,'reason':'special_file'});continue
                if any(source.name.endswith(suffix) and source.with_name(source.name[:-len(suffix)]).is_file() and sqlite_file(source.with_name(source.name[:-len(suffix)])) for suffix in ('-wal','-shm','-journal')):continue
                actual=source;temporary=None
                if sqlite_file(source):
                    temporary=workspace/('sqlite-'+str(len(databases))+'.db')
                    snapshot_database(source,temporary);actual=temporary;databases.append(name)
                item=zipfile.ZipInfo(name);item.external_attr=(info.st_mode&0xffff)<<16
                item.compress_type=zipfile.ZIP_STORED if source.suffix.lower() in ('.gif','.jpg','.jpeg','.png','.webp','.zip','.mp4','.mp3','.ogg') else zipfile.ZIP_DEFLATED
                checksum=hashlib.sha256();size=0
                with actual.open('rb') as incoming,archive.open(item,'w',force_zip64=True) as outgoing:
                    for block in iter(lambda:incoming.read(BLOCK),b''):
                        outgoing.write(block);checksum.update(block);size+=len(block)
                if temporary:temporary.unlink()
                entries.append({'path':name,'size':size,'sha256':checksum.hexdigest(),'mode':stat.S_IMODE(info.st_mode),'uid':getattr(info,'st_uid',0),'gid':getattr(info,'st_gid',0),'mtime_ns':info.st_mtime_ns})
        manifest={'format':FORMAT,'created_at':datetime.now(timezone.utc).isoformat(),'scopes':selected,'entries':entries,'directories':directories,'sqlite_snapshots':databases,'skipped':skipped}
        archive.writestr('_dafeiyu_backup_manifest.json',json.dumps(manifest,ensure_ascii=False))
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:raise ValueError('备份 ZIP 校验失败')
    return manifest

def encrypt_archive(source,target,key):
    nonce=os.urandom(12);header=MAGIC+nonce
    encryptor=Cipher(algorithms.AES(key_bytes(key)),modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    with Path(source).open('rb') as incoming,Path(target).open('wb') as outgoing:
        outgoing.write(header)
        for block in iter(lambda:incoming.read(BLOCK),b''):outgoing.write(encryptor.update(block))
        outgoing.write(encryptor.finalize());outgoing.write(encryptor.tag)

def decrypt_archive(source,target,key):
    source=Path(source);target=Path(target)
    try:
        with source.open('rb') as incoming,target.open('wb') as outgoing:
            header=incoming.read(len(MAGIC)+12)
            if len(header)!=20 or not header.startswith(MAGIC):raise ValueError('备份文件格式无效')
            incoming.seek(-16,2);tag=incoming.read(16);incoming.seek(20)
            decryptor=Cipher(algorithms.AES(key_bytes(key)),modes.GCM(header[8:],tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            remaining=source.stat().st_size-36
            while remaining:
                block=incoming.read(min(BLOCK,remaining))
                if not block:raise ValueError('备份文件不完整')
                outgoing.write(decryptor.update(block));remaining-=len(block)
            outgoing.write(decryptor.finalize())
    except Exception:
        target.unlink(missing_ok=True);raise

def split_archive(source,directory,part_size):
    parts=[]
    with Path(source).open('rb') as incoming:
        while True:
            data=incoming.read(part_size)
            if not data:break
            name='part-%04d.bin'%len(parts)
            (Path(directory)/name).write_bytes(data)
            parts.append({'name':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return parts

def restore_bundle(bundle,key,output):
    bundle=Path(bundle);output=Path(output)
    manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!=FORMAT:raise ValueError('不是大肥鱼全量备份')
    if output.exists() and any(output.iterdir()):raise ValueError('恢复目标必须是空目录，避免覆盖现有数据')
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        encrypted=Path(tmp)/'backup.dfyb';plain=Path(tmp)/'backup.zip'
        with encrypted.open('wb') as outgoing:
            for part in manifest['parts']:
                if Path(part['name']).name!=part['name']:raise ValueError('不安全的分片路径')
                path=bundle/part['name']
                if path.stat().st_size!=part['size'] or digest(path)!=part['sha256']:raise ValueError('备份分片校验失败')
                with path.open('rb') as incoming:shutil.copyfileobj(incoming,outgoing,BLOCK)
        if digest(encrypted)!=manifest['encrypted_sha256']:raise ValueError('备份总校验失败')
        decrypt_archive(encrypted,plain,key)
        if digest(plain)!=manifest['archive_sha256']:raise ValueError('解密后的备份校验失败')
        with zipfile.ZipFile(plain) as archive:
            for item in archive.infolist():
                if not (output/item.filename).resolve().is_relative_to(output.resolve()):raise ValueError('不安全的 ZIP 路径')
            if archive.testzip() is not None:raise ValueError('恢复 ZIP 校验失败')
            archive.extractall(output)
        details=json.loads((output/'_dafeiyu_backup_manifest.json').read_text(encoding='utf-8'))
        for entry in details['entries']:
            path=output/entry['path']
            if not path.resolve().is_relative_to(output.resolve()):raise ValueError('不安全的清单路径')
            if digest(path)!=entry['sha256']:raise ValueError('恢复文件校验失败')
            path.chmod(entry['mode'])
            if getattr(os,'geteuid',lambda:1)()==0:os.chown(path,entry['uid'],entry['gid'])
            if 'mtime_ns' in entry:os.utime(path,ns=(entry['mtime_ns'],entry['mtime_ns']))
        for entry in sorted(details.get('directories',[]),key=lambda x:len(x['path']),reverse=True):
            path=output/entry['path']
            if not path.resolve().is_relative_to(output.resolve()):raise ValueError('不安全的清单路径')
            path.chmod(entry['mode'])
            if getattr(os,'geteuid',lambda:1)()==0:os.chown(path,entry['uid'],entry['gid'])
            if 'mtime_ns' in entry:os.utime(path,ns=(entry['mtime_ns'],entry['mtime_ns']))
        for name in details['sqlite_snapshots']:
            with closing(sqlite3.connect((output/name).resolve().as_uri()+'?mode=ro',uri=True)) as db:
                if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('恢复的 SQLite 校验失败')
    return {'files':len(details['entries']),'sqlite_databases':len(details['sqlite_snapshots']),'scopes':details['scopes']}
