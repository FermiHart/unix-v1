#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Command-level qualification against the native executable, using real PTYs."""
import contextlib
import fcntl
import os
from pathlib import Path
import random
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import unittest

sys.dont_write_bytecode = True
from time_travel import BIN, ROOT, Session, emit, fnv

PROMPT = rb'\(bemu-tt\)> '
MONITOR_COMMANDS = ('help', 'regs', 'devices', 'hash', 'disks', 'console',
                    'snap', 'snaps', 'restore', 'step', 'cycle', 'back',
                    'seek', 'continue', 'c', 'quit', 'q')


def position(session):
    output = session.command('regs')
    fields = re.search(rb'boundary=([0-9A-F]{16}) instructions=([0-9A-F]{16})', output)
    return tuple(int(value, 16) for value in fields.groups())


def drain(session):
    while select.select([session.master], [], [], 0)[0]:
        data = os.read(session.master, 65536)
        session.buffer += data
        session.transcript.extend(data)


class Commands(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='bemu-command-',
                                                     dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.counter = self.work/'counter.bin'
        emit(self.counter, [0x15C6, 0x0200, 0x0A00, 0x0A80, 0x101F, 0x1000, 0x01FC])

    @contextlib.contextmanager
    def monitor(self, *extra, program=None):
        session = Session(['--time-travel', *extra, '--test', program or self.counter])
        try:
            session.until(PROMPT)
            yield session
        finally:
            session.close()

    def run_cli(self, *args, expected=0, data=b'', **kwargs):
        result = subprocess.run([str(BIN), *map(str, args)], input=data,
                                capture_output=True, timeout=15, **kwargs)
        self.assertEqual(result.returncode, expected, result.stderr[-3000:])
        return result

    def test_all_inspection_commands_are_read_only(self):
        with self.monitor() as session:
            initial = session.state_hash()
            help_text = session.command('help')
            for name in MONITOR_COMMANDS:
                with self.subTest(command=name):
                    # Aliases are checked by execution below, not help formatting.
                    if name not in ('c', 'q'):
                        self.assertRegex(help_text, rb'\b' + name.encode() + rb'\b')
            for command, marker in [('regs', b'PSW='), ('devices', b'IRQ-RF='),
                                    ('disks', b'RF=CBF29CE484222325 RK=CBF29CE484222325'),
                                    ('console', b'[sanitized logical console'),
                                    ('snaps', b'snapshot=0000000000000000')]:
                with self.subTest(command=command):
                    self.assertIn(marker, session.command(command))
                    self.assertEqual(session.state_hash(), initial)
            self.assertEqual(position(session), (0, 0))

    def test_default_counts_hex_numbers_and_snapshot_restore(self):
        with self.monitor() as session:
            initial = session.state_hash()
            session.command('step')
            self.assertEqual(position(session), (1, 1))
            session.command('cycle')
            self.assertEqual(position(session), (2, 2))
            session.command('step 0xA')
            self.assertEqual(position(session), (12, 12))
            saved = session.state_hash()
            number = int(re.search(rb'snapshot=([0-9A-F]{16})', session.command('snap'))[1], 16)
            session.command('step 0xa')
            session.command('back')
            self.assertEqual(position(session), (21, 21))
            session.command('back 9')
            self.assertEqual(session.state_hash(), saved)
            session.command(f'restore {number}')
            self.assertEqual(session.state_hash(), saved)
            session.command('seek 0x0')
            self.assertEqual(session.state_hash(), initial)
            session.command('seek 12')
            self.assertEqual(session.state_hash(), saved)

    def test_every_monitor_command_rejects_extra_or_invalid_arguments(self):
        invalid = [name+' unexpected' for name in MONITOR_COMMANDS]
        invalid += ['restore', 'seek', 'unknown', 'step 0', 'cycle 0', 'back 0',
                    'step 1000001', 'cycle 1000001', 'back 1', 'seek 1',
                    'restore 999999', 'restore 18446744073709551616']
        for command in ('step', 'cycle', 'back', 'seek', 'restore'):
            invalid += [command+' '+value for value in
                        ('-1', '+1', '0x', '0xG', '1 2', '1x', '9223372036854775808')]
        with self.monitor() as session:
            initial = session.state_hash()
            for text in invalid:
                with self.subTest(command=text):
                    self.assertIn(b'Invalid command', session.command(text))
                    self.assertEqual(session.state_hash(), initial)

    def test_monitor_line_bounds_backspace_delete_and_recovery(self):
        with self.monitor() as session:
            initial = session.state_hash()
            for line in ('', '   '):
                self.assertNotIn(b'Invalid command', session.command(line))
            for line in ('x'*95, 'step 1'+' '*100):
                self.assertIn(b'Invalid command', session.command(line))
                self.assertEqual(session.state_hash(), initial)
            for line in ('regx\b s', 'regx\x7fs'):
                # Delete the typo; the first variant retains an invalid space.
                output = session.command(line)
                self.assertIn(b'Invalid command' if ' ' in line else b'PSW=', output)
            self.assertIn(b'PSW=', session.command('regx\bs'))
            self.assertEqual(session.state_hash(), initial)

    def test_max_forward_request_automatic_ring_and_pinned_initial(self):
        with self.monitor() as session:
            initial = session.state_hash()
            session.command('step 1000000')
            self.assertEqual(position(session), (1000000, 1000000))
            registers = session.command('regs')
            self.assertIn(f'R0={((1000000//3) & 0xffff):016X}'.encode(), registers)
            rows = re.findall(rb'snapshot=([0-9A-F]{16})boundary=([0-9A-F]{16})',
                              session.command('snaps'))
            self.assertEqual(len(rows), 8)
            self.assertEqual(len({row[0] for row in rows}), 8)
            self.assertIn((b'0000000000000000', b'0000000000000000'), rows)
            self.assertGreaterEqual(max(int(row[1], 16) for row in rows), 900000)
            session.command('restore 0')
            self.assertEqual(session.state_hash(), initial)

    def test_wait_cycles_are_not_instruction_steps(self):
        program = self.work/'wait.bin'
        emit(program, [0x15C6, 0x0200, 1, 0x01FE])
        with self.monitor(program=program) as session:
            session.command('cycle 10')
            self.assertEqual(position(session), (10, 2))
            self.assertIn(b'WAIT=0000000000000001', session.command('devices'))
            saved = session.state_hash()
            session.command('back')
            self.assertEqual(position(session), (1, 1))
            session.command('seek 10')
            self.assertEqual(session.state_hash(), saved)

    def test_console_sanitization_and_history_suppression(self):
        program = self.work/'controls.bin'
        words = [0x15C6, 0x0200]
        for value in (65, 27, 0, 127, 255, 9, 13, 10):
            words += [0x15DF, value, 0xFF76]
        emit(program, words+[0x01FF])
        with self.monitor(program=program) as session:
            session.command('step 20')
            saved = session.state_hash()
            view = session.command('console')
            self.assertIn(b'A....\t', view)
            self.assertNotIn(b'\x1b', view)
            self.assertNotIn(b'\0', view)
            session.command('seek 0')
            output = session.command('seek 20')
            self.assertNotIn(b'\x1b', output, 'seek repeated raw guest output')
            self.assertEqual(session.state_hash(), saved)

    def test_console_view_is_bounded_to_last_4096_bytes(self):
        program = self.work/'output.bin'
        emit(program, [0x15C6, 0x0200, 0x15DF, 65, 0xFF76, 0x01FC])
        with self.monitor(program=program) as session:
            session.command('step 10002')
            view = session.command('console')
            body = re.search(rb'\[sanitized logical console, last 4096 bytes\]\r?\n(A+)\r?\n', view)
            self.assertIsNotNone(body, view[-200:])
            self.assertEqual(len(body[1]), 4096)

    def test_seeded_seek_stress_matches_live_and_independent_replay(self):
        randomizer = random.Random(20261104)
        points = sorted({0, 1, 2, 3, 1023, 1024, 1025, 5000,
                         *[randomizer.randrange(4, 4999) for _ in range(32)]})
        witnesses = {}
        log = self.work/'seek.btt'
        with self.monitor('--record', log) as session:
            previous = 0
            for point in points:
                if point != previous:
                    session.command(f'cycle {point-previous}')
                self.assertEqual(position(session), (point, point))
                self.assertIn(f'R0={point//3:016X}'.encode(), session.command('regs'))
                witnesses[point] = session.state_hash()
                previous = point
            order = list(points)
            randomizer.shuffle(order)
            for point in order:
                session.command(f'seek {point}')
                self.assertEqual(session.state_hash(), witnesses[point], point)
        session = Session(['--time-travel', '--replay', log])
        try:
            session.until(PROMPT)
            randomizer.shuffle(order)
            for point in order:
                session.command(f'seek {point}')
                self.assertEqual(session.state_hash(), witnesses[point], point)
            for text in ('step 5001', 'cycle 5001', 'seek 5001'):
                self.assertIn(b'Invalid command', session.command(text))
            os.write(session.master, b'c\n')
            session.process.wait(timeout=10)
            drain(session)
            self.assertIn(b'Replay verified', session.transcript)
        finally:
            session.close()

    def test_continue_aliases_and_both_monitor_key_cases(self):
        for command, key in ((b'continue', b'm'), (b'c', b'M')):
            with self.subTest(command=command), self.monitor() as session:
                os.write(session.master, command+b'\n\x01'+key)
                session.until(PROMPT)
                boundary, instructions = position(session)
                self.assertGreater(boundary, 0)
                self.assertEqual(boundary, instructions)

    def test_paused_exit_aliases_and_host_controls_restore_terminal(self):
        for keys in (b'q\n', b'quit\n', b'\x05', b'\x01x', b'\x01X', b'\x18a', b'\x18A'):
            with self.subTest(keys=keys), self.monitor() as session:
                os.write(session.master, keys)
                session.process.wait(timeout=5)
                self.assertEqual(session.process.returncode, 0)

    def test_cli_help_trace_and_nonzero_guest_record_replay(self):
        help_result = self.run_cli('--help')
        for option in ('--help', '--trace', '--test', '--time-travel', '--record', '--replay'):
            if option != '--help':
                self.assertIn(option.encode(), help_result.stderr)
        for value in (42, 0):
            with self.subTest(r0=value):
                program, log = self.work/f'halt-{value}.bin', self.work/f'halt-{value}.btt'
                emit(program, [0x15C0, value, 0])
                expected = 0 if value == 42 else 1
                capture = self.run_cli('--trace', '--record', log, '--test', program, expected=expected)
                self.assertRegex(capture.stderr, rb'0000 15C0')
                self.assertEqual(capture.stdout, b'')
                replay = self.run_cli('--trace', '--replay', log, expected=expected)
                self.assertIn(b'Replay verified', replay.stderr)
                self.assertEqual(capture.stdout, replay.stdout)

    def test_record_refuses_symlink_collision_and_missing_parent(self):
        target = self.work/'sentinel'
        target.write_bytes(b'untouched')
        link = self.work/'session.btt'
        link.symlink_to(target)
        self.run_cli('--record', link, '--test', self.counter, expected=1)
        self.assertEqual(target.read_bytes(), b'untouched')
        self.run_cli('--record', self.work/'absent/session.btt', '--test', self.counter, expected=1)
        self.assertFalse((self.work/'absent').exists())

    def test_cli_rejects_a_third_disk_path_instead_of_silently_replacing_rk(self):
        disks = [self.work/name for name in ('rf.dsk', 'rk.dsk', 'extra.dsk')]
        for path in disks:
            path.write_bytes(bytes(512))
        self.run_cli('--time-travel', '--test', self.counter, *disks,
                     expected=2, data=b'quit\n')

    def test_default_image_lookup_is_private_and_volatile(self):
        images = self.work/'images'
        images.mkdir()
        for name in ('rf0.dsk', 'rk0.dsk'):
            (images/name).write_bytes(bytes(512))
        result = self.run_cli('--time-travel', cwd=self.work, data=b'disks\nquit\n')
        expected = f'{fnv(bytes(512)):016X}'.encode()
        self.assertIn(b'RF='+expected+b' RK='+expected, result.stderr)
        self.assertIn(b'Volatile timeline: no session file', result.stderr)
        self.assertFalse(list(self.work.glob('*.btt')))
        for name in ('rf0.dsk', 'rk0.dsk'):
            self.assertEqual((images/name).read_bytes(), bytes(512))

    def test_interrupted_replay_does_not_claim_final_verification(self):
        program, log = self.work/'halt.bin', self.work/'good.btt'
        emit(program, [0x15C0, 42, 0])
        self.run_cli('--record', log, '--test', program)
        session = Session(['--time-travel', '--replay', log])
        try:
            session.until(PROMPT)
            os.write(session.master, b'q\n')
            session.process.wait(timeout=5)
            drain(session)
            self.assertIn(b'Replay interrupted', session.transcript)
            self.assertNotIn(b'Replay verified', session.transcript)
        finally:
            session.close()

    def test_killed_recording_is_incomplete_and_not_verified(self):
        log = self.work/'killed.btt'
        session = Session(['--time-travel', '--record', log, '--test', self.counter])
        try:
            session.until(PROMPT)
            session.command('cycle 2000')
            session.process.kill()
            session.process.wait(timeout=5)
        finally:
            if session.process.poll() is None:
                session.process.kill()
                session.process.wait()
            # SIGKILL cannot execute the emulator's terminal cleanup.
            termios.tcsetattr(session.slave, termios.TCSANOW, session.attributes)
            fcntl.fcntl(session.slave, fcntl.F_SETFL, session.flags)
            os.close(session.master)
            os.close(session.slave)
        self.assertEqual(log.stat().st_size, 0)
        replay = self.run_cli('--replay', log, expected=1)
        self.assertNotIn(b'Replay verified', replay.stderr)

    def test_seeded_corruption_corpus_fails_before_guest_execution(self):
        program, log = self.work/'halt.bin', self.work/'good.btt'
        emit(program, [0x15C0, 42, 0])
        self.run_cli('--record', log, '--test', program)
        original = log.read_bytes()
        randomizer = random.Random(11002026)
        for case in range(64):
            with self.subTest(case=case):
                data = bytearray(original)
                offset = randomizer.randrange(len(data))
                data[offset] ^= 1 << randomizer.randrange(8)
                bad = self.work/'bad.btt'
                bad.write_bytes(data)
                result = self.run_cli('--replay', bad, expected=1)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'Replay verified', result.stderr)
                self.assertIn(b'boundary=0000000000000000 instructions=0000000000000000', result.stderr)

    def test_maximum_disk_sizes_are_admitted_and_restore(self):
        rf, rk = self.work/'rf.dsk', self.work/'rk.dsk'
        rf.write_bytes(bytes(1048576))
        rk.write_bytes(bytes(4194304))
        with self.monitor(rf, rk) as session:
            initial = session.state_hash()
            media = session.command('disks')
            self.assertIn(f'RF={fnv(rf.read_bytes()):016X}'.encode(), media)
            self.assertIn(f'RK={fnv(rk.read_bytes()):016X}'.encode(), media)
            session.command('step 10')
            session.command('restore 0')
            self.assertEqual(session.state_hash(), initial)

    def test_error_exit_restores_pty_and_stdin_flags(self):
        bad = self.work/'invalid.btt'
        bad.write_bytes(b'not a session')
        session = Session(['--replay', bad])
        try:
            session.process.wait(timeout=5)
            self.assertEqual(session.process.returncode, 1)
            self.assertEqual(termios.tcgetattr(session.slave), session.attributes)
            self.assertEqual(fcntl.fcntl(session.slave, fcntl.F_GETFL), session.flags)
        finally:
            if session.process.poll() is None:
                session.process.kill()
                session.process.wait()
            os.close(session.master)
            os.close(session.slave)


if __name__ == '__main__':
    unittest.main(verbosity=2)
