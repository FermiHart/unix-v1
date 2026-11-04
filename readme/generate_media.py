#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.

"""Capture real Bemu sessions and render public README media, without base writes."""
import argparse
from dataclasses import dataclass
import fcntl
from functools import lru_cache
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import tempfile
import termios
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
COPYRIGHT = 'Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>'
LICENSE = 'original unix-v1 terms; see ../LICENSE.'
SOURCES = ('bemu-pdp11/src/bemu_pdp11.basm', 'bemu-pdp11/src/time_travel.basm',
           'jash11/src/jash11.basm', 'readme/generate_media.py')
ASSETS = ('hero-machine.svg', 'hero-machine-mobile.svg', 'unix-v1-boot.png',
          'jash11-live.png', 'time-travel.png', 'unix-v1-in-action.gif')
BG, PANEL, INK = '#070a12', '#0d1220', '#f5f1df'
TEAL, GOLD, VIOLET, MUTED = '#65fbd2', '#ffcc66', '#a4afff', '#8794b8'
COLORS = {'black': '#182030', 'red': '#ff6b8a', 'green': '#65fbd2',
          'brown': '#ffcc66', 'blue': '#8ea1ff', 'magenta': '#d58cff',
          'cyan': '#65e3ef', 'white': '#e7eaf4', 'brightblack': '#8794b8',
          'brightred': '#ff839d', 'brightgreen': '#88ffdc',
          'brightbrown': '#ffe19e', 'brightblue': '#acb8ff',
          'brightmagenta': '#e9b0ff', 'brightcyan': '#78f5ff',
          'brightwhite': '#ffffff'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_id():
    result = hashlib.sha256(b'unix-v1/readme-media/v1\0')
    for name in SOURCES:
        data = (ROOT/name).read_bytes()
        result.update(name.encode()+b'\0'+struct.pack('<Q', len(data))+data)
    return result.hexdigest()


def run(command, cwd=ROOT, **kwargs):
    return subprocess.run(list(map(str, command)), cwd=cwd, check=True, timeout=90, **kwargs)


def hero(identity, guest_bytes, mobile=False):
    width, height = (640, 900) if mobile else (1200, 640)
    x, cx, cy, radius = (40, 320, 420, 146) if mobile else (60, 936, 262, 183)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             '<!-- '+html.escape(COPYRIGHT)+' -->', '<!-- License: '+LICENSE+' -->',
             f'<metadata>source-id:{identity}</metadata>',
             '<title id="title">Unix V1: native Basm execution and time travel</title>',
             '<desc id="desc">Machine geometry links RAM, PSW, interrupts, clock, input and private RF/RK disks. Decorative source-derived geometry, not a hardware attestation.</desc>',
             '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#070a12"/><stop offset=".6" stop-color="#111426"/><stop offset="1" stop-color="#071c21"/></linearGradient>',
             '<radialGradient id="orb"><stop stop-color="#65fbd2" stop-opacity=".16"/><stop offset="1" stop-color="#65fbd2" stop-opacity="0"/></radialGradient>',
             '<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#8794b8" stroke-opacity=".06"/></pattern></defs>',
             f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24" fill="url(#bg)" stroke="#333d5b"/>',
             f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="24" fill="url(#grid)"/>']

    def text(tx, ty, value, size=16, color=INK, weight='400', anchor='start', spacing=0):
        parts.append(f'<text x="{tx}" y="{ty}" fill="{color}" font-family="DejaVu Sans Mono,monospace" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{spacing}">{html.escape(value)}</text>')

    text(x, 58 if mobile else 62, 'FERMI HART / MACHINE GEOMETRY', 12 if mobile else 15, TEAL, '700', spacing=1.6)
    text(x, 150 if mobile else 167, 'UNIX V1', 78 if mobile else 88, INK, '700', spacing=-3)
    text(x, 193 if mobile else 216, 'THE FUTURE STARTED HERE.', 19 if mobile else 21, GOLD, '700')
    text(x, 232 if mobile else 268, 'REAL PDP-11 CODE. NATIVE BASM.', 14 if mobile else 17, VIOLET)
    if not mobile:
        text(x, 325, 'Boot the kernel. Write a file.', 21)
        text(x, 359, 'Rewind the execution.', 21, TEAL)
        text(x, 413, 'A RESTORED SYSTEM. A NEW WAY TO EXPLORE IT.', 12, MUTED)
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{radius+45}" fill="url(#orb)"/>')
    for r, opacity in ((radius+20, '.2'), (radius, '.4'), (radius*.63, '.2')):
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="{TEAL}" stroke-opacity="{opacity}"/>')
    points = [(cx+radius*math.cos(-math.pi/2+i*math.pi/3),
               cy+radius*math.sin(-math.pi/2+i*math.pi/3)) for i in range(6)]
    for i, point in enumerate(points):
        for j in range(i+1, len(points)):
            other = points[j]
            parts.append(f'<path d="M{point[0]:.1f},{point[1]:.1f}L{other[0]:.1f},{other[1]:.1f}" stroke="{GOLD if (i+j)%2 else VIOLET}" stroke-opacity=".22" fill="none"/>')
    for i, label in enumerate(('RAM', 'PSW', 'IRQ', 'CLOCK', 'INPUT', 'RF / RK')):
        px, py = points[i]
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{TEAL}" stroke="#d9fff0" stroke-width="1.2"/>')
        text(round(px), round(py-17 if i < 3 else py+27), label, 11, TEAL, '700', 'middle', 1)
    seed = bytes.fromhex(identity)
    for i in range(24):
        angle = i*math.pi/12
        r = radius+20
        px, py = cx+r*math.cos(angle), cy+r*math.sin(angle)
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{2+seed[i]%3}" fill="{(TEAL,GOLD,VIOLET,"#d58cff")[seed[i]%4]}"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="49" fill="#111b25" stroke="{GOLD}" stroke-width="1.5"/>')
    text(cx, cy-4, 'PDP-11', 16, INK, '700', 'middle')
    text(cx, cy+18, '11/20', 13, GOLD, '700', 'middle')
    cards = [('BEMU', '100% BASM', TEAL), ('JASH / 11', f'{guest_bytes:,} B', GOLD),
             ('HISTORY', 'SNAP / BACK / SEEK', VIOLET), ('RF / RK', 'PRIVATE VERSIONS', '#d58cff')]
    for i, (label, value, color) in enumerate(cards):
        tx = 40+(i%2)*288 if mobile else 60+i*278
        ty = 650+(i//2)*94 if mobile else 482
        parts.append(f'<rect x="{tx}" y="{ty}" width="{272 if mobile else 263}" height="80" rx="10" fill="#0b111e" stroke="#293348"/>')
        text(tx+16, ty+26, label, 11, MUTED, '700', spacing=1)
        text(tx+16, ty+56, value, 15 if i > 1 else 23, color, '700')
    if mobile:
        text(40, 856, 'LINUX X86-64 / ORIGINAL UNIX-V1 TERMS', 11, MUTED)
        text(40, 878, 'SOURCE / '+identity[:24].upper(), 10, MUTED)
    else:
        text(60, 610, 'LINUX X86-64 / ORIGINAL UNIX-V1 TERMS', 12, MUTED)
        text(1140, 610, 'SOURCE / '+identity[:24].upper(), 10, MUTED, anchor='end')
    return '\n'.join(parts+['</svg>', ''])


@dataclass
class Frame:
    cells: list
    cursor: tuple
    phase: str
    duration: int = 90


class Capture:
    """Drive a real emulator PTY; terminal content is never synthesized."""
    def __init__(self, binary, arguments):
        import pyte
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 96, 0, 0))
        self.attributes = termios.tcgetattr(self.slave)
        self.flags = fcntl.fcntl(self.slave, fcntl.F_GETFL)
        self.screen = pyte.Screen(96, 24)
        self.stream = pyte.ByteStream(self.screen)
        self.frames, self.raw = [], bytearray()
        self.pending = b''
        self.phase = '01 / BOOT THE RESTORED UNIX'
        self.last_frame = 0
        self.process = subprocess.Popen([str(binary), *map(str, arguments)],
                                        stdin=self.slave, stdout=self.slave, stderr=self.slave)

    def freeze(self, duration=90):
        cells = [[(cell.data, cell.fg, cell.bg, cell.bold, cell.reverse)
                  for cell in (self.screen.buffer[y][x] for x in range(96))] for y in range(24)]
        frame = Frame(cells, (self.screen.cursor.x, self.screen.cursor.y), self.phase, duration)
        if self.frames and frame.cells == self.frames[-1].cells and frame.phase == self.frames[-1].phase:
            self.frames[-1].duration += duration
        else:
            self.frames.append(frame)
        self.last_frame = time.monotonic()
        return frame

    def receive(self, timeout=.04):
        if select.select([self.master], [], [], timeout)[0]:
            data = os.read(self.master, 65536)
            self.raw.extend(data)
            self.pending += data
            self.stream.feed(data)
            if time.monotonic()-self.last_frame >= .085:
                self.freeze()

    def until(self, pattern, timeout=60):
        expression = re.compile(pattern, re.S)
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            match = expression.search(self.pending)
            if match:
                result, self.pending = self.pending[:match.end()], self.pending[match.end():]
                return result
            if self.process.poll() is not None:
                raise RuntimeError(f'emulator exited while waiting for {pattern!r}')
            self.receive()
        raise RuntimeError(f'timeout waiting for {pattern!r}: {self.pending[-300:]!r}')

    def type(self, text):
        for value in text.encode():
            os.write(self.master, bytes([value]))
            deadline = time.monotonic()+.035
            while time.monotonic() < deadline:
                self.receive(min(.01, max(0, deadline-time.monotonic())))

    def command(self, text, monitor=False, expected=None):
        self.type(text+'\n' if monitor else text+'\r')
        output = self.until(rb'\(bemu-tt\)> ' if monitor else rb'(?:^|[\r\n])(?:\x1b\[[0-9;]*m)*#(?:\x1b\[[0-9;]*m)* ')
        if expected is not None and not re.search(expected, output):
            raise RuntimeError(f'unexpected command result for {text!r}: {output!r}')
        self.freeze(800)
        return output

    def stop(self):
        if self.process.poll() is None:
            os.write(self.master, b'\x05')
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                raise RuntimeError('emulator failed to exit cleanly')
        try:
            assert self.process.returncode == 0, self.raw[-1000:]
            assert termios.tcgetattr(self.slave) == self.attributes, 'terminal attributes changed'
            assert fcntl.fcntl(self.slave, fcntl.F_GETFL) == self.flags, 'stdin flags changed'
        finally:
            os.close(self.master)
            os.close(self.slave)


def color(value, default):
    if value == 'default':
        return default
    if value in COLORS:
        return COLORS[value]
    if re.fullmatch('[0-9a-fA-F]{6}', value):
        return '#'+value
    return default


@lru_cache(maxsize=1)
def fonts():
    from PIL import ImageFont
    regular_path = subprocess.check_output(['fc-match', '-f', '%{file}', 'DejaVu Sans Mono'], text=True)
    bold_path = subprocess.check_output(['fc-match', '-f', '%{file}', 'DejaVu Sans Mono:style=Bold'], text=True)
    regular, bold = ImageFont.truetype(regular_path, 20), ImageFont.truetype(bold_path, 20)
    small = ImageFont.truetype(regular_path, 13)
    title = ImageFont.truetype(bold_path, 25)
    return regular, bold, small, title


def render(frame, proof=None):
    from PIL import Image, ImageDraw
    regular, bold, small, title = fonts()
    image = Image.new('RGB', (1280, 900), BG)
    draw = ImageDraw.Draw(image)
    for x in range(0, 1280, 32):
        draw.line((x, 0, x, 900), fill='#101624')
    draw.text((38, 25), 'FERMI HART / UNIX V1', font=small, fill=TEAL)
    draw.text((38, 51), frame.phase, font=title, fill=INK)
    draw.rounded_rectangle((30, 102, 1250, 795), radius=15, fill=PANEL, outline='#38415b', width=2)
    for x, fill in ((54, '#ff6b8a'), (77, GOLD), (100, TEAL)):
        draw.ellipse((x-5, 121, x+5, 131), fill=fill)
    draw.text((132, 116), 'BEMU / PDP-11/20 / NATIVE LINUX EXECUTABLE', font=small, fill=MUTED)
    draw.line((31, 145, 1248, 145), fill='#293348')
    for y, row in enumerate(frame.cells):
        for x, (character, fg, bg, is_bold, reverse) in enumerate(row):
            foreground, background = color(fg, '#e7eaf4'), color(bg, PANEL)
            if reverse:
                foreground, background = background, foreground
            px, py = 57+x*12, 158+y*26
            if background != PANEL:
                draw.rectangle((px, py, px+12, py+26), fill=background)
            if character.strip():
                draw.text((px, py), character, font=bold if is_bold else regular, fill=foreground)
    cx, cy = frame.cursor
    if 0 <= cx < 96 and 0 <= cy < 24:
        draw.rectangle((57+cx*12, 182+cy*26, 67+cx*12, 184+cy*26), fill=TEAL)
    if proof:
        draw.text((40, 813), 'CAPTURE CHECK / ORIGINAL = RESTORED', font=small, fill=TEAL)
        draw.text((40, 837), proof['initial']+'  =  '+proof['restored'], font=bold, fill=GOLD)
        draw.text((726, 818), 'RAM + CPU + DEVICES + RF/RK', font=small, fill=MUTED)
        draw.text((726, 842), 'FNV WITNESS / NOT AUTHENTICATION', font=small, fill=MUTED)
    else:
        draw.text((40, 816), 'ACTUAL PTY OUTPUT. PAUSES PACED FOR READABILITY.', font=small, fill=MUTED)
        draw.text((40, 840), 'GUEST COMMANDS EXECUTE INSIDE UNIX. BASE DISKS STAY READ-ONLY.', font=small, fill=TEAL)
    draw.text((40, 877), 'BASM RUNTIME / HISTORICAL KERNEL / PRIVATE DISK VERSIONS', font=small, fill=MUTED)
    return image


def capture(work):
    binary, guest = work/'bemu-pdp11', work/'jash'
    basm = os.environ.get('BASM', 'basm')
    run([basm, '-f', 'elf64', '-o', work/'bemu.o', 'src/bemu_pdp11.basm'], cwd=ROOT/'bemu-pdp11')
    run([os.environ.get('LD', 'ld'), '-o', binary, work/'bemu.o'])
    run([basm, '-f', 'bin', '-o', guest, 'src/jash11.basm'], cwd=ROOT/'jash11')
    env = dict(os.environ, TMPDIR=str(work), JASH11_OUTPUT_DIR=str(work/'images'), JASH11_ARTIFACT=str(guest))
    run(['sh', 'jash11/tools/build-images.sh'], env=env, stdout=subprocess.DEVNULL)
    rf, rk, log = work/'images/rf0.dsk', work/'images/rk0.dsk', work/'session.btt'
    before = [digest(path) for path in (rf, rk)]
    session = Capture(binary, ['--record', log, rf, rk])
    try:
        session.until(rb'login:')
        session.type('root\r')
        session.until(rb'(?:^|[\r\n])# ')
        session.command('ls -l', expected=rb'bin[\r\n]')
        boot = session.freeze(1300)
        session.phase = '02 / RUN A NATIVE PDP-11 SHELL'
        session.command('/bin/jash', expected=rb'Jash/11')
        session.command('version', expected=rb'Jash/11 1\.0')
        session.command('echo "hello from 1971" >/tmp/demo')
        session.command('cat /tmp/demo', expected=rb'[\r\n]hello from 1971[ \r\n]')
        session.command('complete /usr/s', expected=rb'/usr/src[\r\n]+/usr/sys')
        session.command('history', expected=rb'cat /tmp/demo')
        jash = session.freeze(1600)
        session.phase = '03 / PAUSE THE MACHINE'
        session.type('\x01m')
        session.until(rb'\(bemu-tt\)> ')
        # Align to the first boundary after an instruction, not a later WAIT cycle.
        session.command('step 1', monitor=True)
        initial = re.search(rb'hash=([0-9A-F]{16})', session.command('hash', monitor=True))[1].decode()
        session.command('snap', monitor=True, expected=rb'snapshot=')
        session.phase = '04 / EXECUTE 100 INSTRUCTIONS'
        session.command('step 100', monitor=True)
        advanced = re.search(rb'hash=([0-9A-F]{16})', session.command('hash', monitor=True))[1].decode()
        assert advanced != initial, 'forward execution did not change canonical state'
        session.freeze(1200)
        session.phase = '05 / GO BACK. MATCH THE STATE.'
        session.command('back 100', monitor=True)
        restored = re.search(rb'hash=([0-9A-F]{16})', session.command('hash', monitor=True))[1].decode()
        assert restored == initial, (initial, advanced, restored)
        session.phase = '06 / THE ORIGINAL STATE. RESTORED.'
        proof_frame = session.freeze(3000)
        recorded_frames = list(session.frames)
        session.type('quit\n')
        session.process.wait(timeout=5)
    finally:
        session.stop()
    replay = run([binary, '--replay', log], input=b'', capture_output=True)
    assert b'Replay verified' in replay.stderr, replay.stderr
    assert [digest(path) for path in (rf, rk)] == before, 'base images changed'
    (work/'capture-raw.bin').write_bytes(session.raw)
    header = struct.unpack('<8H', guest.read_bytes()[:16])
    assert header[0] == 0o407 and header[1]+header[2] <= 8192
    return recorded_frames, (boot, jash, proof_frame), {
        'initial': initial, 'advanced': advanced, 'restored': restored,
        'replay_verified': True, 'bases_unchanged': True,
        'native_sha256': digest(binary), 'guest_sha256': digest(guest),
        'guest_bytes': guest.stat().st_size,
    }


def check():
    from PIL import Image
    identity = source_id()
    shared_capture = None
    for name in ASSETS:
        path = HERE/name
        assert path.is_file() and path.stat().st_size < 8*1048576, name
        if path.suffix == '.svg':
            text = path.read_text()
            assert f'source-id:{identity}' in text and COPYRIGHT.replace('<', '&lt;').replace('>', '&gt;') in text, 'stale '+name
            assert ET.fromstring(text).tag == '{http://www.w3.org/2000/svg}svg', name
            continue
        with Image.open(path) as image:
            metadata = json.loads(image.info['comment'].decode() if path.suffix == '.gif' else image.info['capture'])
            if shared_capture is None:
                shared_capture = metadata
            assert metadata == shared_capture, 'mixed capture sessions: '+name
            assert metadata['copyright'] == COPYRIGHT and metadata['source_id'] == identity, name
            assert metadata['initial'] == metadata['restored'] != metadata['advanced'], name
            assert metadata['bases_unchanged'] and metadata['replay_verified'], name
            assert image.size == (1280, 900), name
            if path.suffix == '.gif':
                assert image.n_frames > 10 and image.info.get('loop') == 0
                for index in range(image.n_frames):
                    image.seek(index)
                    image.load()
    assert sum((HERE/name).stat().st_size for name in ASSETS) < 8*1048576, 'media payload too large'
    print('PASS: public media decode, source identity, actual reverse/replay witness, immutable bases, dimensions and size budget.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate committed media without executing the guest')
    args = parser.parse_args()
    if args.check:
        check()
        return
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    os.umask(0o077)
    base = os.environ.get('TMPDIR', '/tmp/opencode' if Path('/tmp/opencode').is_dir() else None)
    work = Path(tempfile.mkdtemp(prefix='unix-v1-media-', dir=base))
    print('Private capture workspace:', work, flush=True)
    frames, screenshots, proof = capture(work)
    identity = source_id()
    metadata = dict(proof, copyright=COPYRIGHT, license=LICENSE, source_id=identity,
                    method='Real emulator PTY output re-rendered as terminal cells; pauses paced for readability.')
    encoded = json.dumps(metadata, sort_keys=True).encode()
    (HERE/'hero-machine.svg').write_text(hero(identity, proof['guest_bytes']))
    (HERE/'hero-machine-mobile.svg').write_text(hero(identity, proof['guest_bytes'], mobile=True))
    png = PngInfo()
    png.add_text('Copyright', COPYRIGHT)
    png.add_text('License', LICENSE)
    png.add_text('capture', encoded.decode())
    for name, frame in zip(ASSETS[2:5], screenshots):
        render(frame, proof if name == 'time-travel.png' else None).save(HERE/name, pnginfo=png, optimize=True)
    images = []
    durations = []
    palette_source = Image.new('RGB', (1280, 2700))
    for index, frame in enumerate(screenshots):
        palette_source.paste(render(frame, proof if index == 2 else None), (0, index*900))
    palette = palette_source.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    for frame in frames:
        image = render(frame, proof if frame.phase.startswith('06') else None)
        images.append(image.quantize(palette=palette, dither=Image.Dither.NONE))
        durations.append(max(60, min(frame.duration, 3500)))
    images[0].save(HERE/ASSETS[-1], save_all=True, append_images=images[1:],
                   duration=durations, loop=0, optimize=True, disposal=1, comment=encoded)
    for name in ASSETS:
        (HERE/name).chmod(0o644)
    print('Captured reverse witness:', proof['initial'], '->', proof['advanced'], '->', proof['restored'])
    print('GIF:', len(frames), 'frames;', sum(durations)/1000, 'seconds')
    check()


if __name__ == '__main__':
    main()
