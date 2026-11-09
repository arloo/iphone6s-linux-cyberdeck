# Build original static AArch64 cyberprobe for the iPhone 6s test ramdisk.
# Requires an aarch64-linux-gnu cross toolchain on the Linux host.
CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
CFLAGS ?= -O2 -Wall -Wextra -static -s

.PHONY: all clean
all: build/cyberprobe-aarch64
build/cyberprobe-aarch64: tools/cyberprobe.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<
clean:
	rm -rf build
