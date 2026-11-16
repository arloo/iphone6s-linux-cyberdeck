# Companion intelligence and persistent storage — N71 product requirements

Reviewed: 2026-11-16. This document records two **non-optional product goals** beyond hardware bring-up: a privacy-preserving intelligent morning briefing, and reliable writable persistent storage for the Linux cyberdeck. The currently validated implementations are explicitly narrower than those goals.

## Initial user workflow: AI morning briefing

On weekdays at **08:45 Europe/Rome**, and on explicit refresh, a trusted Linux companion service collects:

1. **Email:** authenticated, read-only Gmail recent-inbox snapshot, sender, subject, time and bounded content, with thread/follow-up provenance.
2. **Calendar:** authorized Google Calendar events for the next seven days; display agenda, conflicts, travel/context and upcoming obligations. Other providers require explicit adapters.
3. **Messaging:** the operator uses **personal WhatsApp Messenger**, not Business. Meta offers no official personal-chat inbox API. The preferred future companion connector is **Beeper Desktop On-Device** on the Dell, using its documented LOCAL read-only chat/message APIs, with explicit owner-approved linked-device setup. Our backend now has an offline-tested, **disabled-by-default** Beeper reader and a private per-contact/group exclusion policy; no account is connected. The older KDE notification watcher is incomplete and inactive. No daily export/import workflow will be implemented. See [personal WhatsApp source and exclusion plan](WHATSAPP_PERSONAL_COMPANION_2026_11_16.md).
4. **Projects, notes and existing tasks:** explicit allowlisted inputs, with per-item source attribution.

The **companion** performs filtering, bounded data preparation and AI analysis using the server-side OpenAI Responses API (`store:false` currently used by the pre-existing private DECK backend). The output is structured into a prioritized overview, actions, calendar context and suggested tasks, each with provenance, timestamps and source-completeness indicators. Source text is untrusted, never commands. No email sending, message replying or calendar edits happen without a separate explicit approval.

The **phone** receives **only** a reduced already-analyzed JSON and a readable text rendering over authenticated, pinned host-key, USB-only SSH. The first tested command is `experimental/briefing/n71_push_briefing.py --push` (default is dry-run). Its private credentials and local original source stay on the Dell. Current phone files are `/run/cyberdeck/today.json` and `/run/cyberdeck/today.txt`, both mode 0600 and **volatile**. A new fifth `TODAY` tab in the native touchscreen application opens the reduced text preview; a button opens the full report in the local PTY terminal. Today/PTY phone runtime is qualified at the process level; direct owner finger interaction and fresh boot are still pending.

The current backend already generated a structured AI briefing at **2026-11-16 09:33 CET** from connected Gmail/Calendar; WhatsApp monitor was not active and supplied zero previews. The authenticated manual push succeeded on the physical phone, correctly tagged `cached=true` for its age. **Never represent this as comprehensive WhatsApp analysis.** A Dell user-level systemd delivery timer is installed for weekdays **08:55, 09:45 and 12:00 CET/CEST**; a controlled service execution on 2026-11-16 returned success. The timer only delivers the backend's cached AI result; it does not itself request a fresh model analysis. New-boot host-key rotation is fail-closed until trusted re-pinning.

An owner-private integrated RAM payload including connectivity, the new TODAY UI and RAM-local USB SSH provisioning is **offline built** (26,151,049 bytes) with preserved base kernel/DTBs/m1n1. It has **not** been transferred through Pongo or physically reboot-qualified; the existing working phone session is retained.

### Remaining briefing acceptance gates

- Connect an authorized personal WhatsApp account to a separately installed **Beeper On-Device** client if approved. Use only documented local GET methods, apply exact local contact/group exclusions before model ingestion, and qualify the true indexed-history coverage. Do not claim an official Meta personal API or implement manual export/import.
- Add conflict/deduplication review, explicit urgency/source confidence and unread/reply-needed analysis without inventing actions or due dates.
- Run a scheduled **companion-side** refresh and push after 08:45; preserve an on-demand trigger; report last successful update and offline status.
- Replace USB-only delivery with an independently authenticated, encrypted Wi-Fi path for untethered operation; rotate keys safely after each new RAM boot.
- Display and scroll source-linked actions on glass, allow controlled refresh and retain an encrypted offline cache once persistence is qualified.
- Store API secrets and OAuth/WhatsApp session state **only** in the protected companion environment; never in public Git, firmware images or raw device screenshots.

