#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Check deterministic assembly, fail-closed publication, locks, and backups."""
import fcntl
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'jash11'


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def main():
    artifact = HERE / 'build/jash'
    with tempfile.TemporaryDirectory(prefix='jash11-package-', dir=os.environ.get('TMPDIR')) as temp:
        work = Path(temp)
        rebuilt = work / 'jash'
        subprocess.run([os.environ.get('BASM', 'basm'), '-f', 'bin', '-o', str(rebuilt),
                        str(HERE / 'src/jash11.basm')], check=True)
        assert rebuilt.read_bytes() == artifact.read_bytes(), 'assembly is not byte-identical'
        out = work / 'images'
        env = dict(os.environ, JASH11_OUTPUT_DIR=str(out), JASH11_ARTIFACT=str(artifact))

        def build(success=True):
            result = subprocess.run(['sh', str(HERE / 'tools/build-images.sh')],
                                    env=env, capture_output=True, text=True, timeout=30)
            if (result.returncode == 0) != success:
                raise AssertionError(result.stdout + result.stderr)
            return result

        build()
        before = {name: digest(out / name) for name in ('rf0.dsk', 'rk0.dsk')}
        with (out / 'rf0.dsk').open('r+b') as live:
            inode = os.fstat(live.fileno()).st_ino
            build()
            assert (out / 'rf0.dsk').stat().st_ino != inode, 'live image was truncated in place'
            previous = [p for p in out.glob('previous.*/rf0.dsk') if p.stat().st_ino == inode]
            assert len(previous) == 1, 'previous image inode was not retained'
            assert previous[0].with_name('rk0.dsk').is_file(), 'previous RK image was not retained'
            live.seek(-1, 2)
            live.write(b'Z')
            live.flush()
            assert previous[0].read_bytes()[-1:] == b'Z', 'live writes no longer reach retained image'
            assert digest(out / 'rf0.dsk') == before['rf0.dsk'], 'live write corrupted replacement'
        invalid = work / 'invalid'
        data = bytearray(artifact.read_bytes())
        data[:2] = b'\0\0'
        invalid.write_bytes(data)
        env['JASH11_ARTIFACT'] = str(invalid)
        build(False)
        assert all(digest(out / name) == value for name, value in before.items()), 'failed build changed disks'
        assert not list(out.glob('.images.*')), 'failed build left staging directories'
        oversized = work / 'oversized'
        oversized.write_bytes(struct.pack('<8H', 0o407, 8194, 0, 0, 0, 0, 0, 0) + bytes(8194))
        env['JASH11_ARTIFACT'] = str(oversized)
        build(False)
        assert all(digest(out / name) == value for name, value in before.items()), 'budget failure changed disks'
        env['JASH11_ARTIFACT'] = str(artifact)
        with (out / '.image-build.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = build(False)
            assert 'Another image build' in result.stderr, 'concurrent build was not rejected'
        print('packaging: deterministic bytes, memory cap, failed-build isolation, live-inode backup, and lock PASS')


if __name__ == '__main__':
    main()
