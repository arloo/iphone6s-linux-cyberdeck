# N71/S8000: original port-instance PCIe method fan-out and physical safety boundary

**2026-11-12.** Inputs: owner-private Apple N71/S8000 ARM64 kernelcache, original Apple Device Tree, original stock-iOS PCIe root and port1 IORegistry. **Method:** offline source-code, constructor-vtable, and original-resource analysis. No physical register access, PCIe host startup, DART DMA, storage activity or Wi-Fi operation.

## New findings: 8 local methods and 3 root-controller targets

The inherited AppleS800xPCIePort startup is executed through the actual constructed AppleS8000PCIePort instance vtable. Its port-specific calls reach the following original S8000 PCIe root methods:

| Port-instance vtable slot | Original method | Proven dispatch or effect |
|---|---|---|
| 1528 | Shared port +0x1634 | Forwards port index and flag to root slot 1976 |
| 1848 | Shared port +0x1424 | Forwards port index and flag to root slot 1936 |
| 1864 | Shared port +0x0B3C | Forwards port index to root slot 2040 |
| 1504 | Shared port +0x172C | Uses port-instance slots 2000 and 2008, local value 0x210; complex configuration path |
| 1568 | Shared port +0x0BCC | Conditional table-driven config path involving relative 0x124 |
| 2000 | Shared port +0x1A78 | Additional indirect port-local read/configuration path |
| 2008 | Shared port +0x1B58 | Additional indirect port-local write/configuration path |
| 2016 | Embedded port +0x90EC | Complex inherited method; hardware purpose not qualified |

The actual root controller constructed A9 instance vtable resolves the forwarded slots to:

| Root slot | Original source | Proven software operation |
|---|---|---|
| 1976 | Shared root +0x03FC | Selector ID2, port-indexed, masked bit0 update from caller flag |
| 1936 | Shared root +0x0558 | Selector ID3, port-indexed, masked bit8 update with inverted flag |
| 2040 | Shared root +0x07D8 | Original 32-bit write of value **3** to relative offset **0x4020 + 0x40 × port-index** |

For WLAN **port1**, the original software operations now resolve:

- After the original 100 µs delay, local slot 1528 is called with flag 1. It forwards to root slot 1976, which sets bit0 of root selector ID2 at relative offset **0x180**.
- Later, the conditional slot 1848 is invoked with flag 1. It forwards to root slot 1936, clearing bit8 of selector ID3 at **0x194**.
- Local slot 1864 calls root slot 2040, writing **3** to root-relative **0x4060**, computed from 0x4020 + 64 × 1.

This last value lies within Apple's original root-common IODeviceMemory index 9, verified by original iOS as physical **0x600000000 / 0x8000**. The offset calculation and source write instruction are proven, but **electrical effects, storage and baseband isolation, PCIe clocks/reset and reversible safety are not**. No new S8000 MMIO access is authorized.

The local slots 1504, 1568, 2000, 2008 and 2016 involve other indirect config operations. Their side effects are not qualified as harmless, nor can we assume they are valid DMA, MSI, BAR or RID-to-SID programming paths without more original hardware evidence.

## New independent strict source and model tests

The reproducible checker is [n71_s8000_original_port1_local_fanout_gate.py](../tools/n71_s8000_original_port1_local_fanout_gate.py). It independently chains all existing N71 private-original Apple source validation, verifies the real A9 port-object constructors and exact vtable targets for **eight** port methods and **three** root-controller methods, and pins individual ARM64 instructions governing root dispatch, bit0, inverted bit8, relative 0x4060 calculation and opaque config paths.

The accompanying [21 fail-closed unit tests](../tests/test_n71_s8000_original_port1_local_fanout_gate.py) mutate every source signature, reject malformed/extra register banks, verify original conditional bit behavior and execute 1,000 randomized **synthetic** four-port register vectors. These confirm ports 0, 2, 3 do not change in a **purely software symbolic model that excludes all shared-root write effects**. This is not proof of actual NAND/modem electrical isolation.

Authenticated actual private-input invocation returned:

    N71_S8000_ORIGINAL_PORT1_LOCAL_FANOUT_STATIC_PASS
    N71_REAL_APPLE_PORT_INSTANCE_VTABLE_METHOD_TARGETS_8_OF_8_PASS
    N71_REAL_APPLE_ROOT_CONTROLLER_FANOUT_TARGETS_3_OF_3_PASS
    N71_ORIGINAL_PORT_SLOT1528_TO_ROOT1976_ID2_BIT0_SET=YES
    N71_ORIGINAL_PORT_SLOT1848_TO_ROOT1936_ID3_BIT8_INVERTED=YES
    N71_ORIGINAL_PORT_SLOT1864_TO_ROOT2040_COMMON_OFFSET_0X4060_WRITE3=YES
    N71_ORIGINAL_PORT_SLOT1504_CONFIG_PATH_0X210_SOURCE=YES
    N71_ORIGINAL_PORT_SLOT1568_SWITCHED_CONFIG_PATH_0X124_SOURCE=YES
    N71_PORT_LOCAL_BUS_CONFIG_MSI_POWER_SIDE_EFFECTS_SAFE=NO
    N71_ROOT_COMMON_0X4060_REGISTER_WRITE_AUTHORIZED=NO
    N71_ORIGINAL_SHARED_ROOT_POWER_RESET_SEMANTICS_PROVEN=NO
    N71_PORT1_SOFTWARE_SYMBOLIC_MODEL_PRESERVES_PORT0_2_3=YES
    N71_REAL_S8000_DART1_PHYSICAL_PCIE_REQUESTER_SID_PROVEN=NO
    N71_NATIVE_WIFI_PCIE_DMA_MMIO_TEST_AUTHORIZED=NO

## What remains before hardware experimentation

The original S5L8960x DART driver source proves that the unique original WLAN DART1 mapper logical index 0 reaches the packed TCR byte lane 0 and per-stream TTBR bank. **It does not prove physical PCIe requester routing into DART1 stream 0, nor IOVA protection or fault isolation**. Newer Apple M1/T8103 RID-to-SID code is not a safe substitute for original A9 proof.

The next hard gates are safe global-versus-per-port power/clock/reset ownership, bounded PCIe status polling and link rollback, real port0 NAND/baseband port2 isolation, accurate DART1 requester/SID and TTBR fault behavior, and the original port-local config method side effects. The loaded **metadata-only** guard must keep refusing physical hardware access until these prerequisites are satisfied.

The real iPhone 6s remains running the current RAM Linux (USB gadget 05ac:4142) and its known-good touch initializer; no new DFU, physical MMIO, PCIe/DART DMA or Wi-Fi RF actions occurred.

**Privacy:** Original Apple binaries, per-device firmware/calibration, raw private masks/values, unique identifiers and original iOS acquisition plists remain local to the authorized Dell, not the public repository.
