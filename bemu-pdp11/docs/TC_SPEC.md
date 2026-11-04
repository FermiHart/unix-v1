<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# TC11/TU56 DECtape — programmer-visible spec (from SIMH `pdp11_tc.c`)

Source of truth: `tools/simh/PDP11/pdp11_tc.c`; V1 usage: kernel
`tape/taper/tape1/tape2/tape3` (`pages/e08-0*`), `maki.s` `dtio`,
M792 boot ROM (`boot/m792uv1.s`).

## 1. Registers (base 177340, 5 word regs, IOLN 12 octal)

| Addr | Name | Purpose |
|------|------|---------|
| 177340 | TCST | status (error flags, up-to-speed, ext data bits) |
| 177342 | TCCM | command (unit, dir, func, MEX, IE, DONE, ERR, GO) |
| 177344 | TCWC | word count (negative count, DMAs up to 0) |
| 177346 | TCBA | bus address (16b low; extended by MEX) |
| 177350 | TCDT | data (search result / last word; RALL streaming) |

TCCM layout: ERR b15, MNT b13, INH b12, DIR b11 (1=reverse),
unit b8–10, DONE b7, IE b6, MEX b4–5, function b1–3, GO b0.
GO=1 starts the command; DONE=TCCM<7>; IE=TCCM<6>; ERR=TCCM<15>.
TCST layout: END b15, PAR b14, MRK b13, ILO b12, SEL b11, BLKM b10,
DATM b9, NXM b8, UPS b7 (1=at speed), XD b1–0 (upper 2 bits of 18b cell).
TCCM read recomputes ERR as OR of TCST error bits.
TCST writes only affect XD bits (b1–0); high-byte byte-write ignored.
TCWC/TCBA/TCDT are word-only. Interrupt: BR6, vector 214 (SIMH
`IVCL(DTA)`, `VEC_AUTO` → standard 214; kernel `tape;300`).

## 2. Function codes (TCCM b1–3) — V1 names in parens

0 STOP (stop all) · 1 SRCH (`rnum`) · 2 READ (`rdata`) · 3 RALL (read all)
· 4 SSEL (stop selected unit) · 5 WMRK (timing/mark, unsupported→ILO)
· 6 WRIT (write data) · 7 WALL (write all, hdr dumped).
V1 octal words: `3` = rnum fwd+GO; `4003` = rnum rev+GO (DIR=04000);
`5` = rdata+GO (polled); `103` = rnum+IE+GO; `105` = rdata/read+IE+GO;
`115` = write+IE+GO; `1` = stop+GO. WMRK, or a write to a
write-locked unit, raises ILO/SEL. Any TCCM write (except STOP)
puts the selected unit in motion; changing units deselects the old one.

## 3. Command/data flow of a read (what V1 does)

1. `ptc` issues search: `TCCM = unit | 103` (fwd) or +DIR (rev); GO clears
   DONE and error flops first.
2. SEARCH: when a block passes the head, `TCDT = block number`, DONE sets,
   interrupt fires iff IE=1 (deferred one tick on errors). Handler
   (`tape1` fwd / `tape2` rev with +3 overshoot) compares TCDT to wanted
   block: `<` keep moving, `>` reverse (`taper` retries ≤20, else marks
   unit error and goes `tape3`).
3. On match: `TCBA` = core address, `TCWC` = negative count, then
   `TCCM = 105` (read) or `115` (write) +IE+GO (`tape1` picks by the
   queue entry's read/write-waiting bit).
4. READ DMAs tape→memory: `mem[TCBA] = word`, `TCDT` mirrors it
   (low 16b; top 2b into TCST XD), `TCWC++`, `TCBA+=2` (MEX++ on wrap).
   WC overflow (→0) arms substate; at end-of-block: overflow → DONE +
   interrupt and head runs to end zone; else tape continues into the next
   block automatically (multi-block until WC overflows). Reverse reads
   deliver words in reverse order.
5. `tape3` runs `poke` (wakeup), clears queue bits 12–13; if drive still
   busy it picks up read-ahead/write-behind, else writes stop (`1`).
   DONE is polled as TCCM<7> (`tstb`), errors as TCCM<15> (`tst`).

## 4. Errors (TCST, mirrored to TCCM ERR)

SEL = no tape / disabled unit / deselected mid-op; END = end zone;
BLKM = read/write issued mid-block (must start in gap); DATM = overrun
(DONE still set at next RALL/WALL word); NXM = bad bus address;
PAR/MRK = emulated as clear (data-only sim); ILO as above.
Error path: sets TCST+TCCM ERR, stops/decelerates unit, schedules DONE
slightly deferred (RSTS/V4 setup race), interrupts iff IE.
Write-0-to-ERR (not write-1) or a fresh GO clears error flops.

## 5. SIMH "16b format" tape image layout

Default attach format (`UNIT_11FMT`); 578 blocks × 256 words × 2 B
= 295,936 bytes (`D16_FILSIZ`). File offset = `block*512 + word*2`,
little-endian 16b words; upper 2 of the 18b cell load as 0.
Short file: missing tail zero-filled; `hwmark` = words actually read.
Empty/new file: all-zero buffer, reads return zeros. Past block 577:
END error (end zones ~10 ft each side are not stored). Timing/mark
tracks, headers, checksums are NOT stored; RALL synthesizes the
standard header/trailer, WALL discards non-data words.

## 6. No tape attached (or unit disabled)

Register reads/writes still work. Any motion command (search/read/write)
takes the select-error path: `STA_SEL` in TCST, ERR+DONE in TCCM,
interrupt iff IE=1, unit stopped. Detaching mid-operation cancels it and
raises SEL the same way. Boot/cold-start therefore sees DONE+ERR on the
first `rnum` instead of hanging. DECtape model has 8 units (SIMH);
V1 uses unit from queue entry (`(dev-2)<<8`: `tap7` = unit 7).
