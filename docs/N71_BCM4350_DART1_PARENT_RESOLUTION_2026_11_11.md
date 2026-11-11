# N71/S8000 BCM4350-to-DART1 IOMMU reference resolved

Date: 2026-11-11. Result: Apple Device Tree reference topology VERIFIED OFFLINE on two identical private runtime ADT snapshots. No PCIe link, DMA operation or live hardware changes were attempted.

## Resolved relationship

The N71 Wi-Fi endpoint is at /device-tree/arm-io/apcie/pci-bridge1/wlan. Its one-cell iommu-parent property matches, exactly and uniquely, the AAPL,phandle of /device-tree/arm-io/dart-apcie1/mapper-apcie1. The endpoint references the child mapper of the dedicated WLAN DART1, NOT the DART controller node itself or any storage/baseband mapper. A complete scan of the physical N71 Apple ADT found 178 unique nonzero phandle definitions, with no collisions. Both private snapshots produced the same result. Numeric phandle values and original ADT contents were not published.

DART1 compatible values are dart,s8000 and dart,s5l8960x. DART1 reports page-size=4096 and vm-size=0x3ffff000 bytes. The latter is a virtual-space metadata property and does NOT prove the safe DMA aperture. The DART1 register window begins at 0x602008000 with length 0x4000. The mapper child has reg=0, an Apple mapper index; it is NOT independently established as the physical DART stream ID. The BCM4350 port-1 controller ranges are 0x602000000 and 0x602004000, each 0x4000 bytes.

## Independent Apple source evidence

Apple Darwin XNU iokit/Kernel/IOMapper.cpp registers IOMapper providers using their iommu-id property or, if absent, AAPL,phandle. IOMapper::copyMapperForDeviceWithIndex looks up a device's iommu-parent and matches the corresponding IOMapper provider ID. This is consistent with the verified S8000 relationship. No unreviewed iommu-id override was present on the N71 WLAN mapper.

Source: https://github.com/apple/darwin-xnu/blob/main/iokit/Kernel/IOMapper.cpp

Linux uses its own IOMMU binding with iommus referencing a DART phandle and an explicit stream ID. It would be incorrect to copy Apple's iommu-parent ID or child reg=0 blindly as that Linux stream ID. Binding reference: https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/iommu/apple,dart.yaml

## Reproducible safety checks

The public tools/adt-pcie-map.py parser now offers an opt-in full-tree visitor and strictly reads only relevant property names. Its default filtered CLI behavior is unchanged. The tools/n71_s8000_adt_window_gate.py validator now checks EVERY global AAPL,phandle for correct four-byte encoding, nonzero value and uniqueness; requires the BCM4350 iommu-parent to resolve exactly to DART1's mapper child; rejects unsupported iommu-id override; enforces DART1 4-KiB page and exact VM-size metadata; and preserves the earlier full PCIe register/DART window checks.

The revised synthetic tests now include wrong references pointing directly to DART1, storage DART0, unknown nodes, wrong/duplicate mapper handles, an unexpected mapper iommu-id override, incorrect page-size/VM-size, along with previous register/window/board checks. Three additional parser tests verify opt-in full-tree discovery, default visitor filtering and duplicate-property rejection. Full project suite: 235 offline tests PASS.

A private workstation can rerun the audit with:
    python3 tools/n71_s8000_adt_window_gate.py /private/path/to/runtime-apple-adt.bin

Success prints WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED and HARDWARE_BLOCKED. No raw ADT, firmware, NVRAM, unique device IDs, customer data, user photo or calibration are committed.

## Unresolved blockers

A9/S8000 PCIe host root-complex initialization registers, PHY/reference clocks, shared resets, MSI and per-port side effects require independent validation. The actual DART1 stream ID, page-table translation, IOVA protection and fault handling remain UNKNOWN. The default-off RFC 0011 S8000 PCIe kernel guard stays intentionally inert. No attempt to load the Broadcom driver, start RF or access device NAND is authorized by this metadata proof. The working native Linux graphical touchscreen RAM boot remains untouched.
