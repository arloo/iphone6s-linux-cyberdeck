# N71/S8000 PCIe: original port1 read-modify-write methods and global-status dependency

**Date:** 2026-11-11. **Hardware target:** iPhone 6s N71 Samsung A9/S8000, onboard BCM4350 under PCIe port 1. **Evidence:** original privately retained iOS 15.8.8 N71 ARM64 kernelcache and original private ADT. **Status:** static original-code audit PASSED. No iPhone attached, no MMIO, clock, reset, DART DMA or native WLAN access was performed.

## New original S800x ROOT method-to-register derivation

The [inherited port1 sequence audit](N71_S8000_ORIGINAL_PORT1_INHERITED_SEQUENCE_2026_11_11.md) previously identified virtual ROOT calls 1968, 1984, 2008, 1992, conditional 2000, and 1968. The subsequent [status-bit provenance audit](N71_S8000_PORT1_STATUS_BIT_ROOT_RESOURCE9_2026_11_11.md) proved the state query (slot 2008) reads bit0 of a 32-bit register selected through the original A9 ID5 offset `0x1AC` for port1, on the virtual memory-provider resource numbered 9.

The new `tools/n71_s8000_port1_rmw_provenance_gate.py` goes further: it traces each of the FOUR register-mutating virtual operations to the actual constructed A9 ROOT vtable, confirms that they inherit original S800x methods, and verifies their use of the A9 common register selector, the original embedded root 32-bit read method and the original embedded root 32-bit write method.

| Original ROOT virtual slot | Original selector ID | Relative register offset for port 1 | Exact bit change when called from the observed port method | Safety classification |
|---|---:|---|---|---|
| **1968** | 4 | **`0x1A4`** | RMW bit **0** with **inverse** of boolean argument: the initial arg `1` clears bit0; final arg `0` sets bit0 | Port1-specific in original selector, not safe to write physically yet |
| **1984** | 3 | **`0x194`** | RMW bit **0** with argument; observed arg `1` sets bit0, then waits for shared/global state | Depends on a shared controller register and an additional polling loop |
| **1992** | 2 | **`0x180`** | RMW bit **8** with argument; observed arg `0` clears bit8 | Port1-relative register, functional meaning not established |
| **2000** | 2 | **`0x180`** | RMW bit **20** with argument; observed arg `1` sets bit20 only on the optional branch | Conditional; functional meaning not established |

These are **bit-level static facts** derived from original AArch64 instructions, not guessed register names or reset/power semantics. The selector IDs and virtual method slots are not physical MMIO offsets. The individual read/modify/write paths use original virtual slot 2016 (A9 register selector), 1808 (embedded root read32), and 1816 (embedded root write32); the actual provider array ordering is still unproven.

## Additional critical global dependency discovered

Original ROOT slot **1984**, when passed a nonzero argument (the observed port1 call uses `1`), enters a SECOND query loop after setting port-relative bit0. It selects **register ID1**, corresponding to shared/global relative offset **`0x2C`**, reads it through the same root 32-bit mapping and tests **bit4**.

The original method repeats while that shared bit is zero. It invokes the same direct callback used elsewhere in the port sequence, this time with constant argument **10** on every unsuccessful iteration. The units and timing semantics of that callback remain unknown. No caller-side finite retry counter is present in the inspected loop. A nonzero status bit and bit4 at `0x2C` are NOT proof of PCIe link-ready or clock-good without independent hardware meaning.

**Safety implication:** physical port1 bring-up cannot be considered isolated merely because port-specific register offsets avoid the storage0 and baseband2 address windows. Any shared/common register state may depend on or alter other ports. The new software policy therefore treats `0x2C` as READ-ONLY and forbids any experimental shared/global register writes. This is a conservative model restriction, NOT proof that read operations themselves are harmless.

## Reproducible original-data safety gate

The new, read-only audit performs all existing verified original N71 KEXT class/constructor/root-resource/ADT checks before accepting these four operations. It validates the actual original A9 ROOT vtable target ownership, original register ID1–4 selector formulas, instruction-level bit masks, read32/write32 calls, the inversion of virtual slot 1968, and the shared ID1 bit4 polling backedge. It prints only aggregate derived register facts and explicit `HARDWARE_INIT_AUTHORIZED=NO`.

```bash
python3 tools/n71_s8000_port1_rmw_provenance_gate.py \
  /private/original-n71-kernelcache.macho \
  /private/original-n71-adt.bin
```

Confirmed actual result includes:

