<!-- Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com> -->
<!-- License: original unix-v1 terms; see ../LICENSE. -->

# Jash/11 1.0 — native Unix V1 edition

A bounded, independently implemented shell running **inside the restored
Unix V1 kernel**. Edition 1.0 targets the supported commands and limits
documented here; it is not feature equivalence with modern Jash, POSIX
certification, or a claim of physical PDP-11 validation.

The guest is entirely Basm source containing explicit PDP-11 words,
assembled with Bear Basm. Bemu remains entirely Basm and has no
Jash-specific execution hooks. The host does not interpret guest commands.

## Build and run

```sh
make run-jash11
```

Log in as `root`, then launch the native edition explicitly:

```text
# /bin/jash
Jash/11: native PDP-11 shell, Unix V1 edition.
# version
Jash/11 1.0 (native Unix V1 edition)
# echo "hello from PDP-11" >/tmp/hello
# cat </tmp/hello
hello from PDP-11
# echo 'echo script-ok' >/tmp/run
# source /tmp/run
script-ok
# complete /usr/s
/usr/src
/usr/sys
# history
# exit
```

The visible root prompt remains **`# `**. `exit` returns to the historical
shell. `/bin/sh`, the kernel, `init`, `getty`, and the login configuration
are not replaced. To close Bemu itself, use **Ctrl-E**, **Ctrl-A then X**,
or **Ctrl-X then A** (release Ctrl before the final letter).

