<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# Bemu time travel: version 1 contract

The time-travel engine, recorder, replay path, checkpoints, disk layer, and
monitor are implemented in Basm. Host test automation is not an execution
backend. The historical kernel and shells do not receive debugger hooks.

## Canonical boundary

A boundary is the state before one scheduling cycle: optional external
poll, interrupt arbitration, and either one instruction or a WAIT/IRQ-only
cycle. Boundary positions and dispatched-instruction counts are distinct.
Checkpoints are taken only here, never partway through a synchronous DMA
or a host call. Instruction stepping may cross multiple WAIT/IRQ cycles.

Canonical state covers RAM, R0-R7, PSW flags/priority, all implemented
device registers, console FIFO and indices, pending IRQs, WAIT, the poll
countdown, execution counters, journal cursor, logical console length, and
private RF/RK contents. Host fds, pointers, terminal attributes, escape
prefixes, monitor parsing, and wall-clock reference timestamps are not
guest state. Wall-clock reference time is reset when resuming live capture.

## Disk and external-effect boundary

Time-travel modes never write supplied base files. Version 1 uses bounded
materialized private disk versions: a working image and full copies at
checkpoints, not a claim of page-granular CoW. Supported regular images
are fully loaded before execution, so transient host disk errors are
startup failures rather than hidden runtime nondeterminism.

Restoring a checkpoint restores its private disks. It cannot retract bytes
already displayed on the host terminal or undo arbitrary host effects.
Historical seek suppresses repeated terminal output; a logical transcript
can be inspected separately. Past exploration does not create alternate
input branches: recorded history is replayed to the live frontier.

## Integrity, bounds, and privacy

The versioned session contains the initial machine/images, ordered poll
frames, and a final state witness. FNV-1a-64 detects accidental corruption
and replay divergence; it is not authentication or a collision-resistant
cryptographic proof. Validate dimensions, ordering, reserved fields, and
checksums before executing a loaded session. Reject incomplete sessions.

Recording is opt-in. Files use exclusive creation and owner-only access.
They contain guest RAM, disk contents, console input, and potentially
credentials; they must be treated as sensitive data. No automatic upload
or persistent recording is enabled in ordinary emulation.

## Running the three modes

```sh
# Volatile timeline, initially paused; no session file is created.
./bemu-pdp11 --time-travel rf0.dsk rk0.dsk

# Live recording, initially running; the output path must not exist.
./bemu-pdp11 --record /private/path/NEW.btt rf0.dsk rk0.dsk

# Initially paused recording.
./bemu-pdp11 --time-travel --record /private/path/NEW.btt rf0.dsk rk0.dsk

# Replay uses the initial images embedded in the session, not live disks.
./bemu-pdp11 --replay /private/path/SESSION.btt
./bemu-pdp11 --time-travel --replay /private/path/SESSION.btt
```

`make run-bemu-time` uses the generated base disks in `build/` without the
ordinary installation target that copies over `images/`. Normal emulation
without temporal options retains its original disk-write behavior.
`--help` prints the available invocation forms.

The initial snapshot is taken after the ROM/test loader and before the
first scheduling cycle. Paused execution does not poll the guest clock or
consume guest input. On resume, the host wall-clock reference is reset;
elapsed monitor time is not charged to the guest clock. Clock results are
recorded as the post-poll LKS/request bits, not guessed from replay speed.

In a running temporal session, **Ctrl-A then M** requests a pause at the
next boundary. **Ctrl-E**, **Ctrl-A then X**, and **Ctrl-X then A** retain
their host-exit behavior, including in the monitor. Double an escape prefix
to send one literal prefix to the guest. Replay/history accepts host controls
but drops live guest input; it never mixes new keyboard bytes into the past.

## Host monitor

The prompt is `(bemu-tt)> `, not a command interpreted by the Unix shell.
Arguments accept decimal or `0x` hexadecimal. Numbers are unsigned;
invalid, overflowing, unavailable, or out-of-range requests are rejected.

| Command | Behavior |
|---|---|
| `help` | Show controls, commands, and capacities. |
| `regs` | Show boundary/instruction/event positions, R0-R7, and PSW. |
| `devices` | Show WAIT, console FIFO, clock/IRQ state, RF/RK CS, and EAE AC/MQ. |
| `hash` | Hash canonical state, private disk versions, and the logical console prefix. |
| `disks` | Show the private RF and RK FNV witnesses separately. |
| `console` | Show at most the last 4096 logical output bytes, sanitizing terminal controls. |
| `snap` | Capture a full in-memory checkpoint and print its opaque ID. |
| `snaps` | List retained public checkpoint IDs and their positions. |
| `restore ID` | Restore an available in-memory checkpoint. |
| `step [N]` | Run until N more instructions have been dispatched; default one. |
| `cycle [N]` | Run N scheduling cycles, including IRQ/WAIT-only cycles. |
| `back [N]` | Restore/replay to the first boundary after the preceding N instructions. |
| `seek BOUNDARY` | Restore/replay to an exact canonical cycle-entry position. |
| `continue` / `c` | Continue through history and, for a live recording, rejoin capture. |
| `quit` / `q` | Close the session, finalizing a recording at its live frontier. |

