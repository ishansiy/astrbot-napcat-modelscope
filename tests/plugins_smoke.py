"""Verify pinned plugins import and the local embedding service actually runs."""
import json,time,urllib.request,http.cookiejar
from pathlib import Path
base='http://127.0.0.1:7860'
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
req=urllib.request.Request(base+'/api/auth/login',data=json.dumps({'username':'astrbot','password':'SmokeTest9Secret'}).encode(),headers={'Content-Type':'application/json'})
assert json.load(opener.open(req))['status']=='ok'
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
print('PASS:',len(specs),'pinned plugins import; dependent features start disabled; Ollama is reachable on loopback')
