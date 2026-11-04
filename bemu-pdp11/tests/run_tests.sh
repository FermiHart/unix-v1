#!/bin/sh
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../../LICENSE.
#
# run_tests.sh — CPU, KE11-A MMIO and console regressions.
set -eu
CDIR="$(cd "$(dirname "$0")" && pwd)"
BEMU="$CDIR/../bemu-pdp11"
BASM="${BASM:-basm}"
APOUT="$CDIR/../../tools/apout/apout"
APOUT_ROOT="$CDIR/../../fs/root"
export APOUT_ROOT
T="$(mktemp -d "${TMPDIR:-/tmp}/bemu-tests.XXXXXX")"
trap 'rm -rf "$T"' EXIT

# Assemble with the repo's V1 as and extract .text.
assemble() {
  cp "$1" "$T/t.s"
  if ! ( cd "$T" && "$APOUT" "$APOUT_ROOT/bin/as" t.s ) > "$T/as.log" 2>&1; then
    cat "$T/as.log" >&2
    exit 1
  fi
  # V1 as can report errors without a nonzero exit status.
  if grep -Ev '^(I|II)$' "$T/as.log" | grep -q .; then
    cat "$T/as.log" >&2
    exit 1
  fi
  TSZ=$(od -An -tu2 -N4 "$T/a.out" | awk '{print $2}')
  dd if="$T/a.out" of="$T/t.bin" bs=1 skip=16 count="$TSZ" 2>/dev/null
}

asm_run() {
  # $1 = source, $2 = stdin, $3 = expected stdout, $4 = description
  assemble "$1"
  if ! OUT=$(printf '%s' "$2" | timeout 10 "$BEMU" --test "$T/t.bin" 2>"$T/run.log"); then
    echo "$4 FAIL" >&2
    cat "$T/run.log" >&2
    exit 1
  fi
  [ "$OUT" = "$3" ] || { echo "$4 FAIL: got [$OUT] want [$3]"; exit 1; }
  echo "$4 PASS"
}

asm_run "$CDIR/cpu2.basm" "" "" "cpu2 self-test"

"$BASM" -f bin -o "$T/cpu3.bin" "$CDIR/cpu3.basm"
if ! timeout 10 "$BEMU" --test "$T/cpu3.bin" > /dev/null 2>"$T/run.log"; then
  cat "$T/run.log" >&2
  exit 1
fi
echo "cpu3 EAE PASS"

"$BASM" -f bin -o "$T/cpu7.bin" "$CDIR/cpu7.basm"
if ! timeout 10 "$BEMU" --test "$T/cpu7.bin" > /dev/null 2>"$T/run.log"; then
  cat "$T/run.log" >&2
  exit 1
fi
echo "cpu7 canonical PSW PASS"

asm_run "$CDIR/cpu4.basm" "" "" "cpu4 clist-ops"
asm_run "$CDIR/cpu5.basm" "" "" "cpu5 putlu-shape"
asm_run "$CDIR/cpu6.basm" "" "" "cpu6 MOVB/condition codes"
asm_run "$CDIR/ke11.basm" "" "" "KE11-A MQ/DIV/LSH"

asm_run "$CDIR/echo.basm" "ABC" "ABC" "echo console"
python3 "$CDIR/test_escape.py" "$BEMU" "$T/t.bin"
