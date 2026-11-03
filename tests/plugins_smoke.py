"""Verify pinned plugins import and the local embedding service actually runs."""
import json,time,urllib.request,http.cookiejar
from pathlib import Path
base='http://127.0.0.1:7860'
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
req=urllib.request.Request(base+'/api/auth/login',data=json.dumps({'username':'astrbot','password':'SmokeTest9Secret'}).encode(),headers={'Content-Type':'application/json'})
login=json.load(opener.open(req));assert login['status']=='ok'
token=login.get('token') or (login.get('data') or {}).get('token')
assert token,'Dashboard login did not return a session token'
opener.addheaders=[('Authorization','Bearer '+token)]
plugins=json.load(opener.open(base+'/api/v1/plugins'))['data']
names={p['name'] for p in plugins}
specs=json.loads(Path('deploy/plugins.lock.json').read_text())
missing={s['name'] for s in specs}-names
failed=json.load(opener.open(base+'/api/v1/plugins/failed'))['data']
assert not missing,(missing,failed)
for spec in specs:
 if spec.get('enabled_on_install') is False:
  assert next(p for p in plugins if p['name']==spec['name'])['activated'] is False,spec['name']
import subprocess
subprocess.run(['docker','exec','dafeiyu','curl','-fsS','http://127.0.0.1:11434/api/version'],check=True,stdout=subprocess.DEVNULL)
request=urllib.request.Request(base+'/api/v1/plugins/extensions/meme_manager/packs/import/session',data=json.dumps({'filename':'storage-check.zip','total_chunks':1}).encode(),headers={'Content-Type':'application/json'})
session=json.load(opener.open(request))
if isinstance(session.get('data'),dict):session=session['data']
session_id=session['session_id']
subprocess.run(['docker','exec','dafeiyu','test','-f','/tmp/dafeiyu-meme-manager/pack_import_sessions/'+session_id+'.json'],check=True)
print('PASS:',len(specs),'pinned plugins import; dependent features start disabled; Ollama is reachable on loopback')
print('PASS: actual meme upload staging uses local temporary storage')
import io,zipfile,base64,uuid
archive=io.BytesIO()
with zipfile.ZipFile(archive,'w') as z:
 z.writestr('manifest.json',json.dumps({'schema_version':1,'id':'cross-mount-smoke','name':'Storage check','version':'1.0.0','categories':{'happy':{'description':'Storage check'}}}))
 z.writestr('memes/happy/probe.png',base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC'))
boundary='Smoke'+uuid.uuid4().hex
body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="chunk.part"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+archive.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
chunk_request=urllib.request.Request(base+'/api/v1/plugins/extensions/meme_manager/packs/import/session/chunk/'+session_id+'/0/1',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
inspected=json.load(opener.open(chunk_request))
if isinstance(inspected.get('data'),dict):inspected=inspected['data']
assert inspected['import_token']==session_id
apply=urllib.request.Request(base+'/api/v1/plugins/extensions/meme_manager/packs/import/apply',data=json.dumps({'import_token':session_id,'set_as_default':False,'overwrite':False}).encode(),headers={'Content-Type':'application/json'})
json.load(opener.open(apply))
readback=json.load(opener.open(base+'/api/v1/plugins/extensions/meme_manager/packs'))
if isinstance(readback.get('data'),dict):readback=readback['data']
assert any(p['id']=='cross-mount-smoke' and p['image_count']==1 for p in readback['packs'])
subprocess.run(['docker','exec','dafeiyu','test','-f','/mnt/workspace/dafeiyu/astrbot/plugin_data/meme_manager/packs/cross-mount-smoke/memes/happy/probe.png'],check=True)
print('PASS: an actual archive imports from /tmp into persistent storage and reads back')
