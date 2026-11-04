<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# Console / mux / clock programmer-visible spec (bemu-pdp11)

Sources: `tools/simh/PDP11/pdp11_stddev.c` (console DL11 + KW11-L),
`pdp11_dl.c` (multi-line DL11), `pdp11_dc.c` (DC11),
`pdp11_defs.h` (CSR/addr/vec/IPL constants); cross-checked against
V1 kernel `build/u0.s` (vector table), `u4.s` (clock handler), `u9.s`
(DC11 handlers). Octal throughout. Common: `CSR_IE`=0000100 (bit 6),
`CSR_DONE`=0000200 (bit 7), `CSR_ERR`=1000000 (bit 15).

## 1. DL11 console — TKS 177560, TKB 177562, TPS 177564, TPB 177566

- TKS read returns only DONE+IE (`TTICSR_IMP`); no side effect.
- TKS write: only IE is writable; odd-byte write ignored. IE 1->0
  clears a pending rx interrupt; IE 0->1 with DONE already set
  requests an interrupt immediately. TKB is read-only (writes ignored).
- Rx char arrives (see §4): TKB buffer latched, DONE set; if IE set,
  interrupt at vector 60, BR4 (`IPL_TTI`=4; kernel PSW 240).
- TKB read returns latched byte (low 8 bits; `& 0377`). Reading an
  empty TKB returns the stale last byte. Any TKB read clears DONE and
  clears the rx interrupt, then re-arms the poll timer.
- If a new char arrives while DONE is still set and < 500 ms old, it
  is silently dropped (no overrun bit on the console DL11). After
  500 ms the new char overwrites the buffer.
- Break input stores 0 in TKB (still sets DONE / interrupts).
- TPS reset state: DONE set (transmitter idle). TPS read returns only
  DONE+IE; TPB read returns last byte, no side effect. TPS write: only
  IE writable, same int arm/disarm rules; vector 64, BR4 (`IPL_TTO`=4).
- TPB write: low byte latched, DONE cleared, tx interrupt cleared,
  output starts. On completion DONE set; if IE set, interrupt (64/BR4).
- Multi-line DL11 (`pdp11_dl.c`, for reference, not used by V1):
  same DONE/IE positions; RBUF additionally carries ERR bit 15,
  OVR bit 14, RBRK bit 13; XCSR has XBR bit 0, MAINT bit 2.

## 2. DC11 mux — 8 lines, base 174000, 8 bytes/line

- Line n (0-7): RCSR=174000+10n, RBUF=174002+10n, XCSR=174004+10n,
  XBUF=174006+10n (SIMH: `ln=(PA-ba)>>3`, `IOLN_DC`=010). Block covers
  174000-174077. Bits are NOT DL11-identical:
- RCSR: bit 7 DONE, bit 6 IE (same as DL11), plus bit 0 DTR (RW),
  bit 1 XBR (RWNI), bit 2 CDT (RO), bit 5 PAR odd-parity (RO, 0000040),
  bit 12 OVR (RO), bit 13 RNG (RO), bit 14 CCH (RO), bit 15 ERR (RO,
  recomputed on read as OVR|RNG|CCH). Writable mask 0003533.
- XCSR: bit 7 DONE, bit 6 IE, bit 0 RTS (RW), bit 1 CTS (RO),
  bit 2 MNT (RWNI). Read mask 0100737, write mask 0000535.
- Rx: char latched in RBUF; DONE set, or OVR set if DONE already held
  (new char still replaces buffer, PAR recomputed); if IE, rx interrupt.
  Matches V1 `trcv` (`tst r2; blt` = ERR bit 15, `bit $40,r2` = PAR).
- RCSR read has a side effect: clears DONE and OVR|RNG|CCH|ERR.
  RBUF read: clears the line's rx interrupt, returns the byte,
  re-arms the poll timer. V1 reads RCSR then RBUF, in that order.
- RBUF writes ignored. XBUF write (low byte): clears DONE + tx int,
  starts output; completion sets DONE, interrupts if IE.
- Vectors: rx = base+10n, tx = base+10n+4. V1 base 0300 gives
  300,310,...,370 (rx) and 304,...,374 (tx), table through 377;
  all BR4 (kernel PSW 240; `IPL_DCI`/`IPL_DCO`=4). Interrupt
  acknowledge clears that line's request; lowest requesting line wins.

## 3. KW11-L line clock — LKS 177546, vector 100, BR6

- Single 16-bit register; only DONE (bit 7) + IE (bit 6) exist
  (`CLKCSR_IMP`). 60 Hz nominal (SIMH `clk_tps`=60, tick 16667 us).
- V1 boot does `mov $100,*$lks`: 0100 = IE bit only. That write also
  clears DONE (data bit 7 = 0), so the clock starts clean.
- Each tick sets DONE; if IE set, interrupt at vector 100, BR6
  (`IPL_CLK`=6; kernel PSW 340). DONE stays latched (no error/counter
  semantics); ticks re-request the interrupt every 1/60 s while IE=1.
- LKS read returns DONE+IE (on 11/20, which has the monitor bit,
  `HAS_LTCM` includes `CPUT_20`) and has NO side effect. V1's handler
  (`u4.s`: `tst *$lks`) relies on this: no ack write needed.
- LKS write: only IE writable (odd byte ignored); a 0 in data bit 7
  clears DONE (monitor-bit CPUs). Clearing IE clears the interrupt.
  Interrupt acknowledge does not clear DONE on 11/20 (only on 11/24).

## 4. Host stdin polling semantics to reproduce (SIMH model)

- Console rx is polled, not event-driven: `tti_svc` runs on the
  simulator clock every poll quantum and calls `sim_poll_kbd()`.
- `sim_poll_kbd` returns `SCPE_OK` (0) = no character ready
  (also for errors/disconnect). Ready = return value >= `SCPE_KFLAG`,
  character = return & 0377 (plus a BREAK flag bit for break).
- Linux backend: single non-blocking `read(0, buf, 1)`; `status != 1`
  means not ready. No buffering of partial state in the device.
- Hence the emulated contract: each poll, at most one byte moves
  host -> TKB + DONE (+ interrupt if IE); DONE=0 must read as "no
  input", and handler flow (TKB read clears DONE) naturally paces
  the next poll. Console mode 7P: high bit cleared, non-printing
  suppressed (V1 default `TT_MODE_7P`).
