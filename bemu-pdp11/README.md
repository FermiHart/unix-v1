<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../LICENSE. -->

# Bemu-pdp11

A PDP-11/20 emulator written **entirely in Basm**, part of the BEmu family.
It runs this repository's restored Unix V1 binaries as a native Linux
x86-64 executable, without SIMH or QEMU at runtime.

```text
Bemu-pdp11 -> PDP-11/20 + KE11-A + RF/RK + console -> Unix V1 shell
```

The implementation is assembled with Bear Basm (`basm -f elf64`) and linked
with `ld`. It uses Linux system calls directly and does not link against libc.

## Verified behavior

The original boot sequence executes the M792 ROM, `bos`, and the PDP-11
kernel without boot shortcuts. Tests cover the `login:` prompt, `root`
login, the shell, `ls -l`, `chdir /usr`, and file operations on both the RF
and RK filesystems.

## Requirements

- Linux x86-64, Bear Basm or a compatible derivative, and GNU `ld`.
- Run `make` at the repository root to build the Unix V1 disk images.
- Tests also require `timeout`, `expect`, and the repository's V1 assembler
  running under `tools/apout`.

SIMH is the reference implementation and powers the separate QEMU workflow;
it is not a runtime dependency of Bemu-pdp11. The external assembler is not
bundled with this project.

## Build, run, and test

From the repository root:

```sh
make run-bemu
make test-bemu
```

From this directory, after building the disk images:

```sh
make                       # Assemble and link the emulator.
make test                  # Run CPU, KE11-A, and console regressions.
make test-boot             # Boot and test private copies of the disks.
./bemu-pdp11                # Use the default images/ or ../images/ paths.
./bemu-pdp11 --trace        # Write an instruction trace to standard error.
./bemu-pdp11 rf.dsk rk.dsk  # Use explicit disk images.
```

The default assembler command is `basm`, resolved through `PATH`. To select
a specific Bear Basm installation or compatible derivative:

```sh
make BASM=/absolute/path/to/basm
```

Log in as `root`. Use `chdir`, not `cd`, to change directories. The V1 shell
requires the filename immediately after `>`: `echo test >/tmp/test`.
To close **Bemu itself**, including from the historical `/bin/sh`, use:

- **Ctrl-E**, or
- **Ctrl-A**, release Ctrl, then press **X**, or
- **Ctrl-X**, release Ctrl, then press **A**.

These are host escape sequences, not commands interpreted by Unix V1. The
emulator restores the terminal attributes and original stdin status flags.
Both letter cases are accepted. Double a prefix (Ctrl-A twice or Ctrl-X
twice) to send that control byte to the guest. Unrecognized escape sequences
are forwarded without losing their bytes.

The historical `sh` does not gain a new `exit` builtin. Jash/11's `exit`
returns to that shell; it does not close Bemu. The startup banner lists the
host exit keys so the user does not need to close the terminal window.

Exit codes: `0` for success, `1` for a guest or runtime failure, and `2` for
invalid arguments.

## Disk safety

The emulator writes to the supplied disk images. Keep backups before
experimenting. `make test-boot` uses private copies of
`../build/{rf0,rk0}.dsk`; it does not modify the working disks in `images/`.

## Time travel (Basm runtime)

The temporal runtime provides bounded recording/replay, complete
machine/media checkpoints, reverse navigation, and a separate host monitor.

```sh
make run-bemu-time             # From the repository root: start paused.
make test-time-travel          # Unit, boot, rollback, replay, and fault gates.
```

Or invoke the native emulator directly:

```sh
./bemu-pdp11 --time-travel rf.dsk rk.dsk
./bemu-pdp11 --record /path/to/NEW.btt rf.dsk rk.dsk
./bemu-pdp11 --replay /path/to/SESSION.btt
./bemu-pdp11 --time-travel --replay /path/to/SESSION.btt
```

Time-travel modes open regular base images read-only and run against private
in-memory versions. Ordinary emulation still writes the supplied images.
Recording is opt-in, exclusively creates a new 0600 file, and finalizes on
clean exit. Sessions contain RAM, disks, and input: treat them as sensitive.
Incomplete recordings are rejected; this is not crash recovery or encryption.

**Ctrl-A then M** pauses a running timeline at its next canonical boundary.
The host monitor is separate from both historical `sh` and Jash/11:

```text
(bemu-tt)> regs
(bemu-tt)> snap
(bemu-tt)> step 10
(bemu-tt)> back 10
(bemu-tt)> hash
(bemu-tt)> continue
```

