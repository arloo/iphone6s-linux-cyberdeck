# N71/S8000 PCIe port-1: ARM64 research guard matched to authentic Apple ADT

**Date:** 2026-11-11. **Target:** iPhone 6s N71 Samsung A9 (S8000), native Broadcom BCM4350 WLAN under PCIe port 1. **Status:** read-only/offline qualified metadata; no working Linux S8000 PCIe host controller.

## Original evidence and current limit

The privately retained original N71 ADT independently verifies a four-port `apcie,s8000` host, onboard `wlan-pcie,bcm4350` under `pci-bridge1`, a uniquely resolved WLAN-to-`dart-apcie1` logical mapper, and eleven host register windows plus three DART register windows. Apple iOS kernelcache code establishes PCIe root resource-index formulas returning 0, 9 and 10. **Actual AppleARMIODevice runtime IODeviceMemory resource ordering remains unproven**, and register semantics, clock/refclock/PERST#, link training, MSI, physical DART stream IDs, IOVA and DMA faults are also unverified.

## Compiled, deliberately inert Linux component

The original repository's source `drivers/pci/controller/pcie-apple-s8000-guard.c` (introduced by `patches/0011-...`) has now been compiled into an actual **ELF64 AArch64 relocatable** `pcie-apple-s8000-guard.o` in a private cross-build. Its only external references are platform driver registration, `of_machine_compatible_match`, logging and stack-protector support: no direct MMIO, DMA, IRQ, clocks or resets.

The guard binds **only** to `apple,s8000-pcie-research-blocked` with an explicit opt-in device tree node (which is absent from the known-good boot). Its probe returns `-ENODEV`, `-ERANGE` or `-EOPNOTSUPP`, **never a working PCIe host**. Kconfig defaults disabled. No actual PCIe endpoint can be enumerated through this component.

The new public `tools/n71_s8000_port1_guard_consistency_gate.py` reads a locally held original N71 ADT, the private original GPL Linux guard source and its built AArch64 object; validates that three candidate WLAN/port1+DART1 windows match the original ADT exactly, that six protected aggregate ranges cover shared resources/storage port0/baseband port2/unknown port3/ECAM, and that source still contains no hardware-touching API and returns an error at probe. It prints only aggregate metadata and never writes a file or accesses a device.

| Window class | Offline result | Safety interpretation |
|---|---|---|
| WLAN port1 registers | Two 16-KiB ADT regions matched | Address metadata only, no verified register offsets/bitfields |
| Dedicated DART1 region | One 16-KiB region matched | No runtime SID/IOVA/DMA isolation established |
| Protected regions | Six host/global/other-port aggregate ranges matched | Never configure storage0, baseband2 or shared fabric based on guesses |
| AArch64 guard | Source compiled as ELF REL and compared to strict original ADT | **Hardware probe remains blocked** |

**Nineteen synthetic regression cases** in `tests/test_n71_s8000_port1_guard_consistency_gate.py` reconstruct only the GPL guard from the public RFC11 patch, use a mocked synthetic ADT response, and reject altered port windows, DART0/1 swaps, unexpected shared/storage/modem ranges, unsafe live PCIe compatibles, probe success, direct MMIO or PCI host enumeration, missing isolation and x86 objects.

```bash
python3 tools/n71_s8000_port1_guard_consistency_gate.py \
  /private/original-n71-adt.bin \
  /private/linux/drivers/pci/controller/pcie-apple-s8000-guard.c \
  /private/aarch64-build/drivers/pci/controller/pcie-apple-s8000-guard.o
```

## Why upstream PCIe registers are not used

The Linux upstream Apple PCIe driver currently supports later Apple controller families with port clock/refclock/PERST#, RID/SID and MSI programming. The original A9/S8000 Apple root/port classes have a separate legacy initialization model, and their register values, reset and DMA ownership are **not interchangeably validated**. Upstream reference: https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c

## Next gate

Original iOS provider IODeviceMemory ordering, physical port1 clock/PHY/reset/interrupt and DART1 stream isolation must be proven independently before a separately supervised RAM-only bring-up. The existing known-good Z2 touch, simpledrm display, USB recovery and NAND remain untouched. **A successful static gate is NOT a functional PCIe host or proof of Wi-Fi connectivity.**
