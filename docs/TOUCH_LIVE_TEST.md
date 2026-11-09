# Verified N71/S8000 touchscreen SPI and HBPP bootloader bring-up

**Date:** November 9, 2026
**Hardware:** iPhone 6s, Apple A9 **Samsung S8000**, N71
**Running kernel:** HoolockLinux `7.3.0-rc1-g6831bc701a6c`, ARM64, 16 KiB pages
**Test method:** volatile out-of-tree kernel modules + in-memory Device Tree overlay; **no touch firmware uploaded yet** and no internal phone storage written.

## Confirmed findings

1. The running kernel does not expose SPI2 in its initial Device Tree. We compiled the existing Apple S5L SPI driver and the upstream probe helpers against the **exact running kernel**; all module vermagic strings matched.
2. The test helper powered the SPI2 PMGR domain and read the existing regulator states:
   ```text
   spi2 domain on: 0
   d2255[0x319] (touch core LDO26) = 0x01  [already enabled]
   chestnut[0x05] (touch analog)    = 0x0f  [analog bit 4 disabled]
   ```
3. **Important correction to an upstream prototype overlay:** the live N71 Device Tree's `pinctrl_ap` has phandle **0x0a**, NOT `0x1f`. On our boot `0x1f` refers to a USB2 host power domain. The other required phandles are `aic=0x01`, `clkref=0x05`; a dynamic runtime-only phandle **0xf039** was assigned to the SPI2 power domain. A private corrected SPI2 overlay produced `spi0.0` and:
   ```text
   apple-s5l-spi-v1 20a088000.spi: S5L SPI controller, ref clock 24000000 Hz
   ```
   **Do not copy hard-coded phandles between unrelated Device Trees.** Inspect `/sys/firmware/fdt` / the live phandle map and verify the GPIO provider before applying an overlay.
4. A non-invasive probe at 8 MHz, with the touch analog rail off, transferred 1,024 SPI bytes but returned all `00`. After enabling the 32 kHz touch reference and temporarily enabling the analog rail, the 8 MHz probe received **non-zero bytes** and IRQ transitions, but no recognizable HBPP response.
5. A read-only PMGR register probe found the touch clock at `0x20e078000` reading `0x800002ee` (DISABLE=1, ENABLE=0, divider=750, no unknown bits). A guarded **RAM-only** test activated it with divider 732; hardware readback showed approximately **32,786 Hz**, and no BUSY bit.
6. A guarded, temporary change of the Chestnut touch analog enable bit (register 0x05, value `0x0f -> 0x1f`), combined with a **1 MHz SPI bootloader clock and 5 µs / 10 µs chip-select setup / hold**, led to **successful native HBPP bootloader communication**:
   ```text
   tz2probe-v2 spi0.0: spi_setup mode3 1000000 Hz: 0
   tz2probe-v2 spi0.0: HBPP check 0: ... -> IN HBPP
   tz2probe-v2 spi0.0: HBPP check 1: ... -> IN HBPP
   tz2probe-v2 spi0.0: HBPP check 2: ... -> IN HBPP
   tz2probe-v2 spi0.0: ATN_ACK: 0 rx 48 79
   tz2probe-v2 spi0.0: N1 version reg 0x10008ffc: 0 -> 0x434d15c1
   tz2probe-v2 spi0.0: reset re-asserted
   ```
   This is a **real response from the physical N71 touch controller**, not a simulated or build-only test.
7. The probe was unbound, the Chestnut analog enable bit restored to `0x0f`, and the PMGR touch reference restored to `0x800002ee` (clock disabled). Linux remained accessible over USB; Bluetooth HCI remained available.

## Important limitations

- HBPP bootloader communication is now verified, but **touch firmware execution has not yet been attempted on this device**.
- There is still **no touch input event device**, no verified finger coordinates, no usable single-finger gestures and no multi-touch support.
- Upstream Omarchy-iPhone6s research independently reached coarse/quadrant-only touch reports; full-resolution X/Y remains unresolved. We will not claim working touch from these bootloader results.
- The recovery path remains a RAM-only tethered boot. Avoid persistent iPhone storage writes, blind register writes and undocumented vendor-command fuzzing.

## Next steps

1. Test compiling `apple_z2.c` as a RAM-loadable AArch64 module against the **running kernel**, without modifying the known-good boot image.
2. Stage the locally extracted, private Apple N71 Z2/HBPP firmware (84,092 bytes) under `/lib/firmware/apple/` in RAM and inject the private 1,024-byte per-device calibration through a **non-public** runtime Device Tree overlay.
3. Repeat the strict power/clock guard sequence; bind the N71 Z2 driver at a 1 MHz HBPP initialization rate and capture only minimal, sanitized firmware and input events.
4. If the live-module route fails, use the independently compiled touch-next test kernel for a controlled, **RAM-only** boot with a known-good recovery image preserved.
5. Pursue full-resolution X/Y only from documented, reviewed protocol evidence; do not fuzz unknown controller mode commands.

## Upstream attribution

