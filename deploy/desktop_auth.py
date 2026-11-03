"""Cookie authentication for noVNC, compatible with ModelScope's reserved headers."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs

CONFIG=Path('/run/desktop-auth.json')
COOKIE='dafeiyu_desktop'
TTL=12*3600
FRAME_POLICY="frame-ancestors 'self' https://www.modelscope.ai https://modelscope.ai"
failures=deque()
lock=Lock()
PAGE='''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arch Linux 桌面登录</title><style>
body{background:#0d2538;color:#e9f2fa;font:16px system-ui;display:grid;place-items:center;min-height:95vh}
form{width:min(340px,85vw);background:#17364b;padding:32px;border-radius:16px}
input,button{box-sizing:border-box;width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #698397}
button{background:#63c7f0;color:#082839;font-weight:bold;cursor:pointer}p{color:#b4cad9}
</style><form action="/desktop/login" method="post"><h2>Arch Linux 桌面</h2>
<p>登录后进入 XFCE 远程桌面</p><label>用户名<input name="username" value="desktop" autocomplete="username" required></label>
<label>密码<input name="password" type="password" autocomplete="current-password" required></label>
<button>登录桌面</button></form></html>'''


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def issue(secret):
    payload=f'{int(time.time())}:{secrets.token_hex(16)}'.encode()
    return encode(payload)+'.'+encode(hmac.digest(secret.encode(),payload,'sha256'))


def valid(value, secret):
    try:
        body,signature=value.split('.')
        payload=base64.urlsafe_b64decode(body+'='*(-len(body)%4))
        expected=encode(hmac.digest(secret.encode(),payload,'sha256'))
        age=time.time()-int(payload.split(b':',1)[0])
        return 0<=age<TTL and hmac.compare_digest(signature,expected)
    except (ValueError,TypeError):
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass

    def send(self,status,body=b'',headers=None):
        self.send_response(status)
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        for key,value in (headers or {}).items(): self.send_header(key,value)
        self.end_headers()
        if body: self.wfile.write(body)

    def do_GET(self):
        if self.path=='/auth':
            config=json.loads(CONFIG.read_text())
            cookie=SimpleCookie()
            try: cookie.load(self.headers.get('Cookie',''))
            except Exception: return self.send(401)
            value=cookie[COOKIE].value if COOKIE in cookie else ''
            return self.send(204 if valid(value,config['session_secret']) else 401)
        if self.path.split('?',1)[0]=='/desktop/login':
            return self.send(200,PAGE.encode(),{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':FRAME_POLICY})
        if self.path=='/desktop/logout':
            host=self.headers.get('X-Forwarded-Host','')
            attributes='SameSite=Lax' if host.split(':')[0] in ['localhost','127.0.0.1'] else 'SameSite=None; Secure; Partitioned'
            return self.send(303,headers={'Location':'/desktop/login','Set-Cookie':f'{COOKIE}=; Path=/desktop; HttpOnly; {attributes}; Max-Age=0'})
        self.send(404)

    def do_POST(self):
        if self.path!='/desktop/login': return self.send(404)
        # Prevent cross-site login submissions, without depending on reserved headers.
        origin=self.headers.get('Origin','')
        host=self.headers.get('X-Forwarded-Host','')
        if origin and origin not in ['https://'+host,'http://'+host]: return self.send(403)
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: return self.send(400)
        if not 0<length<=4096: return self.send(400)
        with lock:
            now=time.monotonic()
            while failures and failures[0]<now-60: failures.popleft()
            if len(failures)>=10: return self.send(429,b'Too many login attempts. Try again later.')
        fields=parse_qs(self.rfile.read(length).decode(errors='replace'))
        config=json.loads(CONFIG.read_text())
        password=fields.get('password',[''])[0]
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(config['salt']),600000).hex()
        ok=fields.get('username',[''])[0]=='desktop' and hmac.compare_digest(digest,config['password_hash'])
        if not ok:
            with lock: failures.append(time.monotonic())
            return self.send(401,b'Incorrect username or password. Return to the login page to retry.')
        attributes='SameSite=Lax' if host.split(':')[0] in ['localhost','127.0.0.1'] else 'SameSite=None; Secure; Partitioned'
        cookie=f'{COOKIE}={issue(config["session_secret"])}; Path=/desktop; HttpOnly; {attributes}; Max-Age={TTL}'
        self.send(303,headers={'Location':'/desktop/vnc.html?autoconnect=1&resize=remote&path=%2Fdesktop%2Fwebsockify','Set-Cookie':cookie})


if __name__=='__main__':
    print('[desktop-auth] Cookie login ready on loopback; passwords are not logged.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',6081),Handler).serve_forever()