`seek` uses boundary positions; `step`/`back` use instruction counts.
`devices`, `disks`, `console`, `snaps`, and `restore ID` expose the retained
state. `console` prints a sanitized logical transcript, not a terminal undo.
Past exploration is read-only; continuing replays recorded history before
rejoining live capture. Replay blocks live guest input, keeps host controls,
and reports final verification only when machine/disks/console/journal match.

All these runtime operations are Basm, not a host Python debugger. Python
only drives external regression tests. Read the precise phase, capacity,
privacy, and terminal-event limits in [docs/TIME_TRAVEL.md](docs/TIME_TRAVEL.md)
and the wire layout in [docs/TIME_TRAVEL_FORMAT.md](docs/TIME_TRAVEL_FORMAT.md).

## Compatibility boundary

This implementation targets the restored Unix V1 image, not complete,
cycle-accurate compatibility with every PDP-11 configuration. TC11 and
paper-tape transfers are not implemented. DC11 does not provide TCP or
Telnet sessions; use SIMH for those peripherals.

`make run-qemu` remains a separate path: QEMU runs an x86-64 Linux guest
that launches SIMH, not Bemu-pdp11.

## Regression coverage

From the repository root:

```sh
make test-bemu
make test-time-travel
make -C bemu-pdp11 test-time-commands
make qualify BASM=/absolute/path/to/basm
```

`make qualify` repeats the documented CLI/monitor interfaces, Jash/11 in
Bemu/SIMH, temporal Unix boots, and isolated QEMU/TCG boots three times.
It also checks reproducible artifacts, packaging, ELF identity, historical
file/disk preservation, and source attribution. Every required stage must
pass; missing prerequisites, errors, timeouts, or source drift block approval.

In addition to the build dependencies, the complete gate requires Python 3,
`expect`, `timeout`, `flock`, Git, ELF tools, QEMU, BusyBox, `cpio`, `gzip`,
and a readable Linux kernel. Set `KERNEL` to select a kernel explicitly;
QEMU tests use TCG and do not require KVM. See [the QEMU requirements](../qemu/README.md).

The runner prints a private evidence directory containing stage logs,
source/artifact hashes, preservation manifests, and a JSON verdict. Evidence
is local, not committed or uploaded; treat it as potentially sensitive.
To control the repeat count or evidence location:

```sh
python3 bemu-pdp11/tests/qualify_release.py --repeat 3 --output /private/new-evidence
```

The output directory must be new and outside the repository. These gates
cover the supported profile, not every historical utility, ISA combination,
physical PDP-11, or KVM configuration.

- `cpu2` through `cpu6`: instructions, flags, byte/word addressing,
  clist/putlu instruction patterns, MOVB sign extension, and condition codes.
- `ke11`: word/byte MQ writes, the AC sign word, DIV/LSH, and the kernel's
  RK address calculation. The corrected defect mapped block 4 to `0x5558`.
- `test-boot.exp`: prompts after commands, RF/RK filesystem access,
  file creation/read/removal on both filesystems, and clean Ctrl-E exit.
- `test_escape.py`: both host escape orders, letter cases, literal-prefix
  passthrough, PTY attributes, stdin flags, and error-path exit status.
- `cpu7`: PSW serialization independent of stale host-register high bits.
- `time_travel.py`: full-state/media checkpoints, reverse/seek, pending
  IRQs/FIFO/WAIT, clock/input replay, corruption/types/order/bounds, host
  exits, resource failure, and exclusive session output.
- `time_travel_boot.py`: actual Unix RF/RK writes, reverse/full-boot seek,
  two matching verified replays, and immutable base images.
- `time_travel_commands.py`: command/alias/arity matrix, exact limits,
  seeded navigation/corruption, console sanitization, interruption and crash
  behavior. Run it alone with `make -C bemu-pdp11 test-time-commands` from
  the repository root.

## Source layout

- `src/bemu_pdp11.basm`: CPU, devices, and Linux host integration.
- `src/time_travel.basm`: Basm timeline, disk versions, snapshots, session
  validation, replay, and host monitor (included in the same translation unit).
- `tests/`: PDP-11 regression programs and test automation.
- `docs/`: boot, instruction, register, and device reference notes.

## Attribution and license

Copyright (c) 2026, **F E R M I ∞ H A R T** —
[contact@fermihart.com](mailto:contact@fermihart.com).

Our contributions use the same original `unix-v1` license in
[../LICENSE](../LICENSE). No separate license replaces its copyright
notice, conditions, or disclaimer. Historical authorship and third-party
notices remain intact. See [../CONTRIBUTIONS.md](../CONTRIBUTIONS.md).

This product includes software developed or owned by Caldera
International, Inc.
