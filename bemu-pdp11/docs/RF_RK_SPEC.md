<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../../LICENSE. -->

# RF11 / RK11 programmer-visible spec (from `pdp11_rf.c`, `pdp11_rk.c`)

Base/vectors/BR live in `docs/DEVICES.md` (RF base 177460 vec 204 BR5; RK base 177400 vec 220 BR5). Below is only what SIMH decodes.

## 1. RF11 (fixed head, word-addressable, no sectors)

| Offset from 177460 | Reg | Access |
|---|---|---|
| 00 | DCS (RFCS) | R/W |
| 02 | WC (RFWC) | R/W |
| 04 | CMA (RFCMA) | R/W, bit0 always 0 (mask 0177776) |
| 06 | DAR (RFDA) | R/W, low 16 bits of disk word addr |
| 10 | DAE (RFDAE) | R/W masked (see below) |
| 12 | DB (RFDBR) | R: last word; W: stored |
| 14 | MR (RFMR) | R/W (maint, no effect) |
| 16 | ADS (RFADS) | R-only rotational position 0..2047 |

DCS bits (octal): ERR 100000, FRZ 040000, WCHK 020000, DPAR 010000,
NED 004000, WLK 002000, MXFR 001000, CLR 000400 (W: full reset),
DONE 000200, IE 000100, MEX 000060 (mem ext 17:16), MAINT 000010,
FUNC 000006, GO 000001. Writable: IE|MEX|FUNC (+CLR/GO triggers).
FUNC: 0 NOP, 1 WRITE, 2 READ, 3 WCHK. `READ+GO = 5`.

DAE bits: ALLERR 0176000 (R-only), NXM 0002000 (R-only, NX memory),
INH 000400 (W: don't incr mem addr), RLAT 000200, DAE 000077 (disk ext).
R mask 0176677, W mask 0000677.

Command sequence: WC=`-nwords` (counts up to 0) -> CMA (even) ->
DAR -> DAE -> DCS=`FUNC|MEX|GO` (+IE). Starts only if DONE=1 and
FUNC!=NOP. On GO: DONE cleared, WCHK/DPAR/NED/WLK/MXFR cleared,
INT cleared, rotational delay then DMA. On finish: DONE=1;
ERR=OR(ALLERR incl. NED); FRZ=OR(DAE_ALLERR); NED=(da>=capac);
if IE and DONE 0->1: interrupt vec 204 BR5. Writing DCS with IE=0
clears pending INT; with DONE&IE set re-asserts it. Reset: DCS=DONE.

Disk address (22-bit word index): `da = ((DAE&077)<<16) | DAR`.
File byte offset = `da*2`. Geometry: 2048 words/track x 128 tracks =
262144 words/platter (512 KiB); 1..8 platters (default 1);
transfer 1..65536 words, auto-increments `da` (wraps 22b) and
`ma+=2` (wraps 18b field) unless INH. No block/sector structure.

Write path: per word `Map_ReadW(ma)->fbuf[da]`, DBR=word,
hwmark=da+1. Lock check: `(da>>15)&037` indexes 32-bit `rf_wlk`;
set bit -> WLK error, no write. WCHK func compares mem vs disk,
mismatch -> WCHK error. Read path: `fbuf[da]->DBR->Map_WriteW(ma)`;
NXM on bad `ma` aborts with DAE_NXM. Overflow (`da>=capac`):
NED error, stop.

## 2. RK11 (RK05 cartridge, 256-word sectors)

| Offset from 177400 | Reg | Access |
|---|---|---|
| 00 | RKDS | R-only (constructed) |
| 02 | RKER | R-only (clear by CTLRESET/INIT) |
| 04 | RKCS | R/W |
| 06 | RKWC | R/W (`-nwords`) |
| 10 | RKBA | R/W, mask 0177776 |
| 12 | RKDA | R/W (ignored while DONE=0) |
| 14/16 | RKMR/RKDB | unimplemented (R=0) |

RKCS bits: ERR 100000, HERR 040000, SCP 020000 (seek done),
INH 004000 (no mem incr), FMT 002000, SSE 000400, DONE 000200,
IE 000100, MEX 000060, FUNC 000016>>1, GO 000001.
FUNC: 0 CTLRESET, 1 WRITE, 2 READ, 3 WCHK, 4 SEEK, 5 RCHK, 6 DRVRESET, 7 WLK.
Kept R/W mask RKCS_RW=0006576.

RKDA bits: DRIVE 15:13, CYL 12:5 (0..202), TRACK 12:4 (=cyl*2+surf),
SECT 3:0 (0..11). Block = `track*12+sect`. File byte = `block*512`.
RKDS (on read): ID 15:13 = interrupting drive, RK05+SC_OK+rand sect
always; +RDY if attached; +RWS if idle; +WLK if locked;
+ON_SC if SECT==current. RKER: DRE 100000, OVR 040000, WLK 020000,
SKE 010000, PGE 004000, NXM 002000, DLT 001000, TE 000400,
NXD 000200, NXC 000100, NXS 000040, CSE 000002, WCE 000001
(SOFT=WCE+CSE, HARD=0177740).

Sequence: RKDA -> RKBA -> RKWC -> RKCS=`FUNC|MEX|GO` (+IE).
CTLRESET: clr RKER/RKDA/RKBA, CS=DONE, clr queue. WLK: set sw lock+DONE.
DRVRESET: clr sw lock, seek cyl 0. SEEK: schedule, on completion
SCP=1 + queue per-drive bit (interrupts only if DONE already set,
so R/W wins). READ/WRITE/WCHK validate then seek+rotate delay.
Completion: DONE=1, ERR=(RKER!=0), HERR=(RKER&HARD),
`RKWC+=wc`, `ma+=2*wc` (unless INH), RKBA/MEX from `ma`,
RKDA advanced (sector-rounded; FMT-read counts sectors).
DONE+IE -> INT vec 220 BR5; IE=0 clears queue. `rk_inta` dequeues
one bit, puts drive in RKDS_ID, returns vector.

Geometry/drive: 203 cyl x 2 surf x 12 sect x 256 w (512 B) =
4872 blocks, 1247232 words (~2.39 MiB). 8 drives, one cmd at a time.
FMT bit: with READ fills buffer with cyl nos; with others -> PGE.
INH: single mem addr reused (last/first word). OVR: `da+wc>capac`
trims + sets OVR. NXM trims `wc` by failed count.

## 3. No-disk behavior + image formats

| Case | RF | RK |
|---|---|---|
| No file attached | DONE+ERR+NED (`UNIT_BUF`=0 check) | GO: disabled slot->NXD; else !ATT/busy->DRE; svc !ATT->DRE; RKDS lacks RDY (/RWS if busy) |
| Reset state | CS=DONE, rest 0 | same + queue empty |
| SIMH image | raw flat LE words, whole drive buffered (`MUSTBUF`); no header. `capac=platters*262144` w; autosize `p=(size+524287)/524288`, clamp 1..8 platters | `sim_disk` 512 B sectors, type "RK05", 3 reserved secs; formats AUTO/SIMH/VHD/RAW; short file reads as zero; writes zero-pad to sector; OS I/O err stops |
