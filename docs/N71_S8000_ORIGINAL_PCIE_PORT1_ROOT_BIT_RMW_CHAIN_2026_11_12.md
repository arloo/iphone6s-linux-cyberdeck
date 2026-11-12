# N71/S8000 original Apple PCIe port1 root-bit RMW chain: verified ARM64 path

**Date:** 12 November 2026
**Evidence:** owner-private original iOS 15.8.8 N71/S8000 ARM64 kernelcache; original Apple N71 Device Tree; owner-captured, read-only iOS 15.7.9 `apcie` and `pci-bridge1` IORegistry resource ordering. Source audited **offline**; no access to the live iPhone's physical PCIe/DART registers was performed.

**Result:** Real Apple A9/S8000 root-instance vtable methods, the specific relative selector register IDs, individual masked bit-write formulas, fixed delay and polling structure have now been established with original ARM64 instruction provenance. The interpretation of the actual signal wires (PHY/REFCLK/PERST#/reset) and cross-port effects **remains unproven**.

## Eight original root-instance virtual methods resolved

The original shared `AppleS800xPCIePort` path is inherited by the original specialized S8000 port1 object, and dispatches via the *constructed* A9 root-instance vtable. An independent strict, private-input tool checks all of the following actual targets:

| Original root virtual slot | Verified original target | Behavior grounded in source |
|---|---|---|
| 1808 | `AppleEmbeddedPCIE` + `0x4654` | Read32 from the root's mapped register pointer |
| 1816 | `AppleEmbeddedPCIE` + `0x46B0` | Write32 through the same mapped pointer |
| 1968 | `AppleS800xPCIe` + `0x688` | Original selector ID4, bit0 inverted-flag masked update |
| 1984 | `AppleS800xPCIe` + `0x5D0` | Original selector ID3, bit0 masked update plus optional root-shared status polling |
| 1992 | `AppleS800xPCIe` + `0x468` | Original selector ID2, bit8 masked update |
| 2000 | `AppleS800xPCIe` + `0x4E0` | Original selector ID2, bit20 masked update |
| 2008 | `AppleS800xPCIe` + `0x3B4` | Original selector ID5 read32 with bit0 result |
| 2016 | `AppleS8000PCIe` + `0x7D8` | Four-port, six-case register-ID → relative-offset selector |

The actual original `AppleEmbeddedPCIE` write32 path loads the virtual root common register pointer from the root object's field **+424** and stores a **32-bit value** at the selector-supplied offset. Original root initialization selects IODeviceMemory provider resource **index 9** through independently audited vtable calls. The owner's *live original iOS IORegistry* independently confirmed resource index 9 maps to **`0x600000000 / 0x8000`**. This is **proven physical address provenance**, *not* authorization to map or write this address under Linux.

## Original port1 selector register values and bit effects

The original Apple S8000 six-case root selector computes the following ID-specific addresses for port1 (relative to the common root register mapping):

| Selector ID | Root-relative port1 offset | Original software role |
|---|---|---|
| ID1 (global) | `0x02C` | Shared-status polling; original code tests **bit4** |
| ID2 | `0x180` | Original slot1992 edits **bit8**; slot2000 optionally edits **bit20** |
| ID3 | `0x194` | Original slot1984 edits **bit0**, then on the true path polls ID1 bit4 |
| ID4 | `0x1A4` | Original slot1968 edits **bit0** with inverse of its Boolean argument |
| ID5 | `0x1AC` | Original slot2008 reads **bit0** for repeated status querying |

Each write is a 32-bit **masked read-modify-write (RMW)**: it preserves all bits not selected by that specific operation. No register value, proprietary calibration, private KEXT byte stream or actual live MMIO content is published.

### Ordered original source-level sequence

The actual original inherited port1 method's instructions and root method dispatch establish this logic:

1. Root slot **1968**, argument `1`: selector ID4 port1 bit0 is **cleared** (the method inverts its flag).
2. Root slot **1984**, argument `1`: selector ID3 port1 bit0 is **set**, followed by a conditional polling loop reading **shared ID1 bit4** until it is set, with original XNU `IODelay(10)` between unsuccessful iterations.
3. Original `IODelay(100)`; another port-local virtual method at slot1528 is invoked. Its physical effect is **not** established here.
4. Root slot **2008** repeatedly reads selector ID5 port1 **bit0** until it becomes nonzero.
5. Root slot **1992**, argument `0`: selector ID2 port1 **bit8 cleared**.
6. A separate original conditional branch, depending on a root-object field, may invoke root slot **2000**, argument `1`: selector ID2 port1 **bit20 set**.
7. Original `IODelay(t-refclk-to-perst)`, verified from the actual N71 source and stock-iOS snapshot as **100 microseconds**.
8. Root slot **1968**, argument `0`: selector ID4 port1 **bit0 set**.
9. Additional port-local methods follow; their physical roles and safe interactions still require independent analysis.

**Important:** These are decoded software operations, **not** verified electrical signal semantics. Although original names mention REFCLK/PERST, the individual bit assignments cannot be labeled as the physical PHY, reset or WLAN regulator control without additional evidence. The *shared* ID1 bit4 polling and *per-port* ID5 bit0 polling loops contain no bounded retry counter proven in this path. A future Linux driver must enforce explicit timeouts and never copy an indefinite spin.

### Cross-port risk is independently real in original metadata

As detailed in the [original four-port shared-root tunable alias audit](N71_S8000_COMMON_ROOT_ALL_PORTS_SELECTOR_TUNABLE_ALIAS_2026_11_12.md), four original common-root tuning records also target selector ID2 relative offsets for storage port0, BCM4350 port1, baseband port2 and protected port3. **Per-port addressing in the four individual methods above does not establish that global controller startup and the full 34-record common tuning bank are safe or independently reversible.** The original shared root may be initialized by other software during boot.

## New independent executable verification

The new [strict original source/dynamic registry control-chain gate](../tools/n71_s8000_original_port1_root_bit_control_chain_gate.py) checks:

- Authentic N71/S8000 source, original ADT, original iOS `apcie` and `pci-bridge1` IORegistry evidence and exact 11-element live IODeviceMemory order.
- Real constructed Apple A9 root vtable targets across eight slots, including actual mapped-register read32 and write32.
- Original `AppleS800xPCIe` ARM64 instructions selecting four control methods, bit8/bit20/bit0 masked update behavior, inverted ID4 flag, conditional ID1 bit4 loop and `IODelay(10)` call signature.
- Existing independent original XNU `_IODelay` symbol provenance and true 100 µs `t-refclk-to-perst` value; no millisecond substitution.
- Separate, deterministic **offline symbolic RMW model** applying only the known per-port writes to synthetic four-port register dictionaries. For both optional-path branches, it validates that no register belonging to protected storage port0, baseband port2 or port3 is changed by this *software-only* model.

The [25 adversarial unit tests](../tests/test_n71_s8000_original_port1_root_bit_control_chain_gate.py) mutate every pinned critical ARM64 instruction, every real vtable-method target, the original root mapped-address read32/write32 semantics and source call order; they reject malformed ports, unexpected registers and truncated code, and execute **1,000 deterministic synthetic four-port register vectors** covering both conditional paths.

The actual owner-private original-file invocation returned:

```text
N71_S8000_ORIGINAL_PORT1_ROOT_BIT_RMW_CHAIN_STATIC_PASS
N71_REAL_A9_ROOT_VTABLE_SLOT_METHOD_TARGETS_8_OF_8_PASS
N71_REAL_APPLE_ROOT_WRITE32_MAP_RESOURCE_INDEX9=VERIFIED
N71_PER_PORT_ID2_BIT8_AND_BIT20_RMW_SOFTWARE_PROVEN=YES
N71_PER_PORT_ID3_BIT0_AND_ID4_INVERTED_BIT0_RMW_PROVEN=YES
N71_ORIGINAL_SHARED_ROOT_ID1_STATUS_BIT4_POLL=YES
N71_ORIGINAL_PORT1_ID5_STATUS_BIT0_POLL=YES
N71_ORIGINAL_POLL_TIMEOUT_IN_CALLER_PROVEN=NO
N71_ORIGINAL_XNU_IODelay_100US_AND_10US_PROVEN=YES
N71_ORIGINAL_ROOT_RESOURCE9_PHYSICAL_BASE_FROM_STOCK_IOS=0x600000000
N71_PER_PORT_RMW_SOFTWARE_MODEL_PRESERVES_OTHER_PORT_REGISTERS=YES
N71_GLOBAL_ROOT_SHARED_TUNING_NO_CROSSPORT_IMPACT_PROVEN=NO
N71_RESET_CLOCK_PHY_ELECTRICAL_BIT_MEANINGS_PROVEN=NO
N71_HARDWARE_REQUESTER_TO_DART_SID_AND_DMA_ISOLATION_PROVEN=NO
N71_SAFE_PCIE_MMIO_DART_DMA_NATIVE_WIFI_AUTHORIZED=NO
```

This is a **reproducible source-code and read-only registry milestone**, not an on-phone PCIe driver success.

## Remaining conditions before any native Wi-Fi hardware experiment

**P0, no new DFU now:** Prove clock/PHY/PERST ownership, any additional root-global startup writes and the semantics of status ID1 bit4 and ID5 bit0, including timeout/recovery and per-port storage/baseband safety. Prove the **actual BCM4350 PCIe transaction requester→DART1 physical stream index**, IOVA ownership and fault-isolated page tables before any DMA or PCIe enumeration. The original Apple WLAN→DART1 child mapper index0→packed TCR byte lane0 chain is already software-proven but does not by itself establish the physical bus requester mapping.

**P1 once qualified:** Implement a separately compiled, *default-off*, strictly gated A9/S8000 port1-only Linux research driver with finite query bounds and no global tuning replay. Preserve the current known-good RAM Linux, touch initialization and USB gadget rescue path. Only after passing independent source, MMIO-boundary and DMA safety review should an explicitly supervised *separate RAM boot* exercise physical PCIe and native BCM4350 WLAN. Genuine success requires a native WLAN interface and association with the owner's authorized Dell Wi-Fi network; USB network is not WLAN acceptance.

**Current actual device:** The iPhone 6s continues running the previously verified RAM-only Linux with loaded, fail-closed metadata guard, USB `05ac:4142` and initialized touchscreen. No new iPhone reboot, physical MMIO, DMA, NAND or RF operations were performed in this investigation.

### Private local reproduction (inputs intentionally withheld from the public repository)

```bash
python3 tools/n71_s8000_original_port1_root_bit_control_chain_gate.py \
  /private/owner-n71-kernelcache.macho \
  /private/owner-original-n71-adt.bin \
  /private/owner-ios-live-apcie.plist \
  /private/owner-ios-live-pci-bridge1.plist

python3 -m unittest discover -s tests \
  -p test_n71_s8000_original_port1_root_bit_control_chain_gate.py -v
```
