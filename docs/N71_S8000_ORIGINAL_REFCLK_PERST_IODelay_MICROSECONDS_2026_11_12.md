# N71/S8000 original Apple PCIe PHY / PERST timing: actual XNU IODelay import proven

**2026-11-12 | Original owner-controlled iPhone 6s N71, Samsung A9/S8000 | Result:** original Apple REFCLK-to-PERST scalar **100 is in microseconds** and original root shared-state status polling waits **10 microseconds** per unsuccessful iteration. The original XNU kernel-symbol binding, field dataflow and authentic live iOS metadata are all verified. This is an **offline/original-iOS software timing proof**, not a Linux hardware initialization permission.

## Previously unresolved, now proven

Earlier static A9/S8000 reverse engineering established a per-port C++ control sequence: two calls into an unknown delay-like stub (immediate argument `100` and a 32-bit port object field at `+416`), plus a third call with immediate argument `10` inside an original shared-controller status bit4 polling loop. Both the function identity and delay units had been deliberately left unknown.

The new independent provenance gate `tools/n71_s8000_original_refclk_perst_delay_gate.py` resolves the complete code/data chain on a **genuine, privately retained original iOS 15.8.8 N71 ARM64 kernelcache**:

1. The original `AppleEmbeddedPCIE` class accesses the exact N71 Apple Device Tree property string `t-refclk-to-perst` through a bounded original AArch64 `ADRP+ADD` reference.
2. Its property-load call passes the destination address `port_object + 416` into the original helper. The helper reads the property as a 32-bit value and stores it to that address. This is an actual **property → object-field dataflow proof**, not a name-based inference.
3. The inherited original `AppleS800xPCIePort` method loads `W0` from the same `port_object + 416` field and invokes a direct import stub. Earlier source analysis verified a separate call in that method passing literal argument **100** through another identical import.
4. The original ARM64 calls resolve into a version-pinned `__stubs` trampoline, then through the original KEXT `__got` entry in prelinked `__PLK_DATA_CONST`, to a function in the original XNU `__TEXT_EXEC`. The original kernel's **actual Mach-O LC_SYMTAB** proves the target equals the unique exported `_IODelay` function **exactly**. The neighboring exported `_IOSleep` function is **not** the target.
5. Original XNU IOKit defines `IODelay(unsigned microseconds)`, a busy/spin delay in **microseconds**, distinct from `IOSleep(unsigned milliseconds)`. Apple documentation is an independent ABI reference: https://developer.apple.com/documentation/kernel/1575328-iodelay and https://developer.apple.com/library/archive/documentation/Darwin/Conceptual/KernelProgramming/services/services.html
6. Both privately held original N71 Apple Device Tree copies, as well as the independently acquired original stock iOS 15.7.9 `pci-bridge1` IORegistry on the unlocked owner device, agree on `t-refclk-to-perst = 100` (32-bit). Thus **the original field-based delay on this board is 100 microseconds**.
7. Separately, the original shared-controller root status bit4 poll uses `MOVZ W0, #10`, the **same original `_IODelay` import**, and a conditional backedge. The retry interval is therefore **10 microseconds per unsuccessful attempt**. The original caller does **not** prove a finite timeout, so Linux must add one.

## Grounded original-software timing

| Source | Original software action | Verified unit | Unsafe assumption not made |
|---|---|---|---|
| Port control, fixed original literal | `IODelay(100)` | 100 µs | No inferred PHY enable effect |
| Port control, source from `t-refclk-to-perst` via object field +416 | `IODelay(port_property)` | 100 µs on actual N71 iOS | No extrapolation to unvalidated devices |
| Shared root status register ID1, bit4, polling loop | `IODelay(10)` between retries | 10 µs | No unlimited polling in future Linux driver |
| Actual root register bit4 | Read and test bit4 | Relative register access already separately audited | No proof that bit4 means a specific clock/reset/PHY state |

**Caution:** source-time microseconds are **not** sufficient to infer physical sequencing. Clock and PHY topology, REFCLK versus PERST# operation and the shared status register's actual electrical semantics remain incompletely known. The existing N71 S8000 PCIe kernel preflight is intentionally inert; it never calls `udelay`, maps the controller, changes a GPIO, starts PCIe link training, configures DMA or touches the radio.

## Kernel implementation advanced without hardware changes

The independently built and maintained private Linux `drivers/pci/controller/pcie-apple-s8000-guard.c` was updated to consume the explicitly unit-bearing synthetic source property:

```dts
research,refclk-to-perst-delay-us = <100>;
```

Its identical public source mirror, disabled synthetic FDT fixture, strict FDT policy gate and adversarial tests were all updated to the same **microsecond** contract. This makes accidental conflation with a 100-millisecond sleep fail the metadata checks. However, the component is **still a guarded research `platform_driver` whose probe always returns `-EOPNOTSUPP`**. The unchanged known-good RAM Linux touchscreen/LCD/USB boot has not been modified.

The exact private Linux source was rebuilt with the owner's AArch64 Linux cross-toolchain to a verified ELF64 relocatable kernel object. A separate compiled, **disabled/nonbootable** FDT test passed its validation. No runtime Linux PCIe/Wi-Fi action was authorized.

## Reproduction on owner's Dell

The proprietary original Apple kernelcache, original device-tree blobs and stock iOS IORegistry are supplied as locally held, private files only:

```bash
python3 tools/n71_s8000_original_refclk_perst_delay_gate.py \
  /private/original-iOS-N71-kernelcache.macho \
  /private/original-N71-apple-adt.bin \
  /private/stock-ios15-n71-pci-bridge1.plist

python3 -m unittest discover -s tests \
  -p test_n71_s8000_original_refclk_perst_delay_gate.py -v

make -C examples/n71-pcie-port1 preflight-check
```

The gate checks ARM64 instruction signatures, original property-string address, helper destination and signed call target, source object's 32-bit field, actual inherited dispatch chain, all three prelinked GOT import resolutions, exact original kernel-export symbols, N71 board-specific ADT and independently captured stock-iOS metadata. It **fails closed** if any source changes. It prints only aggregate timing and status, never original proprietary bytes, raw IORegistry, source absolute addresses, firmware, unique hardware IDs or user credentials.

This result supersedes the earlier reports' historical statement that the delay units were unknown. It does **not** alter their outstanding caveats about root-shared register effects, actual PCIe requester-to-DART1 hardware SID, TTBR/IOVA/fault isolation, port1 REFCLK/PHY/PERST#/MSI/power sequencing, or native BCM4350 C5 Wi-Fi readiness.

**Linux PCIe link and native Wi-Fi remain NOT operational. The original iOS device and original known-good RAM Linux boot image are unchanged.**
