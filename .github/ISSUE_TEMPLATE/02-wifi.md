---
name: "Hardware: iPhone 6s Wi-Fi bring-up"
about: "Enable WLAN bus and radio support for N71/S8000"
title: "[WIFI] Identify WLAN transport and bring up wireless on iPhone 6s"
labels: ["hardware", "wifi", "help wanted"]
assignees: []
---

## Observed baseline
- `CONFIG_WLAN` disabled in the tested kernel config.
- No `wlan0` / wireless network interface in Linux.
- No PCI devices enumerated during the current boot; transport not yet conclusively identified.
- Bluetooth HCI UART reports `BCM4350C5`; **do not infer the WLAN transport solely from that**.

## Research questions
- Which exact Wi-Fi radio, board module and bus are used by Samsung A9 iPhone 6s?
- Which host-controller clocks, power sequencing and Device Tree nodes are needed?
- Which kernel wireless stack and Broadcom driver/config combinations apply?
- How can board-specific firmware/NVRAM and private calibration be handled safely?

## Implementation steps
- [ ] Identify hardware and transport with credible source/evidence.
- [ ] Enable appropriate kernel networking configuration.
- [ ] Bind bus/host controller and discover radio.
- [ ] Load properly sourced firmware and private board calibration without publishing blobs.
- [ ] Demonstrate a scan with the interface correctly enumerated.
- [ ] Associate to a test network and validate sustained bidirectional IP.
- [ ] Measure stability and record power-state issues.

## Evidence requested
Exact model, kernel SHA, interface path, device tree patch, reviewed logs and a reproducible test. Never publish MACs, SysCfg, NVRAM or calibration.
