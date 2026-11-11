# N71/S8000: D9 descriptor read and conditional AF enable

Date: 2026-11-11. Status: RFC #9, OFFLINE-VALIDATED ONLY, NOT YET BOOTED ON PHYSICAL HARDWARE.

## Real hardware basis

The Samsung A9 iPhone 6s/N71 has already booted Linux kernel #3 with private device calibration ACK, firmware-block ACKs, Z2 firmware EXECUTE and EVDEV registration. The supervised runtime experiment sent exactly one EE wake and two E3/D9 report-info requests. The second D9 reply was E3, status 0, size 16 and matched the 16-byte response checksum. Touch IRQ on GPIO142 stayed at 1, GPIO high. This proves a responsive D9 metadata query, but neither a readable descriptor nor operational touchscreen input.

## Protocol sources and uncertainty

The GPL-2.0-or-later Corellium Project Sandcastle daemon (https://github.com/corellium/projectsandcastle/blob/master/hx-touchd/hx-touchd.c) describes a two-transaction E7 long-report read for D9. The first is a 16-byte E7 D9 command declaring length 16. The second is a 21-byte data clocking frame:

* Mode 1: a structured 21-byte E7 D9 01 10 00 frame with a final 16-bit little-endian byte-sum checksum.
* Mode 2: 21 bytes of A5 without the same request header.

The corresponding MTFW_SET_TYPE field is not part of the N71 firmware loader metadata in the current private kernel build. Therefore which mode is correct for this particular iPhone remains UNPROVEN. The driver requires an explicit choice and refuses to retry the alternative automatically or within the same boot. Physical evidence must classify the selected mode.

For both firmware modes, the source issues an AF short write of a single zero byte and then an E1 commit. Type 1 additionally uses 9D and BF report initialization. The optional AF command here does NOT guarantee touch events.

## Patch 0009 and controls

Patch path: patches/0009-n71-d9-geometry-and-optional-af-enable-rfc.patch. Apply AFTER public RFCs 0001 to 0008 on pinned HoolockLinux Linux source 68aadac820d01d0cd4efbd1fefd4c45f23be0a51.

Existing manual sysfs controls on an N71/S8000 device:
* runtime_state: passive text state query; no SPI transaction.
* runtime_wake: write ASCII 1, one EE wake maximum.
* runtime_d9: write ASCII 1, up to two E3 D9 metadata queries.

New manual opt-in sysfs controls:
* runtime_d9_fetch: write ASCII 1 for Mode 1, or 2 for Mode 2. Requires successful wake and exactly two D9 info queries, last status zero, reply E3, announced length 16, checksum agreement. On first operator request it locks the single-use gate, sends ONE E7 D9 16-byte command followed by ONE fixed-length 21-byte transfer in the selected mode. Copies only the 16 descriptor bytes locally and summarizes first reply, read checksum agreement and signed 16-bit metric fields; no proprietary payload bytes leave the private memory buffer. No fallback to the other mode.
* runtime_af: write ASCII 1, available only after a successful descriptor fetch with plausible geometry; sends ONE E4 AF 01 00 short write and ONE E1 commit, with no automatic retry. No other report IDs are modified.

Descriptor metric offsets are based on the Sandcastle implementation: signed16 LE left=8, bottom=10, right=12, top=14 within the 16-byte report. Plausibility requires left less than right, top less than bottom, and both positive axis spans at most 20,000 units. A plausible geometry is still an *indicative* heuristic, not definitive proof of correct panel type. The driver does not presume a specific checksum model for the incoming E7 data frame; the flag is observational.

All request writes are root-controlled, S8000-only and synchronized with the Z2 threaded IRQ handler. No reset, power-rail toggles, clock mutations, flash writes, firmware uploads after boot, or unattended polling loops were added. Device-identifying values, calibration bytes and proprietary firmware are never committed publicly.

## Offline checks and physical validation

The modified Z2 object and full ARM64 Image.gz cross-compile on the Kubuntu host. The previously booted private RAM image is reproducible byte-for-byte from m1n1, original bootargs, original private N71 DTB and initramfs, disabled S8003 DTB and saved previous kernel. The new private payload differs only by its newly compiled Image.gz; all original recoveries remain untouched. The public tests cover both E7 frame formats, checksums, state gates, bounds and optional AF command construction, but DO NOT establish real hardware functionality.

Physical gate: one supervised DFU/Pongo RAM boot, verify baseline firmware and USB, execute EE once, E3/D9 twice with status read between, select a single explicitly justified D9 transport mode and fetch once. Inspect the four coordinates and stability before deciding whether to send AF once. Then assess IRQ and evdev tracking/release (and if needed one bounded runtime_probe while a finger is held). No automatic mixed-mode retry. On USB loss or unexpected SPI results, STOP and recover using the prior verified RAM payload.

A physical touch pass requires real EVDEV Type B tracking ID, in-range X/Y, SYN_REPORT, release and two-finger sequences; nothing in this RFC should be described as full touch support yet. S8003/N71m remains outside the physical experiment scope.
