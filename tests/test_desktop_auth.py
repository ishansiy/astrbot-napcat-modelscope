import importlib.util
import unittest
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

if __name__=='__main__': unittest.main()
