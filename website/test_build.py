# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.

"""Pure-stdlib checks for static-site staging and refusal boundaries."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ('hero-machine.svg', 'hero-machine-mobile.svg', 'unix-v1-in-action.gif',
         'unix-v1-boot.png', 'jash11-live.png', 'time-travel.png')


class SiteBuild(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='unix-site-test-')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)

    def build(self, target, root=ROOT):
        return subprocess.run([sys.executable, str(root/'website/build.py'), '--output', str(target)],
                              capture_output=True, text=True, timeout=20)

    def test_only_curated_files_are_staged_byte_identically(self):
        target = self.work/'site'
        result = self.build(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {'index.html', 'css/site.css', 'LICENSE'} | {'assets/'+name for name in MEDIA}
        self.assertEqual({str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()}, expected)
        for name in MEDIA:
            self.assertEqual((target/'assets'/name).read_bytes(), (ROOT/'readme'/name).read_bytes())
        self.assertEqual((target/'LICENSE').read_bytes(), (ROOT/'LICENSE').read_bytes())

    def test_nonempty_directory_is_refused_without_changes(self):
        target = self.work/'existing'
        target.mkdir()
        (target/'keep').write_bytes(b'user data')
        result = self.build(target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('existing files are never deleted', result.stderr)
        self.assertEqual((target/'keep').read_bytes(), b'user data')
        self.assertEqual(list(target.iterdir()), [target/'keep'])

    def test_existing_empty_directory_is_supported(self):
        target = self.work/'empty'
        target.mkdir()
        result = self.build(target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target/'index.html').is_file())

    def test_stale_media_are_refused_before_output_is_created(self):
        fixture = self.work/'source'
        files = ['website/build.py', 'website/index.html', 'website/css/site.css', 'LICENSE',
                 'readme/generate_media.py', 'bemu-pdp11/src/bemu_pdp11.basm',
                 'bemu-pdp11/src/time_travel.basm', 'jash11/src/jash11.basm']
        files += ['readme/'+name for name in MEDIA]
        for name in files:
            target = fixture/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, target)
        with (fixture/'bemu-pdp11/src/bemu_pdp11.basm').open('a') as changed:
            changed.write('\n; different source\n')
        target = self.work/'stale-output'
        result = self.build(target, fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('stale art:', result.stderr)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
