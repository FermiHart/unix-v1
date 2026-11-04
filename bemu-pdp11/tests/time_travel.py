#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Black-box time-travel tests. Python drives the PTY, not the emulator."""
import hashlib
import fcntl
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / 'bemu-pdp11/bemu-pdp11'


class Session:
    def __init__(self, args):
        self.master, self.slave = os.openpty()
        self.attributes = termios.tcgetattr(self.slave)
        self.flags = fcntl.fcntl(self.slave, fcntl.F_GETFL)
        self.process = subprocess.Popen([str(BIN), *map(str, args)], stdin=self.slave,
                                        stdout=self.slave, stderr=self.slave)
        self.buffer = b''
        self.transcript = bytearray()
        self.in_monitor = False

    def until(self, pattern, timeout=10):
        expression = re.compile(pattern, re.S)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = expression.search(self.buffer)
            if found:
                result = self.buffer[:found.end()]
                self.buffer = self.buffer[found.end():]
                self.in_monitor = b'(bemu-tt)> ' in result
                return result
            ready, _, _ = select.select([self.master], [], [], .02)
            if ready:
                data = os.read(self.master, 65536)
                self.buffer += data
                self.transcript.extend(data)
            if self.process.poll() is not None and not ready:
                break
        raise AssertionError(f'waiting for {pattern!r}: {self.buffer[-4000:]!r}')

    def command(self, text):
        self.in_monitor = False
        os.write(self.master, text.encode() + b'\n')
        return self.until(rb'\(bemu-tt\)> ')

    def state_hash(self):
        return re.search(rb'hash=([0-9A-F]{16})', self.command('hash'))[1]

    def close(self):
        if self.process.poll() is None:
            os.write(self.master, b'quit\n' if self.in_monitor else b'\x05')
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                raise AssertionError('time-travel monitor failed to exit')
        assert self.process.returncode == 0, bytes(self.transcript[-2000:])
        assert termios.tcgetattr(self.slave) == self.attributes, 'time-travel exit left the terminal raw'
        assert fcntl.fcntl(self.slave, fcntl.F_GETFL) == self.flags, 'time-travel exit changed stdin flags'
        os.close(self.master)
        os.close(self.slave)


def emit(path, words):
    path.write_bytes(struct.pack('<' + 'H'*len(words), *words))


def basic(work):
    program = work / 'counter.bin'
    emit(program, [0x15C6, 0x0200, 0x0A00, 0x0A80, 0x101F, 0x1000, 0x01FC])
    log = work/'counter-session.btt'
    session = Session(['--time-travel', '--record', log, '--test', program])
    try:
        session.until(rb'\(bemu-tt\)> ')
        initial = session.state_hash()
        for invalid in ('step -1', 'step 0', 'step 1000001', 'seek -1', 'seek 0x',
                        'restore 999999', 'hash unexpected', 'snap unexpected',
                        'quit unexpected', 'step 18446744073709551616'):
            assert b'Invalid command' in session.command(invalid), invalid
            assert session.state_hash() == initial, f'invalid monitor command mutated state: {invalid}'
        session.command('step 2')
        second = session.state_hash()
        assert second != initial
        assert b'PSW=' in session.command('regs')
        assert session.state_hash() == second, 'register inspection changed guest state'
        snap = re.search(rb'snapshot=([0-9A-F]{16})', session.command('snap'))[1].decode()
        session.command('step 3')
        assert session.state_hash() != second
        session.command('back 3')
        assert session.state_hash() == second, 'instruction reverse-step did not reproduce state'
        assert b'snapshot=' in session.command('snaps')
        session.command('restore 0x' + snap)
        assert session.state_hash() == second, 'CPU/RAM/control state did not restore'
        session.command('restore 0')
        assert session.state_hash() == initial
        assert b'Invalid command' in session.command('seek 999999999')
        assert session.state_hash() == initial
        session.command('step 1100')
        future = session.state_hash()
        session.command('seek 0')
        assert session.state_hash() == initial
        session.command('step 1100')
        assert session.state_hash() == future, 'journal replay did not reproduce future'
        session.command('step 1100')       # rejoin the live frontier and append new history
        later = session.state_hash()
        assert later != future
        for _ in range(8):
            assert b'snapshot=' in session.command('snap')
        assert b'Invalid command' in session.command('restore 0x'+snap), 'evicted snapshot id was reused'
        assert session.state_hash() == later
        session.command('restore 0')       # the initial checkpoint is never evicted
        assert session.state_hash() == initial
        session.command('seek 2200')
        assert session.state_hash() == later
    finally:
        session.close()
    replay = subprocess.run([str(BIN),'--replay',str(log)],input=b'',capture_output=True,timeout=10)
    assert replay.returncode == 0 and b'Replay verified' in replay.stderr, replay.stderr
    print('time travel: boundary counters + full-state snapshots PASS')


