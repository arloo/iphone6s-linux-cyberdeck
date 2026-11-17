# N71/S8000 S3E: physical DART0 isolation and original callback chain

**17 November 2026.** Directly tested on owner's iPhone 6s Samsung S8000
running the known-good Linux 7.3.0-rc1 RAM boot. Read-only tests. No
storage write, NAND operation, DFU, new boot or filesystem mount.

## New physical evidence

ARM64 diagnostic `experimental/port0/n71_s3e_dart_compare_ro.c`
ran on the real phone, with its inert load/unload checked first.
It requires genuine N71/S8000 firmware-compatible hardware, a deliberately
blocked PCIe research node and an already enumerated native BCM4350C5.
It performs **only MMIO reads**, with PCIe port 0 untouched and OFF.

| Physical window | Observed values | Result |
| --- | --- | --- |
| WLAN DART1 `0x602008000` | command `0x00000102`, packed TCR `0x00000080`, fault register `0x00000500` | Reachable |
| Storage DART0 `0x601008000` | command/TCR/fault all `0xffffffff` | Unreachable |
| Storage NVMMU0 `0x601004000` | control/init both `0xffffffff` | Unreachable |
| Storage port0 `0x601000000` | FIFO status `0xffffffff` | Unreachable |

This confirms the CPU/MMIO path can reach live Apple DART1 while storage
regions do not decode in the tested state. Previous controlled probes
powered port0, activated the **stock S8000** NVMe mode bit and the
port0-only root ID3/ID2 control bits, then restored every register.
Those probes also returned `0xffffffff` for storage windows. Their
hardware rollback was verified. These tests have **not** enumerated
`106b:2002` and do not prove the storage NAND is usable.

## Original stock Apple callback chain

The genuine owner-supplied N71/S8000 iOS 15.8.8 ARM64 kernelcache and
original Apple ADT independently validate:

- `function-dart_force_active`: 8-byte descriptor; selector `0x80`,
  tag `0x46616374`.
- `function-nvme_mmu_force_active`: distinct selector `0x82`,
  same 4-byte tag.
- `AppleEmbeddedPCIE` resolves/stores its DART callback object
  at a version-pinned object offset `+304`.
- `AppleS800xPCIe` resolves/stores the NVMMU callback object at
  port-object offset `+2912`.
- The original inherited A9 startup/control functions dispatch the
  DART callback then NVMMU callback with a shared 32-bit state word
  initialized to `0` in one code path and `1` in another. The
  underlying electrical meaning of these states is **not established**.
- Original PMGR ADT contains 103 well-formed 48-byte device records.
  Ordinary PMGR ID `0x80` identifies **VENC_ME0**, not storage; ID
  `0x82` is absent. **Never** interpret either callback selector
  as a PMGR device ID or blindly write a PMGR register.

The new source gate
`tools/n71_s8000_storage_force_active_chain_gate.py` independently
pins the original ARM64 callback instructions, vtable provenance,
both descriptor payloads and PMGR device identities. It has 14
synthetic regression tests. Authentic-private source verification:
`N71_STOCK_S8000_STORAGE_CALLBACK_SOURCE_GATE=PASS`.
Full project suite: **1,630 tests PASS**.

## Hardware qualification still needed

The callback's actual implementation and register-level power/clock
effects remain unresolved. The next safe engineering step is to
independently reverse these functions and their PMGR/controller dependencies
before staging an **explicitly gated, reversible** S8000 port0 activation.
Do not copy S8003 PHY, NVMMU, link training or DART assumptions.
Do not release storage reset, enable DMA or interact with the internal
flash until isolation and read-only enumeration are established.

Authentic Apple firmware/ADT, device identifiers, board calibration, SSH
keys, credentials and user content stay on the Dell. The publicly
committed files are original project source and sanitized observations only.
