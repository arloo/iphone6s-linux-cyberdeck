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

All modules are narrowly targeted to N71/S8000. They must not be
loaded on other Apple hardware; do not use them without physical
recovery access and an existing recoverable backup. They have no
permanent install process and do not modify flash. Any module's
presence in this folder does not imply storage-device support.

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
