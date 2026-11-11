# N71/S8000: full alternate ARM64 Wi-Fi kernel and kernel-only RAM candidate

**Date:** 2026-11-11. **Target:** physically proven iPhone 6s N71/Samsung A9 Linux Z2 touch + simpledrm/USB reference, with a new isolated Linux `cfg80211`/Broadcom PCIe radio build. **Status:** full offline kernel and modules linked; private, experimental RAM boot candidate assembled and checked; **no on-device boot or native Wi-Fi**.

## Complete alternate kernel compilation — actual host result

Using the pinned original Linux source and a completely separate, private out-of-tree build on the Dell, `make Image modules` **completed successfully** (approximately 17 minutes on the low-power host). The alternate kernel retains all **1,323 previously enabled settings** of the known-good N71 Z2-touch/display/USB kernel, and adds `CONFIG_WIRELESS=y`, `CONFIG_WLAN=y`, `CONFIG_CFG80211=m`, `CONFIG_BRCMUTIL=m`, `CONFIG_BRCMFMAC=m`, `CONFIG_BRCMFMAC_PCIE=y` and signed regulatory DB verification.

All of the following files now exist privately, compiled and linked for **AArch64**, with `vermagic` `7.3.0-rc1-g68aadac820d0-dirty SMP preempt aarch64`:

| Actual output | Role | Verified |
|---|---|---|
| `arch/arm64/boot/Image` | Complete new ARM64 kernel | **PASS**, differs from known-good Image |
| `vmlinux` and `Module.symvers` | Linked kernel and genuine export map | **PASS**, `verify_pkcs7_signature` is present in new vmlinux |
| `net/wireless/cfg80211.ko` | Linux Wi-Fi control | **PASS**, actual linked module |
| `drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.ko` | Broadcom support | **PASS**, actual linked module |
| `drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.ko` | BCM4350-compatible FullMAC/PCIe transport | **PASS**, actual linked module, **not tested with hardware** |
| `drivers/gpio/gpio-apple-pmic.ko` | Existing Apple PMIC GPIO | **PASS**, linked but never loaded on the phone |

The private known-good ARM64 `Image` remains byte-for-byte unchanged; the alternate `Image` has a different SHA-256. The kernel candidate has signed-regulatory PKCS#7 support compiled into the **linked core**, resolving the previous `cfg80211` missing-symbol error without bypassing signature checks.

Public reproduction entrypoint: `scripts/build_n71_wifi_kernel_full_offline.sh`. It takes the pinned Linux source, the verified original `.config`, the trusted original Image and a **fresh private output** directory. It reuses `scripts/build_n71_wifi_objects_offline.sh`, compiles `Image modules` and validates actual ELF/vermagic/core PKCS#7 export with `tools/n71_wifi_alternate_kernel_gate.py`. The complete kernel compilation here was performed in an existing isolated out-of-tree build, using the same substantive Kbuild steps; **the fresh-directory wrapper has passed synthetic safety tests but was not redundantly run for a second full 17-minute compilation**.

## Private RAM-only candidate: only the kernel was changed

A separate private host-only candidate was assembled using the existing, previously hardware-proven Z2 auto-init RAM payload as the reference. First, the established public `scripts/pack_ram.py` rebuilt the original RAM payload **bit for bit** from the original private m1n1, per-device calibrated N71/S8000 DTB, untouched untested S8003 DTB, known-good compressed kernel, identical N71 touch-init initramfs and extracted original bootargs. Its reference digest matched exactly. Another, non-calibrated DTB did **not** reproduce the hardware-proven image and was excluded.

The new candidate was created privately by replacing **only `Image.gz`** with the new alternate compressed ARM64 kernel, preserving all other package components. `tools/n71_wifi_ram_candidate_diff_gate.py` then verified, by exact byte-level comparison of both complete payloads, that:

