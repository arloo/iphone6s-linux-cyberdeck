# N71/S8000: bounded runtime-report diagnostic RFC

**Date:** 2026-11-11. **Status:** offline ARM64 build and private RAM-only staging PASS. The new diagnostic has NOT yet been booted or physically tested.

## Evidence and problem

On a supervised Samsung S8000/N71 iPhone 6s (aftermarket panel known to work in iOS), the existing private calibration and both firmware blocks were acknowledged. The kernel logged firmware start, registered Linux touchscreen EVDEV event0 with 750x1334 geometry, and maintained USB gadget connectivity. Attended touch input produced no EVDEV events. Apple GPIO142 IRQ counter remained 1, with 320/320 read-only samples at 200ms intervals showing GPIO142 high. Narrow electrical pulses could evade sampling.

The upstream-derived Z2 driver did not bound the untrusted runtime report length against its 4000-byte receive buffer, nor validate the number of fingers against frame length before parsing. This is a kernel memory safety concern independent of the IRQ symptom.

## Patch 0007

RFC 0007 applies after RFC 0001-0006 to the pinned clean HoolockLinux Linux source 68aadac820d01d0cd4efbd1fefd4c45f23be0a51.

* Serialize threaded IRQ and manual runtime SPI report reads with a mutex.
* Refuse a controller-supplied report length outside the received-frame buffer or smaller than required header.
* Reject malformed finger counts before parsing the packet.
* Expose /sys/bus/spi/devices/spi0.0/runtime_probe on S8000/N71 only, after a successful boot. A single userspace read requests precisely one bounded READ_INTERRUPT_DATA transaction and returns rc, reply byte, packet length and finger count; no raw firmware or touch payload is printed.
* No firmware upload, NAND writes, regulator or clock manipulation, reset sequences, automated retry or polling loops are added. A requested SPI read involves sending a command and is not an entirely passive electrical observation.

## Reproducibility and physical acceptance

The new ARM64 Z2 object and complete Image.gz linked successfully on the Kubuntu host. Original already-booted RAM payload was reconstructed byte-for-byte from pinned original components before staging the new private RAM payload. The original working boot payload and older recovery image remain immutable. Private calibration and firmware remain only in the private workspace. All seven RFC patches applied cleanly in sequence to a new pinned kernel worktree. Synthetic test checks validate bounded arithmetic, not physical touchscreen functionality.

**Next supervised gate:** perform exactly one new private RAM boot from DFU/PongoOS, confirm Linux gadget and HBPP startup, then issue one requested runtime_probe read while touching the panel. A reply E1 and well-formed contact report, a different reply, malformed report and SPI error each imply different subsequent experiments. Real EVDEV tracking IDs, coordinates and release still determine functional touch acceptance.

**Stop condition:** if USB is lost, do not loop uploads. Recover using the previously proven RAM payload under supervision. Never alter Apple NAND or publish Apple firmware, private calibration, serial identifiers or raw device logs.

## Physical verification — 2026-11-11, build #2

The privately staged 11,816,131-byte RAM-only N71/S8000 payload booted ARM64 Linux 7.3.0-rc1-g68aadac820d0-dirty #2. Host USB transitioned PongoOS 05ac:4141 to HoolockLinux 05ac:4142, ICMP 3/3 PASS. N71 device-specific calibration ACKed, both firmware blocks ACKed and the driver logged firmware started at 0x10003400. The last log means EXECUTE sent and 40ms elapsed; it does not independently prove capacitive scans.

Sysfs diagnostic runtime_probe is present on-device. The *initial automatic* driver report read saw reply E1 with a calculated short length of 20 bytes, and correctly rejected it as insufficient for the expected touch report layout. The *single manual* user-triggered runtime_probe read (no held-finger coordination) returned rc=-61 reply=0xea len=0 fingers=0. -61 is the driver's ENODATA for a non-E1 response, not a USB transport error. GPIO142 remained high with touch IRQ total 1. USB remained stable (2/2 ICMP after the probe). No actual EVDEV events observed.

The meaning of 0xea or the short E1 report is not proven on this device. Upstream Z2 developers have documented non-E1 not-ready responses during startup and added an explicit E1 guard, but this does NOT prove that EA is a not-ready marker on S8000. Reference: https://lkml.iu.edu/hypermail/linux/kernel/2512.2/03692.html

Next bounded gate: perform one user-timed read-once while the operator continuously holds a finger on the display; then inspect interrupt counter and USB stability. No automatic repeated probe, firmware upload or GPIO flip. This experiment is still classified PARTIAL, not functional touch.


## Finger-held one-shot, same physical RAM boot

A second, exactly-once manual runtime probe was performed while the operator confirmed a continuous finger press on the panel. The SPI diagnostic again returned **rc=-61 reply=0xea len=0 fingers=0**, identical to the previous idle read. GPIO142 Linux IRQ count remained **1**. Host USB gadget 05ac:4142 remained present; 2/2 ICMP replies after the probe.

This does not establish that the controller firmware completed its full operating-mode initialization, nor does it prove the GPIO wiring is defective. In the external m1n1 Z2 SPI tracer, the Z2 runtime command set includes a **0xee wake command**, report metadata queries and an 0xeb interrupt-read operation. The current experimental N71 driver proceeds from firmware EXECUTE directly to 0xeb without an explicit 0xee wake or device-info/report initialization sequence. This is a **specific source-verified diagnostic hypothesis**, not authorization to send 0xee blindly, and cannot be assumed to apply identically to N71.

Next gate should review a physically compatible N71 protocol trace or independently validated Z2 runtime sequence before any further SPI write. Instrument one command with full 16-byte framing, checksum, timing, bounded timeout, rollback and expected reply only after validating the sequence; never claim real touch until EVDEV events pass.
