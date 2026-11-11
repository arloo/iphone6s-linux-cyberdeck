# N71/S8000 PCIe port1: original status bit proven through root resource index 9

**Date:** 2026-11-11. **Evidence class:** strict offline decode of operator-held authentic original iOS 15.8.8 N71 A9 kernelcache and Apple ADT. **No iPhone connected or accessed.** This report contains only derived method/relative offsets, never original executable bytes, raw disassembly, physical device identifiers or firmware.

## Newly resolved end-to-end call and register provenance

The previous [inherited S800x port-method audit](N71_S8000_ORIGINAL_PORT1_INHERITED_SEQUENCE_2026_11_11.md) proved that the specialized S8000 PORT method falls back to the shared S800x PORT method on **port index 1**, and that the latter calls a controller virtual status query repeatedly until it returns nonzero.

An independent new `tools/n71_s8000_port1_status_bit_provenance_gate.py` now traces that status query through the constructed **A9 root controller vtable** and through the embedded root's 32-bit memory access. Results:

| Stage | Original derived behavior | Limit |
|---|---|---|
| A9 PORT index 1 | Inherits shared `AppleS800xPCIePort` virtual slot 1816, which invokes the root status query at slot **2008** | Static code path, not proof of runtime invocation |
| A9 ROOT slot 2008 | Inherits `AppleS800xPCIe` status method, whose original code invokes root virtual slot **2016** with register ID **5** and supplied port index | Original method semantics beyond register selection unknown |
| A9 ROOT slot 2016 | Specialized, bounds-checked six-case selector: ID5 maps to `0x12C + 0x80 * port_index` | For port1, this is relative byte offset **`0x1AC`**, NOT a physical address |
| Embedded ROOT slot 1808 | The inherited 32-bit reader loads `W19` from a base pointer stored in the root object at offset **424**, indexed by the selector's byte offset | The runtime pointer value and physical base are unverified |
| Root slot 2008 return | Takes the readback value and applies an AND with **`0x1`**, returning only bit 0; the PORT method's CBZ backedge repeats the query while zero | Meaning of bit 0 (link ready, PHY state, reset state or another state) is **not established** |

## New root virtual-memory provenance (important distinction)

The new audit separately traces the original EmbeddedPCIe root start method:

1. Call the root controller's **virtual slot 1880** for the common-resource index. The previously audited four-port S800x implementation returns **`1 + 2 * 4 = 9`**.
2. Pass that returned index into the memory-provider virtual **slot 976** to obtain an IODeviceMemory mapping object, which the root stores in its object field at offset **416**.
3. Invoke the returned mapping object's virtual **slot 120** to obtain a virtual address, stored in the root object's field at offset **424**.
4. The inherited root 32-bit read method at slot 1808 reads from **that virtual pointer + `0x1AC`**, and the root query method at slot 2008 masks the result with **bit 0**.

The source thus **statically ties the status read to provider resource INDEX 9**. Independently, the original N71 ADT reg[9] is the 32 KiB common-controller region, whose candidate base is `0x600000000`. **The exact order of the runtime AppleARMIODevice memory-provider resources is still unverified.** Do **not** add `0x1AC` to that ADT candidate and dereference the result on the phone. A correctly derived resource index is not independently verified physical MMIO.

## Reproducibility and safety

Public `tools/n71_s8000_port1_status_bit_provenance_gate.py` validates, all together:

- The original N71 ADT hardware topology and logical BCM4350-to-DART1 mapper relationship.
- Original A9 ROOT constructor vtables, resource-index formula and the PORT class's inherited method dispatch.
- The original six-case A9 selector code, bounds checks and port stride for ID5.
- Exact target ownership for root virtual slots **2008** (S800x), **2016** (A9) and **1808** (Embedded).
- The 32-bit base-plus-offset load, bit-0 mask, backedge, common resource-index 1880 call, provider memory mapping through virtual slot 976 and mapped-address retrieval through slot 120.

Example against privately held, original input files:

```bash
python3 tools/n71_s8000_port1_status_bit_provenance_gate.py \
  /private/verified-original-n71-kernelcache.macho \
  /private/verified-original-n71-adt.bin
```

Actual original-data gate output includes:

```text
N71_A9_PORT1_ORIGINAL_STATUS_REGISTER_CHAIN_STATIC_PASS
ORIGINAL_ROOT_SELECTOR_ID=5
PORT1_RELATIVE_REGISTER_OFFSET 0x1ac
ORIGINAL_PROVIDER_MEMORY_RESOURCE_INDEX=9
ROOT_COMMON_MAPPED_VIRTUAL_POINTER_FIELD=424
REGISTER_READ_WIDTH_BITS=32
RETURNED_STATUS_BIT_MASK 0x1
CONTROLLER_STATUS_QUERY_POLL_BACKEDGE=VERIFIED
ROOT_POINTER_IODEVICE_MEMORY_PROVIDER_ORDER_PROVEN=NO
STATUS_BIT_PHY_OR_LINK_READY_MEANING_PROVEN=NO
SAFE_MMIO_DART1_DMA_AND_WIFI_HARDWARE_AUTHORIZED=NO
```

**22 synthetic-only regression tests** in `tests/test_n71_s8000_port1_status_bit_provenance_gate.py` reject changes to the selector ID, virtual method targets, root memory mapping/resource index, register-map object fields, read width, index register, bit mask or loss of the map-availability guard. Tests do not contain or redistribute Apple code, original kernelcache or device-specific DTB.

The nearby `examples/n71-pcie-port1/port1_bounded_poll_model.c` is an **independent, hardware-free, port1-only finite-query policy model** to avoid copying a potentially unbounded polling loop into a future Linux boot. Its maximum number of attempts is a synthetic policy choice, not hardware timing evidence.

## Remaining hardware blockers before enabling WLAN

1. **Authentic provider array:** independently verify the actual runtime AppleARMIODevice memory-resource order or authoritative equivalent implementation, so index 9 can be connected to a physical base without relying only on ADT tuple order.
2. **Status bit meaning:** verify that the original bit-0 status is safe to sample and what condition it represents. Do not assume this register alone indicates an operational PCIe Wi-Fi link.
3. **Controller bring-up:** review other virtual calls in the inherited method for actual clock/refclock/PHY/reset/M(SI) writes, their ownership and cross-port effects; storage port0, baseband port2 and shared root state must be protected.
4. **DART1:** independently qualify physical SID, correct IOVA/page tables, DMA-fault behavior and isolated ownership. The discovered status bit does not establish DMA safety.
5. **Phone supervised only:** when access returns, boot a separate RAM-only test candidate preserving the already proven Z2 touchscreen/display/USB rescue path; **never alter Apple NAND or attempt unqualified MMIO**.
6. **Actual Wi-Fi:** enumerate the onboard BCM4350 PCIe endpoint, select private Apple C2/C5 board-calibrated firmware, establish authenticated association to the Dell's authorized WLAN and validate LAN traffic over the onboard PHY without USB.

**Physical status:** S8000 Linux PCIe host and DART1 remain uninitialized; BCM4350 is not enumerated and Wi-Fi is not functional. This is a register-provenance breakthrough, not permission for hardware access.
