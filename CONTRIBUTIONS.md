<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see LICENSE. -->

# Local contributions, attribution, and license

## House signature

```text
Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
```

The spelling, spacing, infinity symbol, and email follow the public
[BasmOS source header](https://github.com/FermiHart/BasmOS/blob/main/basmos.basm).
That reference establishes the signature format only; its license is not
imported into this project.

## Governing license

All our contributions in this repository use the **same original
`unix-v1` terms** reproduced in [LICENSE](LICENSE). No separate house
license applies. The upstream license file is retained unchanged,
including the Caldera copyright notice, redistribution conditions,
advertising acknowledgement, non-endorsement condition, and disclaimer.

This product includes software developed or owned by Caldera
International, Inc.

The new copyright attribution identifies our implementation and integration
work. It neither replaces historical authorship nor claims ownership of
the original UNIX sources. Existing third-party components, including
Apout and SIMH, retain their respective notices and licenses.

## Scope

- `bemu-pdp11/`: the Basm emulator, regression programs, automation,
  documentation, and build metadata.
- `qemu/`: the Linux/SIMH launcher, guest initialization, configuration,
  tests, and documentation.
- `jash11/`: the independently implemented native PDP-11 shell edition,
  isolated image builder, validation, and documentation. No modern Jash
  source is imported or relicensed by this profile.
- Root `Makefile`, `.gitignore`, and `README.md`: local integration changes
   only; their upstream content is preserved.
- Root `CHANGELOG.md`: the public summary of our implementation changes.

Generated executables, disk images, and unmodified third-party files do not
receive invented source authorship. The QEMU image carries copies of this
notice and the original `LICENSE` under `/unix/`.

## Source-header convention

Use the signature above and a relative reference to the original `LICENSE`.
Use native comment syntax: `;` for Bear Basm, `/` for the V1 assembler,
`#` for shell/Tcl/Make/configuration files, and HTML comments for Markdown.
Keep a script's shebang on its first line. Existing notices must not be
removed or replaced.

All project-authored documentation, messages, and comments are written in
English. The external assembler is named **Bear Basm**; a compatible
derivative may be selected with `BASM=/absolute/path/to/basm`. The default
is the `basm` command on `PATH`, without private workspace paths.
