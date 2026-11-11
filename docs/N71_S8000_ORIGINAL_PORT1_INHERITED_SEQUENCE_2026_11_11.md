# N71/S8000 Wi-Fi port 1: original inherited control-flow and bounded polling

**Date:** 2026-11-11. **Evidence:** privately held, verified original iOS 15.8.8 N71 ARM64 kernelcache; original three-class port constructor / vtable inheritance; synthetic C/Python test fixtures. **No iPhone access, no MMIO, no DART DMA, no hardware link.**

## New finding from original A9 PCIe executable

Original A9 `AppleS8000PCIePort` method at constructed virtual slot **1816** only takes its specialized path when the port index and an accompanying hardware-query result are both 3. The known N71 Wi-Fi port has index **1**, so the earlier verified A9 override falls back to the inherited `AppleS800xPCIePort` slot-1816 method. The new independent original-Mach-O audit traces that **inherited method** (the shared S800x KEXT, not the root-controller start routine).

Within that original method, the port object reads its **stored port index** from an object field, passes it as `W1` into multiple calls on a separate controller object, and resolves the call targets through the controller's **virtual method table**. The static, ordered dispatch slots are:

| Relative operation order | Controller virtual slot | Static argument / guard | Interpretation limit |
|---|---:|---|---|
| 1 | 1968 | W2 = 1 | Method purpose and hardware effects UNKNOWN |
| 2 | 1984 | W2 = 1 | Method purpose and hardware effects UNKNOWN |
| 3 | — | direct callback with W0 = **100** | Units of callback argument UNKNOWN |
| 4 | — | separate port virtual slot 1528 with W1 = 1 | NOT a verified PCIe link/PHY action |
| 5 | 2008 | value returned in W0; CBZ back to **the same query call** | **Polling until nonzero**; no explicit caller-side retry counter in this loop |
| 6 | 1992 | W2 = 0, after poll condition | Method purpose UNKNOWN |
| 7 (conditional) | 2000 | W2 = 1 if a controller-object byte flag permits it | Flag semantics UNKNOWN |
| 8 | — | **same direct callback** as step 3, now W0 loaded from port-object field +416 | This callback is invoked with two sources of argument; timing units UNKNOWN |
| 9 | 1968 | W2 = 0 | Same controller virtual slot as step 1, different argument |

Further port-object virtual calls occur later in the method, but their semantics are not yet verified. The original code also has other conditional branches; the table presents a **static ordering/conditional control-flow outline**, not an assertion that every branch executes at runtime.

**Important:** virtual slot offsets are **C++ vtable byte offsets**, NOT PCIe MMIO register offsets. Neither the original status method's return-value meaning nor the callback's timing unit or target controller register effect is established. The `CBZ` retry loop alone does not prove a physical PCIe link-training sequence; it demonstrates **a possible unbounded caller-level wait** if that original virtual query never returns nonzero. It is unknown whether that virtual method has internal timeouts.

## Independent fail-closed original-Mach-O evidence gate

`tools/n71_s8000_port1_inherited_sequence_gate.py` works only with the operator's private, version-pinned N71 ARM64 Mach-O. It revalidates the complete original port constructor inheritance and special port-3 fallback, extracts the shared PCIe executable from bounded original prelinked regions, verifies exact ARM64 load widths, field offsets, vtable-dispatch slot offsets, argument registers, return/branch register identity, both direct callback target identities and the conditional polling backedge.

Original authentic host-only result:

```text
N71_S8000_ORIGINAL_PORT1_INHERITED_CALL_ORDER_STATIC_PASS
ORIGINAL_PORT_INDEX_FIELD 168
CONTROLLER_VTABLE_DISPATCH_SLOTS 1968,1984,2008,1992,2000,1968
PORT_SPECIFIC_STATUS_QUERY_BACKEDGE_PRESENT=YES
CALLER_LEVEL_EXPLICIT_POLL_TIMEOUT_PROVEN=NO
CONSTANT_PARAMETER_TO_SHARED_CALLBACK 100
ADDITIONAL_PARAMETER_ORIGIN=PORT_OBJECT_FIELD
SAME_CALLBACK_TARGET_ON_TWO_PATHS=YES
VIRTUAL_METHODS_HARDWARE_ROLE_AND_MMIO_SEMANTICS_KNOWN=NO
PCIE_PORT1_LINK_AND_DART1_HARDWARE_SAFE=NO
```

