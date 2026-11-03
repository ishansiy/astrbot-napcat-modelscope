"""Verify the actual desktop and HTTP/WebSocket authentication boundaries."""
import base64
import socket
import subprocess
import time
import urllib.error
import urllib.request

base='http://127.0.0.1:7860'
credentials=base64.b64encode(b'desktop:SmokeTest9Secret').decode()
for path in ['/desktop/vnc.html','/desktop/websockify']:
    try:
        urllib.request.urlopen(base+path,timeout=10)
        raise AssertionError('Remote desktop accessible without authentication')
    except urllib.error.HTTPError as error:
        assert error.code==401, error.code
req=urllib.request.Request(base+'/desktop/vnc.html',headers={'Authorization':'Basic '+credentials})
with urllib.request.urlopen(req,timeout=10) as response:
    assert b'noVNC' in response.read()
for attempt in range(30):
    result=subprocess.run(['docker','exec','dafeiyu','pgrep','-x','xfce4-panel'],capture_output=True)
    if result.returncode==0: break
    time.sleep(2)
else: raise AssertionError('XFCE panel did not start')
with socket.create_connection(('127.0.0.1',7860),timeout=15) as client:
    client.sendall(('GET /desktop/websockify HTTP/1.1\r\nHost: localhost:7860\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nAuthorization: Basic '+credentials+'\r\n\r\n').encode())
    assert b'101 Switching Protocols' in client.recv(4096)
subprocess.run(['docker','exec','dafeiyu','sh','-c',"grep -q '^ID=arch$' /etc/os-release && pacman -Q xfce4-session firefox tigervnc && test \"$(readlink -f /home/desktop)\" = /mnt/workspace/dafeiyu/desktop"],check=True)
print('PASS: Arch Linux XFCE desktop, persistent home, browser and authenticated noVNC WebSocket')
