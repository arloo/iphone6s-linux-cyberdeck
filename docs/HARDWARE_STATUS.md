# Hardware status — 2026-11-16 baseline, storage/USB updated 2026-11-26

Physical target: **iPhone 6s N71, Samsung A9 / S8000**. Kernel: `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`. All observations concern RAM Linux; no persistent OS installation or NAND write is claimed.

| Subsystem | Physical evidence | Current qualification |
|---|---|---|
| Boot | checkm8/PongoOS/m1n1 chain and Linux USB re-enumeration | PASS |
| Framebuffer | 750 × 1334, 32 bpp; CYBERDECK UI rendered | PASS |
| USB | Direct NCM and authenticated, strictly pinned USB SSH verified on attended RAM boots, 24 November | PASS for the tested USB/SSH path; this does not inventory every exposed service |
| Touch | Automatic firmware/calibration setup, real single-contact and simultaneous two-finger EVDEV events | PASS for tested contacts; endurance/edge/latency open |
| Wi-Fi | Real PCIe BCM4350C5 `14e4:43a3` on brcmfmac, translated SID0 DMA, Linux MSI message 8 / AIC 264 | PASS for native network operation |
| Wi-Fi traffic | WPA2 authentication, DHCP, WLAN default route, DNS, Internet, 1 MiB transfer with verified SHA-256 | PASS at 2412 MHz; 5 GHz not tested |
| Wi-Fi lifecycle | Managed runtime load/unbind/unload, seven power domains restored | PASS; automatic reboot restoration not tested |
| Bluetooth UART/HCI | Genuine BCM4350C5 patchram build 0825, zero transport errors | PASS |
| Bluetooth LE | 12 devices discovered | PASS for discovery; no LE GATT application claim |
| Bluetooth BR/EDR | Dell discovery, Paired and Bonded state, 256 × 256-byte exact echo | PASS for controlled pairing and encrypted L2CAP transport |
| Radio coexistence | Wi-Fi remained WPA_COMPLETED and Internet traffic worked during Bluetooth transfer | PASS for the short concurrent trial; no endurance claim |
| Bluetooth HID | No keyboard/mouse available | NOT TESTED; deferred until a peripheral is available |
| Bluetooth audio | No playback/profile test | NOT TESTED |
| Battery | Gauge telemetry; external 5 V source has physically passed bounded 500 mA input-only charging/rollback; positive net current measured | Bounded charging PASS; full charger driver/durability and abrupt SOC transition remain open; reserve needs voltage/current/RC-FCC checks |
| Internal storage | Five actual userspace NAND Reads validated the same-epoch primary GPT header and all128 entries/full array CRC; one used APFS-type partition, all ranges/overlaps valid | Complete primary GPT PASS; backup GPT/filesystem/general service/reuse/persistence open; interfaces removed, all DMA retained |
| Baseband | No qualification | Telephony unqualified |
| Suspend/resume | No qualification | NOT TESTED |
| New-boot connectivity | Owner-attended RAM boots reached configured USB/authenticated SSH with exact kernel/module/runtime hashes, 24 November | PASS for attended USB/SSH; automatic recovery and new-boot radio endurance remain open |
| N71m / S8003 | No compatible hardware | NOT TESTED across all subsystems |

Bluetooth security level 2 requires encryption; it does not prove MITM-authenticated pairing. The optional BlueZ privacy-setting request was rejected; controller address privacy remains unqualified. Pairing keys are private RAM state and have not been proven to survive a new boot.

Evidence: [Wi-Fi](N71_NATIVE_WIFI_PHYSICAL_PASS_2026_11_16.json), [Bluetooth](N71_BLUETOOTH_PHYSICAL_PASS_2026_11_16.json), [Bluetooth runtime](N71_BLUETOOTH_RUNTIME_2026_11_16.md), [touch](N71_Z2_AUTOINIT_PHYSICAL_MULTITOUCH_PASS_2026_11_11.md), [engineering assessment](PROJECT_STATE_2026_11_16.md). The [older hardware snapshot](history/HARDWARE_STATUS_BEFORE_2026_11_16_REFRESH.md) is historical only.

## Current-session UI and recovery follow-up

The native shell dashboard/PTY/keyboard is running with reviewed framebuffer readback and a passed native synthetic-key/real-PTY selftest. Human typing acceptance remains open. Current-session service recovery passed, including private Bluetooth bond reload and a verified 4 MiB WLAN transfer. Display brightness is 1023/2047; schedutil and WLAN power save remain active. See [detailed evidence and limits](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md).

Latest storage evidence: [complete primary GPT physical proof](N71_S8000_GPT_FULL_ARRAY_SUCCESS_2026_11_26.md), [sanitized full-array acceptance](N71_S8000_GPT_FULL_ARRAY_ACCEPTANCE_2026_11_26.json), [physical GPT entry-prefix proof](N71_S8000_GPT_PREFIX_PAIR_SUCCESS_2026_11_26.md), [sanitized prefix acceptance](N71_S8000_GPT_PREFIX_PAIR_ACCEPTANCE_2026_11_26.json), [physical local userspace preads](N71_S8000_USERSPACE_PREAD_SUCCESS_2026_11_26.md), [sanitized userspace acceptance](N71_S8000_USERSPACE_PREAD_ACCEPTANCE_2026_11_26.json), [physical final-sector Linux block path](N71_S8000_RO_BLOCK_TAIL_PAIR_TRIAL_2026_11_25.md#physical-acceptance-last-two-lba-linux-bios), [sanitized final-sector acceptance](N71_S8000_RO_BLOCK_TAIL_PAIR_ACCEPTANCE_2026_11_25.json), [physical Linux block path](N71_S8000_RO_BLOCK_BRIDGE_TRIAL_2026_11_24.md#physical-acceptance-four-linux-bios-over-real-nvme), [sanitized block acceptance](N71_S8000_RO_BLOCK_BRIDGE_ACCEPTANCE_2026_11_25.json), [preceding direct-Read repeatability](N71_S8000_READ_SERIES_ACCEPTANCE_2026_11_24.json), and [canonical ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md). No raw sector content/hash is published.

Current full-GPT candidate is physically booted/accepted after1,974 host tests. Native500mA/7200s charging activation and positive net current are observed; physical two-hour expiry remains pending. [Accepted storage/power boundary](N71_S8000_GPT_FULL_ARRAY_SUCCESS_2026_11_26.md). The next private APFS metadata pair requires a fresh attended epoch.
