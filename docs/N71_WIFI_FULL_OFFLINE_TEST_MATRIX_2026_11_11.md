# iPhone 6s N71/S8000 — Comprehensive offline BCM4350 Wi-Fi test campaign

**Date:** 2026-11-11. **Scope:** authorized Dell host, no physical iPhone connection. No NAND writes, DFU, on-device module insertion, power reset, PCIe MMIO or DMA.

## Result matrix

| Test / evidence | Verified result | Hardware limitation |
|---|---|---|
| Original iOS ARM64 root PCIe routines | PASS: root constructors, start and selectors 0/9/10 | Actual AppleARMIODevice provider memory order and register semantics unknown |
| Original N71 ADT | PASS: four PCIe ports, 11 PCIe windows, three separate DARTs; onboard BCM4350 under port 1, uniquely referenced DART1 mapper | Physical DART1 SID, IOVA translation, DMA fault isolation unknown |
| Kernel configuration | PASS: all 1,323 previously enabled flags preserved, including Z2 touch, simpledrm LCD, USB NCM, Apple DART | New kernel image has not been linked or booted |
| Original Apple C2/C5 firmware | PASS: 34/34 source/staged files byte-identical by SHA-256; two families isolated with private permissions | Actual silicon rev, board NVRAM/SysCfg and runtime firmware format unverified |
| Broadcom and GPIO source build | PASS: AArch64 objects cfg80211, brcmutil, brcmfmac, gpio_apple_pmic | Physical BCM4350 PCIe endpoint has not enumerated |
| Linked private ARM64 kernel modules | PASS: brcmutil.ko and gpio_apple_pmic.ko, correct original 7.3.0-rc1 vermagic | Not loaded; matching vermagic is not ABI/runtime proof |
| Module link dependency graph | CONTROLLED BLOCKER: only cfg80211 lacks verify_pkcs7_signature from the known-good core | A coherent alternate kernel with SYSTEM_DATA_VERIFICATION is required |
| Strict on-device WLAN acceptance | PASS on synthetic fixtures: requires actual PCI function Broadcom 14e4:43a3, brcmfmac driver, wireless PHY, intended SSID, WLAN routes and ICMP | Real WLAN cannot be accepted without a connected, booted iPhone |
| Public regression suite | **478 / 478 PASS** | Offline unit tests are not hardware trials |

## The exact remaining kernel-link problem

The candidate radio kernel enables CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y and CONFIG_SYSTEM_DATA_VERIFICATION=y, but the original working LCD/touch/USB kernel does not export verify_pkcs7_signature. Source inspection confirms this function is conditionally exported from certs/system_keyring.c only with CONFIG_SYSTEM_DATA_VERIFICATION. An actual modpost against the old kernel correctly rejected cfg80211. No unresolved symbol was masked or fabricated. The verified independent ELF symbol graph showed:

- cfg80211: 186 imports resolved, **one unresolved: verify_pkcs7_signature**.
- brcmutil: 12 imports resolved, none missing.
- brcmfmac: 204 imports resolved from the old core and new module exports, none missing.
- gpio_apple_pmic: 11 imports resolved, none missing.

Two independent modules were actually linked offline: brcmutil.ko and gpio_apple_pmic.ko; both are ELF64 AArch64 with vermagic 7.3.0-rc1-g68aadac820d0-dirty SMP preempt aarch64. The signed regulatory path should remain enabled in the future coherent kernel image. No module was inserted into the existing phone boot (CONFIG_MODULE_UNLOAD=n).

## Reproducible public checks

- scripts/n71_wifi_offline_selftest.sh — one read-only local command orchestrating original ARM64 kernelcache/ADT root checks, provider-order uncertainty, known-good kernel config preservation, original Apple C2/C5 integrity, ARM64 symbol graph and two linked .ko vermagic checks.
- tools/n71_bcm4350_firmware_integrity_gate.py — verify all 34 original private firmware/profile files against Linux staging, reject swaps, mismatched revision trees, extra files, weak permissions or symlinks. Does not select revision or assert TRX is directly compatible with Linux.
- tools/n71_wifi_kernel_symbol_gate.py — fail-closed AArch64 ELF undefined/export symbol comparison against the private original vmlinux Module.symvers and the new modules' actual __export_symbol_ metadata.
- scripts/n71_onboard_bcm4350_identity.sh — read-only PCIe sysfs identity verification. scripts/n71_native_wifi_acceptance.sh now requires real PCIe Broadcom 14e4:43a3 on brcmfmac, rejecting an external USB Wi-Fi dongle even if named wlan0.

**54 new synthetic tests** complement the previous 424 tests: 16 onboard PCIe identity cases, 15 firmware integrity/mixing checks, 14 kernel symbol-graph cases, and 9 integrated selftest failures and safety assertions. All **478/478 PASS**. The integrated selftest passed using only original local private inputs and printed blockers explicitly. No user-specific device data, Apple firmware, kernelcache, calibration, or IORegistry content is published.

### Run the offline preflight (all inputs remain private)

```bash
scripts/n71_wifi_offline_selftest.sh \
  /private/kernelcache.macho \
  /private/n71-adt.bin \
  /private/known-good.config \
  /private/wifi-candidate.config \
  /private/known-good/Module.symvers \
  /private/arm64-wifi-build \
  /private/original-apple-wifi \
  /private/staged-apple-wifi
```

## Unresolved gates, in priority order

1. **Kernel coherence:** build and validate a separate RAM-only kernel with signed regulatory-data verification plus matching cfg80211, brcmutil and brcmfmac, keeping the known-good LCD/touch/USB image intact.
2. **PCIe S8000:** independently verify the physical IODeviceMemory order, controller register semantics and safe port1-specific clocks, PHY/refclock, PERST#, link training, IRQ/MSI without disrupting storage port0 or baseband port2.
3. **DART1:** verify real stream ID, page tables, IOVA range, DMA fault/translation isolation before enabling bus mastering. The original ADT's logical mapper linkage alone is insufficient.
4. **Physical phone step:** USB gadget 05ac:4142 has not re-enumerated since 2026-11-11 19:13:45 CET. Physical cable/power access is required before a supervised RAM-only boot or radio test; no blind restart.
5. **Real native Wi-Fi:** enumerate onboard BCM4350, select the correct original private C2/C5 firmware and board calibration, associate to the Dell's authorized access point, and pass authenticated WLAN-only LAN connectivity. USB networking never counts.

**Current outcome:** major offline software preparation passes, but native BCM4350 Wi-Fi and S8000 PCIe/DART1 hardware bring-up remain unproven. This document makes no physical radio-success claim.
