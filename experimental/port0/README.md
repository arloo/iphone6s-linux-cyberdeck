# N71 / S8000: Apple S3E NAND PCIe port 0 — real hardware bring-up

**2026-11-17. Real device:** iPhone 6s (Samsung A9), Linux ARM64
`7.3.0-rc1-n71-batt2`. This is **not a NAND driver**. The userland and
firmware remain in RAM, and no Apple storage block device is enumerated.

A full, **encrypted iOS user-data backup was completed and checked locally**
before the physical power test. This is not a bare-metal NAND backup.

## Verified on hardware

- N71 stock Apple Device Tree identifies the storage endpoint as
  `apcie/pci-bridge0/s3e`, with Apple PCI ID `106b:2002`.
  The controller uses DART0 and an additional `nvme-mmu0`, distinct
  from the Broadcom PCIe Wi-Fi transport.
- The live Linux `pcie_link0` power domain was initially **OFF**.
  Using a temporary consumer attached to the *existing* Apple PMGR
  genpd provider node (which has no phandle), `n71_s3e_port0_power`
  powered the domain **ON for 25 ms** (hardware actual state 15),
  then synchronously turned it **OFF** (actual state 0).
- In both physical trials, shared `pcie`, `pcie_ref`, `pcie_aux` and
  port1 remained on; port2 and port3 remained off. Native Wi-Fi,
  USB SSH, battery and touch functionality were retained.
- Stock-verified common root MMIO `0x600000000` was read without
  writes by `n71_s3e_port0_root_ro`. PCIe port0 link-status bit0
  was **0**, while port1 was **1**. The same values were observed
  *during* the 25-ms port0 power lease. **Power alone does not train
  the storage PCIe link.**
- Original stock Apple `function-perst` metadata identifies
  physical GPIO **160** for storage and GPIO **161** for Wi-Fi.
  `n71_s3e_p0_gpio_ro` read the actual A9 pinctrl registers:
  storage GPIO160 was input-mode, data 0; Wi-Fi GPIO161 was output,
  data 1. No GPIO pins were driven or reconfigured.
- **No PCIe endpoint reset release, NVMe submission, DART0 enable,
  NVMe-MMU remapping, DMA, APFS resize, NAND write or partitioning**
  was performed. All experimental modules were unloaded afterwards.

## Native Linux storage controller device-model milestone (17 November)

**Executed on the actual iPhone 6s/S8000:** the ARM64 module
`n71_s3e_platform_inventory.c` registered and bound platform devices
`n71-a9-dart0.0.auto` and `n71-a9-nvmmu0.1.auto` with their exact
stock Apple physical resources. Linux confirmed **1 DART0 resource**
and **2 NVMMU0 resources**. Both devices and the module were then
unregistered; Wi-Fi stayed active and PCIe link0 stayed OFF.

The optional `n71-s8000-storage-controllers-disabled.dtsi` also compiled
as part of the **full N71 Linux Device Tree** and supplies both physical
resource sets, original IRQs 245/246 and the `pcie_link0` genpd
dependency. It is **not installed** on the running phone or any boot image.
Both nodes remain `status = "disabled"`. This work does **not** train
the storage link, map DMA, access NAND, enumerate `106b:2002`, or
establish a usable Linux storage volume.

The live phone was discharging (~51%) during registration, so no
further hardware power/PHY reset tests were run. Resume invasive
qualification only with a reliable charging supply.

## Power-domain dependency module — built, hardware activation deferred

`n71_s3e_genpd_attach.c` adds the real DART0 and NVMMU0 platform
devices to the **existing** Apple PMGR `pcie_link0` generic-power-domain
provider using `of_genpd_add_device()`. It explicitly validates the
N71/S8000 board, the physical PMGR node, that the provider's link domain
is **off**, and the preserved Wi-Fi PCIe endpoint. Both genpd links are
detached before platform devices are unregistered.

It contains **no** `pm_runtime_get`, `pm_runtime_enable`, MMIO write,
NVMe command, reset release or DMA enable. It is default-inert and
requires explicit parameters `armed=1 attach_domains=1` to attach.
This module is compiled for the exact N71 booted ARM64 kernel.
**Physical test on 2026-11-17: PASS.** Both platform devices
`n71-a9-dart0.0.auto` and `n71-a9-nvmmu0.1.auto` appeared
under `pcie_link0` in the live Linux `pm_genpd_summary`, while
the domain remained `off-0`. After `rmmod`, both associations
and devices disappeared, Wi-Fi carrier remained up, USB SSH
continued responding, and the NAND block-device list remained empty.
Genpd marked the devices `unsupported`: they have no fully
enabled runtime PM or storage controller driver yet.

The owner's bounded SN2400 charging lease was restored to 300 mA
following the previous automatic timeout. The phone's fuel gauge
alternates charging/idle/discharging over short intervals.
The private staging procedure consequently requires **ten actual
current samples**, a positive total, at least four positive
charging samples, 40%+ capacity, temperature below 40 °C,
3.7–4.25 V battery voltage and a configured USB gadget;
no power-dependent storage trial was approved on this criterion.
Brightness was lowered temporarily to support net-positive current.

