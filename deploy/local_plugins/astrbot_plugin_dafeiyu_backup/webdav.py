"""WebDAV upload with read-back hashes and retention scoped to this installation."""
import hashlib,json,re,time,urllib.parse,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import httpx

class DavError(RuntimeError):pass

class WebDAV:
    def __init__(self,config):
        parsed=urllib.parse.urlsplit(config['url'].strip())
        if parsed.scheme not in ('https','http') or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:raise DavError('WebDAV 地址需为 HTTP(S) 目录地址，账号密码请填写在独立字段')
        path=urllib.parse.quote(urllib.parse.unquote(parsed.path),safe='/').rstrip('/')+'/'
        self.base=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,path,'',''))
        self.client=httpx.Client(auth=(config.get('username',''),config.get('password','')),verify=config.get('verify_tls',True),follow_redirects=True,timeout=httpx.Timeout(300,connect=30))

    def close(self):self.client.close()

    def url(self,*names):return self.base+'/'.join(urllib.parse.quote(name,safe='') for name in names)

    def check(self,response,expected):
        if response.status_code not in expected:raise DavError('WebDAV 请求失败，HTTP '+str(response.status_code))

    def ensure_collection(self,url=None,depth=0):
        url=url or self.base
        response=self.client.request('PROPFIND',url,headers={'Depth':'0'})
        if response.status_code in (200,207):return
        if response.status_code==404 and depth<10:
            parsed=urllib.parse.urlsplit(url);parent=parsed.path.rstrip('/').rsplit('/',1)[0]+'/'
            if parent==parsed.path:raise DavError('WebDAV 父目录不可创建')
            self.ensure_collection(urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parent,'','')),depth+1)
            response=self.client.request('MKCOL',url)
        self.check(response,(200,201,204,405))
        response=self.client.request('PROPFIND',url,headers={'Depth':'0'})
        self.check(response,(200,207))

    def list_names(self):
        response=self.client.request('PROPFIND',self.base,headers={'Depth':'1'},content=b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>')
        self.check(response,(200,207))
        result=[]
        for element in ET.fromstring(response.content).findall('.//{DAV:}response'):
            href=element.findtext('{DAV:}href') or ''
            name=urllib.parse.unquote(urllib.parse.urlsplit(href).path).rstrip('/').rsplit('/',1)[-1]
            if re.fullmatch(r'dafeiyu-\d{8}T\d{6}Z-[0-9a-f]{8}',name):result.append(name)
        return sorted(set(result))

    def upload_part(self,folder,path,part):
        for attempt in range(3):
            try:
                with Path(path).open('rb') as source:
                    response=self.client.put(self.url(folder,part['name']),content=iter(lambda:source.read(1024*1024),b''),headers={'Content-Length':str(part['size']),'Content-Type':'application/octet-stream'})
                self.check(response,(200,201,204))
                checksum=hashlib.sha256();size=0
                with self.client.stream('GET',self.url(folder,part['name'])) as response:
                    self.check(response,(200,))
                    for data in response.iter_bytes(1024*1024):checksum.update(data);size+=len(data)
                if size!=part['size'] or checksum.hexdigest()!=part['sha256']:raise DavError('WebDAV 分片下载校验不一致')
                return
            except (httpx.TransportError,DavError):
                if attempt==2:raise
                time.sleep(2**attempt)

    def upload_bundle(self,directory,manifest,progress):
        folder=manifest['id'];self.ensure_collection(self.url(folder)+'/')
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.upload_part,folder,Path(directory)/part['name'],part) for part in manifest['parts']]
            for index,future in enumerate(as_completed(futures),1):
                future.result();progress(index,len(futures))
        response=self.client.put(self.url(folder,'manifest.json'),content=json.dumps(manifest,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        self.check(response,(200,201,204))
        response=self.client.get(self.url(folder,'manifest.json'));self.check(response,(200,))
        if response.json()!=manifest:raise DavError('WebDAV 备份清单读回不一致')
        if folder not in self.list_names():raise DavError('WebDAV 备份目录列表中未找到新备份')

    def cleanup(self,installation_id,keep):
        owned=[]
        for name in self.list_names():
            response=self.client.get(self.url(name,'manifest.json'))
            if response.status_code!=200:continue
            try:manifest=response.json()
            except ValueError:continue
            if manifest.get('format')=='dafeiyu-stack-backup-v1' and manifest.get('installation_id')==installation_id:owned.append(name)
        removed=[]
        for name in owned[:-max(1,keep)]:
            response=self.client.delete(self.url(name)+'/');self.check(response,(200,202,204))
            removed.append(name)
        if set(removed)&set(self.list_names()):raise DavError('WebDAV 保留策略删除后读回仍有旧备份')
        return removed
