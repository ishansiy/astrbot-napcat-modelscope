"""Verify the actual desktop and HTTP/WebSocket authentication boundaries."""
import http.cookiejar
import socket
import subprocess
import time
import urllib.error
import urllib.request
import urllib.parse

base='http://127.0.0.1:7860'
with urllib.request.urlopen(base+'/desktop/vnc.html',timeout=10) as response:
    assert response.geturl().endswith('/desktop/login')
try:
    urllib.request.urlopen(base+'/desktop/websockify',timeout=10)
    raise AssertionError('Remote control accessible without authentication')
except urllib.error.HTTPError as error:
    assert error.code==401, error.code
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
req=urllib.request.Request(base+'/desktop/login',data=urllib.parse.urlencode({'username':'desktop','password':'SmokeTest9Secret'}).encode())
with opener.open(req,timeout=15) as response:
    assert b'noVNC' in response.read()
assert any(cookie.name=='dafeiyu_desktop' for cookie in jar)
cookies='; '.join(cookie.name+'='+cookie.value for cookie in jar)
for attempt in range(30):
    result=subprocess.run(['docker','exec','dafeiyu','pgrep','-x','xfce4-panel'],capture_output=True)
    if result.returncode==0: break
    time.sleep(2)
else: raise AssertionError('XFCE panel did not start')
with socket.create_connection(('127.0.0.1',7860),timeout=15) as client:
    client.sendall(('GET /desktop/websockify HTTP/1.1\r\nHost: localhost:7860\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nCookie: '+cookies+'\r\n\r\n').encode())
    assert b'101 Switching Protocols' in client.recv(4096)
subprocess.run(['docker','exec','dafeiyu','sh','-c',"grep -q '^ID=arch$' /etc/os-release && pacman -Q xfce4-session firefox tigervnc && test \"$(readlink -f /home/desktop)\" = /mnt/workspace/dafeiyu/desktop"],check=True)
print('PASS: Arch Linux XFCE desktop, persistent home, browser and authenticated noVNC WebSocket')
