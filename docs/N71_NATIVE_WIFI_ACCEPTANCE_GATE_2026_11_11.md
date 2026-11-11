# Native BCM4350 Wi-Fi acceptance gate

2026-11-11. **Status: NOT PASSED on physical N71**. The phone currently has only usb0, no wireless PHY, no PCIe enumeration and no validated A9 DART DMA. Pinging the Dell's LAN address over USB is not a Wi-Fi success.

An on-device script, scripts/n71_native_wifi_acceptance.sh, strictly requires a real wireless PHY, association reported by iw, exact expected SSID, a WLAN route to each tested peer, and two ICMP responses from both the LAN router and Dell via that wireless interface. USB and Ethernet names are rejected, and the script never asks for or stores a Wi-Fi credential.

On the iPhone Linux shell, only after actual PCIe and Wi-Fi bring-up:

    sh scripts/n71_native_wifi_acceptance.sh IFACE SSID GATEWAY_IP DELL_LAN_IP

The script requires ip, iw, and ping in the initramfs. A successful result must include N71_NATIVE_WIFI_ACCEPTANCE_PASS; no relay, USB NAT, host-side ping or host-side Wi-Fi test qualifies.

## Current network observations (do not mistake these for WLAN)

On the same physical N71 Linux boot, /sys/class/net contains only lo,
sit0 and usb0. No wireless phy80211 or PCIe endpoint is registered.
The Dell uses Wi-Fi as its own uplink, but routing an iPhone USB packet
through the Dell (or successfully pinging the Dell Wi-Fi address through
USB) does **not** demonstrate native radio or association.

A short-lived diagnostic USB default route previously added to the
phone was explicitly removed after the operator clarified the requirement.
No USB relay remained running. The native Wi-Fi-only test above requires
an actual radio on the iPhone and will fail closed until it appears.

## Offline Broadcom preparation

The current HoolockLinux RAM boot had CONFIG_WLAN disabled. In an isolated ARM64 host-only build, kernel option CFG80211=m, BRCMFMAC=m, BRCMFMAC_PCIE=y, BRCMFMAC_SDIO=n, BRCMFMAC_USB=n and WLAN=y were generated. The driver already supports PCI ID 14e4:43a3 (BCM4350). ARM64 relocatable cfg80211, brcmutil and brcmfmac objects compiled successfully without changing the phone. This DOES NOT bring up PCIe, load firmware, start RF or create a wlan interface.

The remaining hardware gate is a validated S8000 PCIe controller implementation with correct port-1 clocks, PHY, reset, MSI and safe DART1 stream/DMA mapping. Do not probe shared controller registers, storage port0 or modem port2. Do not put the existing unauthenticated USB Telnet listener onto WLAN; provision authenticated SSH first.

Privacy: public code contains no access-point password, board NVRAM, firmware, Apple code, private ADT or unique hardware ID.

## Apple A9 PCIe reverse-research status

The already locally recovered original iOS 15.8.8 kernelcache places
AppleS8000PCIe within a shared PCIe implementation containing
AppleS800xPCIe and AppleEmbeddedPCIE. A private, read-only summary of the
2,928-byte S8000-specific executable section found 55 direct ARM64
branch-with-link instructions, 46 calling outside the specialized section
and 9 within it. This indicates substantial delegation to shared code;
it is **not** a verified hardware register map, instruction trace or
safe PCIe startup sequence. No disassembly bytes or proprietary code
are published.

Without independently qualified S8000 global register/reset/clock
semantics and correct DART1 DMA stream isolation, a live PCIe probe could
affect storage or modem ports and remains **blocked**. The known-good
RAM Linux image with automatic Z2 multitouch and the framebuffer UI
is preserved. The offline BCM4350 object build is progress toward
native Wi-Fi but must not be described as a Wi-Fi connection test.
