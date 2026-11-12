# N71/S8000 PCIe port1: original 83-record tunable replay in an isolated ARM64 C model

**2026-11-12 | Target: owner-verified iPhone 6s N71/S8000 Samsung A9, onboard PCIe BCM4350 WLAN.**

## Outcome and exact limitations

We now have a **native C, hardware-inert implementation** of the original AppleEmbeddedPCIE 24-byte data-record validation and verified 32-bit masked read/modify/write (RMW) software formula for all four original N71 PCIe/PHY tuning banks. The source compiles both with host GCC, executes under a full synthetic unit suite, and cross-compiles as **ELF64 AArch64 relocatable** with strict warnings.

The code is **not a PCIe host-controller driver**, not an MMIO accessor, not a loadable kernel module, not a Linux network driver, and not a boot image. The only mutable output is an in-memory summary of a **pseudo-register simulator**, calculated from deterministic synthetic seeds and offsets; no live register pointer/callback or hardware resource can be supplied. It explicitly never authorizes physical PCIe MMIO/DMA.

## Grounded original-device data

The separately published [original Apple kernel/Device Tree/live iOS provenance](N71_S8000_ORIGINAL_LIVE_PCIE_PORT1_TUNABLES_2026_11_12.md) verified original Apple ADT versus independently captured real stock iOS 15.7.9, and the original iOS 15.8.8 AppleEmbeddedPCIE ARM64 `_applyTunablesFromData` software implementation.

| Original private bank | Authentic records | Replay bank | Known status |
|---|---:|---:|---|
| S8000 controller common root | 34 | 0 | Shared/global — NO live write |
| Original S8000 PCIe PHY | 41 | 1 | Shared/physical semantics — NO live write |
| BCM4350 PCIe port1 config | 6 | 2 | Port-specific original data — no live write yet |
| BCM4350 PCIe port1 root-complex data | 2 | 3 | Port-specific original data — no live write yet |
| **Total** | **83** | | **OFFLINE only** |

An independent private-data-only summary confirmed that within each original bank **all record-relative offsets are unique**: no collisions, repeated offsets or overlapping-mask pairs on the same offset. This avoids same-bank ordering ambiguity, but cannot establish cross-bank, cross-port, power-on or electrical register safety.

For every original record the model checks original width4, alignment, bounded window size, 32-bit mask/value, `(value & ~mask)==0`, original group length, uniqueness and refusal to include shared common status offset `0x2C`. On any invalid record, processing fails closed before the simulation starts, with no partial-success result.

The model then computes only:

```text
synthetic_before = deterministic_fake_register(bank, offset, seed)
synthetic_after  = (synthetic_before & ~mask) | (value & mask)
```

It checks that all unmasked bits are preserved and masked bits match the expected value. These are **software invariants**, not electrical proof. Real hardware status, MMIO write side-effects, timing/clock domains, endian behavior outside the original code, DMA, TTBR, IOVA and IRQs remain outside the model's scope.

## Executed tests and authentic private replay

The public executable-C unit suite `tests/test_n71_port1_original_tunable_replay_model.py` executes **25 real C tests** with host GCC, including 50,000 deterministic synthetic seed vectors (not merely Python equivalent calculations), all 32 individual mask bit locations, invalid banks/counts/window accesses, non-32-bit and malformed records, duplicate offsets, protected shared-status offset, zero masks, early fail-closed rejection and a permanently denied hardware-authorization function.

The C source `examples/n71-pcie-port1/port1_original_tunable_replay_model.c` was independently compiled with `aarch64-linux-gnu-gcc -std=c11 -Wall -Wextra -Werror -O2 -c` and `readelf` confirmed `Machine: AArch64`, `Class: ELF64`, `Type: REL`.

On the authorized Dell, the **unpublished owner-private v2 manifest** containing all exact original 83 record values was loaded locally into the actual native compiled C model via `ctypes`, without displaying, copying or publishing any original values. The model passed **five different synthetic initial-state seeds** over each of the four authentic record groups:

```text
REAL_OWNER_PRIVATE_83_RECORD_C_TOTAL_EVALUATIONS 415
REAL_OWNER_PRIVATE_VALUES_EXPORTED=NO
PHYSICAL_PCIE_MMIO_AND_DART_DMA_PERMITTED=NO
```

These 415 genuine-source record operations are simulations only; there is no real PCIe device link or DART register access in this milestone.

## Why the current upstream PCIe driver is not immediately usable

The upstream Linux `pcie-apple.c` driver currently has matches for newer `apple,pcie` (T8103) and `apple,t6020-pcie`, **not** original S8000. See: [Linux upstream PCIe driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c) and [Hoolock project's own supported functionality caveat](https://github.com/HoolockLinux). It would be unsafe to add a fictitious `apple,pcie` compatible on S8000 or assume identical register semantics with Apple M1.

## Reproduce the public safety model

```bash
python3 -m unittest discover -s tests \
  -p test_n71_port1_original_tunable_replay_model.py -v

aarch64-linux-gnu-gcc -std=c11 -Wall -Wextra -Werror -O2 -c \
  examples/n71-pcie-port1/port1_original_tunable_replay_model.c \
  -o /tmp/n71-pcie-tunable-offline-aarch64.o

readelf -h /tmp/n71-pcie-tunable-offline-aarch64.o
```

The original-private replay requires the locally retained 0600 manifest from the previous checkpoint; private source/IORegistry/OTP/calibration data are not redistributed, copied into git or linked publicly.

## Concrete next engineering dependency

1. Independently establish the real S8000 **per-port PCIe PHY and clock/refclock/PERST#/MSI/link state sequence** with explicit impact control on port0 NAND/storage, port2 baseband and the shared root. The original status poll at common offset `0x2C` bit4 has not been physically interpreted.
2. Confirm DART1's actual request-to-SID hardware mapping, TTBR/IOVA/fault containment, port1-only initialization and safe rollback. The original Apple mapper index0 is statically connected to TCR byte lane0, but live PCIe DMA ownership remains unverified; the Linux S5L8960x DART code still resets all four streams.
3. Build a separate **non-destructive, RAM-only** on-device candidate while retaining the known-good touch/LCD/USB boot bundle unchanged and explicit user supervision. Then test actual native BCM4350 PCIe enumeration and private board-matched C5 firmware, and prove direct Wi-Fi association to the authorized Dell local network.

**Native S8000 Wi-Fi under Linux remains NOT WORKING as of this milestone.** The value of this checkpoint is eliminating the unknown original tuning-record application formula and creating an executable, tested C basis for the future driver without dangerous premature hardware writes.
