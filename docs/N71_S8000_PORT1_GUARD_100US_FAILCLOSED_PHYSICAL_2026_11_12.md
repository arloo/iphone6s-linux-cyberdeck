# N71/S8000: physical supervised guard boot — fail-closed 100 µs metadata correction

**Date:** 12 November 2026
**Hardware:** real owner-controlled iPhone 6s, Samsung Apple A9 (N71/S8000)
**Evidence:** physical RAM-only Linux boot and one guarded run on device; **driver did not load**
**Status:** issue reproduced, cause confirmed, corrected replacement RAM image built **offline and not yet booted**.

## Physical guarded-boot observation

The user transferred the private, verified 11,926,991-byte supervised RAM image through PongoOS. The Dell saw `05ac:4141` PongoOS disconnect at **15:15:30 CET**, followed by `05ac:4142` HoolockLinux at **15:15:32 CET**. USB CDC-NCM connectivity again passed **2/2 ping with zero packet loss**.

Independent, read-only in-phone checks confirmed:

- Real `7.3.0-rc1-g68aadac820d0-dirty` Linux and N71 port1 synthetic platform node.
- Exact three original Apple port1/DART1 address windows `0x602000000/0x4000`, `0x602004000/0x4000` and `0x602008000/0x4000`.
- Touch automatic initialization `COMPLETE:PROTOCOL_READY` (not a new physical multi-touch gesture test).
- Supervised `pcie-apple-s8000-guard.ko` and `n71_port1_guard_supervised.sh` present in **RAM only**, with byte-for-byte matching owner-private SHA-256 values.
- **Zero** PCIe endpoints, IOMMU groups and native WLAN interfaces; research guard module **not loaded**, no platform driver bound.

The explicit opt-in mechanism was tested first without permission: it exited with code `2` and `N71_PORT1_GUARD_BLOCKED` while the guard module remained unloaded.

An attended one-time run with the explicit `N71_GUARD_ONE_SHOT_ACCEPT=1` setting **also exited safely with code `2` before `insmod`**. A read-only partial shell trace isolated the exact failure, immediately following verified successful N71 compatible, platform, guard flag, original resource order and port index/mapper checks:

```text
research,refclk-to-perst-delay-us (actual FDT): 0x100 = 256 decimal µs
required original 100 microseconds (guard):    0x64 = 100 decimal µs
N71_PORT1_GUARD_BLOCKED
```

**Root cause: an offline DTB-generation bug, not a proven device hardware fault.** The original private builder passed the literal `100` to `fdtput -t x`, but `-t x` parses numeric values as **hexadecimal**, and therefore encoded `0x100` rather than the intended decimal 100 µs. The independent C guard and manual shell gate both correctly refused to accept the mismatched descriptor; neither was weakened.

No `insmod` succeeded or ran, no PCIe/DART1 MMIO or DMA was performed, and the iPhone stayed booted and reachable over USB. This is a **physically proven safety refusal**, *not* a physical success of the driver.

## Corrected, isolated private RAM boot artifact

The private Device Tree builder now writes the original researched 100 µs delay as the correct hex cell literal `64` and checks the actual on-disk encoded property after `fdtput`.

A separate owner-private **new** corrected RAM image was staged:

```text
private-touch-live-test/n71-port1-guard-refclk100-supervised-next/
  m1n1-linux-n71-port1-guard-refclk100-supervised-ram.bin
```

- **Length:** 11,926,991 bytes.
- **SHA-256:** `490e65ae2857a6617268823698215c9bd6b920ab00830806f2914c81230c5fd3`.
- **Physical test:** NOT BOOTED YET; no claim the corrected image runs until the next actual supervised phone boot.
- **Precisely one logical N71 DTB property change** from the physically booted failed candidate: `research,refclk-to-perst-delay-us` changes from `<0x100>` to `<0x64>`.
- The **entire rest of the boot image** is byte-identical: m1n1 bootloader, S8003 DTB, original known-good kernel, touchscreen resources and firmware/calibration, full initramfs, guarded `.ko` and explicit manual launcher.
- The known-good previous descriptor-only RAM image remains intact. The new candidate still has **no automatic hardware driver activation**.

The public offline [exact 100 µs FDT safety checker](../tools/n71_port1_refclk100_fdt_metadata_gate.py) refuses the *actual old* private research DTB and accepts the *new corrected* private DTB, requiring the block flag, correct port1/DART1 resources, mapper0 and the exact decimal 100 µs field. [Fourteen adversarial regression tests](../tests/test_n71_port1_refclk100_fdt_metadata_gate.py) all pass and explicitly cover the `0x100` vs `0x64` confusion.

## What is and is not proven

**Proven on physical hardware:** the supervised boot image can boot the real Samsung N71 to RAM Linux, keep USB networking alive, initialize the touch protocol and preserve the inert port1/DART1 metadata. Both the no-opt-in and explicit-opt-in paths enforce fail-closed behavior under incorrect refclk metadata.

**Still not proven physically:** the corrected image boot, successful module insertion, successful platform driver preflight, actual controller register semantics, requester-to-DART1 SID, DMA isolation, BCM4350 PCIe enumeration and native Wi-Fi. None may be implied from the physical failure or offline correction.

**Next action:** physically enter DFU/Pongo again, upload the **new corrected** pinned image (not the old rejected one), verify USB Linux `05ac:4142`, touchscreen, register metadata, module hashes and no bound driver, then perform at most **one** guarded module insertion. If that fails, do not force-load; use the known-good earlier RAM image if recovery is necessary. The live Linux kernel has `CONFIG_MODULE_UNLOAD=n`; a successfully loaded guard persists in that RAM boot until reboot. All internal NAND writes and unsupported DART/PCIe DMA remain prohibited.

**Privacy:** no original Apple ADT, proprietary firmware/calibration, kernelcache or executable, MAC address, serial/ECID, raw console transcript or private owner binary is published.