For example, save a `hash`, run `step 10`, then `back 10`. An exact earlier
cycle position can be reached with `seek 0xPOSITION`, using the position
printed by `regs`. Instruction and cycle coordinates are not interchangeable:
clock IRQs and WAIT add cycles without adding guest instructions.

Instruction counts include all dispatched PDP-11 instructions, including
kernel code and interrupt handlers, not only the current user program.

There are eight public checkpoints: initial ID 0 is pinned, and seven slots
rotate. Automatic checkpoints are attempted every 100,000 cycles; manual
checkpoints use the same rolling slots. Evicted IDs fail explicitly instead
of restoring another checkpoint. A separate pinned live-frontier copy allows
read-only exploration without losing the current recording state.

IDs are process-local, not persistent bookmarks. Session files retain the
initial state, events, and terminal witness; replay rebuilds checkpoints.
Use boundary coordinates as durable navigation positions for the same
session/model. There is no branch editing or alternate-input timeline in v1.

## Terminal positions and verification

The footer distinguishes a stop before a poll, a host exit during a poll,
and a guest HALT/runtime exit after dispatch. `seek` addresses canonical
cycle entries, not an arbitrary point inside one of those operations.
Reaching a terminal event ends the process, even in initially paused
replay; there is no post-HALT monitor in v1. Inspect a preceding position
or relaunch an initially paused replay to navigate again.

Successful replay reports `Replay verified` only after the final witness,
instruction/boundary counts, console length, and journal cursor agree.
It reproduces the recorded exit status, which may be nonzero for a captured
guest failure. Verification is not a claim that the guest succeeded,
every intermediate state was independently attested, or the log is trusted.
Early host interruption is reported separately, without a final-verification
claim. Quitting from the past finalizes a recording at the saved live
frontier, not at the temporary historical cursor.

## Capacity and persistence limits

| Resource | v1 bound |
|---|---|
| RF input | nonempty even-length regular file, at most 1 MiB |
| RK input | nonempty 512-byte-aligned regular file, at most 4 MiB |
| Poll journal | at most 1,048,576 frames of 32 bytes |
| Logical console | at most 1,048,576 bytes |
| Public checkpoints | pinned initial plus seven rolling |
| Live frontier | one additional private checkpoint |
| Cycle positions | at most 1,000,000,000 |
| Single forward step request | 1 through 1,000,000 |

The bounded buffers reserve about 116 MiB of BSS address space, demand-paged
by Linux; this is host storage, not extra PDP-11 guest RAM. Snapshot disk
copies cover actual image sizes within those caps. A resource overflow
fails rather than silently dropping history. Event-count bounds are also
checked before reading a session payload.

Only clean exit finalizes a persistent session. The exclusively created
file is initially empty; interrupted writes or process death may leave an
incomplete file, which replay rejects. Completed output is fsynced before
reporting completion. There is no crash-recovery or automatic-recording
guarantee. No command writes private versions back to base images or exports
a standalone changed disk in v1; keep a completed recording to reconstruct
an experiment through replay. Volatile sessions disappear on exit.

Use the `.btt` suffix, which is ignored by this repository. File mode 0600
is not encryption. Do not replay untrusted sessions directly to a terminal:
guest output may contain terminal controls. `console` is a sanitized viewer,
but normal guest/replay stdout intentionally reproduces guest output.

## Validation and compatibility

`make test-time-travel` runs original CPU/device/console tests, the ordinary
Unix boot test, temporal tests, and actual-kernel reverse/replay tests.
`tests/time_travel_boot.py` can additionally select a Jash/11 image using
`BEMU_TT_RF`, `BEMU_TT_RK`, and `BEMU_TT_JASH=1`. The runtime path remains
independent of either shell. The tests include clock interrupts, pending
RF/RK/RX/TX IRQs, console FIFO and WAIT restoration, private-media rollback,
all three terminal phases, malformed/resealed sessions, semantic divergence,
FIFO rejection, capacity failure, and repeated verified Unix replays.

The implementation is tied to the current emulator/model and schema, not
a portable hardware migration format. Existing TC11/paper-tape and DC11
transport limitations remain. The replay witness does not make Bemu an
ISA-complete emulator or an OS security sandbox. A focused CPU regression
also proves PSW serialization does not inherit stale host-register high bits.

See [TIME_TRAVEL_FORMAT.md](TIME_TRAVEL_FORMAT.md) for the wire layout.