```text
N71_A9_ORIGINAL_PORT1_CONTROLLER_REGISTER_RMW_STATIC_PASS
PORT1_CONTROLLER_OPERATION_VSLOT 1968 REG_ID 4 RELATIVE_OFFSET 0x1a4 BIT 0
PORT1_CONTROLLER_OPERATION_VSLOT 1984 REG_ID 3 RELATIVE_OFFSET 0x194 BIT 0
PORT1_CONTROLLER_OPERATION_VSLOT 1992 REG_ID 2 RELATIVE_OFFSET 0x180 BIT 8
PORT1_CONTROLLER_OPERATION_VSLOT 2000 REG_ID 2 RELATIVE_OFFSET 0x180 BIT 20
SHARED_GLOBAL_CONTROLLER_POLL_REG_ID=1
SHARED_GLOBAL_CONTROLLER_POLL_RELATIVE_OFFSET=0x2c
SHARED_GLOBAL_CONTROLLER_POLL_BIT=4
ORIGINAL_SHARED_STATUS_POLL_HAS_FINITE_BOUND=NO
PROVIDER_MEMORY_ORDER_AND_GLOBAL_CROSS_PORT_EFFECTS_PROVEN=NO
S8000_PCIE_DART1_AND_WIFI_HARDWARE_INIT_AUTHORIZED=NO
```

**30 synthetic adversarial tests** in `tests/test_n71_s8000_port1_rmw_provenance_gate.py` construct synthetic AArch64 instructions, then independently mutate each virtual-slot selector, register ID, per-port bit mask and write target. They also reject a modified common ID1 polling bit, its conditional exit, callback constant and backedge, incorrect A9 root pointer inheritance, invalid executable extents and fake success without a valid private original kernelcache. No original Apple executable bytes or private ADT are included in the tests.

## New standalone C RMW policy model: 65,536 synthetic vectors

`examples/n71-pcie-port1/port1_rmw_policy_model.c` implements a deliberately **hardware-inert** transition policy over **caller-supplied synthetic uint32 values**. It accepts only logical port 1, the four above virtual operation IDs and boolean 0/1 inputs; all other operations fail closed. It preserves the other 31 bits (for bit0) or the other 31 bits (for bit8/bit20) without clobbering unrelated fields. It explicitly prohibits **any** write to the shared/global ID1 relative offset `0x2C`, to the queried port status register at `0x1AC`, to unknown offsets or to ports 0, 2 or 3. This model has no MMIO pointer, no PCIe root binding, no real I/O and cannot initialize Wi-Fi.

The native Linux C harness generates **65,536 deterministic synthetic bit-mutation vectors**, with an independently coded bit-oracle and unchanged-neighbor invariant. Each vector passes the standalone C source for one of the four register operations and checks that all unselected bits remain identical. Additional cases reject wrong ports, global writes, unknown operation IDs, multi-bit masks and invalid arguments. The SAME source was compiled to a real AArch64 ELF relocatable object under `-std=c11 -Wall -Wextra -Werror` without errors. Eight Python regression tests in `tests/test_n71_port1_rmw_policy_model.py` cover compilation, the vector harness and source-level safety invariants.

## No unsafe conclusions

- Original root **resource index 9** was verified by the original Apple ARM64 code; its presumed physical ADT reg[9] address is still conditional on **unproven IODeviceMemory provider ordering**. Do not construct or dereference physical addresses from these relative offsets.
- **Register semantics** (clock, reset, link training, PHY, MSI, IRQ) and cross-port effects are NOT established by identifying bit masks alone.
- The global/shared register **`0x2C`, bit4**, remains a dependency; it is not safe to infer that toggling another port's RMW bit is harmless.
- The original status-`0x1AC` bit0 loop and the shared `0x2C` bit4 loop both lack explicit **caller-side** retry bounds. Future kernel logic must be separately designed with elapsed-time limits, rollback and fault reporting, not copied into a blocking early init path.
- DART1's physical stream IDs, DMA page tables, IOVA isolation and fault recovery still require independent qualification. The safer packed-TCR C patch remains separate from the proven boot image.
- BCM4350 enumeration, correct private firmware/NVRAM and physical Wi-Fi association to the same authorized network as the Dell remain UNTESTED.

**Conclusion:** the actual A9 port1 bit-modification method identities, target bit positions, original RMW polarity and global waiting dependency are now reproducibly audited and safely emulated. This is an important clean-room engineering input, but it is not a functioning PCIe driver or authorization for hardware activation.
