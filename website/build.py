#!/usr/bin/env python3
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.

"""Stage an allowlisted static site; never copy disks, recordings or host binaries."""
import argparse
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import runpy
import shutil

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ('hero-machine.svg', 'hero-machine-mobile.svg', 'unix-v1-in-action.gif',
         'unix-v1-boot.png', 'jash11-live.png', 'time-travel.png')


class Resources(HTMLParser):
    def __init__(self, site):
        super().__init__()
        self.site = site
        self.english = False
        self.images = 0

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'html':
            self.english = attributes.get('lang') == 'en'
        if tag == 'img':
            assert attributes.get('alt'), 'every image needs an accessible description'
            self.images += 1
        for key in ('href', 'src', 'srcset'):
            value = attributes.get(key, '')
            if not value or value.startswith(('https:', 'mailto:', 'data:', '#')):
                continue
            path = (self.site/value.split('#')[0]).resolve()
            assert path.is_relative_to(self.site) and path.is_file(), value


def build(destination):
    identity = runpy.run_path(str(ROOT/'readme/generate_media.py'))['source_id']()
    for name in MEDIA[:2]:
        assert 'source-id:'+identity in (ROOT/'readme'/name).read_text(), 'stale art: '+name
    files = {'index.html': ROOT/'website/index.html', 'css/site.css': ROOT/'website/css/site.css',
             'LICENSE': ROOT/'LICENSE'}
    files.update({'assets/'+name: ROOT/'readme'/name for name in MEDIA})
    assert all(path.is_file() and not path.is_symlink() for path in files.values())
    destination = destination.expanduser().resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('output directory must be new or empty; existing files are never deleted')
    destination.mkdir(mode=0o755, parents=True, exist_ok=True)
    for name, source in files.items():
        target = destination/name
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o644)
        assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()
    page = Resources(destination)
    page.feed((destination/'index.html').read_text())
    assert page.english and page.images == 5
    assert sum(path.is_file() for path in destination.rglob('*')) == len(files)
    size = sum(path.stat().st_size for path in destination.rglob('*') if path.is_file())
    assert size < 2*1048576, 'unexpected static-site payload'
    print(f'PASS: {len(files)} allowlisted files, {size:,} bytes, English page, valid local resources and current source-bound art.')
    print('Static site:', destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        build(args.output)
    except (AssertionError, ValueError) as error:
        parser.exit(1, f'site build refused: {error}\n')


if __name__ == '__main__':
    main()
