# N71/S8000 DART1: complete original Apple ADT IOMMU consumer census

**Date:** 2026-11-12. **Device:** iPhone 6s N71, Samsung A9/S8000; onboard PCIe Broadcom BCM4350. **Evidence class:** original owner-retained Apple Device Tree (ADT), independently audited OFFLINE. **Result:** DART1 mapper has exactly one *declared* `iommu-parent` consumer in this full ADT, the port1 WLAN node. The physical DMA stream ID and safe reset are NOT established.

## Concrete original-data observations

The full original S8000 Apple ADT was first validated with the existing comprehensive `n71_s8000_adt_window_gate.py`: the PCIe host is `apcie,s8000`, there are four ports, 11 PCIe host windows, three disjoint DART windows, and a unique phandle connecting the original port1 BCM4350 WLAN to the child mapper of `dart-apcie1`. The A9 DART1 window is `0x602008000` / `0x4000`, with Apple ADT `page-size=4096` and `vm-size=0x3ffff000`. That VM-size is descriptive metadata, **not** a verified Linux IOVA DMA aperture.

A new **whole-tree** `iommu-parent` consumer census checks every Apple ADT node, NOT only the previously inspected WLAN. It counts **individual 32-bit references**, including a multi-cell `iommu-parent` vector elsewhere in the tree. All global phandles are verified unique and all IOMMU-parent reference cells must resolve to a declared phandle. Exact original counts:

| Original N71 Apple ADT observation | Verified result |
|---|---:|
| Nodes with an `iommu-parent` property | 9 |
| Total individual 32-bit `iommu-parent` references | 11 |
| References to the unique DART1 child mapper | 1 |
| Source node of the DART1 mapper reference | WLAN (BCM4350 on PCIe port1) |
| Other declared DART1 mapper consumers | 0 |
| Child mapper nodes beneath DART1 | 1 |
| Direct references to DART1 controller | 0 |
| Unresolved `iommu-parent` reference cells | 0 |

A previous cursory four-byte-only scan missed that one **unrelated** node has a 12-byte, three-cell IOMMU reference vector. The final census correctly analyzes all three cells, verifying that none points to DART1. This is why a whole-tree multi-cell audit matters.

**Strict scope of evidence:** these facts prove only the declaration graph in the supplied original ADT. They do NOT prove physical exclusivity of all DART1 DMA masters, the runtime stream-select mapping, the actual PCIe WLAN stream ID, TTBR ownership, safe DART1 clock/reset, MSI, DMA fault handling or physical register access. In particular the Apple child mapper `reg=0` is **not automatically Linux stream ID zero**. No Linux WLAN DMA should be enabled from this evidence alone.

## Linux S5L8960x DART driver safety dependency

The pinned private Linux DART implementation's S5L8960x variant advertises **four hardware streams** (`max_sid_count=4`) and four TTBR registers per stream. During `apple_dart_probe`, its `apple_dart_hw_reset` routine selects **all** streams of the DART instance, disables their DMA, and clears all TTBRs. The reset is also invoked in removal and resume paths. These actions are not restricted to the WLAN's unverified physical stream.

The pinned variant also had a packed four-byte TCR read-modify-write issue already isolated and corrected in a separate experimental patch (not in the known-good Linux boot). Fixing that arithmetic does not qualify automatic whole-instance reset.

This supports a conservative approach: **do not expose `dart-apcie1` to the stock Linux probe or write a guessed `iommus = <&dart1 0>` binding.** A future separate boot needs explicit stream-ID provenance, DMA isolation, protection against global reset of unrelated streams and a bounded fault/rollback path. The stock iOS storage and baseband domains remain protected.

## New verified public tools

The standalone read-only `tools/n71_dart1_consumer_census_gate.py` accepts only a private original Apple ADT file. It first runs the existing strict S8000 metadata gate, then scans every ADT node and every 32-bit `iommu-parent` cell. It fails closed on duplicate, unresolved, zero or malformed phandles, extra DART1 consumers, a wrong SoC/WLAN port and oversized input. It prints only aggregate counts and explicit hardware blockers, never original phandle numbers, unknown node names, raw properties, OTP, firmware or calibration.

The companion `tests/test_n71_dart1_consumer_census_gate.py` contains **28 synthetic adversarial tests**, including a 12-byte multi-reference vector with a hidden DART1 consumer. All original Apple binary inputs remain in the Dell's private local research tree.

To reproduce locally with authorized private original input:

```bash
python3 tools/n71_dart1_consumer_census_gate.py /private/original-n71-adt.bin
python3 -m unittest discover -s tests -p test_n71_dart1_consumer_census_gate.py -v
```

Expected result includes:

```text
N71_S8000_DART1_ORIGINAL_ADT_DECLARED_CONSUMERS_PASS
IOMMU_PARENT_PROPERTY_COUNT 9
IOMMU_PARENT_REFERENCE_CELL_COUNT 11
DART1_MAPPER_DECLARED_CONSUMERS 1
DART1_CHILD_MAPPER_COUNT 1
DART1_DIRECT_CONTROLLER_REFERENCES 0
DART1_ONLY_DECLARED_CONSUMER=WLAN
DART1_PHYSICAL_STREAM_ID_PROVEN=NO
DART1_ACTUAL_EXCLUSIVE_DMA_OWNERSHIP_PROVEN=NO
DART1_IOVA_DMA_FAULT_ISOLATION_PROVEN=NO
DART1_HARDWARE_INITIALIZATION_AUTHORIZED=NO
PRIVATE_APPLE_ADT_OR_DEVICE_VALUES_EXPORTED=NO
```

## Next physical gates (not completed)

1. Trace the Apple DART1 child-mapper index to an actual hardware stream ID through independent original-driver semantics or safe external evidence. The `reg=0` child property alone is inadequate.
2. Establish the port1 PCIe PHY/refclock/PERST#/MSI and global shared-controller status bit4 (`0x60000002C`) meanings, with no storage0/baseband2 side effects.
3. Establish safe DART1 TTBR, IOVA, fault, suspend/resume and rollback isolation before any Linux DMA access.
4. Preserve the working RAM-only Linux touchscreen/LCD/USB boot; require real onboard BCM4350 enumeration and genuine non-USB WLAN association with the authorized Dell network to accept success.

**No hardware register, PMIC, NAND, PCIe link, DART DMA, radio, device reset or operating-system action was performed in this milestone.**
