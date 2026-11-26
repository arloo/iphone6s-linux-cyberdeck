# Hardware-first roadmap — reviewed 2026-11-16

Latest layout acceptance (26 November): the five distinct userspace NAND Reads1,2,3,4,5 passed in a fresh authenticated epoch. The same-epoch native GPT header and all128 entries/full16KiB entry-array CRC validate on snapshot, CPU-target and userspace copies. One used APFS-type partition has a valid range; all-entry overlap checks pass. Exact queue deletion/shutdown/disable and retained-buffer stability passed. [Physical proof](N71_S8000_GPT_FULL_ARRAY_SUCCESS_2026_11_26.md) and [measured flags](N71_S8000_GPT_FULL_ARRAY_ACCEPTANCE_2026_11_26.json).

Next storage boundary: privately validate the selected APFS container header/superblock from its bounded in-partition sector pair, using another fresh attended epoch. The explicit four-pread APFS candidate is now exact-kernel/ARM64-built and privately packaged after1,984 host tests, with unchanged two-hour charging. NXSB/Fletcher64/container/physical-reference validation and private summaries are implemented. It has not booted or issued APFS Reads. [Physical gate and limits](N71_S8000_APFS_SUPERBLOCK_PAIR_TRIAL_2026_11_26.md), [image hashes](N71_S8000_APFS_SUPERBLOCK_PAIR_CANDIDATE_2026_11_26.json). Backup GPT, filesystem metadata/decryption/support, continuous block service, ring/buffer/error lifetime and independent DMA retirement remain open before mounting/persistence. The current full-GPT owner is closed/held and cannot accept another attempt.

Power: exact500mA/7200s native activation is observed with fresh positive-current qualification and21% Good/Charging postflight; physical two-hour expiry remains untested. The owner-selected source-backed15%/150000uAh, cell/thermal/eight-positive-current/native-VBUS gate was declared before the trial and passed. [Charging contract](N71_S8000_TWO_HOUR_CHARGE_PROFILE_2026_11_26.md).

Earlier layout checkpoint: CPU-only inspection of the previously retained LBA0/LBA1 targets found the valid native4KiB GPT header without new NAND I/O. That historical read count stays4; the later prefix trial above is a separate four-Read epoch. [Earlier CPU-only flags](N71_S8000_RETAINED_GPT_HEADER_OBSERVATION_2026_11_26.json).

Userspace probe acceptance (26 November): the corrected /dev-node ARM64 helper has completed four actual private NAND preads through the trusted Linux bio path, with all user copies and full-sector pair comparisons passing. Exact queue deletion and conservative retained-owner shutdown passed in a fresh epoch. General block service, arbitrary requests, ring/buffer lifetime/error handling, independent DMA retirement and persistence remain open. [Physical acceptance](N71_S8000_USERSPACE_PREAD_SUCCESS_2026_11_26.md).

Earlier storage candidate preparation (26 November): a default-off, root-only four-pread character probe is built and host-tested over the accepted trusted-bio transport. It qualifies local userspace initiation and returned-data lifetime without exposing a general block disk or reusing DMA buffers. The exact image has booted with strict identity/runtime checks, but 30% reserve defers its first userspace pread trial during separately guarded recovery. No new physical NAND trial is claimed. [Implementation, lifetime and physical gate](N71_S8000_USERSPACE_PREAD_PROBE_TRIAL_2026_11_26.md).

