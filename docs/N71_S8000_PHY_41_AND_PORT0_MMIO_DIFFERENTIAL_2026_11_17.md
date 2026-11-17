# N71/S8000 storage: full PHY inventory and port0-versus-WLAN local MMIO differential

**17 November 2026 — original Samsung S8000 iPhone 6s running Linux 7.3.0-rc1 RAM-only.**

## Key finding

The shared Apple S8000 PCIe PHY is **reachable and already
consistent with all 41 original masked PHY tunable records**. In
contrast, **neither of the two port0 PCIe local controller windows**
becomes readable under the verified 25-ms `pcie_link0` power lease
and physically asserted NAND reset. Identical reads from both WLAN
port1 local windows succeed.

| Real Linux hardware, direct physical MMIO | Valid readings | Interpretation |
| --- | ---: | --- |
| Shared PHY at `0x600008000` | **41 / 41** | Responsive |
| Original Apple masked PHY values | **41 / 41** | Matching masked tuning bits |
| Port0 bank0 `0x601000000` | **0 / 8** | All `0xffffffff` while port0 powered |
| Port0 bank1 `0x601004000` | **0 / 8** | All `0xffffffff` while port0 powered |
| WLAN port1 bank0 `0x602000000` | **8 / 8** | Responsive; its six config tunables match Apple's masks |
| WLAN port1 bank1 `0x602004000` | **8 / 8** | Responsive; per-bank role still to be qualified |
| Storage DART0 `0x601008000` | Unreachable | Reads still `0xffffffff` |
| Storage NVMMU0 `0x601004000` | Unreachable | Reads still `0xffffffff` |

Important: `0x601004000` appears as an original PCIe port0
resource and as an original NVMMU0 register resource. These are
distinct **software interpretations of overlapping physical
resources**, not evidence that both components are initialized.

All data were acquired via authenticated USB SSH and
owner-verified AArch64 modules. No memory was reflashed or
mounted, no NVMe command was issued and no storage reset was
deasserted.

## Original Apple source verification

The original N71 Apple Device Tree independently defines:

- PCIe common root resource index9: `0x600000000`, 32 KiB.
- PCIe shared PHY resource index10: `0x600008000`, 16 KiB.
- Four pairs of 16-KiB per-port MMIO resources, beginning at
  `0x601000000` for port0 and `0x602000000` for port1.
- 34 original shared-root masked tuning records, 41 PHY tuning
  records, and **six config + two root tuning records for each
  of ports 0, 1 and 2**.
- The two per-port tuning blobs are **byte-for-byte identical**
  across those three ports, but their target hardware windows
  are separate.
- One `PCIE` power-gate entry and six named PCIe gate entries
  (`PCIE_AUX`, `PCIE_REF`, `PCIE_LINK0..3`).
- A separately named `PCIE_APP` entry in Apple PMGR's clock
  metadata. Its electrical meaning and Linux enable sequence
  are **not yet identified**.

The rigorous original-source checker
`tools/n71_s8000_stock_phy_local_clock_gate.py` validates the
11 physical resource mappings, tunable format and counts, seven
sampled offsets, all three identical per-port tuning banks,
PMGR hierarchy, the separate `PCIE_APP` label, and refusal
of unrecognized data. It prints only summary counts and booleans,
never original masks or register programming values.

## Physical trials and rollback

**Shared PHY-only module**
`experimental/port0/n71_s3e_phy_stock_ro.c` validated the actual
N71/S8000 board, active WLAN PCIe endpoint, original root power
state, and stable root-link indicators. It read all 41 stock PHY
offsets without any MMIO writes or port0 power activation.
A private Dell-side comparison against the authentic Apple
mask/value records found **41/41 conformance**.

**Bounded port0-versus-port1 comparison**
`experimental/port0/n71_s3e_p0_local_window_compare.c`
uses the proven earlier rollback sequence. With NAND GPIO160
held **OUTPUT LOW**, it temporarily enabled original S8000
root mode, port0 root ID3/ID2 and `pcie_link0` for 25 ms.
It then read eight original per-port tuning offsets from both
physical banks for port0 and port1, as well as storage
DART0/NVMMU0. All storage reads were invalid and all WLAN
reads were responsive. It restored the root control bits,
the original root NVMe mode, link0 PMGR state and GPIO160
exactly to `0x00072200`. The module was unloaded successfully;
Wi-Fi and authenticated USB continued working.

## Interpretation and next implementation steps

**Supported:** The controller has a usable, Apple-conforming
*shared PHY*, and the failure is localized to the **port0
local MMIO decode/activation path**. A general MMIO bus failure
or a wholly unavailable shared PHY does not fit the evidence.

**Not supported:** Concluding that a specific clock is disabled,
that `PCIE_APP` is missing electrically, that original
PHY tuning has definitely been executed in Linux, or that
the NAND endpoint or DART0 is broken. Per-port registers
can also be hidden while NAND PERST remains asserted or
CLKREQ stays inactive; these possibilities are unresolved.

The highest-value reverse-engineering work is now:
1. Trace actual S8000 `function-dart_force_active` and
   `function-nvme_mmu_force_active` effects, and the distinct
   port0 GPIO164 CLKREQ handling from original Apple ARM64.
2. Establish which original port0-local clock/reset gate
   controls the two inaccessible physical windows, without
   disturbing Wi-Fi or the baseband.
3. Implement S8000-specific DMA quarantine and then qualify
   any later reset release/PCIe link training **read-only**.
   Do not assume T8103/S8003 MMU semantics or bind generic
   NVMe before the correct platform protocol is verified.

## Publication privacy and validation

Only original project source, bounded source-contract tests
and **sanitized test conclusions** are published. Private
Apple firmware/ADT, masked tunable values, SSH material,
identifiers and the encrypted iOS backup stay on the Dell.

No internal flash block device was enumerated during this
test. The existing iOS backup is encrypted and verified,
but is **not** a bare-metal NAND image.
