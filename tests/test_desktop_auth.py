import importlib.util
import unittest
import tempfile,json,threading,http.client,hashlib,urllib.parse
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('desktop_auth',Path(__file__).parents[1]/'deploy/desktop_auth.py')
auth=importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


class DesktopAuthTest(unittest.TestCase):
    def test_signed_cookie_and_tampering(self):
        value=auth.issue('test-secret')
        self.assertTrue(auth.valid(value,'test-secret'))
        self.assertFalse(auth.valid(value,'different-secret'))
        self.assertFalse(auth.valid(value+'x','test-secret'))
        self.assertFalse(auth.valid('invalid','test-secret'))

    def test_expiry_and_future_timestamp(self):
        with patch.object(auth.time,'time',return_value=100000): value=auth.issue('test-secret')
        with patch.object(auth.time,'time',return_value=100000+auth.TTL+1): self.assertFalse(auth.valid(value,'test-secret'))
        with patch.object(auth.time,'time',return_value=99900): self.assertFalse(auth.valid(value,'test-secret'))

    def test_modelscope_iframe_login_uses_partitioned_secure_session(self):
        # The platform embeds ms.fun below modelscope.ai; SAMEORIGIN and Lax
        # prevent the actual login page/session from working in that frame.
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'desktop-auth.json'
            salt=bytes.fromhex('00'*16)
            config.write_text(json.dumps({'salt':salt.hex(),'password_hash':hashlib.pbkdf2_hmac('sha256',b'test-password',salt,600000).hex(),'session_secret':'test-secret'}))
            with patch.object(auth,'CONFIG',config):
                server=auth.ThreadingHTTPServer(('127.0.0.1',0),auth.Handler)
                worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
                try:
                    connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                    connection.request('GET','/desktop/login')
                    response=connection.getresponse();response.read()
                    self.assertEqual(response.status,200)
                    self.assertIsNone(response.getheader('X-Frame-Options'))
                    self.assertIn('https://www.modelscope.ai',response.getheader('Content-Security-Policy'))
                    connection.request('POST','/desktop/login',body=urllib.parse.urlencode({'username':'desktop','password':'test-password'}),headers={'Origin':'https://studio.example.ms.fun','X-Forwarded-Host':'studio.example.ms.fun','Content-Type':'application/x-www-form-urlencoded'})
                    response=connection.getresponse();response.read()
                    self.assertEqual(response.status,303)
                    cookie=response.getheader('Set-Cookie')
                    for attribute in ['HttpOnly','SameSite=None','Secure','Partitioned']:self.assertIn(attribute,cookie)
                    connection.close()
                finally:
                    server.shutdown();server.server_close();worker.join()

if __name__=='__main__': unittest.main()