Requirements: Linux x86-64, a compatible [Bear Basm](https://github.com/FermiHart/basm)
installation, GNU `ld`,
the repository's image-building tools, Python 3, `expect`, and `flock`.
Select the assembler with `BASM=/absolute/path/to/basm` if necessary.

## Builtins

| Command | Behavior |
|---|---|
| `echo [-n] [ARG...]` | Write literal arguments separated by spaces; `-n` omits the newline. No backslash interpretation. |
| `help`, `version` | Show the native edition's implemented contract and version. |
| `cd DIR`, `chdir DIR` | Change this shell's working directory. |
| `source FILE` | Execute an ASCII command file in this shell; nested `source` is rejected. |
| `history` | Display the last four retained interactive commands, numbered oldest to newest. |
| `history clear` | Clear retained history buffers. |
| `history off`, `history on` | Disable-and-clear or enable session history. |
| `!!`, `!1` through `!4` | Recall a retained entry as a standalone interactive command. |
| `complete PREFIX` | Print bounded filename/command candidates; does not edit the current input line. |
| `plain`, `color` | Disable or restore the Midnight prompt palette. |
| `exit` | Leave Jash/11, not the emulator. |

External commands use the native V1 `fork`/`exec`/`wait` ABI: try the given
pathname, then `/bin/`. `echo` is native; the historical `/bin/echo` remains
unchanged and can still be selected explicitly.

## Syntax and bounds

- At most **119 normalized input bytes** before newline and **eight argv
  entries**, including the command. Redirection filenames do not consume
  argv entries. Oversized input is drained, never executed as a prefix.
- Spaces and tabs separate arguments. Single/double quotes preserve
  whitespace and allow empty arguments and adjacent fragments. A backslash
  quotes the next byte, except inside single quotes, where it is literal.
- Quoting is deliberately simpler than POSIX: no variable or command
  expansion is performed, including inside double quotes. For example,
  `echo '$HOME'` prints literal text; unquoted expansion syntax is rejected.
- An unquoted `#` at a word boundary begins a comment in command files.
  Files are ASCII. The historical console's `#` erase / `@` kill behavior
  occurs before the shell sees terminal input and is not changed here.
- Pipes, `;`, `&`, `&&`, `||`, globbing, and expansion are rejected before
  command execution. Quoted or escaped metacharacters are literal data.
- Bracketed-paste markers are normalized, including across V1 canonical
  chunks. Only single-line paste is accepted; multiline paste is discarded
  as a whole. Unknown terminal controls are rejected. EOF exits incomplete
  input without spinning.

## Redirection and scripts

`< FILE`, `> FILE`, and `>> FILE` work with or without adjacent whitespace.
`>` truncates; `>>` appends or creates. A command may have one input and one
output redirection. Duplicate redirections, empty targets, and incomplete
syntax are rejected before any child or output file is created.

Descriptor changes occur in a child. Input is opened before output, so a
missing input cannot truncate an existing output file. Diagnostics use a
separate console descriptor. `echo`, `help`, `version`, history display,
and `complete` support redirection; state-changing builtins reject it
without creating files or losing parent state.

```sh
/bin/jash -c 'echo one-command'
/bin/jash -p /tmp/run
```

`-c` executes one bounded command without a banner or prompt. A script file
executes one command per line, also without interactive presentation.
`source` changes the current shell's state; a separately launched script
does not. Command-file reading uses a separate fd, leaving child stdin
connected to the terminal unless redirected. Source descriptors are closed
in exec children. Invalid lines produce diagnostics; subsequent lines
continue. A final line without a newline is supported. Command files must
be regular files, not directories or device nodes.

## History, completion, and privacy

History is **session-only** and bounded to four 119-byte entries. It stores
successfully parsed interactive commands, including commands that later
fail at dispatch. History commands, syntax failures, source-file bodies,
and duplicate recall are not added. Indices change when the oldest entry
is evicted. Recall is supported only as a standalone interactive command,
not substitution inside another command or a script.

No history file is created. Child-program input, such as a password prompt,
is not read by the shell's command reader. Command arguments can nevertheless
contain secrets: use `history off` before sensitive commands. Clearing
history is not a claim to erase arbitrary guest memory or disk content.

`complete PREFIX` searches the current directory and then `/bin/` for a
bare prefix, or the specified directory for `DIR/PREFIX`. It checks V1's
eight-byte names, skips hidden entries unless the prefix starts with `.`,
and prints at most 16 results in filesystem order. Results are not sorted
or deduplicated. Directories are verified before reading and closed on
all normal/error/limit paths. Tab insertion and arrow-key history are not
implemented: the unchanged V1 console is canonical, not a modern raw editor.

## Presentation and compatibility boundary

The Midnight palette uses a bright-cyan banner and a bold bright-white
prompt symbol. Attributes reset before the trailing space. `plain`,
`color`, and `/bin/jash -p` provide explicit control; V1 has no modern
`NO_COLOR`/`TERM` environment contract. Script and `-c` startup never emit
the interactive banner or prompt.

The restored V1 kernel does not provide native pipes, `dup`, modern job
control, or POSIX child exit status. This edition does not emulate those
features deceptively through the host. There is no environment expansion,
alias system, modern Jash module ABI, AI integration, execution attestation,
or kernel patch. The validated runtime is the guest console; diagnostic
output targets `/dev/tty8` when available, with stdout as a fallback.

## Artifact and disk safety

The `0407` executable loads at `040000` octal. `BITS 64` selects the
assembler container, not the guest CPU. The image verifier enforces an
**8 KiB initialized-code/data budget** within the 16 KiB user window,
reports the exact byte count and SHA-256, checks native file installation,
and rejects RF filesystem overlap with swap/boot space.

Builds use a locked private candidate and validate before publication.
Previous experimental disks are retained under `previous.*/` in the output
directory, preserving their inodes and writes from already running emulator
processes. Backups are not pruned automatically. The provided make launcher
waits for publication; arbitrary manual multi-file opens are not a claimed
atomic transaction. Close a session before switching profiles when practical.

The base disks in `build/` and `images/`, historical shell/init/getty bytes,
and the original boot/kernel region are preserved. Select a disposable
output directory when testing alongside a live session:

```sh
make test-jash11 JASH11_OUTPUT_DIR=/absolute/path/to/disposable-images
make test-bemu
```

Tests use private disk copies. The same artifact is checked independently
in Bemu and SIMH for both presentation and the supported edition. Packaging
tests check byte-identical assembly, the memory cap, validation failure,
concurrent-build exclusion, and continued writes to retained image inodes.

`make qualify` at the repository root adds the complete builtin rejection
matrix, hidden completion, literal/unsupported backticks, child-stdin
isolation, three-round Bemu/SIMH runs, temporal replay, and QEMU boot.
See [the complete test instructions](../bemu-pdp11/README.md#regression-coverage)
for prerequisites, private evidence output, and failure handling.

## Attribution and license

Copyright (c) 2026, **F E R M I ∞ H A R T** —
[contact@fermihart.com](mailto:contact@fermihart.com).

All new code uses the original `unix-v1` terms in [../LICENSE](../LICENSE).
No source from the differently licensed modern Jash is imported. Its
default theme was inspected as a functional reference; ANSI SGR values
are standard terminal controls. Historical authorship is retained.

This product includes software developed or owned by Caldera
International, Inc.
