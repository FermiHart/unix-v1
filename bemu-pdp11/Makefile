# Bemu-pdp11: 100% Basm, assembled with Bear Basm.
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.

BASM ?= basm
LD ?= ld

SRC = src/bemu_pdp11.basm
OBJ = build/bemu_pdp11.o
BIN = bemu-pdp11

all: $(BIN)

$(BIN): $(OBJ)
	$(LD) -o $@ $(OBJ)
	chmod +x $(BIN)

$(OBJ): $(SRC) src/time_travel.basm
	@mkdir -p build
	$(BASM) -f elf64 -o $@ $(SRC)

test: all
	./tests/run_tests.sh

test-boot: all
	expect tests/test-boot.exp

test-time: all
	python3 tests/time_travel.py

test-time-commands: all
	python3 tests/time_travel_commands.py

test-time-boot: all
	python3 tests/time_travel_boot.py

clean:
	rm -rf build $(BIN)

.PHONY: all test test-boot test-time test-time-commands test-time-boot clean
