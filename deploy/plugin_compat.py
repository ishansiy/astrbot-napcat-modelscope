"""Keep large upload staging files off the OSS-backed persistent mount."""
from pathlib import Path

def configure_upload_cache(plugins):
    path=plugins/'meme_manager/config.py'
    if not path.is_file():return
    original=path.read_text(encoding='utf-8')
    needle='TEMP_DIR = PLUGIN_DATA_DIR / "temp"'
    replacement='TEMP_DIR = Path("/tmp/dafeiyu-meme-manager")\nTEMP_DIR.mkdir(parents=True, exist_ok=True)'
    if needle in original:
        path.write_text(original.replace(needle,replacement,1),encoding='utf-8')
        print('[plugins] Meme Manager upload staging uses temporary local storage; installed packs remain persistent.')
