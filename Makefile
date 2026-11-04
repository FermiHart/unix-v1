# Local integration additions:
# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see LICENSE.

JASH11_OUTPUT_DIR ?= $(CURDIR)/jash11/build
export JASH11_OUTPUT_DIR

all:
	$(MAKE) -C tools
	$(MAKE) -C build install

run: all
	tools/pdp11 simh.cfg

run-qemu: all
	qemu/run-qemu.sh

run-bemu: all
	$(MAKE) -C bemu-pdp11
	./bemu-pdp11/bemu-pdp11 images/rf0.dsk images/rk0.dsk

test-bemu:
	$(MAKE) -C tools
	$(MAKE) -C build
	$(MAKE) -C bemu-pdp11 test test-boot

run-bemu-time:
	$(MAKE) -C tools
	$(MAKE) -C build
	$(MAKE) -C bemu-pdp11
	./bemu-pdp11/bemu-pdp11 --time-travel build/rf0.dsk build/rk0.dsk

test-time-travel:
	$(MAKE) -C tools
	$(MAKE) -C build
	$(MAKE) -C bemu-pdp11 test test-boot test-time test-time-boot

qualify:
	python3 bemu-pdp11/tests/qualify_release.py

jash11:
	$(MAKE) -C tools
	$(MAKE) -C build
	$(MAKE) -C jash11 images

run-jash11: jash11
	$(MAKE) -C bemu-pdp11
	@printf '%s\n' 'Log in as root, then run /bin/jash (or /bin/jash -p for plain output).'
	./bemu-pdp11/bemu-pdp11 "$(JASH11_OUTPUT_DIR)/rf0.dsk" "$(JASH11_OUTPUT_DIR)/rk0.dsk"

test-jash11:
	$(MAKE) -C tools
	$(MAKE) -C build
	$(MAKE) -C bemu-pdp11
	$(MAKE) -C jash11 test

clean:
	$(MAKE) -C build clean

distclean: clean
	$(MAKE) -C tools clean
	$(MAKE) -C build distclean

.PHONY: all run run-qemu run-bemu test-bemu run-bemu-time test-time-travel qualify jash11 run-jash11 test-jash11 clean distclean
