# BCM4350 PCIe OTP support — exact N71 Linux ARM64 offline build

**13 November 2026 — host-side compilation only. No iPhone reboot, radio or PCIe activation.**

To reduce the software work remaining after a **safely enumerated PCIe endpoint**, we applied an existing, GPL-licensed [OrchardLinux BCM4350 OTP patch](https://github.com/OrchardLinux/orchard/blob/main/kernel/patches/drivers/wifi/0005-wifi-brcmfmac-pcie-Read-the-BCM4350-OTP.patch) to the project's private experimental ARM64 kernel source. Original author: **Henrik Klee**; report credited to **Martin Puškáč**. The public exact two-hunk source delta is [patch 0017](../experimental/patches/0017-n71-brcmfmac-bcm4350-otp-software-only-offline.patch).

The source adds a case for `BRCM_CC_4350_CHIP_ID` in `brcmf_pcie_read_otp()`. It calculates ChipCommon 40 nm OTP bounds using the capabilities size field, starts Apple's system-vendor record scan at `0x8c0`, and permits a missing Apple record without failing non-Apple BCM4350 devices. This can contribute to correct firmware/NVRAM variant selection once the PCIe device itself is operational. It does **not** enable the Apple S8000 PCIe host controller.

The patch applies cleanly to the owner's pinned Linux 7.3-rc1 kernel. The separately built real `drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.o` is:

- Architecture: **ELF64 little-endian AArch64 relocatable**
- Size: **758,344 bytes**
- SHA-256: `4a16ed4882f2a7e33e87acbf88881b6fd1da38446f87b294b988a975c4916bbe`

Owner-private previous source SHA-256:
`2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c`

Modified source SHA-256:
`1a7e90562fd934352952506f86e0e64d3bedb66dfd16d381cf2caa941615b746`

The new [exact-source and ARM64 build gate](../tools/n71_bcm4350_otp_software_arm64_offline_gate.py) compares the precise before/after source, the two-hunk public patch and the real compiled object. The [15 synthetic adversarial tests](../tests/test_n71_bcm4350_otp_software_arm64_offline_gate.py) cover OTP-size bounds, zero size, wrong types, unrelated MMIO operations and source/hash mutation.

**Critical board-specific limitation:** The upstream OTP layout was demonstrated using a BCM4350 with **C2** firmware on an iPad Air 2. The iPhone 6s **N71/Samsung S8000** uses a BCM4350C5 (`albarossa`) with separately extracted authentic Apple C5 firmware. This build does **not prove** that C5's OTP layout matches the upstream implementation or that Linux accepts Apple's firmware format. Never substitute C2 board calibration for the N71 C5.

**Hardware state unchanged:** The real phone still boots the previously verified RAM Linux with touchscreen, native framebuffer cyberdeck GUI and USB connectivity. The native Wi-Fi interface and PCIe endpoint remain absent. The owner's separate experimental DART patch 0016 continues to **refuse unqualified all-four-stream resets**. No original Apple firmware, NVRAM, OTP, kernelcache or identifying capture is included in the public repository.

## Next actual hardware prerequisite

Qualify **S8000 PCIe port1** clock/reset and physical BCM4350 requester→DART1 stream mapping while proving NAND port0 and modem port2 are unaffected. Only afterward can a separate supervised RAM boot test PCIe link enumeration and the new BCM4350 OTP firmware selection. Static compilation and tests do not authorize real PCIe register writes.
