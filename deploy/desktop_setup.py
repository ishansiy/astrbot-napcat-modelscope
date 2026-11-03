"""Provision a persistent desktop without replacing existing bot settings."""
import hashlib
import json
import os
import shutil
import secrets
from pathlib import Path


def setup_desktop(base, creds, credentials):
    changed=False
    if 'desktop_password' not in creds:
        creds['desktop_password']=os.environ.get('DESKTOP_PASSWORD') or creds['dashboard_password']
        changed=True
    if 'desktop_session_secret' not in creds:
        creds['desktop_session_secret']=secrets.token_urlsafe(48)
        changed=True
    if changed:
        temp=credentials.with_suffix('.tmp')
        temp.write_text(json.dumps(creds,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.chmod(0o600)
        temp.replace(credentials)
    base.chmod(0o711)
    home=base/'desktop'
    home.mkdir(exist_ok=True)
    home.chmod(0o700)
    os.chown(home,1000,1000)
    link=Path('/home/desktop')
    if not link.is_symlink():
        if link.exists():
            for source in link.iterdir():
                target=home/source.name
                if not target.exists():
                    if source.is_dir(): shutil.copytree(source,target)
                    else: shutil.copy2(source,target)
            shutil.rmtree(link)
        link.symlink_to(home,target_is_directory=True)
    elif link.resolve()!=home.resolve():
        raise RuntimeError('Desktop home points to an unexpected location')
    for folder in ['Desktop','Documents','Downloads','.config']:
        target=home/folder
        if not target.exists():
            target.mkdir(); os.chown(target,1000,1000)
    panel=home/'.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
    default_panel=Path('/etc/xdg/xfce4/panel/default.xml')
    if not panel.exists() and default_panel.exists():
        panel.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(default_panel,panel)
        for item in panel.parents:
            if item==home: break
            os.chown(item,1000,1000)
        os.chown(panel,1000,1000)
    launchers={
        'AstrBot.desktop':'[Desktop Entry]\nType=Link\nName=AstrBot\nURL=http://127.0.0.1:7860/\nIcon=applications-internet\n',
        'NapCat.desktop':'[Desktop Entry]\nType=Link\nName=NapCat\nURL=http://127.0.0.1:7860/napcat/webui/\nIcon=applications-internet\n',
        'Files.desktop':'[Desktop Entry]\nType=Application\nName=Files\nExec=thunar\nIcon=system-file-manager\n',
        'Terminal.desktop':'[Desktop Entry]\nType=Application\nName=Terminal\nExec=xfce4-terminal\nIcon=utilities-terminal\n',
        'Firefox.desktop':'[Desktop Entry]\nType=Application\nName=Firefox\nExec=firefox\nIcon=firefox\n',
    }
    for name,text in launchers.items():
        target=home/'Desktop'/name
        if not target.exists():
            target.write_text(text);target.chmod(0o755);os.chown(target,1000,1000)
    runtime=Path('/tmp/runtime-desktop');runtime.mkdir(exist_ok=True)
    runtime.chmod(0o700);os.chown(runtime,1000,1000)
    cache=Path('/tmp/desktop-cache');cache.mkdir(exist_ok=True)
    os.chown(cache,1000,1000)
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',creds['desktop_password'].encode(),bytes.fromhex(salt),600000).hex()
    auth=Path('/run/desktop-auth.json')
    auth.write_text(json.dumps({'salt':salt,'password_hash':digest,'session_secret':creds['desktop_session_secret']}))
    auth.chmod(0o600)
    print('[desktop] Arch Linux XFCE profile ready; persistent home:',home)
