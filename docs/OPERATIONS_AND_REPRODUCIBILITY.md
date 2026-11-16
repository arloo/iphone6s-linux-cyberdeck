# Operations and reproducibility boundaries

Reviewed 2026-11-16. The public repository contains source, checks and sanitized evidence. It does not contain a redistributable turnkey N71 image or all private deployment helpers. A successful offline build is not permission to assume a new hardware boot passed.

## Three distinct verification levels

| Level | What it proves | What it cannot prove |
|---|---|---|
| OFFLINE | Parsers, protocol logic, negative gates and manifest consistency | Physical peripheral operation |
| BUILD | Correct sources/configuration can produce the intended architecture and ABI | Safe runtime or successful RF traffic |
| HARDWARE | A particular device/payload/session satisfied the documented test | Other foundries, reboot endurance or unrelated profiles |

The machine matrix only promotes functional results when corresponding reviewed physical records and reports are present. Removing the multitouch/WLAN/Bluetooth physical record makes the relevant qualification gate fail; a calibration ACK or host-only build cannot substitute for it.

## Workstation and inputs

Use a Linux build host with an AArch64 cross compiler, Python 3, make, dtc and the appropriate pinned kernel sources/build outputs. Exact dependencies vary by target. Keep isolated source/build directories and a dedicated owner-private output directory; do not copy the user's whole working tree into the public repo.

Required private inputs include original board-compatible firmware, touch calibration and validated WLAN tuning/NVRAM. Public docs identify their role and provenance, not their contents. The N71 S8000 path is physically qualified; S8003 inputs in upstream source or a payload format do not constitute S8003 hardware support.

## Source-only validation

```sh
make test
python3 scripts/validate_project.py
python3 tools/security/check_git_privacy.py
```

The first command runs unit tests, the synthetic HBPP audit and project validation. The privacy audit checks Git history/current identity and tracked text. These checks run locally. The versioned ci/verify.yml template has not been activated as a completed GitHub Actions workflow.

## Native WLAN runtime build

The builder checks exact patched GPL IOMMU source hashes and requires the tested batt2 kernel ABI. Its output must be outside the public tree. The following is an offline build template: replace placeholders with reviewed local inputs; it does not access USB or load a module.

```sh
python3 tools/build_n71_native_iommu_runtime.py \
  --kernel-source /path/to/kernel-source \
  --kernel-build /path/to/tested-batt2-build \
  --patched-source /path/to/reviewed-patched-source \
  --private-calibration /path/to/private-port1-calibration.h \
  --managed-wlan-runtime \
  --output /path/to/private-new-runtime-output
```

The managed flag enables the brcmfmac and native-MSI paths. Default/reset-held diagnostic mode is different from the managed runtime. The output build-manifest records the ABI, source pins, file sizes/hashes and selected mode; it begins physically_tested=false even if the same source previously worked elsewhere.

For the associated static ARM64 WPA/iw stack, use [Wi-Fi userspace source pins/configuration](../experimental/wifi-userspace/README.md). The validated legacy-kernel compatibility patch and the minimal supplicant limitations are documented there. Provide owner-private firmware/NVRAM and credentials only in the private staging process.

## Runtime readiness and independent evidence

| Stage | Required observation | Insufficient substitute |
|---|---|---|
| PCI/driver | Real 14e4:43a3 endpoint, brcmfmac binding and native interface | Compiled driver or USB interface |
| DMA/IRQ | Tested translated SID0 path and standard MSI delivery | An allocated buffer with no endpoint activity |
| Authentication | WPA completed plus actual encrypted network traffic | Status string alone |
| IP | DHCP address, native WLAN default route and resolver configuration | USB proxy reachability |
| Data | Controlled peer sees WLAN source and payload SHA-256 matches | An unbound HTTP request that might use USB |
| Lifecycle | Controlled unbind/unload, temporary objects removed and seven domains restored | Plain rmmod attempted while IOMMU consumers still pin the module |

The managed module remains active until explicitly stopped. [n71_native_wlan_runtime_stop.sh](../scripts/n71_native_wlan_runtime_stop.sh) is a phone-side teardown tool, not a routine status command. It deliberately stops WLAN services and unbinds before unloading. Do not invoke it merely to inspect a working session.

## Bluetooth build/runtime and controlled test

The already qualified HCI UART transport uses private genuine BCM4350C5 patchram build 0825. RAM-local BlueZ 5.85 and D-Bus 1.16.2 provide controller management and pairing. Their validated packaging is documented in [Bluetooth runtime notes](N71_BLUETOOTH_RUNTIME_2026_11_16.md). That packaging checkpoint is private; a general public end-to-end bootstrap is still to be implemented.

```sh
make build/n71-bt-l2cap-echo-aarch64 \
  BLUEZ_HEADERS=/path/to/isolated/bluez-include
```

This builds only the static ARM64 echo client. A controlled peer must already run a matching encrypted SOCK_SEQPACKET L2CAP listener on PSM 0x1001. The client takes one private peer-address file, requires BT_SECURITY_MEDIUM, checks every 256-byte echoed packet and prints only aggregate verification. The original tests also checked the expected peer at the Dell and restored temporary discoverability. Two successful same-session tests do not prove recovery after daemon restart or reboot.

## Boot integration status

The existing qualified payload has automatic touchscreen setup and a monitored charging/HCI startup path. The new [connectivity startup candidate](../scripts/n71_connectivity_autostart.sh) is prepared source only. It expects a private hash manifest and staged runtime paths; it is not self-contained and has not been installed or physically tested. Its guards/ordering must be tested before inclusion in a candidate.

Keep the known-good payload immutable. Record m1n1, both DTBs, kernel, initramfs and final payload hashes; inspect differences and image size before a supervised Pongo transfer. Preserve USB recovery on partial startup failure. The older n71-batt2 smoke script is tied to its dated payload and does not automatically select a newer image.

## Power and recovery

The tested charging experiment uses a 300 mA USB input setting with a 3600-second lease. Input current limit and measured battery charging current are different quantities. Watch actual Charging state, signed battery current, capacity and temperature; the lease can expire during active work. Renewal policy and unattended operation are still qualification tasks.

The existing USB Telnet shell is bench-only and unauthenticated. [SSH migration](REMOTE_SHELL_HARDENING.md) requires a verified alternate key-only path before Telnet is removed. No documentation update should disrupt the working recovery channel.

## Contribution/evidence handoff

For a new result, record board/foundry, source commit, exact private payload hash, selected experimental mode, bounded test, independent positive/negative observations and postflight. Publish only reviewed summaries without addresses, keys, credentials, raw captures, firmware or calibration. Keep historical failures and uncertain root causes attributed to the payload that produced them.

Use the [issue map](ISSUE_STATUS_2026_11_16.md) to choose current work instead of restarting already solved bring-up steps. The optional Kali tool environment has its own [integration and smoke-test gates](KALI_ARM64_INTEGRATION.md).