**25 synthetic Python tests** in `tests/test_n71_s8000_port1_inherited_sequence_gate.py` build generic AArch64 instructions from independent encoders, not Apple copyrighted firmware. They reject changed target virtual slots, port-index provenance, root-object pointer, constant and dynamic arguments, altered branch endpoints and callback destinations, malformed executable length and fake success without the original image.

## New bounded polling safety model (not a driver)

The new original-code finding exposed a design risk worth handling **before** touching hardware: Linux should not copy an indefinite status-query loop into an early boot driver. `examples/n71-pcie-port1/port1_bounded_poll_model.c` is a tiny **standalone, no-hardware C policy model** that accepts only port index 1, rejects zero/overlarge retry budgets, and returns distinctly on nonzero callback status, query error or exhaustion. An illustrative upper limit of **4096 attempts** is a software test guard, NOT a hardware timing threshold; later a real driver must also implement explicit elapsed-time limits and may require the proper status bits rather than any nonzero value.

The model was compiled with native GCC and as an **AArch64 relocatable ELF object** with warnings treated as errors. A real native-C harness performed **12 independent mock scenarios** (initial/third success, timeout, callback error, rejection of ports 0/2/3, invalid arguments, maximum permitted retries). Eight additional synthetic Python regression tests exercise the C harness, cross-compilation, interface and absence of device side effects.

**Neither the model nor the original-code audit binds to a PCIe controller, performs real PCIe configuration, or qualifies DART1.** No hardware test was claimed.

## Reproduction

```bash
python3 tools/n71_s8000_port1_inherited_sequence_gate.py /private/verified-n71-kernelcache.macho
python3 -m unittest discover -s tests -p 'test_n71_s8000_port1_inherited_sequence_gate.py' -v
python3 -m unittest discover -s tests -p 'test_n71_port1_bounded_poll_model.py' -v
```

**Update — exact status-read provenance now independently established:** the [A9 root resource-index-9 / port1 register-bit audit](N71_S8000_PORT1_STATUS_BIT_ROOT_RESOURCE9_2026_11_11.md) traced virtual status query slot 2008 through the A9 ID5 selector and embedded 32-bit root reader. For logical port1 the status query tests **bit0 of the register at relative offset 0x1AC from the virtual address of provider resource index9**. The actual physical provider memory-array order remains UNPROVEN; do not infer a safe physical address from the Apple ADT tuple alone. The meaning of the status bit remains unverified.

## Next real blockers

1. Resolve semantic identities of the original controller vtable calls at 1968, 1984, 2008, 1992 and 2000 — without equating the vtable slot numbers to MMIO offsets.
2. Establish independently verified physical AppleARMIODevice provider IODeviceMemory ordering and physical S8000 port1-only clock/refclock/reset/PHY/link effects; guard the other ports and global register state.
3. Determine actual DART1 stream ID, IOVA table format, fault handling and DMA isolation; the ADT mapper relationship does not identify an operational SID.
4. Only after these safety gates, prepare an explicitly reviewed RAM-only hardware experiment with the unchanged known-good Z2 touch/display/USB rescue image and no NAND write.
5. Finally enumerate real onboard BCM4350, select correct private Apple C2/C5 firmware and board calibration, and prove authenticated Wi-Fi association and local network reachability without any USB relay.

**Status:** meaningful progress in original A9 port-indexed call order and a safe finite-polling design. A functional S8000 Linux host-controller driver and native BCM4350 WLAN remain unimplemented and untested.
