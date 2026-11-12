# S8000/N71 PCIe port-1: fail-closed offline FDT gate

**This is a NONBOOTABLE safety scaffold, not a working Wi-Fi driver.**

The hardware's sanitized Apple ADT maps PCIe port 1 to Broadcom BCM4350 WLAN and DART apcie1. Port 0 is storage, port 2 is baseband and port 3 is not independently qualified. All four ports and the DART remain disabled in the fixture. There are NO real MMIO, power, clock, interrupt, reset, MSI or DMA resources.

Build and validate locally with dtc and Python 3:

    make -C examples/n71-pcie-port1 check
    python3 -m unittest discover -s tests -p 'test_n71_pcie_fdt_gate.py' -v

The standalone tool tools/n71_pcie_fdt_gate.py parses the compiled binary FDT, checks board/foundry identity, exact port indices, explicit disabled statuses, absent hardware resources, DART isolation, malformed FDT headers and unexpected nodes. This is stronger than matching source text. It cannot access an iPhone or write registers.

Successful output MUST include HARDWARE_PROBE_BLOCKED. A pass authorizes NO boot or device interaction. Source and design evidence: docs/N71_PCIE_ADT_MAPPING.md and docs/N71_BCM4350_PCIE_S8000_DRIVER_GAP_2026_11_11.md.

Next engineer a separately verified S8000-specific PCIe/DART register profile, ensure global setup cannot touch storage/modem ports, and establish safe DMA translation. Only then test a port-1-only link in a new supervised RAM boot. Finally enable cfg80211/brcmfmac with board-matched private firmware and secure SSH before attaching Wi-Fi.

No firmware, NVRAM, calibration, device ID, user photo or private image ships here.

## Offline finite-polling safety model

`port1_bounded_poll_model.c` is a deliberately standalone C policy model for the original A9/S800x port-1 inherited method's nonzero-status query loop. It accepts only logical port index 1, enforces a finite number of attempts, and distinguishes nonzero reply, invalid parameters, callback failure and exhausted retries. It does not identify the original virtual method's physical meaning or perform real link training, register accesses or DMA.

The bound (4096 attempts) is a **synthetic test maximum**, not a validated radio timing parameter. Any later kernel implementation needs reviewed time-based cancellation, safe hardware power state, IOMMU SID/IOVA isolation and explicit opt-in, rather than copying this model into a live driver.

Run the tests without phone hardware:

```bash
python3 -m unittest discover -s tests -p 'test_n71_port1_bounded_poll_model.py' -v
```

See [original N71 port-method sequence evidence](../../docs/N71_S8000_ORIGINAL_PORT1_INHERITED_SEQUENCE_2026_11_11.md).

## Standalone RMW policy emulator (no hardware access)

`port1_rmw_policy_model.c` models the four verified Apple A9/S800x port1 register-bit transitions on **synthetic integer inputs only**. It rejects all other ports, unknown operations and global/shared register writes; the status/shared-register meaning is NOT assumed. It has NO MMIO or PCIe driver registration functions.

The model was actually executed through 65,536 synthetic random-vector bit-preservation tests and built as a genuine AArch64 relocatable object. Tests are in `tests/test_n71_port1_rmw_policy_model.py`. Background: [original private-code RMW static audit](../../docs/N71_S8000_PORT1_RMW_GLOBAL_STATUS_2026_11_11.md).

## Original Apple shared ID1 bit4: real-device memory anchor (2026-11-12)

The [three-source iOS + ADT + original Apple ARM64 proof](../../docs/N71_S8000_ORIGINAL_LIVE_SHARED_STATUS_PHYSICAL_GATE_2026_11_12.md) establishes that the original PCIe ROOT's shared ID1 status polling targets physical address `0x60000002C` (COMMON provider index 9, offset `0x2C`) on N71/S8000, as reconstructed from privately held original kernelcache and authentic live stock iOS 15.7.9 memory-provider order.

`port1_shared_status_snapshot_model.c` is a **data-only, nonbootable C model**. It accepts an immutable array of synthetic 32-bit statuses, checks original bit4 rather than any nonzero value, and fails closed outside the exact port/index/window or a maximum of 4096 samples. The model never maps, probes or writes hardware and never authorizes PCIe initialization.