**This success proves safe platform/genpd wiring only.** The MMIO
register windows still require verified electrical power/clock
sequencing and DMA quarantine before the real S3E PCIe endpoint
can be brought up.

## Physical S3E reset GPIO160 control and safe recovery

**Tested on real Samsung S8000 N71 hardware, 17 November 2026:**

- Original Apple N71 storage `function-perst` identifies physical
  **GPIO160**, distinct from WLAN PERST **GPIO161**.
- A bounded first-stage kernel GPIO experiment exclusively acquired
  GPIO160 and actively drove it **LOW for 50 ms**, keeping NAND reset
  asserted while `pcie_link0` remained OFF. Hardware readback confirmed
  `0x00072202`; WLAN stayed operational. The pin was never driven HIGH.
- Native `gpiod_direction_input()` then left pin160 in Linux input
  IRQ-disabled mode `0x0007220e`, not the original firmware mode
  `0x00072200`. The experimental module correctly quarantined itself
  and retained exclusive pin ownership instead of assuming restoration.
- A separate private recovery module, using the **already registered
  Apple pinctrl device regmap** and a strictly masked `regmap_update_bits`,
  restored `0x0007220e -> 0x00072200`. A **separate independent raw MMIO
  reader** confirmed exact original hardware `GPIO160=0x00072200`,
  `GPIO161=0x00072203`, and untouched storage CLKREQ164. Port0 remained
  powered OFF, and WLAN/USB/OS stayed functional.
- The quarantine owner's kernel-module reference and GPIO reservation
  are still present. **Do not forcibly unload this module.** A clean RAM
  reboot is required before the next GPIO160 ownership test.

The version-controlled `n71_s3e_perst160_low.c` incorporates the
confirmed correction: it obtains the **existing pinctrl driver's
`dev_get_regmap()`** and restores all changed bits before releasing
the GPIO line. It builds for the actual N71 Linux ARM64 kernel and
passes its source-contract checks, but its **combined corrected
acquire/restore path has not yet been hardware-retested** after a fresh
boot. Keep `pcie_link0`, S3E DMA and endpoint PERST release disabled
until that verification passes.

This is a true GPIO160 reset-control milestone, **not** successful
PCIe link training or S3E/NAND enumeration.

## Full PHY and physical port0/port1 comparison (17 November)

The source gate `tools/n71_s8000_stock_phy_local_clock_gate.py`
authenticates the original Samsung S8000 PCIe resource topology,
41 shared PHY tunables, six+two identical per-port records and
the distinct Apple `PCIE_APP` clock descriptor.

The physically executed `n71_s3e_phy_stock_ro.c` read all
**41/41 shared PHY** tunable registers. All were responsive, and
all 41 matched the original Apple masked register values.
No power, reset or MMIO writes were made by this probe.

A separate bounded, owner-supervised
`n71_s3e_p0_local_window_compare.c` physical trial held
GPIO160 **OUTPUT LOW** during a 25-ms `pcie_link0` power lease.
It returned **0/8 valid** per-port tuning register reads in each
port0 bank, versus **8/8 valid** in each of the identical
WLAN port1 banks. DART0/NVMMU0 also remained unreadable.
All root registers, PMGR domains and GPIO160 restored
successfully; both test modules were unloaded.

**Conclusion:** The shared PHY is reachable and stock-conforming.
The remaining target is the **storage port0-specific register
decode / clock / force-active path**, not wholesale common PHY
initialization. The exact gating condition is still unproven.
Do not release NAND PERST or enable DMA based on this alone.

[Real-device results and limitation details](../../docs/N71_S8000_PHY_41_AND_PORT0_MMIO_DIFFERENTIAL_2026_11_17.md).

## Sources

`n71_s3e_port0_power.c` — opt-in PMGR 25-ms physical power lease,
fail-closed gating and synchronous rollback. Defaults inert.
`sample_root=1` additionally reads the root link-status register
during the powered interval.

`n71_s3e_port0_root_ro.c` — root MMIO physical register snapshot.
Defaults inert; explicitly use `armed=1` for the bounded reads.

`n71_s3e_p0_gpio_ro.c` — existing tested read-only A9 GPIO
snapshot, rebuilt for the active N71 kernel. Does not request or
change the reset lines.

### Follow-up physical S8000 storage MMIO results

The native read-only comparison module `n71_s3e_dart_compare_ro.c` has
also been built for the actual booted kernel and physically tested. It
confirmed active Wi-Fi DART1 command `0x00000102` and packed TCR
`0x00000080` while storage DART0, NVMMU0 and port0 each returned
`0xffffffff`. The comparator never changes PMGR power or any MMIO
register. Details and original Apple callback provenance:
[storage force-active diagnostics](../../docs/N71_S8000_STORAGE_FORCE_ACTIVE_DART0_DIAG_2026_11_17.md).

The following additional native modules have been **executed on the iPhone**:

- `n71_s3e_p0_mode_ro.c`: root common mode `+0x14 = 0x101`,
  `+0x24 = 0`, while Wi-Fi was active.
