#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Boot the real kernel, write private disks, rewind, and replay the session."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
from time_travel import BIN, ROOT, Session


def main():
    rf = Path(os.environ.get('BEMU_TT_RF', ROOT/'build/rf0.dsk'))
    rk = Path(os.environ.get('BEMU_TT_RK', ROOT/'build/rk0.dsk'))
    before = [hashlib.sha256(p.read_bytes()).digest() for p in (rf,rk)]
    with tempfile.TemporaryDirectory(prefix='bemu-tt-boot-', dir=os.environ.get('TMPDIR')) as temp:
        log = Path(temp)/'unix.btt'
        session = Session(['--record', log, rf, rk])
        try:
            session.until(rb'login:', timeout=60)
            os.write(session.master, b'root\r')
            session.until(rb'(?:^|[\r\n])# ', timeout=30)
            if os.environ.get('BEMU_TT_JASH'):
                os.write(session.master, b'/bin/jash -p\r')
                session.until(rb'Jash/11')
                session.until(rb'(?:^|[\r\n])# ')
            for text, expected in [
                (b'echo time-travel-ok >/tmp/ttest\r', None),
                (b'cat /tmp/ttest\r', b'time-travel-ok'),
                (b'echo rk-rollback-ok >/usr/ttest\r', None),
                (b'cat /usr/ttest\r', b'rk-rollback-ok'),
            ]:
                os.write(session.master, text)
                output = session.until(rb'(?:^|[\r\n])# ', timeout=30)
                if expected:
                    assert re.search(rb'[\r\n]' + expected + rb'[ \r\n]', output), output
            os.write(session.master, b'\x01m')
            session.until(rb'\(bemu-tt\)> ', timeout=20)
            position = int(re.search(rb'boundary=([0-9A-F]{16})', session.command('regs'))[1],16)
            present = session.state_hash()
            assert b'time-travel-ok' in session.command('console')
            assert session.state_hash() == present, 'console inspection changed logical state'
            session.command('back 100')
            assert session.state_hash() != present
            session.command(f'seek {position}')
            assert session.state_hash() == present, 'Unix reverse/forward replay diverged'
            session.command('seek 0')
            assert session.state_hash() != present
            session.command(f'seek {position}')
            assert session.state_hash() == present, 'full boot replay diverged'
        finally:
            session.close()
        one = subprocess.run([str(BIN),'--replay',str(log)], input=b'', capture_output=True, timeout=90)
        two = subprocess.run([str(BIN),'--replay',str(log)], input=b'blocked live input', capture_output=True, timeout=90)
        assert one.returncode == two.returncode == 0, (one.stderr[-2000:], two.stderr[-2000:])
        assert b'Replay verified' in one.stderr and b'Replay verified' in two.stderr
        assert one.stdout == two.stdout, 'two Unix replay transcripts differ'
        assert b'time-travel-ok' in one.stdout and b'rk-rollback-ok' in one.stdout
        assert before == [hashlib.sha256(p.read_bytes()).digest() for p in (rf,rk)], 'base image changed'
        print('time travel: Unix boot + RF/RK writes + reverse/seek + two verified replays + immutable bases PASS')


if __name__ == '__main__':
    main()
