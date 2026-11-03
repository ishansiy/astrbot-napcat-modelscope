"""Provision a persistent desktop without replacing existing bot settings."""
import grp
import json
import os
import shutil
import subprocess
from pathlib import Path


def setup_desktop(base, creds, credentials):
    if 'desktop_password' not in creds:
        creds['desktop_password']=os.environ.get('DESKTOP_PASSWORD') or creds['dashboard_password']
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
    result=subprocess.run(['openssl','passwd','-6','-stdin'],input=creds['desktop_password']+'\n',text=True,capture_output=True,check=True)
    auth=Path('/run/desktop.htpasswd')
    auth.write_text('desktop:'+result.stdout.strip()+'\n')
    auth.chmod(0o640);os.chown(auth,0,grp.getgrnam('http').gr_gid)
    print('[desktop] Arch Linux XFCE profile ready; persistent home:',home)
