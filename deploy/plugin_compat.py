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
    storage=plugins/'meme_manager/backend/packs/storage.py'
    if storage.is_file():
        source=storage.read_text(encoding='utf-8')
        # /tmp and the official persistent mount are separate filesystems.
        # shutil.move retains rename on one filesystem and copies across mounts.
        before='prepared_pack_dir.rename(target_pack_dir)'
        after='shutil.move(str(prepared_pack_dir), str(target_pack_dir))'
        if before in source:
            storage.write_text(source.replace(before,after,1),encoding='utf-8')
            print('[plugins] Meme pack installation supports a separate persistent filesystem.')
