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
