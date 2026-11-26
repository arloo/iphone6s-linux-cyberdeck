# iPhone 6s Linux Cyberdeck — N71 / Apple A9

**Current storage acceptance (2026-11-25):** Real N71/S8000 Linux block bios have passed over both the **initial and final two sectors of the 64 GB namespace**, in two separate authenticated fresh-boot trials. Each trial completed four 4 KiB reads with exact CQEs, independent guarded data, private same-LBA comparisons and four kernel-client completions. The new final-pair sequence is 15624998,15624999,15624998,15624999. Exact Create/Delete SQ/CQ and shutdown/disable/BME-off passed. Temporary disks were removed and all DMA owners retained. **This qualifies four distinct LBAs, not the intervening full drive, arbitrary userspace access, ring/buffer reuse, independent DMA retirement or persistence.** [Final-sector physical proof](docs/N71_S8000_RO_BLOCK_TAIL_PAIR_TRIAL_2026_11_25.md#physical-acceptance-last-two-lba-linux-bios), [sanitized acceptance](docs/N71_S8000_RO_BLOCK_TAIL_PAIR_ACCEPTANCE_2026_11_25.json), [earlier initial-sector block path](docs/N71_S8000_RO_BLOCK_BRIDGE_ACCEPTANCE_2026_11_25.json) and [canonical ledger](docs/N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).

**Read-only interface boundary:** the accepted block bridge admits exactly four trusted kernel bios, blocks userspace opens/partition scanning and retains every DMA owner. It is a physical integration milestone, not a usable or mountable userspace disk. Broader request admission, ring/lifetime rules and error handling are the next qualification work. [Scope and evidence](docs/N71_S8000_RO_BLOCK_BRIDGE_TRIAL_2026_11_24.md).

**Userspace probe follow-up (2026-11-26):** The first root-only four-pread trial passed its bounded power gate at 37–38% but failed before any NVM Read: the helper node was placed on nodev /run. The software interfaces were removed; failed controller shutdown retains every owner and forbids a same-boot retry. A corrected /dev-node helper and private RAM image are built; the storage module is unchanged and **1,944 host tests pass**. The corrected image has not booted or passed userspace NAND I/O. [Failure, exact cleanup limits and corrected candidate](docs/N71_S8000_USERSPACE_PROBE_NODEV_FAILURE_2026_11_26.md).

**S3E DMA-retirement audit (2026-11-20):** The real N71/S8000 NVMe Identify succeeded again, and a 32-sample read-only SQ burst resolved separate observed FIFO and DART register transitions within tens of microseconds. Shutdown/BME-off **do not prove DMA quiescence**; owned queues, HMB, NVMMU and DART pages remain quarantined. A host/static audit confirmed three fail-closed retirement guards; the public driver now includes the conservative latch and four retirement guards, with 112 host-only injected-fault scenarios and an offline ARM64 build. A separate read-only admin protocol-accounting observer now distinguishes a validated Identify from a CQ phase bit (4,096 exhaustive host combinations); no accounting result authorizes DMA release. The updated source is not hardware-tested and does not authorize DMA release. A new bounded, opt-in post-stop CQ/data RAM-change witness is also built offline; unchanged fingerprints are explicitly **not** a quiescence proof. An offline sanitized analyzer now compares prior physical S3E shutdown snapshots: identical DART `0x500` with five distinct FIFO values across eight archived records, without inferring device quiescence or unique boot count. At that historical checkpoint no Linux NAND block I/O or persistence was qualified; the subsequent one-block Read acceptance is recorded above. [Current sanitized evidence and next gates](docs/N71_S8000_S3E_DMA_RETIREMENT_AUDIT_2026_11_20.md).

**CYBERDECK // ARLO visual milestone (2026-11-18):** The owner-approved portrait boot splash now **renders on the real N71/S8000 in RAM-only Linux**, with USB SSH-confirmed framebuffer output, `quiet loglevel=3`, native touch-first UI, Wi-Fi and Bluetooth. The original debug boot image is retained. This was a visual/showcase boot, **not** a persistent-storage test. [Physical test evidence and charging caveats](docs/N71_ARLO_SHOWCASE_PHYSICAL_BOOT_2026_11_18.md).

**Guarded faster charging research (2026-11-19):** The real N71/S8000 has already demonstrated a bounded **500 mA SN2400 USB input-limit** pilot versus the default 300 mA RAM profile. A separate **owner-attested, fail-closed 500 mA supervisor** is now staged offline; it has not been applied to the low-battery phone running iOS. Source capability and cell-voltage/cable qualifications remain mandatory; no host USB limit or battery charge-voltage setpoint was raised. [Source limits, evidence and guarded deployment plan](docs/N71_CHARGING_SOURCE_CEILING_AND_500MA_PROFILE_2026_11_19.md).

**Current integrated RAM acceptance (2026-11-18):** Verified the exact on-phone runtime image, authenticated **Wi-Fi SSH** on a short-lived key-only listener, 4 MiB bidirectional SHA-matched LAN transfer, native UI hardware/PTY tests, BlueZ power, Kali passive capture, Dell-backed RAM file vault restore/backup, cached TODAY delivery and a running fail-closed charging supervisor. A **first automatic 300 mA charge-module renewal physically succeeded** while NVMe was quarantined; multi-cycle endurance, sustained net-positive cell charging and persistent NAND are **not** yet qualified. A read-only **Dell terminal monitor** is available. [Live hardware evidence and monitor instructions](docs/N71_CYBERDECK_CURRENT_RAM_SESSION_2026_11_18.md).

**NVMe queue-retirement checkpoint (2026-11-18):** A sixth physical one-shot Identify confirmed normal controller shutdown, cleared ANS HMB descriptors, and **retained AQA/ASQ/ACQ queues plus DART mappings**. A separately armed queue-register-only retirement gate correctly **refused its attempt**; no queue registers were cleared, no DMA pages were freed, and the module remains in quarantine. A new **13-condition read-only refusal diagnostic** has been compiled for the next *fresh* boot (53 S3E host tests passing). No block device or persistent NAND access exists. [Physical evidence and safety-gate investigation](docs/N71_S8000_NVME_SHUTDOWN_POSTQUALIFIER_2026_11_18.md).

**NVMe teardown diagnostics (2026-11-18):** A second real, guarded Identify completed. The controller separately acknowledged normal shutdown (`CSTS=0x9`, shutdown return 0), disable (`CSTS=0`, return 0), and BME-off on both PCI functions. The pilot still intentionally quarantines because the **post-disable reused pre-start qualifier fails**. That logging-only, unchanged-quarantine candidate has since been physically tested in a **fresh boot**, isolating the two HMB descriptor mismatches; the present session is quarantined and must not be retested. [Physical proof and next predicate diagnostics](docs/N71_S8000_NVME_SHUTDOWN_POSTQUALIFIER_2026_11_18.md).

Earlier **physical storage breakthrough (2026-11-18)**: On a real N71/S8000, the source-verified PA|3 DART non-leaf descriptor **successfully completed NVMe Identify Namespace 1** with an independently arrived DMA payload. The namespace reports **64,000,000,000 bytes (64 GB decimal), 4 KiB logical LBAs** using the owned 8 MiB HMB. **This is not a mounted block device or filesystem**: controller shutdown did not satisfy the full DMA teardown gate, so the module remains pinned in safe quarantine with bus mastering off. The shutdown phase is now verified; the post-disable qualifier and DMA release proof remain open. Do not repeat I/O in the held state. [Physical proof and retention limits](docs/N71_S8000_NVME_IDENTIFY_SUCCESS_2026_11_18.md).

Previous controller failure (2026-11-18): PA|1 DART non-leaf descriptors caused `NO_PMD` at the queue IOVA; this was the blocker that PA|3 overcame for Identify. [Earlier fault analysis](docs/N71_S8000_NVME_READY_FIRST_QUEUE_FAULT_2026_11_18.md).

Earlier HMB result (2026-11-18): the S8000 ANS controller requests an **8 MiB HMB**, measured with CC.EN and bus mastering off inside owned DART0/NVMMU guards. A subsequent physical checkpoint installed the owned 8 MiB SART/HMB descriptor, verified it and fully restored it with CC.EN/BME still off. All state restored and native WLAN survived. [Evidence and limits](docs/N71_S8000_ANS_HMB_REQUEST_2026_11_18.md).


A pocket Linux cyberdeck built around an iPhone 6s: native touchscreen operation, Wi-Fi and Bluetooth, a local terminal and a targeted Kali ARM64 tool environment. The intended experience is a fullscreen touch-first console for diagnostics, authorized security assessments and selected companion workflows.

**Physical milestone, 17 November 2026:** native Linux on the real **N71 / Samsung S8000** now runs a **six-tab KALI / TODAY / AI Cyberdeck**, retaining HOME, TERM and SYS. Automatic multitouch, Wi-Fi and Bluetooth from 16 November remain available. A first-stage Kali-compatible tool profile and genuine ARM64 static tcpdump 4.99.7 passed physical tests; TODAY receives a privacy-checked AI briefing via pinned USB SSH; and the text AI tab connects via an owner-only Dell USB bridge to the OpenAI Responses API without placing an OpenAI key on the phone. A private next-boot RAM payload has been built but **not physically boot-tested**. Full Kali userspace, manual ergonomic acceptance, standalone storage and automatic per-boot provisioning remain open. This is a RAM-only research system, not a persistent phone OS. [Detailed evidence and limits](docs/N71_THREE_PILLARS_KALI_TODAY_AI_2026_11_17.md).

**Hardware-test charging policy (17 Nov 2026):** before every further N71/S8000 PCIe, DART or NVMe MMU trial, check the SN2400 lease age, battery capacity/temperature/voltage and USB VBUS. The Dell USB device advertises **500 mA** and a 30-second physically monitored trial at 500 mA input delivered an average **+265 mA net battery current**; this does not imply a fast-charge negotiation or authorize higher USB draw. A 3600-second rollback lease is active only in the attended RAM session. It must be explicitly renewed as part of subsequent testing before expiry, and never bypassed if health checks fail. [Physical charging and 0x210 driver evidence](docs/N71_S8000_SN2400_500MA_AND_PCIE_LOCAL0210_2026_11_17.md).

**Storage hardware breakthrough (17 Nov 2026):** the real N71/S8000 now identifies its internal **Apple S3E 106b:2002**, class018002/revision11, through bounded PCIe config reads on temporary bus2. Empty Linux-owned DART0 roots covered all four hardware streams, endpoint bus mastering stayed disabled, and routing/reset/controls/tables were restored. BAR0 is64-bit/16KiB. Five real NVMe register reads passed: CAP `0x00000020f00103ff`, VS `0x00010001` (1.0.1), CC0 and CSTS0, with bus mastering OFF and full PCI/MMIO rollback. WLAN then passed a real native Internet ping. Owned NVMMU TCB/auxiliary table replacement and bounded invalidation also passed with exact restoration. [NVMMU ownership result](docs/N71_S8000_NVMMU_OWNED_TABLES_2026_11_17.md). A registered Linux storage device, NVMe queue transport and namespace access remain open. [NVMe register result](docs/N71_S8000_S3E_NVME_BAR0_REGISTERS_2026_11_17.md). [Physical S3E identification](docs/N71_S8000_S3E_2002_PHYSICAL_PCIE_ID_2026_11_17.md) and [MMIO/DART0 stages](docs/N71_S8000_PORT0_DART_NVMMU_MMIO_BREAKTHROUGH_2026_11_17.md).

A [complete documentation index](docs/INDEX.md) links current guides and the retained detailed experiment catalog.

## Start here

| Reader/task | Document |
|---|---|
| Understand the intended cyberdeck and operator workflows | [Product vision and architecture](docs/CYBERDECK_VISION_AND_ARCHITECTURE.md) |
| Inspect what genuinely works on the phone | [Hardware state](docs/HARDWARE_STATUS.md) and [engineering assessment](docs/PROJECT_STATE_2026_11_16.md) |
| Understand build/runtime/recovery boundaries | [Operations and reproducibility](docs/OPERATIONS_AND_REPRODUCIBILITY.md) |
| Plan Kali and select tool packages | [Kali ARM64 integration](docs/KALI_ARM64_INTEGRATION.md) and [profile manifest](manifests/kali-tool-profiles.json) |
| Manage music, documents and file backups while standalone persistent storage is unavailable | [A9 NAND blocker and file/media workspace](docs/N71_INTERNAL_STORAGE_AND_MEDIA_WORKSPACE_2026_11_17.md) |
| Build the AI briefing and persistent storage | [Companion briefing and storage](docs/COMPANION_BRIEFING_AND_STORAGE_2026_11_16.md) |
| Choose current work | [Roadmap](docs/ROADMAP.md) and [GitHub issue map](docs/ISSUE_STATUS_2026_11_16.md) |
| Review historical reverse engineering | [Driver worklog](docs/DRIVER_WORKLOG.md), dated reports and [historical README](docs/history/README_BEFORE_2026_11_16_REFRESH.md) |

## Product objective

The goal is a usable handheld cyberdeck, beyond successful hardware detection. An operator should be able to open a local terminal, enter a command with an on-screen keyboard, launch a selected tool against an explicit lab target, stop a job and review its private output directly on the phone. A Bluetooth keyboard is optional; no keyboard/mouse is currently at hand, so genuine HID tests are deferred rather than silently passed.

The product now has **three primary interactive functions**: a targeted **KALI** shell/toolset for authorized diagnostics, a **TODAY** AI briefing of Gmail/Calendar and optionally privacy-filtered personal WhatsApp, and a direct **AI** text conversation powered by a securely isolated Dell API bridge. Standalone, reliably writable storage is a prerequisite for a full Kali distribution rather than a fourth user-facing mode. On 17 November the phone received a current TODAY briefing, ran the first real tcpdump capture and answered an AI text request; personal WhatsApp remained disconnected. A separate 64 MiB Dell-backed NBD/ext4 laboratory disk previously passed physical phone read/write and host readback, but is not standalone persistent internal storage. [Three-pillar milestone](docs/N71_THREE_PILLARS_KALI_TODAY_AI_2026_11_17.md) and [storage limits](docs/COMPANION_BRIEFING_AND_STORAGE_2026_11_16.md).

The Dell serves as build/recovery workstation, controlled Bluetooth/network test peer and optional heavy-workload companion. Native Wi-Fi now provides actual phone radio networking; Dell-assisted execution and USB-forwarded Internet must remain labeled separately from phone-local operation.

## Current hardware and software matrix

| Component | Observed on N71/S8000 | Status and exact limit |
|---|---|---|
| Boot chain | checkm8 → PongoOS → m1n1 → Linux | Physical RAM boot PASS; persistent installation unqualified |
| Running kernel | 7.3.0-rc1-n71-batt2-g68aadac820d0-dirty, AArch64 | Specific tested build; kernel presence does not qualify other images |
| Display/UI | Native six-tab dashboard with KALI, TODAY and AI; 38 × 14 ASCII PTY and on-screen keyboard on 750 × 1334 fbdev | Physical ARM64 selftest and live-process activation PASS; owner manual finger acceptance pending |
| Touch | Automatic Z2 initialization and real single/two-finger EVDEV events | Functional PASS; edge/latency/endurance/resume open |
| USB networking and SSH | NCM recovery link and key-only Dropbear on USB address | Authenticated current-session SSH/Telnet cutover PASS; fresh-boot recovery still open |
| Wi-Fi transport | Real BCM4350C5 PCIe 14e4:43a3, brcmfmac binding | Managed native runtime PASS |
| Wi-Fi networking | Scan, WPA2, DHCP, native route/DNS, Internet and checked 1 MiB transfer | PASS at 2412 MHz; 5 GHz/reboot/resume/endurance open |
| Bluetooth transport | BCM UART HCI, genuine private patchram build 0825 | Enabled with zero observed transport errors |
| Bluetooth discovery/data | LE scan (12 devices), classic Dell pairing/bonding and encrypted L2CAP echo | Two controlled same-session trials PASS; HID/audio/GATT/reboot open |
| Radio coexistence | Wi-Fi Internet traffic during Bluetooth transfer | Short concurrent test PASS; no sustained benchmark |
| Battery/charging | SN2400 verified 500 mA USB input pilot: 14 positive samples, +265 mA mean net battery; subsequent supervised 3600 s lease | Measured positive charging PASS; automatic kernel rollback on expiry; full-charge, unattended renewal and reboot persistence not proven |
| Kali ARM64 security tools | First-stage n71-kali profile and genuine tcpdump 4.99.7/libpcap 1.10.7 ARM64 static build | Phone-local PASS for version and bounded USB capture; full signed Kali ARM64 rootfs and nmap are pending |
| Touch terminal/jobs | Real local PTY/keyboard dispatch selftest passed on phone; Home/System/Tools views running | Manual typing, full VT/scrollback and Kali job integration remain open |
| Remote experimental storage | Dell-backed 64 MiB ext4 on /dev/nbd0 via USB | Read-only and read/write mount, synced file and host readback PASS; detached; not standalone or suitable for private data |
| Internal Apple storage | 64 GB Identify; four physical Linux bios with exact CQEs, guarded data and private returned-pair equality; teardown/controller stop passed | Bounded kernel block path PASS; temporary disk removed, DMA retained; userspace access, reuse and persistence open |
| Baseband | PCIe link2 kept OFF | Telephony unqualified |
| AI companion briefing | Gmail/Calendar AI snapshot delivered via pinned USB SSH to live TODAY UI | Reduced JSON/text push PASS; cached data; WhatsApp ingestion and owner finger-UI acceptance incomplete |
| S8003 / N71m | No compatible physical device available | All hardware results NOT TESTED |

The machine-readable [test matrix](manifests/test-matrix.json) covers established hardware acceptance tasks. The [Kali profile manifest](manifests/kali-tool-profiles.json) is a proposed package allowlist, not an installation/version lockfile.

## Touchscreen: what was proved

The N71 Z2 path includes private board firmware/calibration, the S5L SPI2 controller and board-specific power/clock/protocol initialization. After an attended RAM boot, the public autostart logic completed runtime setup without operator-issued manual touch sysfs commands.

A bounded physical input sample captured 4,096 events, reconstructed 581 SYN_REPORT frames and contained 138 frames with two simultaneous contacts. Earlier contact tests verified movement and release. A capture ending at its event cap cannot independently prove that all contacts were released afterward, and observed XY range is not a calibrated edge-accuracy measurement.

- [Automatic startup and physical multitouch evidence](docs/N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md)
- [Simultaneous two-finger test](docs/N71_SIMULTANEOUS_TWO_FINGER_EVDEV_PASS_2026_11_11.md)
- [Framebuffer cyberdeck proof of concept](docs/N71_LIVE_FBDEV_CYBERDECK_POC_2026_11_11.md)
- [Current touch issue #1](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/1)

## Native Wi-Fi: what changed

Bring-up progressed through original resource/firmware identification, bounded port-1 power/link experiments, PCI enumeration, translated DMA, interrupts and genuine brcmfmac operation. The current managed runtime uses SID0 DART mappings and the standard Linux MSI hierarchy (message 8 / AIC 264).

This is native phone Wi-Fi: the tested interface is attached to the physical PCIe Broadcom endpoint, obtains DHCP and its own default route, resolves DNS and transfers traffic through the phone radio. A controlled 1 MiB payload was checked by SHA-256, independently of supplicant status. It is distinct from the earlier Dell-to-phone USB proxy experiment.

The runtime stays active until explicitly stopped. Controlled platform unbind and module unload restored all seven PCIe power domains and removed the temporary objects while preserving USB, touch and Bluetooth presence. Plain rmmod while active IOMMU consumers pin the module is not the verified shutdown procedure.

- [Sanitized physical result](docs/N71_NATIVE_WIFI_PHYSICAL_PASS_2026_11_16.json)
- [Managed runtime builder](tools/build_n71_native_iommu_runtime.py) and [phone-side teardown](scripts/n71_native_wlan_runtime_stop.sh)
- [Pinned WPA/iw sources, minimal configuration and compatibility notes](experimental/wifi-userspace/README.md)
- [Current Wi-Fi issue #2](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/2)

Automatic new-boot restoration, AP-loss reconnect, 5 GHz, suspend/resume and long-duration performance are not yet qualified. Managed connectivity does not establish monitor mode, AP mode or frame injection.

## Bluetooth: what was proved

The current RAM-local BlueZ/D-Bus services use the already working BCM4350C5 HCI UART/patchram path. LE discovery saw 12 devices; classic inquiry discovered the intended Dell. Pairing and Bonded state succeeded, followed by an exact encrypted L2CAP echo: 256 packets × 256 bytes, totaling 65,536 bytes per trial. Two initial same-session trials passed; a later third trial passed after controlled BlueZ/private-bus restart.

Both the echo client and Dell listener require encryption; the listener checks the expected peer. The observed security level 2 does not establish MITM-authenticated pairing. HCI transport errors remained zero and native Wi-Fi Internet traffic worked during the Bluetooth test. Temporary Dell discoverability was restored afterward.

- [Sanitized physical result](docs/N71_BLUETOOTH_PHYSICAL_PASS_2026_11_16.json)
- [Runtime versions, packaging and security scope](docs/N71_BLUETOOTH_RUNTIME_2026_11_16.md)
- [Encrypted ARM64 echo client](tools/n71-bt-l2cap-echo.c)
- [Current Bluetooth issue #3](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/3)

Bond keys currently live in private RAM state. The follow-up verified service restart and bond reload, but no new kernel boot has been tested. HID input, A2DP, BLE GATT applications, address privacy and power-state recovery remain separate qualifications. A rejected optional privacy-setting request is documented rather than treated as passed.

## Targeted Kali ARM64 direction

Keep the custom hardware-qualified N71 kernel and add a measured ARM64 userspace/tool subset. The first integration candidate is a minimal native command-line environment, with explicit mounts/lifecycle and a retained recovery path. A chroot shares the existing kernel and is not a security sandbox.

| Proposed profile | Examples | Intended workflow |
|---|---|---|
| Base | bash, tmux, Python, SSH client, iproute2 | Local shell, scripting and authenticated companion access |
| Network diagnostics | Nmap, tcpdump, DNS utilities, curl/OpenSSL, iperf3 | Controlled inventory, bounded capture and network/TLS checks |
| Optional protocol/web lab | TShark, WhatWeb, Nikto, sqlmap | Selected private capture analysis or explicitly scoped test application |
| Bluetooth diagnostics | BlueZ clients | Controlled adapter inspection using the existing service |
| Wireless research | iw, Aircrack-ng | Capability inventory/offline analysis; RF modes require their own proof |

These packages are planned, not installed/validated on the phone. Resolve exact ARM64 versions, signed package metadata, dependency closure and memory/storage cost before staging. Larger desktop/database/cracking/reverse-engineering workloads initially belong on the Dell as an authenticated companion.

The physical phone has about 2 GiB RAM, shared with the kernel, tmpfs, unpacked tools and active jobs. Do not infer a usable rootfs budget from archive size alone. Do not mix Kali repositories into the Dell's Kubuntu configuration or replace the tested recovery userspace indiscriminately.

Read the [complete build/provenance/resource and K0–K7 test plan](docs/KALI_ARM64_INTEGRATION.md). This is not an official iPhone Kali/Android NetHunter port, and no distribution package can enable missing kernel/radio capabilities by itself.

## Current-session finalization and power profile

[Native shell UI 0.4](examples/cyberdeck-shell/) is running on the phone. Its actual ARM64 selftest executed a controlled command through the PTY using simulated keyboard hit dispatch. Framebuffer readback was reviewed; operator touch typing and optical confirmation of the new application are still pending. The console is ASCII/TERM=dumb, with no full VT emulation or scrollback browser.

The display is now at 1023/2047 (about 50% of its register range), with the previous 1505 value retained for restoration. Existing schedutil CPU scaling and Wi-Fi power saving were preserved. A short observation measured 8,832 KiB UI RSS and 0.31% aggregate CPU utilization; this is not a battery-life benchmark. An independently verified 4 MiB WLAN transfer passed with the UI active after service recovery.

The separate integrated boot candidate carries private runtime/configuration/bonds and this UI while preserving m1n1, DTBs and kernel. It requires a supervised physical DFU/Pongo boot before any reboot-restoration claim. See [session finalization evidence](docs/N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md), [readable observations](docs/N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.json) and the [new boot hook](scripts/n71_integrated_ram_startup.sh).

## Remaining release work and live issues

| Priority/workstream | Concrete next result | Issue |
|---|---|---|
| Integrated boot | Private pinned candidate; idempotent startup and new-boot verification | [#4](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/4) |
| Recovery security | Key-only USB SSH, refusal tests and verified Telnet cutover | [#7](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/7) |
| Handheld usability | Local terminal/on-screen keyboard, job launch/stop/results | [#6](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/6) |
| Kali subset | Signed measured ARM64 build and real-phone controlled tool tests | [#5](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/5) |
| Peripheral qualification | Touch precision, WLAN reconnect/endurance, Bluetooth recovery/profiles | [#1](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/1), [#2](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/2), [#3](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/3) |
| Power | Temperature-aware finite charging policy, idle/resume/endurance | [#8](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/8) |

The connectivity startup is installed in the current RAM session. Consecutive calls preserved all four daemon PIDs; controlled restart of BlueZ/D-Bus/WPA/DHCP restored networking and private bond state. A separate 25,066,924-byte integrated RAM candidate is hash-verified but has NOT been transferred/booted. The running recovery image remains unchanged. See [operations](docs/OPERATIONS_AND_REPRODUCIBILITY.md) before treating a code path as an executable boot recipe.

## Reproduce source and build checks

```sh
# Public-source-only verification; no phone or proprietary firmware required.
make test
python3 scripts/validate_project.py
python3 tools/security/check_git_privacy.py

# Requires the AArch64 cross compiler and isolated BlueZ headers.
make all BLUEZ_HEADERS=/path/to/isolated/bluez-include
make build/n71-bt-l2cap-echo-aarch64 BLUEZ_HEADERS=/path/to/isolated/bluez-include
```

The current finalization checks passed 1,584 offline tests, the HBPP audit and project validation. Each later check must be reported for its own revision. Local regression/build checks do not qualify hardware. The [GitHub Actions template](ci/verify.yml) is prepared but not activated remotely; no completed cloud CI run is claimed.

The public builder needs independent pinned source/build inputs and private calibration, and writes outside the public tree. The [operational guide](docs/OPERATIONS_AND_REPRODUCIBILITY.md) explains prerequisites and includes an offline build template. Private images, proprietary files and credentials are not published for convenience.

## Safety, power and data handling

Current experiments are RAM-only and avoid internal NAND writes. Preserve the known-good recovery payload and inspect candidate hashes/component differences before another supervised boot. A RAM-only design can still lose a session or require physical recovery.

Charging is presently a guarded 300 mA USB input lease lasting 3600 seconds. The input limit is not the measured battery current. Charging state, temperature and actual net current must be checked; automatic full-charge/endurance behavior is not yet qualified.

The working root Telnet shell is a temporary bench recovery interface. Authenticated SSH is still an open gate. See [remote-shell hardening](docs/REMOTE_SHELL_HARDENING.md); installing Kali tools does not close that gate.

Keep Apple firmware, touch calibration, WLAN NVRAM/tuning, MAC/serial/ECID, credentials, private keys/bonds, target inventories and raw captures private. Public results contain reviewed aggregate evidence. The pre-push hook checks Git privacy; operators must still review newly staged artifacts. Tool use must have an explicit authorized scope and bounded outputs.

## History, contributions and attribution

Historical reports are retained, including failures and uncertain causes. Their dated blockers describe those experiments, not the present state. Start with current status documents, then follow their evidence links. The [pre-refresh README](docs/history/README_BEFORE_2026_11_16_REFRESH.md), [hardware snapshot](docs/history/HARDWARE_STATUS_BEFORE_2026_11_16_REFRESH.md) and [roadmap snapshot](docs/history/ROADMAP_BEFORE_2026_11_16_REFRESH.md) preserve earlier detail.

Read [CONTRIBUTING.md](CONTRIBUTING.md), [firmware policy](docs/FIRMWARE_POLICY.md), [source/CI reproducibility](docs/CI_REPRODUCIBILITY.md) and the [issue alignment review](docs/ISSUE_STATUS_2026_11_16.md). Contributions should distinguish N71/S8000 from N71m/S8003 and OFFLINE/BUILD/HARDWARE evidence. No S8003 support claim follows from shared source files or dual-DTB packaging.

Original userspace toolkit material is MIT licensed. Experimental kernel sources retain their own SPDX terms, including GPL-2.0-only; external projects retain their licenses. See [LICENSE](LICENSE) and individual source headers.

Credits to HoolockLinux, Asahi Linux, Linux kernel contributors, checkra1n/PongoOS contributors, Omarchy-iPhone6s and the broader open-source iPhone/Linux community. This project builds on their work and preserves attribution in source and dated research notes.

### Keyboard usability follow-up

The owner confirmed initial touch typing works and requested larger keys. [Keyboard 0.3](docs/N71_KEYBOARD_03_2026_11_16.md) is now running with staggered QWERTY rows, larger full-width touch targets and glyphs, dedicated Shift/Delete/Return and a wide space bar. The previous 0.2 evidence remains dated; the fresh 0.3 integrated candidate is separately retained and still unbooted.

### Typography follow-up

[Typography 0.4](docs/N71_TYPOGRAPHY_04_2026_11_16.md) uses IBM Plex Mono Medium TrueType with baseline-aligned grayscale antialiasing and larger console text. The approved portrait keyboard geometry remains unchanged. The local font generator and source are public; font assets and binaries remain private. Earlier resource measurements apply to their dated revision, not a new typography benchmark.

**24 Nov 2026 power checkpoint:** A USB/charger boot-order race was measured on the real N71 (SN2400 rolled back at 6.319s; DWC2 rebound at 28s). A guarded detached charge worker and **private, unbooted RAM-only** next-boot candidate are ready for owner-attended acceptance. See [USB charging boot race evidence](docs/N71_S8000_USB_CHARGE_BOOT_RACE_2026_11_24.md). This is not yet a claim of reliable Linux charging or internal NAND access.
