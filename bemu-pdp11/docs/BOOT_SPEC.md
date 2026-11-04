<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# BOOT_SPEC — V1 RF warm-boot chain (all numbers octal unless noted)

## 0. Conventions
- Word = 2 bytes, little-endian. File offsets decimal bytes; disk blocks 512 B.
- RF disk word addr = ((DAE & 077) << 16) | DAR. File byte off = word addr * 2.
- `JMP @#A` (000137 A): PC := A (effective addr = extension word; no 2nd deref).

## 1. Stage 0 — M792 ROM (`boot/m792low.s` -> `m792low.load`)
- load origin 073700 (real HW 173700, see `m792uv1.s`; simh has no mem there).
- `go 73700`, SR=173700. ROM has no SR test; bos re-checks SR at 177570.
- Register writes (r0=177472, 5x predecrement):
  [177470]=3 (DAE) | [177466]=140000 (DAR) | [177464]=054000 (CMA)
  [177462]=176000 (WC=-2000oct=-1024 words) | [177460]=5 (DCS=read+GO)
  poll: `tstb (r0) / bge .-2` (bit7 DONE). Then `jmp *$54000` -> PC=054000.
- Disk word addr = (3<<16)|140000 = 0x3C000 = 245760 dec = 740000 words.
  Byte addr = 491520 dec = 1700000 (the "1700000 of rf0" comment = byte addr).
  491520 / 512 = block 960.
- Xfer: 1024 words = 2048 B = blocks 960-963 -> mem 054000-055777.
  Verified in simh: post-xfer RFDA=142000 (140000+2000), Mem[54000]=0407.
- `boot/bos`: PDP-11 a.out 0407, 296 B. Header (16 B): 0407 0172 0 0 044 0 0 0
  (tsize=0172oct=122 B text, dsize=0). Word 0407 at 054000 executes as BR.+16,
  skipping header -> text entry 054020 (`mov $177472,r1`).

## 2. Stage 1 — bos (entry 054020, src `fs/usr/boot/bos.s`), SR=*177570
- warm (SR 173700 or 073700): [177470]=3, [177466]=142000, [177464]=0,
  [177462]=-14000oct (WC=-6144 words=6KW), [177460]=5.
  Word addr (3<<16)|142000 = 0x3C400 = 246784 -> byte 493568 = block 964.
  Xfer 6144 words = 12288 B = 24 blocks 964-987 -> mem 0-027777.
  Then `jmp *$400` -> PC=000400 = kernel `mov $ecore,sp` (u0.s: `.=orig+400`).
- cold (SR 1): DAR=156000 -> word 0x3DC00=252928 -> byte 505856 = block 988,
  same WC -> blocks 988-1011 -> mem 0, jmp 400.
- unassigned (SR 2): DAR=172000 -> word 0x3F400=259072 -> byte 518144 = blk 1012,
  WC=-6000oct (-3072 words=6144 B=12 blks) -> blocks 1012-1023 -> mem 0, jmp 400.
- SR 10: TC11 dump 12KW mem 0 -> DECtape unit 7 (no RF). Else: halt loop.

## 3. Stage 2 — unix (`build/unix`, a.out 0407, tsize 040000oct = 16384 B)
- Makefile: `dd if=unix bs=1 skip=16 count=16384 | dd of=rf0.dsk bs=512 seek=964`
  (skip = 16 B a.out header). File bytes 493568+ = kernel text, verified equal.
- bos loads only bytes 0-12287 (24 blks). Kernel text last nonzero = off 8931;
  bytes 12288-16383 are all zero -> 24-block load is complete.
- Note: Makefile writes 32 blocks (964-995); blocks 988-995 overlap cold slot
  (988-1011) but warm boot never reads them.

## 4. Disk layout (`tools/mkfs.c`, `build/Makefile images` rule)
- BLKSIZE=512. RF_SIZE=1024 blks (file actually 509952 B = 996 blks; 996-1023
  absent -> read as zero). RK_SIZE=4864 blks.
- RF inodes: icount = 1024/4 = 256 (RF_INODES 512 unused), 16 inodes/blk ->
  16 inode blocks -> fs data starts block 18. ROOTDIR_INUM=41. Blks 0,1 = freemap.
- RF map: fs 0-431 (RF_NOSWAPSIZE=432), swap 432-959 (SWPSIZ=33 x N_PROC=16),
  boot 960-1023 (KERNBLKS=64): bos 296 B @960 (rest zeros), kernel @964.
- msys slots (octal blk nos): b bos=1700 (=960), u warm=1704 (=964),
  1 cold=1734 (=988), 2 unassigned=1764 (=1012). Copies whole file incl header.
- RK: icount = 4864/4 = 1216 inodes, 76 inode blocks -> data starts block 78.
