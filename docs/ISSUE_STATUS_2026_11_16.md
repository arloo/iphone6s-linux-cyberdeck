# GitHub issue alignment — 2026-11-16

All three original issues were read together with their comments. Their previous bodies still described the November 9 baseline. The issue bodies/titles are now updated remotely; historical comments remain untouched as dated evidence.

The original issues remain open because each contains real uncompleted qualification work. Completed bring-up steps are checked, rather than repeatedly reported as missing. No keyboard/mouse is currently available; the genuine HID test is explicitly deferred, while the Dell is the controlled pairing/data peer.

| Issue | Area | Current purpose | Remote state |
|---|---|---|---|
| [#1](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/1) | [TOUCH] | Multitouch works; qualify edges, latency, endurance and resume | Open |
| [#2](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/2) | [WIFI] | Native networking works; qualify reconnect, 5 GHz and endurance | Open |
| [#3](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/3) | [BT] | Dell pairing/encrypted echo works; qualify recovery/HID/profiles | Open |
| [#4](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/4) | [BOOT] | Integrate and physically qualify automatic RAM startup | Open |
| [#5](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/5) | [KALI] | Build and measure selected Kali ARM64 tools on the phone | Open |
| [#6](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/6) | [UI] | Deliver touch-only terminal, keyboard and tool-job workflow | Open |
| [#7](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/7) | [SSH] | Verify key-only recovery SSH and retire Telnet after cutover | Open |
| [#8](https://github.com/arloo/iphone6s-linux-cyberdeck/issues/8) | [POWER] | Qualify lease management, idle, thermal and endurance behavior | Open |

## Responsibility boundaries

- #1–#3 own peripheral-specific behavior and endurance. A display demo, ordinary WLAN connection or L2CAP echo does not qualify unrelated modes.
- #4 owns integrated boot ordering, private provisioning, recovery and boot-level acceptance; it coordinates, rather than duplicates, the component evidence.
- #5 owns signed Kali packaging, ABI/resource gates and actual phone tool execution. The profile manifest is proposed, not a completed package installation.
- #6 owns the handheld operator workflow and keeps a real touch-only path available without an external keyboard.
- #7 owns authenticated remote access; matrix status stays blocked until physical cutover evidence exists.
- #8 owns power/thermal policy and long-duration measurements. A successful lease renewal is not permanent power-management support.

Priority is to prepare integration/recovery and the minimal usable console, then qualify a measured Kali subset. HID testing resumes when a real peripheral is available. S8003 remains outside active hardware experiments.

Versioned records: [reviewed issue bodies](../manifests/issue-alignment-2026-11-16.json), [applied remote issue map](../manifests/issue-live-state-2026-11-16.json). These are dated snapshots; future remote edits require a new review, not an assumption that this snapshot is live forever.

## Later current-session progress

Issues #3, #4, #6 and #8 now also record verified service recovery/bond reload, the running native UI/PTY and the measured display/resource profile. The integrated candidate is built but remains unbooted, and manual finger typing is pending. See [session evidence](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md) and [applied issue progress](../manifests/issue-session-finalization-2026-11-16.json).