Latest storage checkpoint (25 November): the initial and final two namespace LBAs have each passed a separate four-bio physical Linux block trial, with private repeat equality and conservative retained-owner shutdown. The final pair extends addressing evidence, not whole-drive reliability. Broader request admission, ring/buffer lifetime and error handling must be qualified before read-only userspace disk service; independent DMA retirement and persistence remain open. [Final-sector proof](N71_S8000_RO_BLOCK_TAIL_PAIR_TRIAL_2026_11_25.md#physical-acceptance-last-two-lba-linux-bios).

**Storage status update (2026-11-25):** The real N71/S8000 temporary read-only gendisk completed four trusted Linux bios for NS1/LBA0,LBA1,LBA0,LBA1. All wire CQEs, independent guarded data, private returned-sector equalities and bounded RAM observations passed, followed by Delete SQ/CQ and shutdown/disable/BME-off. Software disk removed; DMA/owners retained. Next qualify broader request admission, ring/reuse/lifetime and error policy before usable userspace access. [Physical block-path evidence](N71_S8000_RO_BLOCK_BRIDGE_TRIAL_2026_11_24.md#physical-acceptance-four-linux-bios-over-real-nvme) and [canonical ledger](N71_S8000_STORAGE_ACCEPTANCE_2026_11_23.md).

The [temporary read-only kernel block bridge](N71_S8000_RO_BLOCK_BRIDGE_TRIAL_2026_11_24.md) has now physically passed its four-bio budget on qualified external power. Its userspace opens remain denied and all DMA retained. Arbitrary access and a usable disk remain later work.

Active target: **N71 / Samsung S8000**. N71m / S8003 remains deferred until compatible hardware is available.

## Achieved on physical N71

- RAM boot, framebuffer UI and USB recovery access.
- Automatic Z2 touchscreen initialization, genuine single-contact and simultaneous two-finger EVDEV input.
- Native BCM4350C5 Wi-Fi: PCIe, translated DART DMA, Linux MSI, brcmfmac, WPA2, DHCP, DNS, Internet and checked 1 MiB transfer.
- Managed Wi-Fi runtime with verified load/unbind/unload and complete power-domain cleanup.
- Bluetooth LE/classic discovery, controlled Dell pairing/bonding and 65,536-byte encrypted L2CAP transfer with Wi-Fi active.
- Battery telemetry and monitored charging with a finite guarded USB input lease.

## Next: make the verified session reproducible after boot

1. Assemble an owner-private RAM candidate containing the pinned Wi-Fi runtime, BlueZ/D-Bus, credentials and existing pairing state. Preserve the known-good recovery image and USB access.
2. Validate startup idempotence and service recovery in the current session, then inspect the offline image/component differences.
3. Qualify a supervised new RAM boot: touch, USB, charging, automatic Wi-Fi association/DHCP and restored Bluetooth controller/bond state. Startup source alone does not satisfy this gate.
4. Repeat the encrypted Dell transfer after service restart and after a new boot, with native Wi-Fi traffic in parallel.

The Dell is the currently available controlled Bluetooth peer. Keyboard/mouse HID tests are deferred until a real peripheral is available. A successful Dell L2CAP test must not be relabeled as a HID or audio result.

## Remaining qualification

- Authenticated key-only SSH and Telnet closure **passed in the current RAM session**; fresh-boot recovery and host-key continuity are pending: [physical cutover](N71_USB_SSH_CUTOVER_2026_11_16.md).
- Touch edge accuracy, latency, stuck-contact checks and repeated-boot endurance.
- Longer concurrent Wi-Fi/Bluetooth traffic, 5 GHz association, reconnect/recovery and idle behavior.
- Power management: suspend/resume and sustained charging/full-charge behavior. The current charging lease expires after one hour.
- HID input, A2DP playback and LE application profiles when appropriate devices are available.
- GitHub Actions activation remains separate from local tests; the template is prepared, no remote CI success claimed.

See [current state](PROJECT_STATE_2026_11_16.md), [hardware matrix](HARDWARE_STATUS.md), [machine-readable results](../manifests/test-matrix.json) and the [historical roadmap](history/ROADMAP_BEFORE_2026_11_16_REFRESH.md).

## Product delivery beyond hardware bring-up

The target remains the handheld cyberdeck described in [product architecture](CYBERDECK_VISION_AND_ARCHITECTURE.md). Successful radios and touch are prerequisites, not the whole product.

| Workstream | Entry point | First acceptance result |
|---|---|---|
| Integrated boot | [#4](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/4) | Reproduce the verified session after a fresh RAM boot |
| Recovery security | [#7](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/7) | Key-only USB SSH and tested Telnet cutover |
| Touch console | [#6](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/6) | On-screen keyboard, terminal and job stop/results using touch only |
| Targeted Kali | [#5](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/5) | Signed ARM64 subset, controlled TCP assessment and bounded capture on the phone |
| Power/endurance | [#8](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/8) | Measured thermal/charging/idle policy and agreed endurance window |

The Kali environment retains the tested N71 kernel. Package installation, monitor mode, injection, USB host accessories and HID gadget capability have distinct prerequisites and must never be inferred from each other. See [Kali gates](KALI_ARM64_INTEGRATION.md) and [proposed package profiles](../manifests/kali-tool-profiles.json).

The original touch/Wi-Fi/Bluetooth issues [#1–#3](ISSUE_STATUS_2026_11_16.md) now track remaining qualification, with completed bring-up explicitly checked. **Server-side AI briefings (mail/calendar/authorized messaging), a touch TODAY view and standalone writable internal data storage are mandatory product requirements**, not optional cosmetic integrations. [Detailed current acceptance and storage findings](COMPANION_BRIEFING_AND_STORAGE_2026_11_16.md).

## Current-session progress after the product review

Startup idempotence and controlled recovery of four userspace daemons now pass. The native dashboard/PTY/on-screen keyboard runs on the phone, with native selftest and framebuffer-readback checks; real finger typing remains an acceptance task. A separate integrated RAM candidate is built and pinned, not booted. Display reduction and a short resource/network observation are recorded in [session evidence](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md). Kali, endurance, suspend and **fresh-boot** SSH recovery remain unqualified. Subsequent current-session SSH cutover, native TODAY briefing and Dell-backed ext4 NBD laboratory read/write have since passed; see [companion/storage scope](COMPANION_BRIEFING_AND_STORAGE_2026_11_16.md).