## Storage goal: independent, writable persistent `/data`

### Verified current environment

The N71/S8000 phone currently runs a writable **volatile RAM rootfs**. No physical NVMe, eMMC, UFS or other internal mass-storage device appears in `/proc/partitions`; the `mtd0/mtd1` entries are the RAM-backed m1n1 log/ADT, **not** iOS mass storage. Loop/zram and sixteen `nbdX` devices exist, and ext4 is supported.

**Physical experiment, 2026-11-16:** a dedicated, freshly formatted **64 MiB** ext4 file image on the Dell was exported on the **isolated USB gadget address** via a bounded NBD oldstyle proof of concept. A static ARM64 client bound to USB attached it as `/dev/nbd0`. The phone mounted ext4 in read-only mode, detached cleanly, then in read-write mode wrote a small test file and synchronized it. After a clean unmount/detach, the Dell's offline ext4 reader recovered the exact file. No iPhone storage controller, firmware partition, APFS volume, NVMe or NAND was read or written. The NBD device was detached at the end.

This demonstrates **read/write to remote Dell-backed storage**, not autonomous iPhone storage. The experimental export is **plaintext**, USB-only, single-client and oldstyle, with no reconnect recovery, journal/power-failure endurance or secure key management. **Do not store personal mail, chat, credentials or production data on the test image.** The current image is a lab artifact, not an automatic startup dependency.

### Final internal storage acceptance criteria

- Independently identify and enumerate the **internal Apple storage path** with a reviewed N71/S8000 PCIe port-0 controller implementation. The Wi-Fi port-1 result does **not** prove internal storage can be safely driven by Linux.
- First validate **read-only** capabilities, size, partition map, controller reset and DMA isolation; prohibit accidental writes to firmware, iOS or APFS structures. Do not assume APFS encryption can be transparently mounted by Linux. The current kernel has `CONFIG_NVME_APPLE=y`, but its upstream Apple NVMe driver only lists `apple,t8015-nvme-ans2`, `apple,t8103-nvme-ans2` and generic `apple,nvme-ans2` matches; no physical N71/S8000 storage block device is enumerated. The board's separate `apcie` port-0 `s3e` path needs its own reviewed, isolated driver study. Enabling the existing NVMe Kconfig option is not a read/write solution.
- Obtain a validated full recovery/backup strategy, explicit operator approval for repartitioning and an exclusive, Linux-owned filesystem or alternative independently supported medium.
- Demonstrate actual writable ext4 or another suitable filesystem on intended storage; checksum data after unmount, disconnect and **fresh boot**; test recovery and power-loss behavior.
- Provide secure at-rest storage, clear key ownership, bounded writes, health telemetry, quotas, metadata durability and a robust `/data` mount that does not block recovery.
- Make `/data/briefings`, `/data/projects`, `/data/results`, `/data/captures` and `/data/kali` available only after the storage test gates pass. No claim of internal-storage read/write support is made yet.

## Integration order

1. Preserve current known-good USB SSH recovery and verified touch/WLAN/BT runtime.
2. Finish native TODAY UI user acceptance and the supervised integrated RAM boot.
3. Finish Beeper On-Device account onboarding, verify strict contact/group exclusions, and connect the optional local reader to scheduled AI briefings without exposing raw conversations to the Cyberdeck.
4. Extend isolated NBD proof into a guarded temporary workspace while developing and independently qualifying the internal storage controller; **do not** bridge the plaintext NBD service to WLAN.
5. Qualify standalone persistent internal `/data`, encrypted private cache, Kali data and long-duration charge/power controls.
