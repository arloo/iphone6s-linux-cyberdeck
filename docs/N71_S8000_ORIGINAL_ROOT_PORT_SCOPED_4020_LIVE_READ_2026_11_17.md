# N71 S8000 original PCIe root per-port command-register reconnaissance

**Date:** 2026-11-17. Owner-authorized, physically running iPhone 6s
N71/Samsung S8000, Linux RAM 7.3.0-rc1. Existing native Wi-Fi port1,
USB authenticated SSH, and no Linux NAND block device.

## Original source provenance

The owner-private Apple N71 ARM64 kernelcache's original `AppleS800xPCIe`
port constructor/vtable fan-out has already been verified via
`tools/n71_s8000_original_port1_local_fanout_gate.py`.
Root-controller vtable slot **2040** implements a per-port 32-bit
**write of constant 3** to relative register `0x4020 + (port << 6)`.
The corresponding original Apple common-root resource is physical
`0x600000000`, size `0x8000`. Port0 is `+0x4020`; port1 is
`+0x4060`. This source proves the **write instruction**, not whether
the register is latched, self-clearing, write-only, FIFO, or electrically
safe to replay. No physical write to those offsets was authorized.

## New independent real-world read-only control comparison

The ARM64 Linux module
`experimental/port0/n71_s3e_root_local_4020_ro.c`
was compiled for the exact booted kernel, transferred over the
authenticated direct USB connection, SHA-256 verified, run in
default-inert mode and then armed **once**. It independently checked
N71/S8000 identity, the still-blocked PCIe research node, active
native BCM4350C5 on port1, and the PMGR state: common PCIe, auxiliary,
reference and WLAN link1 ON; storage link0 and links2/3 OFF.

It mapped only the original shared root window for **readl** calls:

| Register / port | Real read-only value |
|---|---|
| `root+0x4020` (NAND port0) | `0x00000000` |
| `root+0x4060` (WLAN port1) | `0x00000000` |
| `root+0x40a0` (baseband port2) | `0x00000000` |
| `root+0x40e0` (port3) | `0x00000000` |
| Port0 root-link status ID5 | `0x00000000` |
| Port1 root-link status ID5 | `0x00000001` |
| Shared PCIe root status | `0x00000011` |

The *operating WLAN port1 also reads zero at the source-proven
write-3 register*. This **rules out treating the observed value as a
simple 'link up' indicator**. It does not prove the register's electrical
meaning or establish that an S8000 storage port0 write of 3 is safe.

The module was successfully unloaded. Link0 remained OFF, WLAN carrier
remained up, NAND block-device list remained empty. The iPhone battery
was about 50% and its charging state fluctuated; no new power lease was
requested during this module's run.

## PMGR naming ambiguity resolved offline

The genuine N71/S8000 Apple ADT PMGR records identify `PCIE` as
device ID `0x1e`, `PCIE_AUX` as `0x39`, `PCIE_REF` as `0x3a`,
and `PCIE_LINK0..3` as `0x3b..0x3e`. They do **not** contain a
separate PMGR record named `PCIE_APP`. This does *not* establish
that every relevant S8000 PCIe peripheral/register clock is enabled
by those domains or that additional analog PHY clocks are absent.

## Next actionable reverse-engineering gates

- Trace stock port-instance vslot1864 -> root vslot2040 call **relative
  to original clock, PHY and PERST operations**. Establish whether the
  write of 3 is a one-shot reset/pulse or an actual persistent setting.
- Resolve stock DART0/NVMMU0 `Fact` force-active callback targets to
  real device init and clock-domain operations. Distinguish controller
  register accessibility from the link's endpoint training process.
- Validate storage DMA quarantine before any PERST-high transition.
  Do not bind generic NVMe to `106b:2002`, write to flash, or assume
  later S8003 initialization ordering applies to Samsung S8000.

The full encrypted private iOS backup, unmodified Apple binaries, device
identifiers, pairing keys and private execution logs never enter Git.
