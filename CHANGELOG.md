<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see LICENSE. -->

# Changelog

## Unreleased

### Added

- Bemu-pdp11: native Linux x86-64 PDP-11 emulation written entirely in
  Basm, assembled with Bear Basm and linked without libc. Boots the
  restored Unix V1 kernel and historical shell.
- Basm time-travel runtime: complete machine/media checkpoints, private
  RF/RK versions, opt-in session recording, deterministic replay, reverse
  instruction navigation, exact boundary seeking, and a host monitor.
- Jash/11 1.0 native Unix V1 edition: quoting/escapes, redirection,
  scripts and `source`, command mode, session history/recall, bounded
  completion, native echo, and controlled console presentation.
- QEMU launch path using a minimal Linux guest and SIMH PDP-11.
- Isolated image packaging, regression suites, and repeatable release
  qualification through `make qualify`.
- A responsive machine-geometry hero, real Unix/Jash terminal captures,
  and a reproducible reverse-execution animation for the public README.
- A standalone English project site with accessible animation controls,
  source-bound media staging and automated GitHub Pages publication.

### Fixed

- PDP-11 byte-memory reads, MOVB register sign extension, condition codes,
  KE11-A MQ/AC sign-word behavior, and PSW serialization independent of
  stale host-register bits.
- Host exit controls and terminal/stdin restoration, including sessions
  running the unchanged historical shell.
- Rejection of excess disk arguments instead of silently replacing the
  selected RK image.
- Rejection of unsupported unquoted backticks before Jash command effects,
  while retaining quoted and escaped backticks as literal data.
- Host monitor line endings in raw terminals, without changing guest
  console bytes or redirected diagnostic line endings.

### Compatibility and safety

- Preserve the historical kernel, `/bin/sh`, `init`, `getty`, and upstream
  attribution. Contributions use the unchanged original `unix-v1` license.
- Ordinary Bemu sessions retain writable-disk behavior. Temporal modes use
  read-only bases and private working images, without base writeback.
- Recordings contain sensitive guest state and finalize on clean exit.
  Version 1 does not provide crash recovery or alternate-input branches.
- This profile does not claim complete PDP-11 ISA/peripheral coverage,
  POSIX shell compatibility, or physical-hardware qualification.

This product includes software developed or owned by Caldera
International, Inc.
