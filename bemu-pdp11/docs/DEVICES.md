<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# Unix V1 device map

Derived from the kernel (`build/u0.s`) and checked against SIMH
(`show <dev>`). Addresses and vectors are 16-bit octal values.
This is the target hardware map, not a claim that every peripheral is
fully implemented; see the compatibility boundary in `../README.md`.

## CPU

PDP-11/20, 32 KW address space (64 KiB, including the final 4 KW I/O page),
without an MMU. The PSW is at 177776. `cold = 0`; the kernel runs at address 0.

## Interrupt vectors and priorities

| Vector | Handler | PSW | Device |
|---|---|---|---|
| 60 | ttyi | 240 | Console input (BR4) |
| 64 | ttyo | 240 | Console output (BR4) |
| 70/74 | ppti/ppto | 240 | Paper tape, not used during warm boot |
| 100 | clock | 340 | KW11-L clock (BR6) |
| 204 | drum | 300 | RF11 (BR5) |
| 214 | tape | 300 | TC11 (BR6) |
| 220 | disk | 300 | RK11 (BR5) |
| 300-377 | trcv/txmt, eight lines | 240 | DC11 multiplexer (BR4) |

## Registers

- DL11 console: TKS 177560, TKB 177562, TPS 177564, TPB 177566.
- DC11 line `n`: base 174000 + `10*n`; RCSR +0, RBUF +2, XCSR +4, XBUF +6.
- KW11-L: LKS 177546. `mov $100,*$lks` enables 60 Hz interrupts.
- RF11: DCS 177460, WC 177462, CMA 177464, DAR 177466, DAE 177470.
- RK11: RKDS 177400, RKER 177402, RKCS 177404, RKWC 177406,
  RKBA 177410, RKDA 177412.
- TC11: TCST 177340, TCCM 177342, TCWC 177344, TCBA 177346, TCDT 177350.
- KE11-A: 177300-177317, DIV/MUL/NOR/LSH/ASH and AC/MQ/SC registers;
  operations do not generate interrupts.

## Boot sequence

The M792 loader at 73700 (`boot/m792low.load`), with switch register
173700, reads `bos` from RF byte offset 1700000 into 54000 and transfers
control to it. `bos` loads the kernel beginning at RF block 964 and jumps
to its entry point. Bemu-pdp11 executes this sequence without a boot shortcut.
See `BOOT_SPEC.md` for transfer sizes and disk layout.
