# Targeted Kali ARM64 integration for N71

Design reviewed 2026-11-16. **Not installed or physically qualified on the phone.** The current live tools are the minimal bring-up utilities, WPA/DHCP and BlueZ/D-Bus; their existence is not a Kali installation.

## Architectural decision

Retain the hardware-qualified N71 Linux kernel and recovery environment. Add a curated Kali ARM64 filesystem/userspace as an optional local tool environment. Start with native AArch64 execution; use host-side QEMU only for build/ABI checks. Prefer an explicit chroot for the first integration experiment once its mounts, capabilities and teardown are tested. A chroot is not a security isolation boundary.

Do not replace the custom N71 kernel with a generic Kali ARM image. Do not describe this native Linux work as a supported Android NetHunter port: NetHunter's Android application/installer/kernel workflow is a different platform. Distribution packages cannot supply missing radio firmware capabilities or device drivers.

Earlier project notes described a foreign-debootstrap/minbase workflow and base/diagnostics profiles. Preserve that direction, but the referenced offline-kit build scripts are not currently present in this public repository. They must be imported, reviewed and tested before documentation offers them as runnable repository commands.

## Tool profiles

The proposed exact package names are versioned in [kali-tool-profiles.json](../manifests/kali-tool-profiles.json). This is a design allowlist, not a resolved lockfile. ARM64 availability, dependencies, licenses, installed size and runtime behavior must be resolved against signed repository metadata for the selected build date.

| Profile | Proposed packages | Intended phone workflow | Qualification |
|---|---|---|---|
| Base | bash, coreutils, ca-certificates, openssh-client, less, nano, tmux, python3, iproute2, iputils-ping, procps | Local shell, scripting, authenticated companion client, resource inspection | Not built/tested as Kali |
| Network diagnostics | nmap, tcpdump, dnsutils, traceroute, ethtool, iperf3, curl, openssl, netcat-openbsd | Owned-lab inventory, bounded packet capture, DNS/TLS and throughput diagnostics | First functional security-tool milestone |
| Protocol analysis | tshark | Filter and inspect the phone's private, bounded PCAP files without a desktop GUI | Optional after memory/dependency measurement |
| Web lab | whatweb, nikto, sqlmap | Explicitly scoped assessment of a controlled local web test application | Optional; no default background scans |
| Bluetooth diagnostics | bluez client utilities such as btmon, bluetoothctl and btmgmt | Inspect the already managed adapter and controlled lab pairing | Coordinate with the existing BlueZ service; never start a competing daemon |
| Wireless research | iw, aircrack-ng | Capability inventory and offline analysis; RF operations need separate acceptance | Native monitor mode/injection/AP mode unqualified |

Avoid broad kali-linux-everything/default/top10 installations for the first RAM experiment. Metapackages select dependency groups; the tiny metapackage itself does not represent the installed footprint. No fixed package-set size or ARM64 compatibility is promised until the actual dependency closure is recorded.

Desktop Burp/ZAP, Metasploit with database, bulk password-recovery jobs and large reverse-engineering workloads are initially companion candidates. They are not included in the default phone profiles. Additional packages require a specific workflow and measured cost rather than an indiscriminate expansion.

## Capability boundary

| Capability | Evidence today | Requirement before use/claim |
|---|---|---|
| Ordinary WLAN sockets | Phone-native WPA2/DHCP/Internet passed | Kali tool must independently use the native route |
| TCP connect assessment | Kernel networking available; Nmap not phone-qualified | Execute selected Nmap version on a controlled Dell listener; record result |
| Raw sockets/packet capture | Tool/kernel/runtime integration not tested | Required capabilities and AF_PACKET support, bounded capture, correct decoding |
| Managed-interface capture | Not qualified | Capture generated lab traffic; do not label it raw 802.11 monitor capture |
| Monitor mode | Not qualified | Driver-advertised mode, successful mode transition and actual authorized 802.11 reception |
| Frame injection | Not qualified | Device-specific firmware/driver support and independent controlled RF test |
| Bluetooth HCI diagnostics | HCI and encrypted transport passed; Kali client integration not tested | Correct bus/socket access and no conflicting bluetoothd instance |
| USB wireless/SDR adapters | USB gadget networking works; USB host/OTG peripheral path not qualified | Physical power/role/controller/driver tests for the actual adapter |
| HID input vs USB HID gadget | Genuine Bluetooth keyboard/mouse not tested; USB HID gadget not tested | Separate profile and kernel/gadget acceptance; one does not prove the other |

Installing aircrack-ng cannot establish monitor mode or injection. A successful encrypted Bluetooth echo cannot establish HID, A2DP, BLE GATT or NetHunter Bluetooth Arsenal compatibility.