Research and SPI/Z2 protocol work: [modpunk/Omarchy-iPhone6s](https://github.com/modpunk/Omarchy-iPhone6s), particularly its [touch research](https://github.com/modpunk/Omarchy-iPhone6s/blob/main/docs/drivers/touch.md) and [touch-next PR #19](https://github.com/modpunk/Omarchy-iPhone6s/pull/19). This repository documents **independent, on-device verification on our N71/S8000** and the different live phandle mapping observed on our boot.

No Apple firmware, device calibration, unredacted hardware logs or identifiers have been published.

## Follow-on: full Apple Z2 driver probe and firmware calibration handshake

**Still November 9, 2026; same running Samsung N71/S8000 kernel.**

We compiled the upstream touch-next `apple_z2.c` as a volatile ARM64 module against the **currently running** kernel. For this live-only test, we added narrow compatibility safeguards:

- Fail unless the updated runtime OF node matches the N71 HBPP variant.
- Resolve an IRQ newly added to an already-enumerated SPI device using `of_irq_get`, if the device's original `spi->irq` is absent.
- Use a fixed experimental input-device name rather than dereferencing a potentially missing original SPI modalias after the runtime Device Tree was changed.

The original N71 `apple/mtfw-n71.bin` (84,092 bytes, proprietary; not published) was staged in the iPhone's RAM-only `/lib/firmware/apple`. A private dynamic Device Tree overlay set `compatible = "apple,n71-multitouch"`, `firmware-name`, the touch IRQ and exactly **1,024 bytes of privately recovered calibration**. The overlay was validated on the phone before the module was loaded.

With previously verified 1 MHz HBPP timing, 5/10 µs CS timing, clock and analog power enabled, the driver:

```text
apple-z2 spi0.0: HBPP at 1000000 Hz (run 1000000 Hz), mode 3, CS setup 5000 hold 10000 ns
input: iPhone 6s Touchscreen (A9 experimental) as .../input/input1
apple-z2 spi0.0: HBPP bootloader: 1f 01 48 79 ...
apple-z2 spi0.0: calibration 1038 bytes to 0x10009000: ack 0x1f01 (REQ_CAL), want 0x4bc1
apple-z2 spi0.0: probe with driver apple-z2 failed with error -5
```

**This input registration was temporary and was automatically removed when probe failed. It does not mean touch works.**

To test the hypothesis that the controller simply needed more time, we built a second bounded test module: only for an expected `ACK_DATA (0x4bc1)`, a `REQ_CAL (0x1f01)` status was treated as pending, never as success. We polled at most 50 times; the result was:

```text
apple-z2-v2 spi0.0: calibration 1038 bytes to 0x10009000:
    ack 0x4879 (idle) after 50 polls, want 0x4bc1
apple-z2-v2 spi0.0: probe with driver apple-z2-v2 failed with error -5
```

The result rules out an **immediate-ACK-only timeout**. The calibration DATA packet framing, checksum, byte order or required preceding bootloader sequence needs a documented review. We will not bypass the ACK check, replay arbitrary firmware commands or fuzz unknown vendor modes.

After each test, we restored Chestnut register `0x05 = 0x0f`, PMGR touch clock to `0x800002ee` (disabled), cleared any temporary SPI driver override and confirmed USB connectivity. No Apple data, unique calibration, firmware bytes or raw DT were committed.

## Follow-up: complete Z2 driver reaches the calibration transfer but does not boot (November 9)

The in-tree `apple_z2.c` with upstream N71 HBPP support compiled as an out-of-tree module against the running kernel (exact module vermagic). A **local-only** Device Tree overlay populated the N71-compatible node, the expected firmware filename, IRQ wiring and the confirmed 1,024-byte private calibration. We transferred the 84,092-byte private touch firmware into the RAM filesystem at the filename the driver requests. Neither the proprietary firmware nor the calibration were published.

The first on-device driver bind showed:

```text
apple-z2 spi0.0: HBPP at 1000000 Hz (run 1000000 Hz), mode 3, CS setup 5000 hold 10000 ns
input: iPhone 6s Touchscreen (A9 experimental) ... input/input1
apple-z2 spi0.0: HBPP bootloader: 1f 01 48 79 ...
apple-z2 spi0.0: calibration 1038 bytes to 0x10009000: ack 0x1f01 (REQ_CAL) after 1 polls, want 0x4bc1
apple-z2 spi0.0: probe with driver apple-z2 failed with error -5
```

The input device in the trace was **rolled back** when the driver failed to probe. It did not become a usable touchscreen.

A second, deliberately bounded test accepted the transient `REQ_CAL` and polled up to 50 times for `ACK_DATA=0x4bc1`. The controller instead returned `0x4879 (idle)` at the deadline; the driver failed to bind. A third comparison used the driver's existing `hbpp_cal_swap=0` setting, changing **only** the documented per-16-bit-word calibration byte order, with identical results. The parameter was reset to its original value. We did not proceed to firmware EXECUTE or any undocumented vendor commands.

### Confirmed diagnostic boundary

- **Works:** SPI2 host, GPIO reset and IRQ sampling, touch core and analog supply switching, 32 kHz reference switching, 1 MHz HBPP handshakes, N1 bootloader version `0x434d15c1`, on-device firmware and calibration staging.
- **Blocker:** The 1,038-byte HBPP calibration DATA frame to `0x10009000` does not elicit `ACK_DATA=0x4bc1`.
- **Potential areas for reviewed investigation, not established causes:** calibration DATA checksum/header encoding, chip-select continuity during the long PIO transfer, ACK semantics/timing, this specific N1 bootloader revision, and driver error handling. A status-only trace or packet-format review is preferable to speculative firmware commands.
- **Safety:** After every powered probe, the touch analog switch was verified back at `Chestnut 0x05=0x0f`; the touch clock returned to `0x800002ee` (disabled). The controller reset is asserted by the probe, USB networking remains online, and Bluetooth HCI remains present. None of these tests wrote the iPhone's internal storage.

Help wanted: review the N71 calibration framing against iOS `AppleMultitouchN1SPI`/HBPP, especially with N1 version `0x434d15c1`. Please contribute a reproducible patch or sanitized status-only trace, **not** Apple firmware, calibration contents or per-device identifiers.
