# N71/S8000 port1: real AArch64 Linux kernel preflight, private source mirror, disabled DT fixture

**Date:** 2026-11-12. **Target:** owner-verified iPhone 6s N71 Samsung A9/S8000, onboard BCM4350 Wi-Fi at PCIe port 1, DART1 child logical mapper 0. **Outcome:** a proper Linux `platform_driver` with a **read-only resource-descriptor preflight** compiled against the actual Hoolock-derived private ARM64 Linux worktree. It is deliberately **NOT a functional PCIe host or Wi-Fi driver**, and remains excluded from the known-good RAM image.

## Engineering change

The previous private Linux S8000 guard merely checked fixed disjoint hardware regions and refused to probe. This iteration improves the **kernel implementation**: the real C `platform_driver` receives a narrowly scoped, opt-in **synthetic** OF compatible `apple,s8000-pcie-research-blocked`. A function `apple_s8000_preflight_private_port_metadata()` validates:

1. The board must be explicitly `apple,n71` **and** `apple,s8000`; not the TSMC A9 S8003 and not an Apple M1 PCIe-compatible controller.
2. OF metadata contains a synthetic `research,hardware-activation-blocked` marker, `research,pcie-port-index=1`, `research,dart1-mapper-index=0`, and `research,refclk-to-perst-metadata=100`. This **100 is an Apple original property scalar, not an inferred millisecond/microsecond delay**.
3. Through the **actual Linux kernel platform-device metadata API**, `platform_get_resource_byname()`, exactly three named `IORESOURCE_MEM` descriptors must match the original N71 Apple Device Tree hardware windows. The code never maps a descriptor, reads a register, or claims DMA ownership.
4. The candidate windows must be mutually disjoint and disjoint from six protected regions containing PCIe shared root/config, storage port0, baseband port2 and unreviewed port3.
5. No fourth `IORESOURCE_MEM` descriptor is accepted. No resource, property mismatch or unknown SoC reaches the final stage.

**Mandatory fail closed:** even after every descriptor passes, the only result of `apple_s8000_guard_probe()` is **`-EOPNOTSUPP`**. The static, deliberate probe failure is essential: PCIe link, PHY clock, PERST#, DART1 TTBR and MSI ownership are still unqualified. The guard never calls `ioremap`, `readl`, `writel`, clock, GPIO, reset, IRQ, IOMMU or PCI enumeration APIs.

The separately public `examples/n71-pcie-port1/pcie-apple-s8000-port1-preflight.c` is an **exact byte-for-byte copy** of the modified `drivers/pci/controller/pcie-apple-s8000-guard.c` in the owner's private Linux worktree. The private original Linux Kconfig/Makefile already has the `PCIE_APPLE_S8000_RESEARCH_GUARD` build target, which remains `# ... is not set` in the known-good build configuration.

## Evidence from the actual private Linux build

The guard was built using the real Hoolock-derived Linux kernel build tree and cross-compiler `aarch64-linux-gnu-`, with a separate private out-of-tree `O=` build location. The result was a valid **ELF64 AArch64 relocatable kernel object**, with its actual `apple_s8000_guard_probe` function present. This is **a real Linux kernel compilation**, not a userspace C simulation and **not** a kernel module loaded onto the phone.

The preexisting independent `tools/n71_s8000_port1_guard_consistency_gate.py` verified that exact kernel C source against the owner-held original Apple Device Tree and the newly built ARM64 object:

```text
N71_S8000_WLAN_PORT1_METADATA_GUARD_ARM64_STATIC_PASS
CANDIDATE_PORT1_WINDOWS 3
PROTECTED_STORAGE_MODEM_GLOBAL_WINDOWS 6
ORIGINAL_ADT_BCM4350_DART1_ASSOCIATION_PASS
DART1_PHYSICAL_SID_DMA_ISOLATION_VERIFIED=NO
PORT1_PCIE_LINK_DRIVER_OR_RADIO_READY=NO
```

