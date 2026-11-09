# Build original static AArch64 cyberprobe for the iPhone 6s test ramdisk.
# Requires an aarch64-linux-gnu cross toolchain on the Linux host.
CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
CFLAGS ?= -O2 -Wall -Wextra -static -s

.PHONY: all clean
BLUEZ_HEADERS ?= /usr/include
all: build/cyberprobe-aarch64 build/hci-probe-aarch64
build/cyberprobe-aarch64: tools/cyberprobe.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<
build/hci-probe-aarch64: tools/hci-probe.c
	mkdir -p build
	$(CC) $(CFLAGS) -I$(BLUEZ_HEADERS) -o $@ $<
clean:
	rm -rf build
