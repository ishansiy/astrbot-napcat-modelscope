import base64,hashlib,json,os,sqlite3,sys,tempfile,threading,unittest,urllib.parse,zipfile
from contextlib import closing
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).parents[1]/'deploy/local_plugins/astrbot_plugin_dafeiyu_backup'))
from core import FORMAT,build_archive,encrypt_archive,decrypt_archive,split_archive,digest,restore_bundle
from webdav import WebDAV,DavError

class BackupTest(unittest.TestCase):
    def test_live_wal_encrypted_roundtrip_preserves_memory_plugins_and_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);root=directory/'source';(root/'astrbot/plugins/example').mkdir(parents=True);(root/'desktop/Documents/backups').mkdir(parents=True)
            (root/'astrbot/plugins/example/main.py').write_text('print("plugin")')
            (root/'desktop/Documents/backups/important.txt').write_text('desktop document')
            (root/'astrbot/cmd_config.json').write_text('{"persona":"fish"}')
            (root/'astrbot/backups').mkdir();(root/'astrbot/backups/old.zip').write_bytes(b'do not recurse')
            db=sqlite3.connect(root/'astrbot/memory.db');db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE memory (value TEXT)');db.execute('INSERT INTO memory VALUES (?)',('remember me',));db.commit()
            try:
                archive=directory/'source.zip'
                details=build_archive(root,{'astrbot':True,'desktop':True},archive,directory)
                self.assertIn('astrbot/memory.db',details['sqlite_snapshots'])
                with zipfile.ZipFile(archive) as z:
                    self.assertNotIn('astrbot/memory.db-wal',z.namelist());self.assertNotIn('astrbot/backups/old.zip',z.namelist())
                key=base64.urlsafe_b64encode(os.urandom(32)).decode();encrypted=directory/'encrypted';encrypt_archive(archive,encrypted,key)
                bundle=directory/'bundle';bundle.mkdir()
                parts=split_archive(encrypted,bundle,500)
                manifest={'format':FORMAT,'parts':parts,'encrypted_sha256':digest(encrypted),'archive_sha256':digest(archive)}
                (bundle/'manifest.json').write_text(json.dumps(manifest))
                result=restore_bundle(bundle,key,directory/'restored')
                self.assertEqual(result['sqlite_databases'],1)
                restored=directory/'restored'
                with closing(sqlite3.connect(restored/'astrbot/memory.db')) as snapshot:self.assertEqual(snapshot.execute('SELECT value FROM memory').fetchone()[0],'remember me')
                self.assertEqual((restored/'desktop/Documents/backups/important.txt').read_text(),'desktop document')
                self.assertTrue((restored/'astrbot/plugins/example/main.py').is_file())
                with self.assertRaises(ValueError):restore_bundle(bundle,key,restored)
                damaged=bundle/parts[0]['name'];damaged.write_bytes(b'changed')
                with self.assertRaises(ValueError):restore_bundle(bundle,key,directory/'damaged')
                self.assertFalse((directory/'damaged').exists())
            finally:db.close()

    def test_authentication_failure_never_leaves_plaintext_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.write_bytes(os.urandom(2048));encrypted=root/'encrypted'
            key=base64.urlsafe_b64encode(os.urandom(32)).decode();encrypt_archive(source,encrypted,key)
            data=bytearray(encrypted.read_bytes());data[30]^=1;encrypted.write_bytes(data)
            with self.assertRaises(Exception):decrypt_archive(encrypted,root/'plaintext',key)
            self.assertFalse((root/'plaintext').exists())

class DavHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def response(self,status,content=b''):
        self.send_response(status);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def authorized(self):
        if self.headers.get('Authorization')!='Basic '+base64.b64encode(b'user:password').decode():self.response(401);return False
        return True
    def do_MKCOL(self):
        if not self.authorized():return
        self.server.directories.add(self.path.rstrip('/')+'/');self.response(201)
    def do_PUT(self):
        if not self.authorized():return
        self.server.files[self.path]=self.rfile.read(int(self.headers['Content-Length']));self.response(201)
    def do_GET(self):
        if not self.authorized():return
        self.response(200,self.server.files[self.path]) if self.path in self.server.files else self.response(404)
    def do_PROPFIND(self):
        if not self.authorized():return
        if self.path not in self.server.directories:self.response(404);return
        paths=[self.path]
        if self.headers.get('Depth')=='1':paths.extend(sorted(p for p in self.server.directories if p.startswith(self.path) and p!=self.path))
        body='<d:multistatus xmlns:d="DAV:">'+''.join('<d:response><d:href>'+p+'</d:href></d:response>' for p in paths)+'</d:multistatus>'
        self.response(207,body.encode())
    def do_DELETE(self):
        if not self.authorized():return
        for key in list(self.server.files):
            if key.startswith(self.path):del self.server.files[key]
        self.server.directories.discard(self.path);self.response(204)

class WebDAVTest(unittest.TestCase):
    def test_upload_readback_and_retention_only_delete_this_installations_backups(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),DavHandler);server.files={};server.directories={'/'}
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        dav=WebDAV({'url':'http://127.0.0.1:'+str(server.server_port)+'/dav/测试/','username':'user','password':'password'})
        try:
            dav.ensure_collection()
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);content=b'Encrypted backup bytes';(path/'part-0000.bin').write_bytes(content)
                for number,owner in [(1,'ours'),(2,'other'),(3,'ours')]:
                    manifest={'format':FORMAT,'id':'dafeiyu-20261103T04000'+str(number)+'Z-'+('0'*7)+str(number),'installation_id':owner,'parts':[{'name':'part-0000.bin','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]}
                    dav.upload_bundle(path,manifest,lambda *args:None)
                removed=dav.cleanup('ours',1)
                self.assertEqual(len(removed),1)
                remaining=dav.list_names();self.assertEqual(len(remaining),2)
                self.assertTrue(any('040002' in x for x in remaining))
        finally:dav.close();server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
