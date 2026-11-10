# N71/S8000 SPI2-OFF — first on-device boot validation

**Date:** 2026-11-10
**Hardware:** iPhone 6s, Samsung Apple A9 (S8000/N71)
**Status:** **PASS** for conservative RAM-only kernel boot; **not** a touch or Wi-Fi bring-up result.

## Boot image and method

The previously prepared separate `CYBERDECK_A9_SPI2_OFF_TEST.iso` was booted on the Dell XPS via Ventoy/palen1x. Eight embedded toolkit file checksums passed. The user entered DFU, loaded PongoOS, and started the `00-spi2-off` m1n1 + Linux payload via the USB PongoOS handoff.

- Experimental RAM boot payload SHA-256 (verified on host): `0c93711939a7d847c9ef323e16205bda0160253cc4021f4bdcc4b5821f94cc93`.
- Known-good recovery payload retained: `220e086184d0cfdec1f04f3ea038e4c439378c8add6610727357fd2d4503c032`.
- The host PongoOS tool reported an upload of 11,249,548 bytes followed by `LIBUSB_ERROR_IO` as the bootloader USB connection closed. The phone's display independently showed the HoolockLinux test ramdisk shell and USB gadget startup.

After the Dell returned to Kubuntu, a live USB-root Telnet shell into the phone confirmed the new boot.

## Live evidence collected through the phone's Linux shell

| Check | On-device or host evidence | Result |
| --- | --- | --- |
| Kernel release | `uname -a` -> `7.3.0-rc1-g68aadac820d0`, AArch64 | **PASS: new experimental kernel, distinct from old `g6831bc701a6c`** |
| Board model | `/proc/device-tree/compatible` -> `apple,n71 apple,s8000 apple,arm-platform` | **PASS** |
| USB enumeration | `lsusb` on host -> `05ac:4142` HoolockLinux | **PASS** |
| USB network | host `172.16.42.2/24`, phone `172.16.42.1` | **PASS** |
| USB stability | ten consecutive ping replies, no loss; 2.302 ms average | **PASS for this brief test** |
| Remote shell | BusyBox root Telnet on isolated USB port 23 | **PASS** |
| SPI2 generic PM domain | `/sys/kernel/debug/pm_genpd/spi2/current_state` -> `off-0`, repeated | **PASS: SPI2 stays off** |
| Registered SPI endpoints | `/sys/bus/spi/devices` empty | **PASS: none enumerated** |
| Input devices | `/proc/bus/input/devices` lists only `gpio-keys` at `event0` | **PASS: touch remains inactive** |
| Runtime loadable modules | `/proc/modules` empty | No extra modules loaded |
| Bluetooth | `/sys/class/bluetooth` empty | **Not initialized after new RAM boot**; requires separate board-specific PMIC/firmware retest |
| RAM | `MemTotal: 2024176 kB` | About 1.93 GiB visible |

The kernel log had an early legacy `g_multi` initialization failure (`-22`). The configfs-based USB gadget subsequently bound and worked; do not misrepresent the legacy error as a full USB failure. The filtered diagnostic scan showed no `kernel panic`, `Oops` or call trace; this is **not** a full audit of every boot line.

## Scope and safety

- This proves a first **real-device** boot of the conservative SPI2-OFF kernel, not just ISO validity or emulator operation.
- **No touchscreen calibration was attempted**, no SPI2 driver was probed, and no analog touch power or clock control was modified by the test instructions.
- Bluetooth receiving advertisements was previously validated on the old kernel, but **not yet revalidated** on this fresh experimental build.
- Neither PCIe Wi-Fi nor multitouch is functional as a result of this test.
- The test is RAM-only: nothing here requires flashing or restoring iOS. The original boot payload and the separate recovery ISO remain available.
- Telnet root is unencrypted. Restrict it to the isolated USB gadget and do not bridge it to an untrusted network.

## Next experiment gate

Prepare and separately validate the existing `01-spi2-host-only` candidate, with the N71 Z2 child **still disabled**. Only after a supervised boot should the SPI host driver lifecycle be checked, comparing generic PM-domain state before driver bind, during bind and after unbind, with USB shell and recovery immediately available. Do not power analog touch rails, transfer private calibration or test the NOP hypothesis yet.

**Hardware acceptance:** no immediate faults, USB shell alive, SPI2 off. **Functional touch acceptance:** not met.
