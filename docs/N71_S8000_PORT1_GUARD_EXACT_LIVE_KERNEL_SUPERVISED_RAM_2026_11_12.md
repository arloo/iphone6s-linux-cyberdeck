# N71/S8000 port1 fail-closed guard: exact live-kernel ABI and supervised RAM candidate

**Date:** 12 November 2026
**Evidence:** real N71/S8000 Linux kernel matched byte-for-byte to the owner's local build; guarded ARM64 module **compiled offline only**, not yet loaded on the phone
**Scope:** synthetic platform resource-descriptor verification, **not** a functioning PCIe host, DART1 DMA, BCM4350 WLAN interface, association or DHCP.

This milestone follows the [physically verified N71 descriptor-only RAM boot](N71_S8000_PORT1_DESCRIPTOR_ONLY_PHYSICAL_2026_11_12.md): the owner-controlled iPhone 6s is currently running Linux over the USB gadget `05ac:4142`, with one inert port1/DART1 platform device, the previously verified touchscreen initialization, zero enumerated PCIe devices, zero IOMMU groups, zero WLAN interfaces and **no bound PCIe driver**.

## Reconstruct the exact physical kernel ABI, not merely its version string

The actual owner-private, physically booted RAM image contains an embedded Linux `Image.gz`. An independent parser extracted the *first gzip member* after the two original boot Device Trees and compared its decompressed bytes to the owner-local kernel build:

- Exact matching build output: `build-z2-cal-ack-next/arch/arm64/boot/Image` (owner-private build directory, not committed).
- Physically booted, decompressed ARM64 kernel SHA-256: `fbf9ec6754245d48922e6da8b82c90e6c985ea088ed8ab896397af8e3f9f7845`.
- Kernel release: `7.3.0-rc1-g68aadac820d0-dirty`.
- Both the original physically verified descriptor-only RAM image and the next staged image contain exactly the same kernel bytes.

The matching build was missing automatically generated Kbuild `autoconf.h`; the matching `Image` hash was pinned, Kconfig was prepared **offline** with `olddefconfig` and `prepare modules_prepare`, and the `Image` SHA was re-verified unchanged after preparing the headers.

## Experimental module built but not physically run

The existing owner-private `pcie-apple-s8000-guard.c` research source was built as an **external AArch64 kernel module** against the exact matching kernel build, with no functional PCIe host driver:

```text
pcie-apple-s8000-guard.ko
ARM64 relocatable kernel module
vermagic: 7.3.0-rc1-g68aadac820d0-dirty SMP preempt aarch64
SHA-256: 40f2275047a3be6739b3d7760fb038033a818253f56cd9a495ad377013fe73d7
```

The module imports exactly nine kernel symbols: `_dev_info`, `of_machine_compatible_match`, `of_property_read_bool`, `of_property_read_variable_u32_array`, `__platform_driver_register`, `platform_driver_unregister`, `platform_get_resource`, `platform_get_resource_byname`, and `__stack_chk_fail`. **All nine symbols were independently found exported in the exact matching `vmlinux`**, not just in a different kernel with the same release string.

The build used `KBUILD_MODPOST_WARN=1` because this matching offline build lacks `Module.symvers`. Consequently Kbuild emitted unresolved-symbol warnings at *build time*. The independent export verification resolves their expected provenance but **does not guarantee that the module will successfully load on the real phone**. Treat that as an unresolved physical test gate; never force-load it.

The private research source's platform `probe` validates the N71/S8000 identity, requires the explicit `research,hardware-activation-blocked` flag, checks the three original port1/DART1 resource descriptors and exact sizes, then **returns `-EOPNOTSUPP` even if every check passes**. It contains no direct register-mapping, MMIO read/write, PCI host initialization, IOMMU DMA, clock, regulator, GPIO, reset or interrupt-request function calls. It does not implement BCM4350 hardware access or native Wi-Fi.

