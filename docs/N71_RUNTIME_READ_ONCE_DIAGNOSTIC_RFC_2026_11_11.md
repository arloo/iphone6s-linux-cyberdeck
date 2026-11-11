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