The three hardware-fixed candidate windows (SoC properties, **not private calibration**) are:

| Source descriptor name | Original N71 hardware region | Purpose |
|---|---|---|
| `port1-reg-a` | `0x602000000` / `0x4000` | WLAN PCIe port1 region A |
| `port1-reg-b` | `0x602004000` / `0x4000` | WLAN PCIe port1 region B |
| `dart1-reg` | `0x602008000` / `0x4000` | DART1 dedicated controller region |

**No private original Apple code, IORegistry captures, BoardConfig identifiers, Wi-Fi calibration, OTP, C5 firmware or wireless credentials are bundled.**

## Offline, explicitly disabled, synthetic Device Tree

The `examples/n71-pcie-port1/port1-preflight-disabled.dts` file is a **standalone, nonbootable** fixture: it declares those three descriptors and the synthetic guard compatible, with `status="disabled"` and no clocks, interrupts, MSI, DMA or IOMMU bindings. Its purpose is to exercise exact kernel metadata policy, never to enable the hardware.

The `tools/n71_s8000_port1_preflight_fdt_gate.py` verifies the **compiled** FDT, rejecting enabled statuses, Apple M1 native compatibles, any extra nodes, wrong port/mapper/refclk property, changed region names/values, fourth window, storage/modem/shared-root windows, illegal `clocks`, `resets`, `iommus`, `interrupts`, `dma-ranges`, or malformed FDT. The matching `tests/test_n71_s8000_port1_preflight_fdt_gate.py` runs the actual `dtc` compiler, then mutation-tests the parsed FDT.

From the public repository:

```bash
make -C examples/n71-pcie-port1 preflight-check

python3 -m unittest discover -s tests \
  -p test_n71_s8000_port1_preflight_fdt_gate.py -v
```

The expected result is `N71_S8000_PORT1_PREFLIGHT_FDT_OFFLINE_PASS`, `FDT_STATUS_DISABLED=YES`, `HARDWARE_PROBE_MMIO_DART_RESET_PERMITTED=NO` and `LINUX_S8000_PCIE_LINK_AND_WLAN_INITIALIZED=NO`.

**Never load the standalone fixture as the phone's primary Device Tree. Never set the guard's disabled status to `okay` as a hardware workaround.** Even if enabled, the guard still returns `-EOPNOTSUPP` and cannot enumerate WLAN.

## Original iOS correlation and remaining physical dependencies

The immediately preceding [owner-unlocked stock-iOS original-live snapshot](N71_S8000_UNLOCKED_IOS_LIVE_DART1_PCIE_PORT1_2026_11_12.md) confirmed stable native BCM4350 PCIe Gen1 ×1 under iOS, actual original DART1/mapper nodes and `AppleS5L8960XDART` matched at boot. The original metadata and original Apple software index0→packed TCR lane0 chain were independently validated, as were the 83 original PCIe/PHY tuning records.

This kernel preflight removes uncertainty about **which exact Linux resource descriptors** an S8000 port1-specific probe would accept and how an accidental storage/baseband/shared binding is rejected. It does **not** solve actual DART1 physical requester-to-SID routing, safe TTBR/IOVA/fault isolation, full original PHY/refclock/PERST#/power/MSI sequence, shared root bit4 register meaning, reversible hardware rollback or genuine Linux WLAN association.

A future separate supervised RAM-only boot candidate must first preserve the tested touch/LCD/USB rescue image, implement bounded per-port-only PCIe startup and **safe** dedicated DART1 DMA ownership, then physically enumerate BCM4350 with board-matched C5 firmware and verify direct WLAN association to the authorized Dell LAN. A USB-tethered connection is not an acceptable Wi-Fi acceptance test.

**No physical MMIO, NAND, DART1 DMA, PMIC, clock, reset, PCIe enumeration, iOS system change, Wi-Fi reconfiguration or Linux boot was performed here.**
