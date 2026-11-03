"""Install all bundled plugin requirements in the image, not at user startup."""
import subprocess
from pathlib import Path
command=['uv','pip','install','--python','/opt/astrbot-venv/bin/python','dashscope','imageio-ffmpeg','edge-tts==7.3.1']
for path in sorted(Path('/opt/plugin-seeds').glob('*/requirements.txt')):
    command.extend(['-r',str(path)])
subprocess.run(command,check=True)
