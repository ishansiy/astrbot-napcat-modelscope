"""Regression: recreating the container must never restore image defaults over user data."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).parents[1]/'deploy/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class PersistenceTest(unittest.TestCase):
    def test_persistent_user_configuration_wins_on_recreation(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            image=base/'app/config'
            image.mkdir(parents=True)
            (image/'webui.json').write_text('image-default')
            (image/'new-default.json').write_text('new-file')
            persistent=base/'mnt/workspace/napcat'
            persistent.mkdir(parents=True)
            (persistent/'webui.json').write_text('user-customized')
            (persistent/'login.session').write_text('existing-login')
            bootstrap.link_directory(image,persistent)
            self.assertTrue(image.is_symlink())
            self.assertEqual((image/'webui.json').read_text(),'user-customized')
            self.assertEqual((image/'login.session').read_text(),'existing-login')
            self.assertEqual((image/'new-default.json').read_text(),'new-file')
            bootstrap.link_directory(image,persistent)
            self.assertEqual((image/'webui.json').read_text(),'user-customized')

    def test_wrong_persistent_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            old=base/'old'; old.mkdir()
            link=base/'link'; link.symlink_to(old,target_is_directory=True)
            with self.assertRaises(RuntimeError):
                bootstrap.link_directory(link,base/'new')

if __name__=='__main__': unittest.main()
