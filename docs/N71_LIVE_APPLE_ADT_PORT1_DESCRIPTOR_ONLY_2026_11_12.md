# N71/S8000: live original Apple PCIe/DART1 ADT comparison and isolated port1 DT candidate

**November 12, 2026.** This milestone extends the physical, read-only [N71 RAM-Linux PCIe/IOMMU baseline](N71_S8000_PHYSICAL_LINUX_WLAN_READONLY_FIELDTEST_2026_11_12.md). Native BCM4350 Wi-Fi is **NOT** working yet. The phone remains in the already booted and verified USB-reachable RAM-only Linux; no reset, PCIe/DART MMIO operation or NAND write was performed.

## A second, independent original Apple ADT acquisition from the live phone

The owner-controlled iPhone 6s N71/S8000 was running `7.3.0-rc1-g68aadac820d0-dirty` with the real USB Linux gadget `05ac:4142`. Read-only `/proc/mtd` confirmed the original Apple Device Tree stored at `/dev/mtd1ro` as a **163,840-byte** image. This is the boot-retained Apple ADT, not the Linux FDT. The new 163,840-byte binary was read, base64-encoded for a transfer over the existing local USB Linux shell, verified and saved **only in the private owner-controlled Dell research directory**, with restrictive permissions. It was not uploaded to GitHub or this conversation.

The new Apple ADT has a different SHA-256 digest from the prior read-only capture, but the new strict [all-property comparator](../tools/n71_original_apple_live_adt_pcie_dart1_topology_gate.py) proves:

- **178 parsed original Apple ADT nodes**, in the **same order and structure**.
- **Every original property value** under `/arm-io/apcie`, `/arm-io/dart-apcie1`, and named WLAN nodes matches the earlier owner-original ADT byte-for-byte; this includes otherwise unknown/proprietary keys, not merely a list of selected known fields.
- Exactly **28 changed properties outside the PCIe/DART1/WLAN-relevant paths**; their content is deliberately withheld, and their cause is not assumed.
- Original port1 physical windows **`0x602000000/0x4000`** and **`0x602004000/0x4000`**, original port1 DART1 window **`0x602008000/0x4000`**, and the original `apcie/pci-bridge1/wlan` node are confirmed in the independently captured ADT.

The new live Apple ADT independently passes the existing original ARM64 Apple S5L8960x TTBR/PTE encoding gate against the actual source Linux IOMMU driver. [Twelve adversarial synthetic tests](../tests/test_n71_original_apple_live_adt_pcie_dart1_topology_gate.py) check legitimate unrelated boot-state differences, modified/relocated PCIe/DART resources, modified unknown Apple PCIe properties, absent WLAN children, malformed trees, private symlinks and raw data protection.

This cross-check **does not prove** the BCM4350's actual hardware PCIe requester-to-DART SID, safe IOVA, TLB operations, real DMA isolation, PCIe PHY link training in Linux or native Wi-Fi.

## Next RAM-only experiment: port1 descriptors WITHOUT hardware activation

A new **owner-private and not yet booted** RAM-only image is staged on the Dell:

```text
private-touch-live-test/n71-s8000-port1-descriptor-only-next/
  m1n1-linux-n71-port1-descriptors-only.bin
```

SHA-256: `6f460870bbded3648ba9136afac45a428c55c4470185e5f0873b6c074605b986`. Size: **11,822,390 bytes**.

The builder takes the **already physically booted** diagnostic RAM Linux image (11,821,980 bytes) and modifies **exactly one thing**: the Samsung N71 Linux Device Tree binary, expanding it by **410 bytes**. The entire remaining boot blob is byte-identical including the m1n1 bootloader, bootargs, TSMC S8003 Device Tree, actual physically verified kernel Image.gz, private touch calibration and firmware, existing automatic Z2 touch initialization, and diagnostic initramfs.

It adds one synthetic metadata-only OF child below `/soc`:

```dts
pcie-port1-preflight@602000000 {
    compatible = "apple,s8000-pcie-research-blocked";
    status = "okay";
    reg = <0x6 0x02000000 0x0 0x4000>,
          <0x6 0x02004000 0x0 0x4000>,
          <0x6 0x02008000 0x0 0x4000>;
    reg-names = "port1-reg-a", "port1-reg-b", "dart1-reg";
    research,pcie-port-index = <1>;
    research,dart1-mapper-index = <0>;
    research,refclk-to-perst-delay-us = <100>;
    research,hardware-activation-blocked;
};
```

These are **resource descriptors only**: they do not map MMIO or cause PCIe enumeration. The exact genuine Linux Image.gz extracted from the **already booted** private image was decompressed and verified not to contain a driver matching `apple,s8000-pcie-research-blocked`. The existing initramfs likewise has no such research compatible or matching research driver. The new node **does not use** the upstream hardware-driving `apple,pcie` binding and has no clocks, PHY, GPIO, resets, MSI, IOMMU linkage, PCIe bus ranges or active DMA properties.

To verify isolation, the builder removed the synthetic node from a copy of the modified DTB and compared decompiled DTB structures: **all remaining N71 tree content is identical**. Independently, all bytes of the staged boot image *before* the N71 DTB and *after* its new end were compared with the previously booted image and were **identical**.

The synthetic node also matches a separately developed **fail-closed experimental** PCIe guard that would return `-EOPNOTSUPP`, but **that guard is not present in this physically verified Linux kernel or included in this staged boot candidate**. No functional hardware driver is being enabled.

## Meaning of the next physical test

When the owner next physically enters DFU and loads this candidate in RAM, the expected outcome is a **synthetic port1 metadata-only platform device**, while PCIe endpoints, native WLAN interfaces and active IOMMU groups may remain at zero. Confirmation would validate the Linux OF descriptor ingestion and resource boundaries *only*; it must not be described as a Broadcom PCIe link, DART DMA transaction or Wi-Fi connection.

The current phone **was not rebooted** to test this new staged candidate. The existing working Linux image and recovery SHA remain intact. The next engineering milestone *after* descriptor acceptance is a controlled root/port1-only PCIe host with validated shared-root, PERST#/REFCLK and DART requester/SID safety, preserving port0 NAND/storage and port2 baseband. No automatic MMIO access is authorized by this stage.
