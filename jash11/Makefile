# Copyright (c) 2026, F E R M I ∞ H A R T <contact@fermihart.com>
# License: original unix-v1 terms; see ../LICENSE.

BASM ?= basm
JASH11_OUTPUT_DIR ?= $(CURDIR)/build
export JASH11_OUTPUT_DIR

all: build/jash

build/jash: src/jash11.basm
	@mkdir -p build
	$(BASM) -f bin -o $@ $<

images: build/jash
	sh tools/build-images.sh

test: images
	expect tests/native.exp bemu
	expect tests/native.exp simh
	expect tests/edition.exp bemu 5
	expect tests/edition.exp simh 5
	python3 tests/packaging.py

.PHONY: all images test