The [25 private-provenance mutation tests](../../tests/test_n71_port1_live_shared_status_provenance_gate.py) and [21 executed-C synthetic tests](../../tests/test_n71_port1_shared_status_snapshot_model.py) establish the offline code policy. The real C source also compiles as an AArch64 ELF64 object. **Its success means only bit4 present in a synthetic snapshot, NOT PCIe link-ready, DART safety or native WLAN association.**

## Native ARM64 C replay of original 83 Apple PCIe tuning records (2026-11-12)

The [full original-device evidence and C simulation report](../../docs/N71_S8000_PCIE_PORT1_AUTHENTIC_TUNABLE_C_REPLAY_2026_11_12.md) describes the new `port1_original_tunable_replay_model.c`, a strictly hardware-inert implementation of the original `(old & ~mask) | (value & mask)` formula for N71/S8000 PCIe/PHY tuning data. It validates four original record-group cardinalities **34+41+6+2=83**, 24-byte data-record structure, four-byte masked writes, bounds, alignment, unique offsets and shared status-register protection. All reads/writes happen to deterministic **synthetic values only**; there is no physical register pointer, MMIO, GPIO, DMA, system call or clock action.

To execute the compiled real C test suite from this directory: `make replay-check`. It includes 25 safety and mutation cases and **50,000** synthetic seed vectors. The exact private original-device 83 records were separately replayed with **five** synthetic register-state seeds (415 original data-record evaluations), without exposing the Apple tuning values or permitting physical operations. Real ARM64 compilation succeeded separately; **no on-phone test, WLAN initialization or PCIe link-up was claimed**.

## Real Linux ARM64 port1/DART1 metadata-only kernel preflight (2026-11-12)

See the [full Linux kernel preflight build and safety report](../../docs/N71_S8000_LINUX_PCIE_PORT1_METADATA_PREFLIGHT_ARM64_2026_11_12.md). The source `pcie-apple-s8000-port1-preflight.c` is an exact public mirror of the owner's separate Hoolock-derived Linux kernel `pcie-apple-s8000-guard.c`; it has been compiled in that actual private Linux ARM64 build as an ELF64/AArch64 relocatable object. It validates exactly **three named original source-proven PCIe port1/DART1 resource descriptors** using `platform_get_resource_byname()` and OF source metadata. All clock, reset, physical register access, IOMMU, DMA, IRQ and PCI host functionality is absent. Even a fully matched device always returns **`-EOPNOTSUPP`**, so it is not usable as an operational host driver.

The separate `port1-preflight-disabled.dts` is a deliberately **nonbootable standalone** metadata test with `status="disabled"`, and `make preflight-check` compiles it and runs the strict [fail-closed FDT verifier](../../tools/n71_s8000_port1_preflight_fdt_gate.py) plus synthetic tests. **Never merge this fixture into the known-good iPhone boot DTB, set it to `okay`, or claim Linux Wi-Fi is enabled.**

## Original Apple N71 REFCLK/PERST units verified from genuine XNU (2026-11-12)

See the [original ARM64, XNU symbol-binding and actual iOS read-only provenance report](../../docs/N71_S8000_ORIGINAL_REFCLK_PERST_IODelay_MICROSECONDS_2026_11_12.md). The board-specific Apple `t-refclk-to-perst=100` is now proven to feed the original `_IODelay` kernel function as **100 microseconds**, not 100 milliseconds. The separate shared-root status bit4 polling loop uses `IODelay(10)`, i.e. **10 microseconds** per unsuccessful attempt, but requires an independently designed **finite timeout** before Linux hardware use.

The disabled research Device Tree and exact-matching real ARM64 Linux kernel preflight now use the unit-bearing, synthetic `research,refclk-to-perst-delay-us = <100>;` property. The guard remains **hardware-inert**, its probe always returns `-EOPNOTSUPP`, and this fixture remains **nonbootable**. Original XNU/kernelcache bytes, board calibration and live IORegistry captures remain private.