- `n71_s3e_p0_iommu_ro.c`: with port0 powered for 25 ms, reads of
  DART0 at `0x601008000`, NVMMU0 at `0x601004000` and storage port0
  at `0x601000000` **all returned `0xffffffff`**. These are invalid
  register reads, NOT successful device enumeration.
- `n71_s3e_p0_nvme_mode.c`: temporarily enabled and verified root
  `+0x24 = 1`, following original **N71/S8000** Apple root vtable
  instructions, then restored `+0x24 = 0`. The inaccessible bus
  windows remained `0xffffffff`.
- `n71_s3e_p0_rootstart.c`: RMW-preserving the actual physical
  baseline `port0 ID3 = 0x00000100` and
  `port0 ID2 = 0x01000110`, temporarily set only bit 0 in each,
  observed positive hardware readbacks, then restored both original
  register values. Storage PERST GPIO160 remained LOW. DART0/NVMMU
  still returned `0xffffffff`, PCIe port0 ID5 link bit remained 0,
  and no NAND block device appeared.
- All experiments returned the port0 power domain OFF; native WLAN
  and USB SSH stayed operational. Battery was approximately 58–59%.

These findings are grounded in actual Linux MMIO, combined with the
owner's original Apple N71 **iOS 15.8.8** Mach-O kernelcache and original
N71 Apple Device Tree. The live phone runs iOS 15.7.9 when not in
Linux; do not conflate the two iOS build versions.

Stock S8000 `Fact` callback selectors have since been resolved
against the original Apple `AAPL,phandle` registry: storage DART0
is device `0x80`, its mapper `0x81`, and NVMMU0 device `0x82`;
WLAN DART1 is device `0x83`, mapper `0x84`. The live Linux FDT
currently lacks dedicated DART0/NVMMU0 platform devices. This
verifies the **target identity** of the callback, not an MMIO or
power-on implementation.

The stock Apple initialization sequence additionally requests
`function-dart_force_active` and
`function-nvme_mmu_force_active` (separate encoded callback
identifiers in the genuine ADT). Their electrical and DMA behavior
is not yet validated, so these calls are **not** replayed. The actual
S8000 code was also traced through the original port-local and root
controller vtables; merely duplicating the S8003 PHY bring-up would
be unjustified.

All modules are narrowly targeted to N71/S8000. They must not be
loaded on other Apple hardware; do not use them without physical
recovery access and an existing recoverable backup. They have no
permanent install process and do not modify flash. Any module's
presence in this folder does not imply storage-device support.

## Combined physically asserted S3E PERST + PCIe link0 (verified)

The `n71_s3e_p0_asserted_reset_rootstart.c` module was compiled
for the live N71 ARM64 kernel, SHA-256 verified and executed once on
the real iPhone 6s/S8000. It kept NAND GPIO160 **OUTPUT LOW** while
the genuine `pcie_link0` PMGR domain was powered for 25 ms and
stock S8000 NVMe mode / port0 ID3 and ID2 bits were temporarily
enabled. All requested writes acknowledged; all root registers,
power domain and GPIO160 returned to their original exact values
before the module was unloaded. GPIO160 was not retained in
quarantine, and the native Wi-Fi/USB remained available.

**Unresolved:** DART0, NVMMU0 and port0 MMIO still read
`0xffffffff`. Root port0 link was down, and no NAND block device
was enumerated. Do not misrepresent this as functional NAND.

[Full original-hardware test details](../../docs/N71_S8000_STORAGE_ASSERTED_PERST_COMBINED_ROOTSTART_2026_11_17.md).

## Original root vslot2040 port-local register: hardware comparison

One physically executed, read-only N71/S8000 ARM64 probe measured
`root+0x4020` (storage) and `root+0x4060` (live WLAN) plus corresponding
ports2/3: **all four read `0x00000000`**. The WLAN link status was 1
(up), port0 0 (down), so this port-scoped register value is **not**
a direct indication of link training. Original Apple source calls
root vslot2040 to **write 3** to these offsets; we did **not**
replay that command, as its electrical behavior and side effects
are not qualified. See the
[physical and original-code analysis](../../docs/N71_S8000_ORIGINAL_ROOT_PORT_SCOPED_4020_LIVE_READ_2026_11_17.md).

## Next engineering milestone

1. Derive port0-specific PHY/REFCLK/PERST sequencing from the stock
   Apple PCIe controller and S3E NVMe initialization code.
2. Qualify DART0 and the S8000 `nvme-mmu0` DMA isolation, with
   bounded fault paths and no request allowed outside approved buffers.
3. Train PCIe port0 with deterministic rollback and identify
   the physical `106b:2002` endpoint via **read-only PCI config access**.
4. Build an S8000-compatible Apple NVMe controller transport and
   enumerate *existing* namespaces read-only; only after the
   full read-only block path and independent backups are qualified
   may any writable Linux volume be considered.

The generic NVMe PCI table in the tested Linux kernel recognizes
Apple `106b:2001/2003/2005`, **not** `106b:2002`. Binding generic
NVMe blindly is unsafe without verified NVMMU/PCIe initialization.
The upstream `nvme-apple` platform driver is for newer ANS2
controllers, not proof of A9 S3E compatibility.