- m1n1 bytes are unchanged;
- original bootargs are unchanged;
- both calibrated N71/other-variant DTB bytes are unchanged;
- the private N71 touch auto-init initramfs is unchanged and has a valid gzip CRC;
- the **sole changed binary component** is the compressed alternate ARM64 kernel, which passes gzip CRC and differs from the known-good uncompressed kernel.

The private candidate is approximately **11.82 MB** and intentionally named `*-UNTESTED.bin`. Four matching `.ko` files are retained in an adjacent **private sidecar directory**, not inserted into the original initramfs and **not automatically loaded**. The original Apple BCM4350 C2/C5 firmware and per-device calibration remain in their earlier private staging areas and are **not included** in the new boot candidate.

The existing proven Z2 touch/USB rescue RAM image is retained independently and unchanged. A successful offline binary-diff check does **not** make the new candidate a device-tested or fully WLAN-capable boot image.

## S8000 PCIe port-1 research guard linked and compared to original ADT

The already present, deliberately inert `drivers/pci/controller/pcie-apple-s8000-guard.c` was independently compiled to a real AArch64 ELF relocatable object. The new [port-1/ADT consistency gate](N71_S8000_PORT1_GUARD_ORIGINAL_ADT_ARM64_2026_11_11.md) matched **three candidate WLAN+dedicated DART1 windows** and **six aggregate protected ranges** for storage port0, baseband port2, unknown port3, common controller and ECAM. Its live probe still returns `-EOPNOTSUPP`; the experimental controller guard remains disabled in the alternate kernel config.

Reference for later Apple PCIe controllers: https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c . That driver cannot be assumed to initialize S8000 merely by copying newer register values.

## New safety tests and reproducibility

- `tests/test_n71_s8000_port1_guard_consistency_gate.py`: 19 synthetic tests: unchanged port1 window geometry, protected regions, PCIe compatibles, no MMIO/DMA/link bring-up.
- `tests/test_n71_wifi_alternate_kernel_gate.py`: 16 synthetic tests: AArch64 `vmlinux`, different Image, core `verify_pkcs7_signature`, matching four module `vermagic` values, config preservation and no false boot claim.
- `tests/test_n71_wifi_full_offline_build.py`: 12 synthetic tests: isolated new-directory build, source/config/image preservation, no symlink reuse or hardware commands.
- `tests/test_n71_wifi_ram_candidate_diff_gate.py`: 14 synthetic byte-diff tests: unchanged M1N1, bootargs, two DTBs and private touch ramdisk, with only the new kernel gzip section allowed to change.

All tools and tests are public code **only**; no proprietary Apple firmware, private DTB, kernelcache, actual bootargs, on-device identifiers, Wi-Fi passwords, calibration or compiled private RAM bundles are published.

## Still unverified: physical Wi-Fi, PCIe and DART1

1. The alternate kernel has **NOT BEEN BOOTED** on an iPhone and has no verified runtime module behavior. Its four `.ko` modules are staged as private sidecars; future initramfs integration must be explicit and separately reviewed.
2. S8000 PCIe host resource/provider ordering is unproven, the port1-only clock/refclk/PERST#/PHY/MSI/link sequence is not implemented, and the original Linux research guard intentionally prevents hardware probing.
3. DART1 true hardware SID/IOVA/page tables and DMA isolation have not been proven. The separately tested S5L8960x packed-TCR fix does not address whole-instance reset safety.
4. Actual N71 onboard Broadcom BCM4350 PCIe enumeration has **not happened**; C2/C5 firmware choice, NVRAM/SysCfg calibration, regulatory DB acceptance, RF link and direct association to the Dell WLAN all remain unresolved.
5. The iPhone is still absent from Dell USB. No remote reboot, DFU transition, hardware register writes, NAND access, or live firmware load occurred.

**Conclusion:** full alternative Linux Wi-Fi kernel, four linked ARM64 modules and a kernel-only private RAM boot candidate now exist with strong offline integrity gates and a separately preserved known-good recovery payload. This materially advances software readiness, **not native Wi-Fi operational status**.
