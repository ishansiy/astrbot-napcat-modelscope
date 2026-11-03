"""Fetch the exact upstream plugin revisions recorded in plugins.lock.json."""
import io, json, shutil, tempfile, urllib.request, zipfile
from pathlib import Path
_archives={}
def fetch_plugin(spec, dest):
    url=f"https://codeload.github.com/{spec['repo']}/zip/{spec['revision']}"
    if url not in _archives:
        with urllib.request.urlopen(url,timeout=120) as response:
            _archives[url]=response.read()
    archive=zipfile.ZipFile(io.BytesIO(_archives[url]))
    with tempfile.TemporaryDirectory() as directory:
        base=Path(directory)
        for item in archive.infolist():
            if not (base/item.filename).resolve().is_relative_to(base.resolve()):
                raise ValueError('Unsafe archive path')
        archive.extractall(base)
        source=next(base.iterdir()) / spec.get('subdir','')
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns('.git','__pycache__'))
        print('Bundled plugin:',spec['name'],spec['revision'])

if __name__=='__main__':
    for spec in json.loads(Path(__file__).with_name('plugins.lock.json').read_text()):
        if not spec.get('runtime_download'):
            fetch_plugin(spec,Path('/opt/plugin-seeds')/spec['name'])
