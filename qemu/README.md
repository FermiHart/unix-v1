<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../LICENSE. -->

# Unix V1 inside QEMU

QEMU does not provide a PDP-11 target, so it cannot execute this kernel
directly. This workflow boots a minimal **x86-64 Linux guest** whose `/init`
launches **SIMH PDP-11** with the Unix V1 disk images.

```text
QEMU (x86-64) -> Linux initramfs -> SIMH PDP-11 -> Unix V1
```

This is nested emulation, separate from the native Basm implementation in
`bemu-pdp11/`.

## Requirements

- Run `make` at the repository root first to generate the disk images and
  `tools/pdp11`.
- Install `qemu-system-x86_64`, `busybox`, `cpio`, and `gzip`.
- Provide a readable Linux kernel in `/boot/vmlinuz*`, or set `KERNEL` to
  an explicit path. The launcher selects the first readable kernel.

## Usage

```sh
make run-qemu
./qemu/run-qemu.sh --build-only
KERNEL=/path/to/vmlinuz ./qemu/run-qemu.sh
./qemu/run-qemu.sh --no-kvm
```

At the serial console, log in as `root` and run `ls -l` or `chdir /usr`.
Press **Ctrl-A X** to exit QEMU.

## Automated test

```sh
expect qemu/test-qemu.exp
```

The test rebuilds the initramfs through the public launcher, boots Unix V1,
logs in as `root`, checks `ls -l` and directory access under `/usr`, and
requires a successful exit. It forces TCG so `/dev/kvm` is not required,
honors `KERNEL`, and resolves paths relative to the repository.

`make qualify` runs this test repeatedly from a private copied repository
layout, including RF/RK write/read/removal checks. This avoids replacing
the existing `qemu/initramfs` staging tree. See the
[complete test instructions](../bemu-pdp11/README.md#regression-coverage).

## Implementation

- `run-qemu.sh` stages BusyBox, SIMH and its runtime libraries, the Unix V1
  disks, the M792 loader, the configuration, and `init-src-init` as `/init`.
- The original `unix-v1` license and local contribution notice are included
  in the generated image under `/unix/`.
- `initramfs.cpio.gz` is passed to QEMU with the selected Linux kernel and
  a serial console. The staged disks are guest copies, not host disk devices.
- `simh-qemu.cfg` uses the original device configuration with `/unix/` paths.
- `/bin/sh` is provided by a BusyBox symlink; `/init` explicitly selects
  `/bin/busybox sh`.
- Do not pre-create `/unix/tape`: the tested configuration allows SIMH to
  create it on attachment. An existing empty tape file caused attachment
  problems during development.
- Keep the complete tested SIMH configuration, including the KE11-A and
  DC11 settings. A reduced RF/RK-only configuration did not reach login.

## Attribution and license

Copyright (c) 2026, **F E R M I ∞ H A R T** —
[contact@fermihart.com](mailto:contact@fermihart.com).

Our integration uses the same original `unix-v1` terms in
[../LICENSE](../LICENSE). The original copyright, conditions, and disclaimer
are preserved. SIMH, Linux, BusyBox, and runtime libraries retain their own
licenses and attribution; this integration does not relicense them.

This product includes software developed or owned by Caldera
International, Inc.
