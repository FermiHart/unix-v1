#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Validate the native artifact and its isolated V1 filesystem profile."""
import hashlib
from pathlib import Path
import struct
import sys


class Image:
    def __init__(self, path):
        self.data = Path(path).read_bytes()

    def inode(self, number):
        if not 1 <= number < 256:
            raise ValueError(f"invalid RF inode {number}")
        return struct.unpack_from('<16H', self.data, 1024 + (number - 1) * 32)

    def blocks(self, number):
        inode = self.inode(number)
        count = (inode[2] + 511) // 512
        result = []
        for pointer in inode[3:11]:
            if not pointer:
                continue
            self.check_block(pointer)
            if inode[0] & 0o10000:
                entries = struct.unpack_from('<256H', self.data, pointer * 512)
                result.extend(entry for entry in entries if entry)
            else:
                result.append(pointer)
        if len(result) < count:
            raise ValueError(f"truncated block list for inode {number}")
        for block in result:
            self.check_block(block)
        return result[:count]

    @staticmethod
    def check_block(number):
        if not 2 <= number < 432:
            raise ValueError(f"filesystem block {number} overlaps reserved RF space")

    def contents(self, number):
        size = self.inode(number)[2]
        return b''.join(self.data[b*512:(b+1)*512] for b in self.blocks(number))[:size]

    def find(self, name):
        number = 41
        for component in name.strip('/').split('/'):
            directory = self.contents(number)
            entries = {}
            for offset in range(0, len(directory), 10):
                ino, label = struct.unpack_from('<H8s', directory, offset)
                if ino:
                    entries[label.rstrip(b'\0').decode('ascii')] = ino
            number = entries[component]
        return number


def main():
    artifact, experimental, base = map(Path, sys.argv[1:])
    binary = artifact.read_bytes()
    header = struct.unpack_from('<8H', binary)
    if header != (0o407, len(binary)-16, 0, 0, 0, 0, 0, 0):
        raise ValueError('invalid native 0407 executable header')
    if len(binary) % 2 or len(binary) - 16 > 8192:
        raise ValueError('artifact exceeds the 8 KiB edition budget or is unaligned')
    current, original = Image(experimental), Image(base)
    if current.contents(current.find('/bin/jash')) != binary:
        raise ValueError('/bin/jash differs from the assembled artifact')
    for path in ('/bin/sh', '/etc/init', '/etc/getty'):
        if current.contents(current.find(path)) != original.contents(original.find(path)):
            raise ValueError(f'historical {path} was changed')
    start = 960 * 512
    if current.data[start:len(original.data)] != original.data[start:]:
        raise ValueError('original bootloader/kernel region was changed')
    for number in range(41, 256):
        if current.inode(number)[0] & 0o100000:
            current.blocks(number)
    print(f'PASS: native PDP-11 artifact, {len(binary)} bytes, SHA-256 {hashlib.sha256(binary).hexdigest()}')
    print('PASS: historical sh/init/getty and boot region preserved; no RF swap/boot overlap.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, struct.error) as error:
        sys.exit(f'Jash/11 image validation failed: {error}')
