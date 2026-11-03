import json, time, urllib.request, urllib.error
base='http://127.0.0.1:7860'
def get(path):
    with urllib.request.urlopen(base+path,timeout=10) as response:
        return response.read()
for attempt in range(90):
    try:
        get('/healthz')
        ui=get('/napcat/webui/')
        assert b'<html' in ui.lower() or b'<!doctype html' in ui.lower()
        break
    except (OSError,AssertionError): time.sleep(3)
else: raise SystemExit('AstrBot or NapCat UI did not become ready')
req=urllib.request.Request(base+'/api/auth/login',data=json.dumps({'username':'astrbot','password':'SmokeTest9Secret'}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=15) as response:
    result=json.load(response)
assert result.get('status')=='ok' or result.get('data',{}).get('token'), 'AstrBot login failed'
print('PASS: AstrBot health, authenticated login and NapCat UI through the single gateway')