def disks(work):
    program = work / 'disks.bin'
    words = [0x15C6, 0x0200]
    for value, address in [(0xA55A, 0x1000), (0x5AA5, 0x1002), (0, 0xFF36),
                           (0, 0xFF38), (0x1000, 0xFF34), (0xFFFF, 0xFF32),
                           (3, 0xFF30), (0, 0xFF0A), (0x1002, 0xFF08),
                           (0xFFFF, 0xFF06), (3, 0xFF04)]:
        words += [0x15DF, value, address]
    words += [0x0A80, 0x01FE]
    emit(program, words)
    rf, rk = work/'rf.dsk', work/'rk.dsk'
    rf.write_bytes(bytes(512))
    rk.write_bytes(bytes(512))
    rf.chmod(0o400); rk.chmod(0o400)
    before = [hashlib.sha256(p.read_bytes()).digest() for p in (rf, rk)]
    log = work/'disk-session.btt'
    session = Session(['--time-travel', '--record', log, '--test', program, rf, rk])
    try:
        session.until(rb'\(bemu-tt\)> ')
        initial = session.state_hash()
        base_disks = re.search(rb'RF=([0-9A-F]{16}) RK=([0-9A-F]{16})', session.command('disks')).groups()
        session.command('step 50')
        assert session.state_hash() != initial
        changed_disks = re.search(rb'RF=([0-9A-F]{16}) RK=([0-9A-F]{16})', session.command('disks')).groups()
        expected = tuple(f'{fnv(struct.pack("<H", value)+bytes(510)):016X}'.encode()
                         for value in (0xA55A,0x5AA5))
        assert changed_disks == expected, 'DMA changed the wrong private drive/data'
        assert before == [hashlib.sha256(p.read_bytes()).digest() for p in (rf, rk)]
        session.command('restore 0')
        assert session.state_hash() == initial, 'private disk versions were not restored'
        assert re.search(rb'RF=([0-9A-F]{16}) RK=([0-9A-F]{16})', session.command('disks')).groups() == base_disks
    finally:
        session.close()
    replay = subprocess.run([str(BIN), '--replay', str(log)], input=b'', capture_output=True, timeout=20)
    assert replay.returncode == 0 and b'Replay verified' in replay.stderr, replay.stderr
    print('time travel: RF/RK private writes + rollback + immutable bases PASS')


