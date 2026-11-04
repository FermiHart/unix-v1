#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

"""Run fail-closed release qualification with isolated images and durable logs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE = 'Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def protected_files():
    paths = [ROOT/'LICENSE', ROOT/'fs/root/bin/sh',
             ROOT/'fs/root/etc/init', ROOT/'fs/root/etc/getty']
    paths += [p for parent in ('src', 'boot', 'patches', 'images')
              for p in (ROOT/parent).rglob('*') if p.is_file()]
    paths += [ROOT/parent/name for parent in ('build', 'jash11/build')
              for name in ('rf0.dsk', 'rk0.dsk') if (ROOT/parent/name).is_file()]
    return {str(p.relative_to(ROOT)): {'sha256': sha256(p), 'inode': p.stat().st_ino,
                                     'size': p.stat().st_size} for p in sorted(set(paths))}


def authored_files():
    result = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                      '--exclude-standard'], cwd=ROOT, text=True)
    return [ROOT/name for name in result.splitlines()
            if name.startswith(('bemu-pdp11/', 'jash11/', 'qemu/')) or name in
            ('.gitignore', 'Makefile', 'README.md', 'CONTRIBUTIONS.md', 'CHANGELOG.md')]


def source_identity():
    return {str(p.relative_to(ROOT)): sha256(p) for p in authored_files()}


def terminate_tree(process):
    """Only terminate descendants of the timed-out stage, not unrelated emulators."""
    def descendants(pid):
        try:
            children = Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
        except FileNotFoundError:
            return []
        return [child for item in children for child in [*descendants(int(item)), int(item)]]
    owned = descendants(process.pid)
    for pid in [*owned, process.pid]:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


class Qualification:
    def __init__(self, output, repeat):
        self.output = output
        self.env = dict(os.environ, TMPDIR=str(output),
                        JASH11_OUTPUT_DIR=str(output/'jash-images'))
        for name in ('BEMU_TT_RF', 'BEMU_TT_RK', 'BEMU_TT_JASH', 'JASH11_ARTIFACT'):
            self.env.pop(name, None)
        self.report = {'copyright': SIGNATURE, 'license': 'original unix-v1 terms; see LICENSE',
                       'started_utc': datetime.now(timezone.utc).isoformat(),
                       'repeat': repeat, 'verdict': 'IN_PROGRESS', 'stages': []}
        self.save()

    def save(self):
        temporary = self.output/'report.json.new'
        temporary.write_text(json.dumps(self.report, indent=2)+'\n')
        temporary.chmod(0o600)
        temporary.replace(self.output/'report.json')

    def stage(self, name, command=None, action=None, timeout=240, extra_env=None):
        log = self.output/(name+'.log')
        entry = {'name': name, 'log': log.name, 'status': 'FAIL'}
        start = time.monotonic()
        try:
            with log.open('x') as stream:
                log.chmod(0o600)
                if command is not None:
                    command = list(map(str, command))
                    entry['command'] = command
                    stream.write('$ '+shlex.join(command)+'\n')
                    stream.flush()
                    env = dict(self.env, **(extra_env or {}))
                    process = subprocess.Popen(command, cwd=ROOT, env=env,
                                               stdin=subprocess.DEVNULL,
                                               stdout=stream, stderr=subprocess.STDOUT,
                                               start_new_session=True)
                    try:
                        status = process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        terminate_tree(process)
                        raise RuntimeError(f'stage exceeded {timeout} seconds') from None
                    entry['exit_code'] = status
                    if status:
                        raise RuntimeError(f'command exited with status {status}')
                else:
                    action(stream)
            entry['status'] = 'PASS'
        except Exception as error:
            entry['error'] = str(error)
            print(f'{name}: {error}', file=sys.stderr)
        entry['seconds'] = round(time.monotonic()-start, 3)
        self.report['stages'].append(entry)
        self.save()
        print(f"{entry['status']}: {name} ({entry['seconds']}s)", flush=True)
        return entry['status'] == 'PASS'

    def preflight(self, stream):
        required = ('make', 'ld', 'expect', 'timeout', 'flock', 'git', 'readelf',
                    'nm', 'qemu-system-x86_64', 'busybox', 'cpio', 'gzip')
        tools = {name: shutil.which(name) for name in required}
        tools['assembler'] = shutil.which(self.env.get('BASM', 'basm'))
        missing = [name for name, value in tools.items() if not value]
        if missing:
            raise RuntimeError('missing required tools: '+', '.join(missing))
        if self.env.get('KERNEL'):
            candidates = [Path(self.env['KERNEL'])]
        else:
            candidates = [Path('/boot/vmlinuz'), *sorted(Path('/boot').glob('vmlinuz-*'))]
        kernel = next((p for p in candidates if p.is_file() and os.access(p, os.R_OK)), None)
        if kernel is None:
            raise RuntimeError('no readable Linux kernel; set KERNEL=/path/to/vmlinuz')
        self.env['KERNEL'] = str(kernel)
        self.report['environment'] = {'tools': tools, 'kernel': str(kernel),
                                       'kernel_sha256': sha256(kernel),
                                       'python': sys.version, 'platform': list(os.uname())}
        stream.write(json.dumps(self.report['environment'], indent=2)+'\n')

    def reproducible_artifacts(self, stream):
        folder = self.output/'artifacts'
        folder.mkdir(mode=0o700)
        assembler = self.env.get('BASM', 'basm')
        obj, binary, guest = folder/'bemu.o', folder/'bemu-pdp11', folder/'jash'
        for command, cwd in [([assembler, '-f', 'elf64', '-o', obj, 'src/bemu_pdp11.basm'], ROOT/'bemu-pdp11'),
                             (['ld', '-o', binary, obj], ROOT),
                             ([assembler, '-f', 'bin', '-o', guest, 'src/jash11.basm'], ROOT/'jash11')]:
            subprocess.run(list(map(str, command)), cwd=cwd, env=self.env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True, timeout=30)
        for rebuilt, current in ((binary, ROOT/'bemu-pdp11/bemu-pdp11'), (guest, ROOT/'jash11/build/jash')):
            if sha256(rebuilt) != sha256(current):
                raise RuntimeError(f'nonreproducible artifact: {current.relative_to(ROOT)}')
        elf = subprocess.check_output(['readelf', '-l', '-d', binary], text=True)
        undefined = subprocess.check_output(['nm', '-u', binary], text=True)
        if 'INTERP' in elf or 'There is no dynamic section' not in elf or undefined.strip():
            raise RuntimeError('Bemu must remain static and have no undefined symbols')
        stream.write(elf+'\nPASS: byte-identical native and guest rebuilds; Bemu has no dynamic runtime.\n')
        self.report['artifacts'] = {str(p.relative_to(ROOT)): sha256(p) for p in
                                    (ROOT/'bemu-pdp11/bemu-pdp11', ROOT/'jash11/build/jash')}

    def qemu_sandbox(self, stream):
        sandbox = self.output/'qemu-sandbox'
        for name in ('LICENSE', 'CONTRIBUTIONS.md', 'boot/m792low.load', 'tools/pdp11',
                     'images/rf0.dsk', 'images/rk0.dsk', 'qemu/run-qemu.sh',
                     'qemu/init-src-init', 'qemu/simh-qemu.cfg', 'qemu/test-qemu.exp'):
            target = sandbox/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name, target)
        self.sandbox = sandbox
        stream.write('PASS: public QEMU launcher/tests copied unchanged into a private repository layout.\n')

    def preservation_and_policy(self, stream):
        after = protected_files()
        self.report['protected_after'] = after
        if after != self.report['protected_before']:
            changed = sorted(name for name in after.keys() | self.report['protected_before'].keys()
                             if after.get(name) != self.report['protected_before'].get(name))
            raise RuntimeError('protected files changed (not reverted): '+', '.join(changed))
        original_license = subprocess.check_output(['git', 'show', 'HEAD:LICENSE'], cwd=ROOT)
        if (ROOT/'LICENSE').read_bytes() != original_license:
            raise RuntimeError('original LICENSE differs from HEAD')
        for path in authored_files():
            text = path.read_text()
            header = '\n'.join(text.splitlines()[:8])
            reference = re.search(r'License: original unix-v1 terms; see (\S+)', header)
            if SIGNATURE not in header or reference is None:
                raise RuntimeError(f'missing attribution/license header: {path.relative_to(ROOT)}')
            if path.parent.joinpath(reference[1].rstrip('.')).resolve() != ROOT/'LICENSE':
                raise RuntimeError(f'incorrect license reference: {path.relative_to(ROOT)}')
            if any(line.rstrip() != line for line in text.splitlines()):
                raise RuntimeError(f'trailing whitespace: {path.relative_to(ROOT)}')
        if source_identity() != self.report['source_sha256']:
            raise RuntimeError('source changed during qualification; rerun for the new source identity')
        stream.write(f'PASS: {len(after)} protected files retain bytes/inodes; historical LICENSE and source headers match.\n')

    def execute(self, repeat):
        self.report['protected_before'] = protected_files()
        self.report['source_sha256'] = source_identity()
        self.save()
        ready = self.stage('preflight', action=self.preflight)
        if ready:
            for name, command in [('build-tools', ['make', '-C', 'tools']),
                                  ('build-base', ['make', '-C', 'build']),
                                  ('build-bemu', ['make', '-C', 'bemu-pdp11']),
                                  ('build-jash', ['make', '-C', 'jash11', 'images'])]:
                if not self.stage(name, command):
                    ready = False
                    break
        if ready:
            self.stage('artifact-rebuild', action=self.reproducible_artifacts)
            self.stage('legacy-and-boot', ['make', '-C', 'bemu-pdp11', 'test', 'test-boot'])
            self.stage('packaging', ['python3', 'jash11/tests/packaging.py'])
            sandbox_ready = self.stage('qemu-isolation', action=self.qemu_sandbox)
            if sandbox_ready:
                self.stage('qemu-build-only', [self.sandbox/'qemu/run-qemu.sh', '--build-only'])
            for number in range(1, repeat+1):
                prefix = f'round-{number}'
                self.stage(prefix+'-temporal', ['python3', 'bemu-pdp11/tests/time_travel.py'])
                self.stage(prefix+'-commands', ['python3', 'bemu-pdp11/tests/time_travel_commands.py'])
                self.stage(prefix+'-unix-replay', ['python3', 'bemu-pdp11/tests/time_travel_boot.py'])
                self.stage(prefix+'-jash-replay', ['python3', 'bemu-pdp11/tests/time_travel_boot.py'],
                           extra_env={'BEMU_TT_RF': str(self.output/'jash-images/rf0.dsk'),
                                      'BEMU_TT_RK': str(self.output/'jash-images/rk0.dsk'), 'BEMU_TT_JASH': '1'})
                for backend in ('bemu', 'simh'):
                    self.stage(prefix+'-native-'+backend, ['expect', 'jash11/tests/native.exp', backend])
                    self.stage(prefix+'-edition-'+backend, ['expect', 'jash11/tests/edition.exp', backend, '5', 'qualify'])
                if sandbox_ready:
                    self.stage(prefix+'-qemu', ['expect', self.sandbox/'qemu/test-qemu.exp'], timeout=300)
        self.stage('preservation-and-policy', action=self.preservation_and_policy)
        self.stage('diff-check', ['git', 'diff', '--check'])
        passed = ready and all(item['status'] == 'PASS' for item in self.report['stages'])
        self.report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        self.report['verdict'] = 'QUALIFIED' if passed else 'NOT_QUALIFIED'
        self.save()
        print(f"{self.report['verdict']}: {self.output/'report.json'}", flush=True)
        return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat', type=int, default=3, help='full repeat rounds, 1 through 10 (default 3)')
    parser.add_argument('--output', type=Path, help='new private evidence directory; must not exist')
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10:
        parser.error('--repeat must be between 1 and 10')
    os.umask(0o077)
    if args.output:
        output = args.output.expanduser().resolve()
        if output == ROOT or ROOT in output.parents:
            parser.error('--output must be outside the source repository')
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
    else:
        base = os.environ.get('TMPDIR', '/tmp/opencode' if Path('/tmp/opencode').is_dir() else None)
        output = Path(tempfile.mkdtemp(prefix='unix-v1-qualification-', dir=base))
    print(f'Private qualification evidence: {output}', flush=True)
    return Qualification(output, args.repeat).execute(args.repeat)


if __name__ == '__main__':
    sys.exit(main())
