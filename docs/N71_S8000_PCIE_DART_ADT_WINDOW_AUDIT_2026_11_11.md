# N71/S8000: PCIe WLAN and DART physical-resource audit

2026-11-11. **OFFLINE RESULT; NO LIVE PCIe LINK OR DMA PROBE.** The iPhone continues to run its known-good native Linux framebuffer and automatically initialized multitouch.

## Breakthrough: a preexisting DART hardware-family profile

Two identical private Apple Device Tree (ADT) snapshots were independently checked by a new strictly read-only audit tool. Both describe the S8000 host as apcie,s8000 with four PCIe ports, a wlan-pcie,bcm4350 endpoint on bridge 1, and a distinct dart-apcie1 node. Crucially, the DART compatible list contains **dart,s8000 AND dart,s5l8960x**. The pinned Linux driver already includes the legacy apple,s5l8960x-dart OF match and a four-stream, 36-bit output address profile.

The Apple ADT and Linux OF compatible strings are *not literally identical*. Whether this older DART hardware layout can safely operate on A9 remains UNTESTED. The WLAN endpoint has an IOMMU parent reference and the associated DART child mapper reports index 0; a working Linux phandle/stream ID relationship, DMA translation and fault behavior have NOT yet been established.

## Allowed audit results: physical address map (metadata only)

| S8000 resource | Base | Size |
|---|---|---|
| PCIe shared/global region 1 | 0x600000000 | 0x8000 |
| PCIe shared/global region 2 | 0x600008000 | 0x4000 |
| PCIe configuration aperture (functional mapping unverified) | 0x610000000 | 0x1000000 |
| Port 0 storage window A | 0x601000000 | 0x4000 |
| Port 0 storage window B | 0x601004000 | 0x4000 |
| **Port 1 WLAN window A** | **0x602000000** | **0x4000** |
| **Port 1 WLAN window B** | **0x602004000** | **0x4000** |
| **DART1 WLAN** | **0x602008000** | **0x4000** |
| Port 2 baseband window A | 0x603000000 | 0x4000 |
| Port 2 baseband window B | 0x603004000 | 0x4000 |
| DART2 baseband | 0x603008000 | 0x4000 |
| Port 3 unknown window A | 0x604000000 | 0x4000 |
| Port 3 unknown window B | 0x604004000 | 0x4000 |
| DART0 storage | 0x601008000 | 0x4000 |

The host has eleven physical register windows and three DART register windows. All fourteen regions are pairwise nonoverlapping. Their existence DOES NOT prove that shared root complex initialization can avoid writing storage/modem-controlled registers. Port window A/B register semantics are not yet known: do not reuse modern T8103 offset definitions.

The ADT additionally lists MSI vector offset 0x100, host IRQs 0xf4/0xf7/0xfa/0xfd, clock gate IDs 0x39..0x3e and power gate ID 0x38, but NO runtime operations on these resources are authorized.

## Public reproducibility without private binary publication

Public file tools/n71_s8000_adt_window_gate.py reads only allowlisted hardware fields from a **private local** Apple ADT via the new visitor hook in tools/adt-pcie-map.py. It checks compatible lists, 11 expected PCIe registers, all three DART ranges, WLAN endpoint, mapper index, nonzero IOMMU reference, host ports/interrupt metadata, address bounds and overlap. It never publishes raw ADT, unknown properties, firmware, calibration, serials, MAC addresses or device fingerprints.

Usage (requires a private file, NEVER commit the file):

    python3 tools/n71_s8000_adt_window_gate.py /private/path/to/runtime-apple-adt.bin

Successful output contains BOTH S8000_ADT_METADATA_GATE_PASS and HARDWARE_BLOCKED. Nineteen synthetic tests in tests/test_n71_s8000_adt_window_gate.py reject corrupted ADT, wrong silicon, spoofed WLAN, altered or overlapping memory windows, missing/incorrect DART, wrong mapper index, absent IOMMU reference and accidental disclosure. Together with the previous compiled-DTB isolation gate, **38 adversarial PCIe/DART safety tests are now available offline.**

## Remaining actual hardware blockers

The pinned Linux PCIe Apple driver only has generic newer/T8103 and T602x layouts, not an independently validated S8000 profile. It configures global clock, reset, PHY, MSI and RID/SID state which could affect storage or baseband. The older DART fallback is promising but requires an explicitly reviewed S8000 OF binding, page table and IRQ mapping. Modern Asahi M1 PCIe documentation cannot be used as A9 register instructions.

Reference material:
- https://asahilinux.org/docs/hw/soc/apcie/ (M1 PCIe, comparison ONLY)
- https://github.com/torvalds/linux/blob/master/drivers/iommu/apple-dart.c
- https://github.com/corellium/linux-m1/blob/master/drivers/iommu/apple-dart-iommu.c (A10/M1, comparative ONLY)

Next engineering work: independently derive A9 root-complex registers and ownership, resolve DART stream IDs, implement a separate disabled-by-default S8000 driver with provable port-1-only effects, and **only after safety review** attempt one attended RAM-only PCIe test. Port 0 storage and port 2 modem remain strictly off-limits. Once the link and DMA work, bring up brcmfmac/cfg80211 with private board-matched firmware. Replace insecure Telnet with authenticated SSH before any independent Wi-Fi connection.

**No Wi-Fi function is claimed. No live register, controller, NAND or RF changes were made.**
