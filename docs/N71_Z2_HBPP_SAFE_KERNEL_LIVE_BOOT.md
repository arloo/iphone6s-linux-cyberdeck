# N71/S8000 — first LIVE boot of Z2 HBPP safe-patched kernel

**Test date:** 2026-11-10
**Status:** **LIVE BOOT AND HOST-ONLY SPI2 STRESS PASS.** Touchscreen firmware/calibration **not yet tested** on this build.

## Confirmed physical boot

The user started `CYBERDECK_A9_Z2_HBPP_SAFE_TEST.iso` from SanDisk Ventoy via the existing DFU → PongoOS → RAM-only m1n1 pipeline. The iPhone 6s (Samsung Apple A9, N71/S8000; aftermarket replacement touchscreen confirmed previously functional in iOS) reached HoolockLinux BusyBox shell.

The Dell was restarted into Kubuntu and a direct root shell on the iPhone was opened over the USB gadget. This independently verified the kernel identity:

```
Linux 7.3.0-rc1-g68aadac820d0-dirty #4 SMP PREEMPT Tue Nov 10 15:00:37 CET 2026 aarch64
```

The `-dirty` suffix identifies the locally compiled source worktree containing the three experimental code changes, as documented in [the build report](N71_Z2_HBPP_SAFE_BOOT_ISO.md). It is not a sign of damaged on-device storage.

| Live check | Readback / observation |
| --- | --- |
| USB identity | `05ac:4142` HoolockLinux USB gadget |
| USB link | `172.16.42.2` Dell → `172.16.42.1` phone, Telnet root shell |
| Initial reachability | 3/3 ping replies |
| After stress reachability | **25/25** ping replies, 0% loss, 2.562 ms mean RTT |
| SPI host and input | `apple-s5l-spi` driver registered, `spi0` available |
| SPI2 domain | `on` |
| SPI2 ref-clock enable count | `1` |
| `touch_ref` clock | Registered, calculated 32,000 Hz at disabled baseline |
| `touch_ref` enable / prepare counts | `0 / 0` |
| N71 clock provider DT status | `okay` |
| N71 Z2 touchscreen child DT status | `disabled` |
| Active SPI children | None |
| Input devices | Only `gpio-keys` / `event0` |
| Kernel fault filter | No Oops, panic, Call Trace, watchdog or SPI error after stress |

A nonfatal `g_multi: -22` appears early in the boot log, as in previous successful boots. The separate configfs USB gadget later initialized correctly. This error is not evidence of Z2 initialization failure.

## 100-cycle real-device stress on the NEW kernel

The running A9 phone executed **100 consecutive guarded `apple-s5l-spi` platform driver unbind/rebind cycles**, after checking that the Z2 child was disabled, the SPI device list empty, and the clock/power baseline valid.

Each iteration required:

- SPI power domain transitions `on → off-0 → on`;
- SPI reference-clock enable count transitions `1 → 0 → 1`;
- touch reference enable count stays `0`;
- platform driver link and `spi0` recover after rebind.

All 100 cycles passed. A separate bounded watchdog and cleanup trap were in place to rebind the host if necessary. The phone remained reachable after the test. This is **not** a 100-transaction test of the Z2 peripheral; it is a bus-controller lifecycle test with the peripheral isolated.

## What remains unproven

Although the new compiled kernel includes code for power/clock rollback, strict HBPP register-read status/checksum validation and bounded `REQ_CAL` handling, the **Z2 child is disabled** for this boot. Accordingly, none of those three Z2 behavior changes has been validated against the actual replacement touchscreen.

The next experimental stage must first establish accurate board-specific clock, core/analog power, reset GPIO and recovery readbacks before enabling Z2. A real `ACK_DATA=0x4bc1` and functioning 750×1334 multitouch evdev reporting remain outstanding. Bluetooth HCI and PCIe Wi-Fi remain separate unfinished hardware enablement paths.

## Reproducibility and privacy

The ISO and embedded payload SHA-256 values appear in the adjacent [safe-boot ISO report](N71_Z2_HBPP_SAFE_BOOT_ISO.md); neither that report nor this one contains raw Apple firmware, per-device calibration, serial numbers, USB MAC addresses, private DT dumps, login credentials or unique provisioning data. The phone ran Linux in RAM only; no iOS NAND modifications were performed during this validation.
