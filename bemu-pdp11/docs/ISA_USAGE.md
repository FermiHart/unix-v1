<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# ISA usage by Unix V1 (kernel + init + sh + boot ROMs)

Scope: `build/u0.s-u9.s, ux.s, init.s, sh.s`, `boot/m792low.s, m792uv1.s`
(16 files; `ux.s` is data-only). Parser: strip `/` comments (not `\/`),
split `;` inline words, first token must be a V1-`as` mnemonic (vocab from
`usr/src/cmd/as19.s`: `sys`=104400 TRAP; `halt=0 wait=1 rti=2` are plain
symbols in u0.s). Total: **2908 instructions**, 46 distinct mnemonics.

## Frequency (descending)
| mnemonic x count (x4 per row) |
|---|
| mov 709, jsr 342, br 203, beq 150 |
| cmp 139, bne 133, movb 124, tst 96 |
| rts 92, clr 83, sys 78, jmp 58 |
| asl 55, tstb 54, add 53, inc 47 |
| bit 39, bic 37, asr 37, sub 34 |
| cmpb 34, dec 30, clrb 28, bis 28 |
| bgt 27, bge 23, bhis 22, blo 19 |
| blt 18, incb 17, neg 16, decb 12 |
| bitb 12, blos 9, bhi 7, bes 6 |
| ble 6, rti 6, bec 5, bisb 5 |
| bcs 3, swab 3, rol 3, bcc 2 |
| asrb 2, halt 1, bicb 1 |

## Explicit present/absent checklist
- `mul div ash ashc` (and `mpy dvd als alsc` aliases): **absent as opcodes
  (0x)**. EAE is driven by `mov` to MMIO regs (`div`=177300, `ac`=177302,
  `mq`=177304, `mul`=177306, `sc`=177310, `lsh`=177314, `ash`=177316,
  `csw`=177570; predefined in as19.s): `mov $12.,div`, `mov $-8,lsh`, ...
- `xor sob sxt mark spl mtps mfps` (+`mfpi mtpi`): **absent (0x)**.
- `emt trap` mnemonics: **absent (0x)** — no such vocab in V1 `as`; syscalls
  use `sys` (=TRAP, see below). `bpt iot rtt reset nop`: **absent (0x)**.
- `rti`: **present 6x** (u0.s rtssym return; u1.s sysret x2; u4.s x3).
- `wait` opcode: **absent (0x)** (`sys wait` is a syscall, not opcode 1).
- `halt`: **1x but dead** — inside `.if cold` (cold=0), never assembled.
- Byte ops present: `movb cmpb bitb bicb(1x) bisb clrb incb decb tstb asrb(2x)`.
  Absent: `comb negb adcb sbcb rorb rolb aslb`.
- Word single-op present: `clr inc dec neg tst asl asr rol(3x,u8.s) swab(3x)`.
  Absent: `com adc sbc ror`.
- Branches present: `br bne beq bge blt bgt ble bhi blos bhis` + aliases
  `bec bcc` (=bhis/clear) and `bes bcs blo` (=blo/set). Absent: `bpl bmi bvc bvs`.
- All 7 word double-ops present: `mov cmp bit bic bis add sub`.
- `jsr`: r0 x317 (call + inline args via `(r0)+`), r5 x13, pc x12.
  `rts`: all 8 regs (r0 dominant; r1-r5/sp/pc only in rtssym table, u0.s:324-331).

## R7/PC addressing in source text
- `$N` immediate (=(PC)+): **569x** (incl. `$'c` char consts, `$sys`).
- `*$N` absolute (=@(PC)+): **60x** (`jmp *$54000`, `jmp *$173700`,
  `tst *$177350`, ...). Literal `(r7)+` / `@(r7)+` / `X(r7)`: **0x** —
  PC-relative access is spelled with bare symbols (`mov ac,...`,
  `jsr r0,alloc`) and assembled by `as` into X(PC)/@X(PC) forms.
- `*sym` deferred-relative (@X(PC)): **46x** (`*u.fofp`, `*u.r0`, ...).
- `*(Rn)` / `*N(Rn)` deferred (other regs): **8x** (`*(r0)`, `*2(r5)`, ...).
- No `@Rn` / `@(Rn)+` / `@N(Rn)` spellings outside the above.

## EMT / TRAP numbers used
- `sys <name>` = TRAP 104400+n, n = syscall no.; args are inline words after
  it (kernel reads trap word via `mov -(r0),r0; sub $sys,r0`, u1.s:25-26).
  Vectors: EMT=30 oct -> `rtssym`, TRAP=34 oct -> `sysent` (u0.s:54-58).
- Used (78x): close 11, open 11, exec 10, exit 7, seek 5, write 5, intr 3,
  quit 3, chmod 3, creat 3, read 3, wait 2, fork 2, chown 2, mount/time/
  getuid/chdir/stat/break 1x each, plus numeric `sys 1` (=exit, u1.s:224)
  and `sys 0` (=sysrele, u4.s:36). Unused by these sources: link unlink
  mkdir tell umount setuid stime fstat cemt mdate stty gtty ilgins nice.
- Explicit `emt`: never emitted. `rtssym` decodes EMT#0-7 at runtime
  (`bic $!7,r0`; #6 -> `badrts`, u0.s:282-333). `sys cemt`(29)/`sys ilgins`(33)
  repoint the user EMT(30) / illegal-insn(10) vectors (u1.s:437-459).

## NEVER used (safe to defer -> illegal-insn trap, vector 10)
`mul mpy div dvd ash als ashc alsc xor sob sxt mark spl mtps mfps mfpi mtpi
emt trap bpt iot rtt reset wait halt nop com comb adc adcb sbc sbcb negb ror
rorb rolb aslb bpl bmi bvc bvs clc clv clz cln sec sev sez sen`, all FP
(`setf movf addf ...`), `mulf divf` words. Rare-but-required: `rol swab bicb
bisb bitb asrb bcc/bcs/bec/bes` (keep; 1-12x each).

## Implementation priority
1. `mov/movb` + all modes (incl. `-(sp)/(sp)+/N(sp)`, `*sym`, `$`/`*$`).
2. Branches + CCR (N/Z/V/C), aliases `bec/bcc/bes/bcs/blo/bhis`.
3. `cmp/cmpb bit/bitb bic/bis add/sub`, `tst/tstb clr/clrb`.
4. `jsr r0/r5/pc` (+inline-word convention), `rts` all regs, `jmp` all modes.
5. `inc/incb dec/decb neg asl/asr(+asrb) rol swab`.
6. `sys` (TRAP to `sysent`, inline args) + `rti` + vectors 30/34.
7. EAE-as-MMIO words at 177300-177316 (plain `mov`, no CPU mul/div needed).
8. Devices only after CPU boots to `br panic` loop (u0.s:265-267).