## Build and provenance pipeline

1. Choose an empty, explicit output directory on the build workstation. Check disk space, host tooling and actual privilege availability. The current remote workflow does not have unrestricted host sudo; do not claim a root/chroot build has run.
2. Retrieve the official Kali archive keyring over HTTPS. Compare its signing-key fingerprint with current official documentation; the published 2025 key is 827C8569F2518CC677FECA1AED65462EC8D5E4C5. Record the selected keyring digest and signed metadata. A future rotation requires review, not disabled verification.
3. Bootstrap a minimal arm64 filesystem from one signed Kali repository. An isolated foreign-debootstrap/QEMU second stage is a candidate workflow; unprivileged mmdebstrap/user-namespace alternatives need host qualification before use.
4. Resolve only selected packages and record exact versions, architecture, package hashes and the complete dependency closure. Keep package services disabled during image construction. Do not mix Kali repositories into the Dell's Kubuntu sources or the recovery ramdisk.
5. Run host ABI/version smoke checks and inspect ELF64/AArch64, loaders, shared-library dependencies and interpreters. Label QEMU results HOST-ONLY.
6. Remove emulation helpers, package caches, temporary build mounts and host-specific identity. Lock passwords. Do not bake client private keys or default reusable credentials into public artifacts.
7. Archive with numeric ownership, record the uncompressed size/file inventory and SHA-256, and retain the verified source/package metadata. Rolling repositories do not guarantee an identical rebuild later without retained inputs or an appropriate snapshot.
8. Stage an operator-private candidate through the existing recovery channel; recheck hashes on the phone before extraction. Never replace the known-good RAM payload in place.

## Runtime and resource plan

The physical phone reports MemTotal 2,023,216 KiB. A current-session snapshot showed MemAvailable 1,756,064 KiB; this is a transient observation, not a Kali memory budget guarantee. tmpfs files, decompression, libraries, page cache and active tools all consume the same limited memory.

Before staging, measure archive size, extracted size and available RAM. Set a deliberate extraction ceiling and retain recovery headroom. If the minimum useful rootfs does not fit, stop that candidate and evaluate a smaller selected-binary bundle or a separately qualified external/host-served filesystem. Do not allocate all apparently free RAM or write a rootfs to internal storage to force success.

Keep the first environment command-line only. Use explicit proc/sys/dev mounts appropriate to the experiment; record them and unmount them on exit. Never start another DHCP client/server, network manager or bluetoothd from inside Kali. Preserve recovery USB addresses and the active native WLAN default route. Disable automatic public listeners; jobs must have a visible stop/timeout and output size cap.

## Physical smoke tests

| Gate | Controlled test | Required result |
|---|---|---|
| K0 provenance | Verify signed metadata and package/archive hashes | Matching identity and complete manifest |
| K1 ABI | Execute shell and tool --version on the actual phone | Correct ARM64 execution; no missing loader or libraries |
| K2 TCP | Nmap TCP connect test against one deliberate Dell lab listener | Expected open port and a deliberately closed comparison; no broad network sweep |
| K3 capture | Generate known phone-to-Dell traffic and capture a bounded packet count | Decodable PCAP containing the intended flow; private file retained locally |
| K4 TLS/DNS | Use curl/openssl and resolver utilities against controlled endpoints | Expected response/certificate checks with no insecure-verification bypass |
| K5 lifecycle | Stop tool environment and remove only its own mounts/processes | Recovery, touch, WLAN, Bluetooth and charging still available |
| K6 handheld | Launch and stop the tested job using the touch UI | No Bluetooth keyboard required |
| K7 reboot | Repeat the essential flow after a fresh integrated RAM boot | Reproducible result with private provisioning restored |

K0–K7 are planned gates, not completed tests. No public package plan, host emulation result or documentation check can mark Kali working on the phone.

## Official references checked 2026-11-16

- [Kali metapackages](https://www.kali.org/docs/general-use/metapackages/) and [package groups](https://www.kali.org/tools/kali-meta/): selective package planning.
- [Kali archive signing key](https://www.kali.org/blog/new-kali-archive-signing-key/): key provenance.
- [NetHunter architecture](https://www.kali.org/docs/nethunter/) and [components](https://www.kali.org/docs/nethunter/nethunter-components/): Android-specific platform and kernel/userspace distinction.
- [Nmap package](https://www.kali.org/tools/nmap/), [tcpdump package](https://www.kali.org/tools/tcpdump/), [Wireshark/TShark](https://www.kali.org/tools/wireshark/), [Aircrack-ng](https://www.kali.org/tools/aircrack-ng/): tool reference, not proof of N71 compatibility.

The design choices and test budgets above are project proposals. None is an official Kali iPhone support claim.
