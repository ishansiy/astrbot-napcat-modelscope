"""Launch the preinstalled graphical browser and verify an actual X11 window."""
import subprocess
import time

subprocess.run(['docker','exec','-d','-u','desktop','-e','HOME=/home/desktop','-e','DISPLAY=:99','-e','XDG_RUNTIME_DIR=/tmp/runtime-desktop','dafeiyu','firefox','--new-window','about:blank'],check=True)
for attempt in range(30):
    result=subprocess.run(['docker','exec','-e','DISPLAY=:99','dafeiyu','xwininfo','-root','-tree'],capture_output=True,text=True)
    if 'firefox' in result.stdout.lower(): break
    time.sleep(2)
else: raise AssertionError('Firefox did not open a graphical window')
print('PASS: Firefox opens a real window on the XFCE desktop')
subprocess.run(['docker','exec','dafeiyu','pkill','-u','desktop','-x','firefox'],check=False)