def recording(work):
    program, log = work/'uart.bin', work/'session.btt'
    setup = [0x15C6,0x2000,0x15DF,0x0100,0x0040,0x15DF,0x00C0,0x0042,
             0x15DF,0x0040,0xFF66]
    uart = [0x15C1,0xFF70,0x15C2,4,
                   0x8BC9,0x80FE,0x9C40,2,0x9031,6,0x0AC2,0x02F8,
                   0x15C0,42,0]
    words = [0x005F,0x0200]          # entry away from the vector table
    words += [0]*((0x0100-len(words)*2)//2)
    words += [0x1026,0x0A9F,0x1800,0x1580,2]  # clock handler preserves R0
    words += [0]*((0x0200-len(words)*2)//2)
    words += setup
    words += [0x0BDF,0x1800,0x03FD]  # wait until a clock IRQ really increments RAM
    words += [0x15DF,126,0xFF76]     # '~' proves the clock path ran before input
    words += uart
    emit(program, words)
    session = Session(['--record', log, '--test', program])
    try:
        session.until(rb'Bemu time travel:')
        session.until(b'~')
        os.write(session.master, b'ABCD')
        session.until(b'ABCD')
        session.process.wait(timeout=15)
        assert session.process.returncode == 0, bytes(session.transcript[-2000:])
    finally:
        session.close()
    assert log.is_file() and log.stat().st_mode & 0o777 == 0o600
    data = log.read_bytes()
    state_size, rf_size, rk_size = struct.unpack_from('<Q', data, 16)[0], struct.unpack_from('<Q', data,32)[0], struct.unpack_from('<Q',data,40)[0]
    frames = data[128+state_size+rf_size+rk_size:-80]
    assert any(frames[n+9] == 1 for n in range(0,len(frames),32)), 'clock IRQ was not recorded'
    replay = subprocess.run([str(BIN), '--replay', str(log)], input=b'ignored live input',
                            capture_output=True, timeout=20)
    assert replay.returncode == 0, replay.stderr
    assert replay.stdout == b'~ABCD', replay.stdout
    assert b'Replay verified' in replay.stderr, replay.stderr
    original = log.read_bytes()
    collision = subprocess.run([str(BIN), '--record', str(log), '--test', str(program)],
                               input=b'', capture_output=True, timeout=5)
    assert collision.returncode != 0 and log.read_bytes() == original
    malformed(work, original)
    for label, physical, logical in [('unknown-prefix',b'\x01qBC',b'\x01qBC'),
                                      ('literal-prefix',b'\x01\x01xBC',b'\x01xBC')]:
        extra = work/f'{label}.btt'
        session = Session(['--record',extra,'--test',program])
        try:
            session.until(rb'Bemu time travel:')
            session.until(b'~')
            os.write(session.master,physical)
            session.until(re.escape(logical))
            session.process.wait(timeout=10)
        finally:
            session.close()
        data = extra.read_bytes()
        offset = 128+struct.unpack_from('<Q',data,16)[0]
        if label == 'unknown-prefix':
            assert any(data[n+10] == 2 for n in range(offset,len(data)-80,32)), 'two-byte delivery was not recorded'
        result = subprocess.run([str(BIN),'--replay',str(extra)],input=b'',capture_output=True,timeout=10)
        assert result.returncode == 0 and result.stdout == b'~'+logical and b'Replay verified' in result.stderr
    print('time travel: private session record + clock/input replay + exclusive output PASS')


def fnv(data, seed=0xCBF29CE484222325):
    for value in data:
        seed = ((seed ^ value) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return seed


def malformed(work, original):
    state_size = struct.unpack_from('<Q', original, 16)[0]
    dev_size = struct.unpack_from('<Q', original, 24)[0]
    cpu_size = state_size-dev_size-37
    rf_size, rk_size = struct.unpack_from('<QQ', original, 32)
    frames_at = 128+state_size+rf_size+rk_size

    def reseal(data, initial=False):
        if initial:
            value = fnv(data[:64] + data[72:frames_at])
            struct.pack_into('<Q', data, 64, value)
        value = struct.unpack_from('<Q', data, 64)[0]
        for offset in range(frames_at, len(data)-80, 32):
            value = fnv(data[offset:offset+24], value)
            struct.pack_into('<Q', data, offset+24, value)
        struct.pack_into('<Q', data, len(data)-40, value)
        struct.pack_into('<Q', data, len(data)-8, fnv(data[-80:-8]))

    cases = []
    for label, offset in [('magic',0), ('version',8), ('reserved',96),
                          ('initial-bytes',128+123), ('frame-hash',frames_at+24),
                          ('footer-count',len(original)-72)]:
        data = bytearray(original)
        data[offset] ^= 1
        cases.append((label, data, True))
    for label, offset, value in [('state-size',16,2**63), ('RF-cap',32,1048578),
                                  ('RK-cap',40,4194816), ('end-position',len(original)-64,1000000001)]:
        data = bytearray(original)
        struct.pack_into('<Q',data,offset,value)
        if label == 'end-position':
            struct.pack_into('<Q',data,len(data)-8,fnv(data[-80:-8]))
        cases.append((label,data,True))
    for label, offset, value in [('PSW-type',128+65552,2), ('priority',128+65556,8),
                                  ('WAIT-type',128+cpu_size+dev_size,2),
                                  ('IRQ-type',128+cpu_size,2),
                                  ('FIFO-count',128+cpu_size+89,65)]:
        data = bytearray(original)
        data[offset] = value
        reseal(data, True)
        cases.append((label,data,True))
    for label, offset, value in [('input-count',frames_at+10,3), ('frame-padding',frames_at+13,1)]:
        data = bytearray(original)
        data[offset] = value
        reseal(data)
        cases.append((label,data,True))
    data = bytearray(original)
    data[frames_at+10] = 0
    data[frames_at+11] = 7
    reseal(data)
    cases.append(('unused-payload',data,True))
    data = bytearray(original)
    struct.pack_into('<Q',data,frames_at+32,struct.unpack_from('<Q',data,frames_at)[0])
    reseal(data)
    cases.append(('event-order',data,True))
    data = bytearray(original)
    data[-48] ^= 1                       # final state hash: valid envelope, wrong execution witness
    struct.pack_into('<Q',data,len(data)-8,fnv(data[-80:-8]))
    cases.append(('semantic-divergence',data,False))
    cases += [('truncated',original[:-1],True), ('extra-byte',original+b'X',True)]
    for label, data, before_execution in cases:
        path = work/f'bad-{label}.btt'
        path.write_bytes(data)
        result = subprocess.run([str(BIN),'--replay',str(path)], input=b'', capture_output=True, timeout=10)
        assert result.returncode == 1 and b'Replay verified' not in result.stderr, (label,result.stderr)
        if before_execution:
            assert result.stdout == b'', (label,result.stdout)
            assert b'boundary=0000000000000000 instructions=0000000000000000' in result.stderr, label
    fifo = work/'session.fifo'
    os.mkfifo(fifo)
    result = subprocess.run([str(BIN),'--replay',str(fifo)], input=b'', capture_output=True, timeout=3)
    assert result.returncode == 1, 'FIFO input was not rejected'
    sparse = work/'too-many-events.btt'
    sparse.write_bytes(original[:128])
    with sparse.open('r+b') as stream:
        stream.truncate(frames_at+(1048576+1)*32+80)
    result = subprocess.run([str(BIN),'--replay',str(sparse)], input=b'', capture_output=True, timeout=3)
    assert result.returncode == 1 and not result.stdout
    for args in (['--record'], ['--replay'], ['--replay','unused','--test','unused'],
                 ['--record','unused','--replay','unused'], ['--time-travel','--unknown']):
        result = subprocess.run([str(BIN),*args], input=b'', capture_output=True, timeout=3)
        assert result.returncode == 2, (args,result.stderr)
    help_result = subprocess.run([str(BIN),'--help'],input=b'',capture_output=True,timeout=3)
    assert help_result.returncode == 0 and b'--record' in help_result.stderr
    print('time travel: malformed dimensions/types/order/checksums, divergence, FIFO, event cap, CLI failures PASS')


def exits_and_capacity(work):
    counter = work/'exit-counter.bin'
    emit(counter,[0x15C6,0x0200,0x0A80,0x01FE])
    empty = work/'empty-session.btt'
    session = Session(['--time-travel','--record',empty,'--test',counter])
    session.until(rb'\(bemu-tt\)> ')
    session.close()
    data = empty.read_bytes()
    assert struct.unpack_from('<Q',data,len(data)-72)[0] == 0
    result = subprocess.run([str(BIN),'--replay',str(empty)],input=b'',capture_output=True,timeout=5)
    assert result.returncode == 0 and b'Replay verified' in result.stderr
    for index, keys in enumerate((b'\x05',b'\x01x',b'\x18a')):
        log = work/f'exit-{index}.btt'
        session = Session(['--record',log,'--test',counter])
        try:
            session.until(rb'Bemu time travel:')
            os.write(session.master,keys)
            session.process.wait(timeout=10)
            assert session.process.returncode == 0
        finally:
            session.close()
        assert struct.unpack_from('<Q',log.read_bytes(),log.stat().st_size-24)[0] == 1
        result = subprocess.run([str(BIN),'--replay',str(log)], input=b'', capture_output=True, timeout=10)
        assert result.returncode == 0 and b'Replay verified' in result.stderr, result.stderr
    program, log = work/'console-cap.bin', work/'incomplete-capacity.btt'
    emit(program,[0x15C6,0x0200,0x15C1,0xFF76,0x15C0,65,0x9009,0x01FE])
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen([str(BIN),'--record',str(log),'--test',str(program)],
                                   stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
        try:
            process.wait(timeout=30)
            assert process.returncode == 1, 'console-cap overflow did not fail'
            errors.seek(0)
            assert b'bemu-tt:' in errors.read()
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            process.stdin.close()
    assert log.stat().st_size == 0, 'capacity failure published a complete recording'
    result = subprocess.run([str(BIN),'--replay',str(log)],input=b'',capture_output=True,timeout=3)
    assert result.returncode == 1 and not result.stdout
    print('time travel: recorded host exits + live console capacity + incomplete-session rejection PASS')


def image_bounds(work):
    program = work/'image-bound-counter.bin'
    emit(program,[0x15C6,0x0200,0x0A80,0x01FE])
    rf,rk = work/'bound-rf.dsk',work/'bound-rk.dsk'
    for label,rf_bytes,rk_bytes in [('odd-RF',3,512),('RF-cap',1048578,512),
                                  ('RK-align',512,513),('RK-cap',512,4194816)]:
        for path,size in ((rf,rf_bytes),(rk,rk_bytes)):
            with path.open('wb') as output:
                output.truncate(size)
        recording = work/f'{label}.btt'
        result = subprocess.run([str(BIN),'--record',str(recording),'--test',str(program),str(rf),str(rk)],
                                input=b'',capture_output=True,timeout=5)
        assert result.returncode == 1 and not recording.exists(), (label,result.stderr)
    fifo = work/'base.fifo'
    os.mkfifo(fifo)
    rk.write_bytes(bytes(512))
    result = subprocess.run([str(BIN),'--time-travel','--test',str(program),str(fifo),str(rk)],
                            input=b'',capture_output=True,timeout=3)
    assert result.returncode == 1
    print('time travel: read-only image admission, size/alignment caps, nonblocking device rejection PASS')


def pending_devices(work):
    program, log = work/'pending.bin', work/'pending.btt'
    words = [0x15C6,0x2000]
    for value,address in [(0x00E0,0xFFFE),(0x0040,0xFF70),(0x0040,0xFF74),
                          (0x0040,0xFF66),(0x1234,0x1000),(0,0xFF36),(0,0xFF38),
                          (0x1000,0xFF34),(0xFFFF,0xFF32),(0x0043,0xFF30),
                          (0,0xFF0A),(0x1000,0xFF08),(0xFFFF,0xFF06),(0x0043,0xFF04),
                          (87,0xFF76)]:
        words += [0x15DF,value,address]
        if address == 0xFF66:
            words += [0x8BDF,0xFF66,0x80FD]  # actual clock DONE before readiness output
    words += [1,0x01FE]                    # WAIT; BR WAIT (priority 7 blocks IRQs)
    emit(program,words)
    rf,rk = work/'pending-rf.dsk',work/'pending-rk.dsk'
    rf.write_bytes(bytes(512)); rk.write_bytes(bytes(512))
    session = Session(['--time-travel','--record',log,'--test',program,rf,rk])
    try:
        session.until(rb'\(bemu-tt\)> ')
        os.write(session.master,b'continue\n')
        session.until(b'W')
        os.write(session.master,b'abc\x01m')
        session.until(rb'\(bemu-tt\)> ')
        devices = session.command('devices')
        assert b'WAIT=0000000000000001 FIFO=0000000000000002' in devices, devices
        for label in (b'IRQ-C',b'IRQ-RF',b'IRQ-RK',b'IRQ-RX',b'IRQ-TX'):
            assert label+b'=0000000000000001' in devices, devices
        present = session.state_hash()
        position = int(re.search(rb'boundary=([0-9A-F]{16})',session.command('regs'))[1],16)
        snapshot = re.search(rb'snapshot=([0-9A-F]{16})',session.command('snap'))[1].decode()
        session.command('cycle 10')
        session.command('restore 0x'+snapshot)
        assert session.state_hash() == present
        assert session.command('devices').count(b'=0000000000000001') >= 6
        session.command('seek 0')
        session.command(f'seek {position}')
        assert session.state_hash() == present, 'pending device/FIFO/WAIT replay diverged'
    finally:
        session.close()
    result = subprocess.run([str(BIN),'--replay',str(log)],input=b'',capture_output=True,timeout=10)
    assert result.returncode == 0 and b'Replay verified' in result.stderr, result.stderr
    print('time travel: pending clock/RF/RK/RX/TX IRQs + FIFO + WAIT checkpoint/replay PASS')


def main():
    with tempfile.TemporaryDirectory(prefix='bemu-tt-', dir=os.environ.get('TMPDIR')) as temp:
        work = Path(temp)
        basic(work)
        disks(work)
        recording(work)
        pending_devices(work)
        exits_and_capacity(work)
        image_bounds(work)


if __name__ == '__main__':
    main()
