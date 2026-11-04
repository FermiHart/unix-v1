#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Exercise host escape keys and terminal restoration through a real PTY."""
import fcntl
import os
import select
import subprocess
import sys
import termios
import time


def collect(master, process, seconds, until=None):
    output = bytearray()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ready, _, _ = select.select([master], [], [], .02)
        if ready:
            output.extend(os.read(master, 4096))
        if until is not None and until in output:
            return bytes(output)
        if process.poll() is not None:
            return bytes(output)
    return bytes(output)


def exercise(binary, fixture, keys, passthrough=None, expected_status=0):
    master, slave = os.openpty()
    attributes = termios.tcgetattr(slave)
    flags = fcntl.fcntl(slave, fcntl.F_GETFL)
    process = subprocess.Popen([binary, '--test', fixture], stdin=slave,
                               stdout=slave, stderr=slave, close_fds=True)
    try:
        collect(master, process, 1, b'emulator')
        if expected_status == 0:
            deadline = time.monotonic() + 2
            while termios.tcgetattr(slave)[3] & termios.ICANON:
                if time.monotonic() > deadline or process.poll() is not None:
                    raise AssertionError('emulator did not enter raw terminal mode')
                collect(master, process, .02)
        if passthrough is not None:
            sent, expected = passthrough
            os.write(master, sent)
            output = collect(master, process, 2, expected)
            if expected not in output or process.poll() is not None:
                raise AssertionError(f'escape passthrough failed: {output!r}')
        os.write(master, keys)
        collect(master, process, 2)
        if process.poll() is None:
            raise AssertionError(f'exit sequence {keys!r} did not close the emulator')
        if process.returncode != expected_status:
            raise AssertionError(f'exit sequence {keys!r}: status {process.returncode}')
        if termios.tcgetattr(slave) != attributes:
            raise AssertionError('terminal attributes were not restored')
        if fcntl.fcntl(slave, fcntl.F_GETFL) != flags:
            raise AssertionError('stdin status flags were not restored')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        os.close(master)
        os.close(slave)


def main():
    binary, fixture = sys.argv[1:]
    for sequence in (b'\x01x', b'\x01X', b'\x18a', b'\x18A', b'\x05'):
        exercise(binary, fixture, sequence)
    exercise(binary, fixture, b'\x05',
             (b'\x01q\x18b\x01\x01\x18\x18', b'\x01q\x18b\x01\x18'))
    exercise(binary, fixture + '.missing', b'', expected_status=1)
    print('host escapes + PTY/stdin restoration PASS')


if __name__ == '__main__':
    try:
        main()
    except AssertionError as error:
        sys.exit(f'host escape regression FAIL: {error}')
