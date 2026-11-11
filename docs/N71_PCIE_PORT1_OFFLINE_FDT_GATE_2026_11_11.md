# N71 BCM4350 PCIe port-1: compiled Device Tree safety gate

Date: 2026-11-11. Hardware state: NOT STARTED. This deliverable is entirely offline; the real phone remains on its proven Linux touch+GUI RAM boot.

The sanitized S8000 Apple ADT identifies PCIe port 1 as the BCM4350 WLAN endpoint, with dart-apcie1. The other ports include storage port 0 and baseband port 2, which must not be reset, clocked or DMA-mapped by an unqualified prototype.

New tools:
- tools/n71_pcie_fdt_gate.py: bounded read-only FDT binary parser and strict isolation gate, no phone access.
- examples/n71-pcie-port1/port1-disabled.dts: small nonbootable fixture with all ports and DART disabled, no live hardware resources or usable driver compatible.
- examples/n71-pcie-port1/Makefile: reproducible compiled DTB check.
- tests/test_n71_pcie_fdt_gate.py: 19 synthetic test cases including attacks that enable storage, modem, WLAN, PCIe host or DART, swap to the wrong A9 foundry, spoof newer silicon, insert unexpected controllers, duplicate/mislabel ports, introduce MMIO/DMA properties, or corrupt FDT.

This gate deliberately REJECTS any enabled host or port, including Wi-Fi port 1. Passing does not mean the device supports that register layout. It only verifies that a proposed structural starting point cannot accidentally activate unrelated hardware.

Current pinned Linux pcie-apple.c uses a T8103-like generic Apple compatible and has no validated S8000 register profile. Its setup writes to clocks, reset, PHY, MSI and RID/SID mappings. apple-dart.c lacks an S8000 compatible. Current running Linux enumerates zero PCIe devices. Existing m1n1 PCIe code also lacks a directly reusable apcie,s8000 initialization path.

Next, BEFORE any on-device probe, establish independently verified A9 host-bridge and DART layout, port1-only global register side-effect isolation, safe S8000 stream IDs and DMA translation. Create a separately reviewed S8000-specific disabled-by-default driver. Only then use a supervised new RAM-only candidate and never touch ports 0/2 or NAND.

External architecture references:
https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c
https://projectzero.google/2017/10/over-air-vol-2-pt-3-exploiting-wi-fi.html

No raw Apple ADT, device-identifying bytes, unique calibration, firmware, photo, or binary boot image is committed.
