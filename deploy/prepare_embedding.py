"""Pull the selected local model into the official persistent mount."""
import json,os,time,urllib.request
model=os.environ.get('LOCAL_EMBEDDING_MODEL','').strip()
if not model:
    print('[embedding] Automatic model download not requested.',flush=True)
    raise SystemExit(0)
for attempt in range(60):
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=5):break
    except Exception:time.sleep(2)
else:raise RuntimeError('Local embedding service did not become ready')
print('[embedding] Preparing local model:',model,flush=True)
request=urllib.request.Request('http://127.0.0.1:11434/api/pull',data=json.dumps({'model':model,'stream':False}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=1800) as result:
    status=json.load(result)
assert status.get('status')=='success',status
print('[embedding] Persistent local model ready:',model,flush=True)
