#!/bin/sh
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.
#
# run-qemu.sh - Boot Unix V1 inside QEMU (x86_64 guest running SIMH PDP-11)
# Usage: ./run-qemu.sh [--build-only] [--no-kvm]
# QEMU has no PDP-11 target, so we boot a minimal x86_64 Linux guest
# whose /init launches the SIMH PDP-11 emulator with the Unix V1 disks.
set -eu
CDIR="$(dirname "$0")"
ROOT="$(cd "$CDIR/.." && pwd)"
STAGE="$ROOT/qemu/initramfs"
INITRD="$ROOT/qemu/initramfs.cpio.gz"
KERNEL="${KERNEL:-}"
QEMU="qemu-system-x86_64"

# Pick a host kernel: first *readable* one (override with KERNEL=/path/to/vmlinuz).
# Note: some /boot/vmlinuz-* are 0600 root-only; prefer a readable one.
if [ -n "${KERNEL:-}" ]; then
  : # use env
else
  for k in /boot/vmlinuz /boot/vmlinuz-*; do
    if [ -r "$k" ]; then KERNEL="$k"; break; fi
  done
fi
if [ -z "${KERNEL:-}" ] || [ ! -r "$KERNEL" ]; then
  echo "No readable kernel found. Set KERNEL=/path/to/vmlinuz (try a 0644 one," >&2
  echo "e.g. sudo chmod 644 /boot/vmlinuz-*)" >&2
  exit 1
fi
# qemu running as user must be able to open -kernel; stage a copy if needed
if [ ! -r "$KERNEL" ]; then
  echo "Kernel $KERNEL not readable" >&2; exit 1
fi

build_initramfs() {
  echo "[qemu] building initramfs in $STAGE"
  rm -rf "$STAGE"
  mkdir -p "$STAGE/bin" "$STAGE/unix" "$STAGE/proc" "$STAGE/sys" "$STAGE/dev" \
           "$STAGE/lib64" "$STAGE/lib/x86_64-linux-gnu"
  cp /usr/bin/busybox "$STAGE/bin/busybox"
  chmod +x "$STAGE/bin/busybox"
  ln -sf busybox "$STAGE/bin/sh"
  ln -sf busybox "$STAGE/bin/ash"
  # pdp11: resolve symlink tools/pdp11 -> simh/BIN/pdp11
  cp -L "$ROOT/tools/pdp11" "$STAGE/bin/pdp11"
  chmod +x "$STAGE/bin/pdp11"
  # shared libs for pdp11 (dynamically linked)
  cp -L /lib64/ld-linux-x86-64.so.2 "$STAGE/lib64/" 2>/dev/null || \
    cp -L /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 "$STAGE/lib64/"
  cp -L /lib/x86_64-linux-gnu/libc.so.6 "$STAGE/lib/x86_64-linux-gnu/"
  cp -L /lib/x86_64-linux-gnu/libm.so.6 "$STAGE/lib/x86_64-linux-gnu/"
  # unix v1 disks + bootloader + config
  cp "$ROOT/images/rf0.dsk" "$ROOT/images/rk0.dsk" "$STAGE/unix/"
  cp "$ROOT/boot/m792low.load" "$STAGE/unix/m792low.load"
  cp "$ROOT/qemu/simh-qemu.cfg" "$STAGE/unix/simh-qemu.cfg"
  # Preserve the original project terms and identify local contributions.
  cp "$ROOT/LICENSE" "$ROOT/CONTRIBUTIONS.md" "$STAGE/unix/"
  # NOTE: do NOT pre-create unix/tape - SIMH must create it on first
  # attach; a pre-existing 0-byte tape file hangs the emulator.
  # /init
  cp "$ROOT/qemu/init-src-init" "$STAGE/init"
  chmod +x "$STAGE/init"
  # device nodes (also covered by devtmpfs, but harmless)
  ( cd "$STAGE" && \
    mkdir -p dev && \
    mknod -m 622 dev/console c 5 1 2>/dev/null || true; \
    mknod -m 666 dev/null c 1 3 2>/dev/null || true; \
    mknod -m 666 dev/zero c 1 5 2>/dev/null || true; \
    mknod -m 666 dev/tty c 5 0 2>/dev/null || true )
  ( cd "$STAGE" && find . -print0 | cpio --format=newc --create --null 2>/dev/null | gzip -9 > "$INITRD" ) || \
  ( cd "$STAGE" && find . -print0 | busybox cpio -H newc --create --null 2>/dev/null | gzip -9 > "$INITRD" )
  echo "[qemu] initramfs: $INITRD ($(du -h "$INITRD" | cut -f1))"
}

build_initramfs

if [ "${1:-}" = "--build-only" ]; then
  echo "[qemu] build-only, not booting."
  exit 0
fi

# KVM if available
ACCEL=""
if [ -e /dev/kvm ] && [ "${1:-}" != "--no-kvm" ]; then
  ACCEL="-enable-kvm"
fi

echo "[qemu] kernel: $KERNEL"
echo "[qemu] booting... login as 'root', try 'ls -l'. Ctrl-A X to quit."
echo ""

# shellcheck disable=SC2086
exec $QEMU \
  -m 512 \
  -nographic \
  $ACCEL \
  -kernel "$KERNEL" \
  -initrd "$INITRD" \
  -append "console=ttyS0,115200 rdinit=/init panic=-1 noreboot" \
  -no-reboot
