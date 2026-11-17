# N71 / S8000 storage port0: asserted PERST and root-power experiment

Date: 17 November 2026. **Real physical iPhone 6s Samsung S8000 test.**
The test was conducted from authenticated USB SSH into the existing,
verified 7.3.0-rc1 N71 Linux RAM boot, without modifying internal flash.

## Objective

Close the difference between **observing** storage GPIO160 in an
input-low state and holding S3E reset **actively low** while temporarily
powering PCIe link0 and exercising the original Apple S8000 root-port
control sequence. The experiment expressly **never drives GPIO160 high**,
does not release the storage endpoint from reset, does not configure DMA
and does not submit NVMe commands.

## Hardware sequence and observed results

Module: `experimental/port0/n71_s3e_p0_asserted_reset_rootstart.c`.
The exact executable logic was tested on the device. After testing, only
the module's introductory source comment was editorially clarified.

1. N71/S8000 board, original power state, WLAN `14e4:43a3`, GPIO160,
   GPIO161 and PCIe common-root baseline guards passed.
2. Linux claimed storage-only GPIO160 via the real Apple pinctrl GPIO
   provider, drove **OUTPUT LOW**, and confirmed the pin register:
   `0x00072202` (original `0x00072200`).
3. S8000 root NVMe mode `root+0x24 = 1` was temporarily enabled.
4. The **real** `pcie_link0` generic power domain reached
   `actual=15, target=15`; dwell was 25 ms.
5. Original port0 root ID3 and ID2 bit0 RMW operations acknowledged:
   - ID3 baseline `0x00000100`, temporary bit0 set.
   - ID2 baseline `0x01000110`, temporary bit0 set.
   - Storage endpoint remained under physically **asserted PERST**.
6. The physical DART0 (`0x601008000`), NVMMU0
   (`0x601004000`) and storage-port (`0x601000000`) MMIO regions
   still returned **`0xffffffff`**. The port0 root-link status
   ID5 `0x00000000` remained down, while port1 Wi-Fi ID5 was
   `0x00000001` (up).
7. The module restored ID2 and ID3, powered link0 back off
   (`actual=0, target=0`), restored root NVMe mode to `0`, and
   restored GPIO160 through the **native pinctrl driver's regmap**.
   It confirmed the original exact pin value `0x00072200` and
   unchanged Wi-Fi GPIO161. GPIO160 was released, and the module was
   subsequently unloaded cleanly.

The diagnostic intentionally returned an internal `-EIO` because the
DART0/NVMMU0 reads were invalid; **this is a test failure for storage
accessibility, not a failure of restoration**. The kernel's
`DIAGNOSTIC_REJECTED_AFTER_SAFE_ROLLBACK` log denotes that no further
automatic attempts were performed. Follow-up real-device checks
confirmed Wi-Fi carrier 1, USB SSH available, battery 51% charging,
`pcie_link0` off, GPIO160 unowned and no block devices.

## What this test proves and does not prove

**Proven:** The complete bounded N71-only sequence can coexist with
live Wi-Fi while actively holding NAND PERST asserted. The GPIO
provider, S8000 root controls and PMGR can be driven and restored
without needing another reboot or retaining a quarantined module.

**Not proven:** DART0/NVMMU0 MMIO accessibility, translation table setup,
PCIe port0 link training, discovery of Apple SSD PCI `106b:2002`,
or any Linux NAND/namespace read path. GPIO160 has not been deasserted
because doing so without validated DMA protections could expose
unprotected internal storage bus mastering.

The remaining problem is **not solved** by the stock root mode, ID3/ID2
RMW, temporary link0 PMGR power and active PERST alone. Investigate the
N71/S8000-specific port0 PHY/REFCLK control and the DART0/NVMMU0
clock/register accessibility path. Further experiments must use exact
Apple original firmware evidence and fail-closed guards; do not blindly
copy S8003 sequencing, modify storage partitions or bind generic NVMe.

## Safety and publication

The repository publishes original project C source, a synthetic source
contract test and sanitized hardware observations. Owner-private Apple
firmware, the full encrypted iOS backup, SSH material, host keys,
hardware identifiers and kernel logs containing identifiers remain
private on the Dell. No NAND writes or persistent iOS changes occurred.