An independent [fail-closed exact-kernel/module/source audit](../tools/n71_port1_guard_module_exact_live_kernel_abi_gate.py) checks the original kernel-image SHA, exact boot-image kernel member, ARM64 relocatable ELF identity, module `vermagic`, complete imported-symbol allowlist against the exact linked kernel exports, forbidden hardware APIs in the research source and mandatory refusal path. [Fifteen adversarial synthetic unit tests](../tests/test_n71_port1_guard_module_exact_live_kernel_abi_gate.py) cover unexpected imports, missing exports, altered physical resource windows, MMIO/DMA/clock/reset functions, missing hardware-block safety, malformed Device Trees, unexpected boot images and parser correctness.

## Dedicated, separately recoverable supervised RAM boot prepared

**New private-only candidate (not yet physically booted):**

```text
private-touch-live-test/n71-port1-guard-supervised-next/
  m1n1-linux-n71-port1-guard-supervised-ram.bin
```

- Size: **11,926,991 bytes**.
- SHA-256: `5cd2581beccfb399c4be7fa24509b43dbf31b7232f3692dcb6ec1a3782a5d17b`.
- Previous proven descriptor-only physical RAM boot SHA-256 remains `6f460870bbded3648ba9136afac45a428c55c4470185e5f0873b6c074605b986`.

The private builder repacked **only** the new candidate's initramfs. The entire remaining boot image is *byte-for-byte identical* to the physically booted predecessor: m1n1, Apple N71/S8003 Device Trees, real Linux `Image.gz`, touchscreen support and existing diagnostic configuration. It preserved the contents and permissions of **every original initramfs file**, including `/init`, the touchscreen automatic initializer and read-only WLAN test hook.

Exactly two executable/data files were added: the experimental `.ko` (not autoloaded) and `/usr/bin/n71_port1_guard_supervised.sh` (not called from `/init`). Independent re-extraction of the final image verified both files, module checksum, zero changes outside the initramfs, and original `/init` unmodified.

The manual launcher is **explicitly opt-in** via `N71_GUARD_ONE_SHOT_ACCEPT=1`. Before issuing a single `insmod`, it verifies N71/S8000 board identity, exact running-kernel release, exact three 64-bit MMIO **descriptors** from the OF node, safety flag, port index 1, DART mapper 0, known module SHA, absence of any bound driver, PCIe endpoints, IOMMU groups and WLAN interfaces, and the already proven touchscreen protocol-ready log. If any check fails it does not execute the module. After a successful load it requires the hardware-blocked metadata-probe log and still no bound hardware driver, no PCIe devices, no IOMMU groups and no native WLAN. This does not exercise or prove a physical PCIe/DMA interface.

### Important non-unloadable module constraint

The exact phone kernel configuration has `CONFIG_MODULES=y`, but **`CONFIG_MODULE_UNLOAD` is disabled**. A successfully loaded module cannot be removed with `rmmod` in the current RAM session. This is why the module was **not loaded into the already working phone session**. The next stage requires a separately attended RAM-only boot; recovery is the proven previous RAM image via DFU/PongoOS, not an attempted forced unload or storage restore. No bypass of the S8000 DART1 pre-MMIO guard is permitted.

## Engineering outcome and next gate

**Now established offline:** A9 guard module matching the exact physically booted Linux kernel and using only known exported metadata/platform symbols, 15 synthetic safety tests, dedicated separate owner-private RAM-only recovery-compatible candidate.

**Still not established physically:** Module loading and the platform driver metadata-probe result on the phone, real BCM4350 enumeration, hardware root-complex state, actual DART1 requester-to-hardware SID mapping, DMA isolation, PHY/clock/reset ordering or native Wi-Fi.

The already running descriptor-only Linux remains untouched and reachable via local USB. No phone restart, firmware flash, NAND write, root-port MMIO access or DART1 DMA enablement was carried out during this offline milestone.

**Privacy:** The compiled module, original Apple ADTs/kernelcache, private iPhone firmware/calibration and both boot images remain only on the owner's Dell. Public GitHub contains only this sanitized audit, associated Python tests, technical documentation and exact reproducible non-secret status statements.
