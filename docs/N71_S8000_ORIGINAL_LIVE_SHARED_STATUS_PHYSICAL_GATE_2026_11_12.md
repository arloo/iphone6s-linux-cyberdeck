# N71/S8000: original shared status bit anchored to live iOS physical provider

**2026-11-12 | N71 Samsung A9/S8000, onboard BCM4350 WLAN | OFFLINE/ORIGINAL/LIVE-IOREGISTRY provenance PASS, hardware initialization NOT authorized.**

## Concrete result

Three independently acquired inputs were combined **read-only** on the authorized Dell workstation:

1. Owner-held original iOS **15.8.8** N71/S8000 ARM64 Mach-O kernelcache: validated S8000 root vtable inheritance, original register-ID selector and original S800x controller slot1984's shared ID1 **bit4** status-poll loop.
2. Independently retained original N71 Apple Device Tree (ADT): proved four-port `apcie,s8000` layout, original ordered address ranges and WLAN port1-to-DART1 association.
3. An authentic live `idevicediagnostics ioregentry apcie` result captured from the paired N71 phone booted in stock iOS **15.7.9**: all **11** `IODeviceMemory` ranges match the original ADT `reg` tuples at the exact same indices.

The original root method selects COMMON provider **index 9**, which on the live original device has base `0x600000000` and size `0x8000`. Original code selects relative offset `0x2C`, so its **derived absolute physical status-register address is `0x60000002C`**. The original method tests **bit 4**, repeating its read until that bit is set, with **no explicit caller-side retry bound** in the inspected code path.

These are static code and genuine original-iOS provider-address facts. **No actual register contents were read under Linux, and no bit semantics have been electrically verified.** The original-code source and live provider capture are from different iOS releases, although pinned to the same S8000 SoC family; this is cross-version corroboration, not a claim of binary-identical software.

**Do not label bit4 as PCIe link-up, power-good, refclock-ready, reset released, or DMA-ready. None of those physical meanings is proven.** The source of a shared register may affect storage port0 and baseband port2. Even a seemingly read-only MMIO probe awaits independent safe-side-effects analysis.

## New public implementation and reproducibility

- `tools/n71_port1_live_shared_status_provenance_gate.py`: independently validates original ARM64 control-flow provenance, live original iOS provider ordering and the portable C policy against **three private local inputs**; prints only well-known SoC ranges/bit positions and explicit blockers.
- `examples/n71-pcie-port1/port1_shared_status_snapshot_model.c`: an executable **hardware-inert** C data-only model that accepts a bounded list of synthetic 32-bit snapshots. It permits only port1, original index9, base `0x600000000`, length `0x8000` and offset `0x2C`. It checks **bit4**, not merely a nonzero value, and stops after at most 4096 in-memory samples. It exposes **no MMIO function**, and its `n71_port1_shared_snapshot_authorizes_hardware()` always returns zero.
- `tests/test_n71_port1_live_shared_status_provenance_gate.py`: **25** synthetic failure-path, provenance, mutation and privacy checks; no private original data.
- `tests/test_n71_port1_shared_status_snapshot_model.py`: **21** tests execute compiled actual C including 50,000 deterministic 32-bit status masks, all 32 individual bits, port/index/window failures, maximal bounded sampling and hardware-denial checks.

The real C source compiled both as a host shared object for executable unit testing and a strict **AArch64 ELF64 relocatable object** using `aarch64-linux-gnu-gcc -std=c11 -Wall -Wextra -Werror`; it was **not linked into a bootable Linux image** or loaded onto the phone.

Private-only reproduction:

```bash
python3 tools/n71_port1_live_shared_status_provenance_gate.py \
  /private/original-n71-kernelcache.macho \
  /private/original-n71-apple-adt.bin \
  /private/original-ios15-ioregentry-apcie.plist

python3 -m unittest discover -s tests \
  -p test_n71_port1_live_shared_status_provenance_gate.py -v
python3 -m unittest discover -s tests \
  -p test_n71_port1_shared_status_snapshot_model.py -v
```

Expected original-data result:

```text
N71_PORT1_ORIGINAL_CODE_AND_LIVE_IOS_PROVIDER_PASS
DERIVED_PHYSICAL_SHARED_STATUS_REGISTER 0x60000002c
HARDWARE_INIT_AND_PCIE_LINK_PROVEN=NO
LINUX_ONBOARD_BCM4350_WIFI_WORKING=NO
```

All original iOS IORegistry plist blobs, original Mach-O code, Apple ADT, firmware, OTP and per-device calibration remain outside the public Git repository, in the private Dell research tree. The public tool prints no original input paths, bytes, device identifiers, passwords, keys, BSSID or MAC addresses.

## Non-negotiable next gates

1. Establish the **meaning and cross-port effects** of the root global register at `0x60000002C`, and exact port1 refclock/PHY/PERST#/MSI/link initialization order; verify safe timeouts and rollback.
2. Establish real **DART1 stream ID, IOVA aperture, TTBR and fault isolation**. The existing Linux DART reset affects every stream of the probed instance, and the experimental four-lane TCR RMW fix alone does not remove that risk.
3. Preserve the known-good iPhone 6s RAM-only Linux touch/LCD/USB fallback and Apple NAND. No irreversible operations or unreviewed shared register writes.
4. Later, supervise native port1-only BCM4350 enumeration, board-matched privately retained C5 firmware and genuine iPhone-to-authorized-Dell-WLAN association. USB routing is not a Wi-Fi acceptance result.

**This milestone makes a previously conditional physical register offset verifiable against the real phone. It does NOT yet provide a working S8000 PCIe or Wi-Fi driver.**
