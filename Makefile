# Build original static AArch64 cyberprobe for the iPhone 6s test ramdisk.
# Requires an aarch64-linux-gnu cross toolchain on the Linux host.
CROSS_COMPILE ?= aarch64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
CFLAGS ?= -O2 -Wall -Wextra -static -s

.PHONY: all clean test
# Override BLUEZ_HEADERS with an isolated directory containing bluetooth/*.h
# for reproducible cross-compilation (avoid host glibc include pollution).
BLUEZ_HEADERS ?= /usr/include
all: build/cyberprobe-aarch64 build/hci-probe-aarch64 build/le-passive-scan-aarch64 build/ble-probe-aarch64
build/cyberprobe-aarch64: tools/cyberprobe.c
	mkdir -p build
	$(CC) $(CFLAGS) -o $@ $<
build/hci-probe-aarch64: tools/hci-probe.c
	mkdir -p build
	$(CC) $(CFLAGS) -I$(BLUEZ_HEADERS) -o $@ $<
build/ble-probe-aarch64: tools/ble-probe.c
	mkdir -p build
	$(CC) $(CFLAGS) -I$(BLUEZ_HEADERS) -o $@ $<
build/le-passive-scan-aarch64: tools/le-passive-scan.c
	mkdir -p build
	$(CC) $(CFLAGS) -I$(BLUEZ_HEADERS) -o $@ $<
clean:
	rm -rf build

# Offline-only protocol checks; safe to run without a connected phone.
test:
	python3 -m unittest discover -s tests -v
	python3 tools/touch/hbpp_cal_audit.py
	python3 scripts/validate_project.py

# Controlled encrypted BR/EDR data test; never embeds a peer address.
build/n71-bt-l2cap-echo-aarch64: tools/n71-bt-l2cap-echo.c
	mkdir -p build
	$(CC) $(CFLAGS) -I$(BLUEZ_HEADERS) -o $@ $<

# USB-only NBD laboratory bridge: never point this at an Apple device/partition.
build/n71-nbd-client-aarch64: experimental/storage/n71-nbd-client.c
	mkdir -p build
	$(CC) $(CFLAGS) -Werror -o $@ $<

# Root-only, RAM-node, four-pread hardware probe; never auto-run.
build/n71-nand-private-probe-aarch64: experimental/storage/n71-nand-private-probe.c
	mkdir -p build
	$(CC) $(CFLAGS) -Werror -o $@ $<
