<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# BTTLOG01 / BTTEND01: session schema 1

All multibyte integers are unsigned little-endian. No host pointer, fd,
pathname, terminal setting, or wall-clock timestamp is serialized.
This is the current model's bounded replay format, not authenticated input.

```text
128-byte header
initial canonical state
initial RF bytes
initial RK bytes
N x 32-byte poll frames
80-byte terminal footer
```

## Header

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 8 | ASCII `BTTLOG01` |
| 8 | 8 | Format version = 1 |
| 16 | 8 | Canonical state size = 65,769 for this model |
| 24 | 8 | Device vector size = 175 for this model |
| 32 | 8 | RF byte count, at most 1 MiB |
| 40 | 8 | RK byte count, at most 4 MiB |
| 48 | 8 | Test-program mode, 0 or 1 |
| 56 | 8 | Normal poll quantum = 1024 cycles |
| 64 | 8 | Initial witness |
| 72 | 8 | Model/schema marker = `0x0001000000000001` |
| 80 | 8 | Logical console capacity = 1,048,576 |
| 88 | 8 | Poll frame size = 32 |
| 96 | 32 | Reserved zero bytes |

Zero RF/RK sizes are accepted together only in test-program mode. Otherwise
RF is positive/even and RK is positive/512-aligned. Dimensions and the exact
file envelope are checked before loading or executing the initial state.

## Canonical state vector

The first 65,557 bytes are 65,536 RAM bytes, eight 16-bit registers, and five
PSW bytes (N, Z, V, C, priority). The next 175 bytes are the emulator's
implemented device block from `irq_clk` through `sr_val`, in source order.
It includes all pending IRQs, console/FIFO state, RF/RK registers, DC11,
KE11-A, and switches. Host scratch variables are excluded.

The remaining 37 bytes, relative to the end of the device block:

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 1 | WAIT flag |
| 1 | 4 | Poll countdown |
| 5 | 8 | Boundary position |
| 13 | 8 | Dispatched-instruction count |
| 21 | 8 | Consumed-event cursor |
| 29 | 8 | Logical console length |

The loaded initial state requires countdown 1024 and zero positions,
cursor, and console length. PSW flags, priority, WAIT, IRQ booleans, and
FIFO count/indices are type/range checked independently of their checksum.
Working disks initially copy the embedded initial images. Runtime snapshots
copy this vector and complete working images into bounded in-memory slots.

## Poll frames

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 8 | Canonical cycle-entry position |
| 8 | 1 | Post-poll LKS (DONE/IE bits only) |
| 9 | 1 | Post-poll clock request, 0 or 1 |
| 10 | 1 | Guest console delivery count, 0 through 2 |
| 11 | 2 | Delivered 7-bit console bytes; unused bytes must be zero |
| 13 | 11 | Reserved zero bytes |
| 24 | 8 | Running frame witness |

One poll may deliver two bytes when an unrecognized host escape prefix is
forwarded literally. Host exit/monitor commands are not guest input.
Frames include empty polls, have strictly increasing positions, and must
be consumed exactly where the deterministic scheduler expects a poll.

## Terminal footer

| Offset | Bytes | Meaning |
|---|---|---|
| 0 | 8 | ASCII `BTTEND01` |
| 8 | 8 | Frame count, matching the exact file size |
| 16 | 8 | Final boundary position |
| 24 | 8 | Final instruction count |
| 32 | 8 | Final canonical state witness |
| 40 | 8 | Final frame-chain witness |
| 48 | 8 | Process exit code, 0 through 2 |
| 56 | 8 | Terminal phase: 0 entry, 1 post-poll/pre-IRQ, 2 guest exit |
| 64 | 8 | Final logical console length |
| 72 | 8 | Footer witness |

For phase 1 the last frame is at the final position and a frame is required.
For phases 0/2 any last frame precedes the final position. Instruction count
cannot exceed boundary count. Final position is capped at 1,000,000,000.
No trailing bytes or incomplete footer are accepted.

## Witness calculation

FNV-1a-64 uses offset basis `0xCBF29CE484222325`, prime `0x100000001B3`,
and unsigned modulo-2^64 multiplication after XORing each byte.

- Initial: hash header bytes `[0,64)`, then `[72,128)`, initial canonical
  state, initial RF, and initial RK, in that order.
- Frame chain: use the preceding witness as seed and hash frame `[0,24)`;
  the first frame uses the initial witness as seed.
- Terminal state: hash canonical state, working RF, working RK, and the
  raw logical console prefix, starting from the offset basis.
- Footer: hash footer `[0,72)` from the offset basis.

Replay validates structure, dimensions, typed state, ordering, reserved and
unused bytes, the initial witness, the full frame chain, and the footer
before executing guest code. Final verification additionally checks actual
execution state, disks, logical output, counters, and cursor. These are
accidental-corruption/divergence witnesses, not signatures, authentication,
collision-resistant cryptographic hashes, or formal trace equivalence.
