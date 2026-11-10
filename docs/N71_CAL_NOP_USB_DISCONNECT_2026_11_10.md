# N71/S8000 incident — USB loss during calibration-NOP experiment

**Date:** 2026-11-10. **Target:** iPhone 6s N71 Samsung A9 S8000, aftermarket replacement display. **Kernel:** native RAM-only Linux 7.3.0-rc1-g68aadac820d0-dirty build #5.

**Status: HARDWARE BLOCKED.** Phone stopped enumerating via USB. No final kernel log, calibration ACK or recovery confirmation.

## Before the incident

The iPhone previously enumerated as USB 05ac:4142 and answered the direct host link 172.16.42.1. Status-only SPI2 tests had independently verified the raw controller version 0x434d15c1 with strict HBPP READ_DATA and checksums, and clock, reset and Chestnut analog baseline had been qualified. No Linux touchscreen EVDEV input was operational.

A single-use private ARM64 kernel module was built specifically for the running kernel ABI; 53 external references were verified against its exports. Its only calibration-bearing transmission was a 1,040-byte HBPP frame: one optional two-byte NOP, standard 10-byte DATA header to 0x10009000, 1,024 bytes of device-specific calibration in word-swapped wire order, and four-byte checksum. The preceding original calibration experiment had used 1,038 bytes without NOP. The original firmware container structurally comprises one CALIBRATION operation followed by two DATA operations.

The per-device calibration was extracted from an existing private 1,550-byte device-tree overlay and validated as exactly 1,024 bytes without printing its contents. The module contained one-run guards, a 1.5-second delayed cleanup watchdog, reset/power/clock baseline checks and intended explicit memory wiping. These safeguards do not establish a successful cleanup when no completion log is available. Neither its private source code nor its compiled module may be published.

The operator transferred this private module into the phone's volatile RAM using an HTTP server bound only to the dedicated Dell USB-gadget address, verified the destination SHA-256, and issued one insmod command. No automatic retries or firmware upload followed.

## Actual observed result

After the shell marker SINGLE_CAL_NOP_HBPP_EXPERIMENT, the remote console did not return a module status, HBPP reply or post-test clock/supply readbacks.

The Dell recorded an actual host-side event at **2026-11-10 20:21:05**: USB port 1-1 disconnected, including removal of the CDC-NCM interface. Subsequent lsusb contained no phone, ping to 172.16.42.1 returned four losses out of four, TCP port 23 was unreachable, and the USB network interface disappeared. A later read-only recheck still found no re-enumeration.

**No ACK_DATA=0x4bc1 was observed.** The physical state of the clock, Chestnut analog rail, reset pin, watchdog, module-memory zeroization, Linux kernel and touchscreen is unknown after USB loss. This result is a negative observation, **not proof of a particular crash root cause**.

The operator stopped the private USB HTTP server immediately, restricted sensitive experiment source and module files to mode 0600 with private directory mode 0700, and performed no USB reset, simulated GPIO toggle or new SPI attempt while the user was away.

## Hypotheses — none established

The difference between the 1038-byte original DATA framing and 1040-byte NOP-prefixed DATA framing could matter, but the loss could also stem from Apple S5L polled SPI handling, the long programmed RXCNT/TXCNT transaction, analog/power interactions or a bug in the private test harness. Earlier 1038-byte SPI attempts returned REQ_CAL/IDLE without this observed USB disconnection; that limits confidence in a length-only explanation.

The current Apple S5L SPI polled PIO driver programs its transfer count directly. The incident-specific private helper used a **single 1040-byte SPI transfer**, bypassing apple_z2_hbpp_xfer; consequently, RFC 0006 alone would **not** have changed that private helper. A future private helper would have to use the patched driver or independently implement bounded segmentation without releasing CS. The Apple Z2 driver previously used up to 4,096 bytes per transfer. A separate **offline-only, not hardware-qualified** RFC reduces its chunks to 256 bytes while keeping all pieces in one SPI message to preserve chip select. See the versioned patch 0006-n71-hbpp-segmented-spi-256-rfc.patch. It has **not** been used on the disconnected device and must never be described as a verified fix.

## Safe recovery gate

1. A person physically present must inspect the iPhone. Do not infer DFU state or issue recovery commands until its actual USB identity is observed.
2. If a restart is necessary, use attended DFU → PongoOS → the last known good RAM-only ISO/kernel build #5 or earlier fallback. Avoid iOS NAND flashing.
3. Restore the USB gadget and obtain **read-only** PMGR, Chestnut, PMU, GPIO/reset and SPI2 baseline readings before attempting powered Z2 probes.
4. Reproduce small status-only controller reads with exact checksums. Do not repeat the 1040-byte single-transfer private experiment unattended.
5. A future write-bearing calibration attempt requires an independent recovery/diagnostic path that survives loss of USB gadget, or direct operator attendance; physical clock behavior and segmentation must be verified.
6. Keep the per-device calibration, private binary and raw logs outside Git.

The project release gate stays **BLOCKED**: no accepted calibration, no working Linux EVDEV touch, and no confirmed multitouch. S8003 remains deferred until compatible hardware is available.
