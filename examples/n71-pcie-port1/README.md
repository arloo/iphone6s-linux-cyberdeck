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
