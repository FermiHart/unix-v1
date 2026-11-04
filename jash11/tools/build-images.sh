#!/bin/sh
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.

set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
ARTIFACT="${JASH11_ARTIFACT:-$HERE/build/jash}"
OUT="${JASH11_OUTPUT_DIR:-$HERE/build}"
mkdir -p "$OUT"
OUT=$(CDPATH= cd -- "$OUT" && pwd)
for path in "$ROOT/build/root/bin/sh" "$ROOT/build/rf0.dsk" "$ROOT/build/rk0.dsk" "$ROOT/tools/mkfs" "$ARTIFACT"; do
  [ -r "$path" ] || { echo "Missing $path; build the base system first." >&2; exit 1; }
done
exec 9>"$OUT/.image-build.lock"
flock -n 9 || { echo 'Another image build is already using this output directory.' >&2; exit 1; }
STAGE=""
CANDIDATE=""
cleanup() {
  [ -z "$STAGE" ] || rm -rf "$STAGE"
  [ -z "$CANDIDATE" ] || rm -rf "$CANDIDATE"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/jash11-root.XXXXXX")
CANDIDATE=$(mktemp -d "$OUT/.images.XXXXXX")
cp -R "$ROOT/build/root/." "$STAGE/"
cp "$ARTIFACT" "$STAGE/bin/jash"
cmp "$ROOT/build/root/bin/sh" "$STAGE/bin/sh"
# Match the base image builder's default modes. Only this private tree is used.
"$ROOT/tools/mkfs" "$STAGE" "$CANDIDATE/rf0.dsk" rf
# Preserve the exact boot area (M792/bos/kernel source image), not a patched kernel.
dd if="$ROOT/build/rf0.dsk" of="$CANDIDATE/rf0.dsk" bs=512 skip=960 seek=960 conv=notrunc 2>/dev/null
cp "$ROOT/build/rk0.dsk" "$CANDIDATE/rk0.dsk"
python3 "$HERE/tools/verify-image.py" "$ARTIFACT" "$CANDIDATE/rf0.dsk" "$ROOT/build/rf0.dsk"
cmp "$ROOT/build/rk0.dsk" "$CANDIDATE/rk0.dsk"
sha256sum "$ARTIFACT" | awk '{print $1 "  jash"}' > "$CANDIDATE/artifact.sha256"
# Preserve old inodes before publishing. A running emulator can continue to
# use its open descriptors, and its writes remain in the retained directory.
BACKUP=""
if [ -e "$OUT/rf0.dsk" ] || [ -e "$OUT/rk0.dsk" ]; then
  BACKUP=$(mktemp -d "$OUT/previous.XXXXXX")
  for name in rf0.dsk rk0.dsk artifact.sha256; do
    [ ! -e "$OUT/$name" ] || mv "$OUT/$name" "$BACKUP/$name"
  done
fi
for name in rf0.dsk rk0.dsk artifact.sha256; do
  mv "$CANDIDATE/$name" "$OUT/$name"
done
[ -z "$BACKUP" ] || printf 'Previous experimental disks retained at %s\n' "$BACKUP"
printf '%s\n' 'Jash/11 experimental images ready; base images and /bin/sh preserved.'
