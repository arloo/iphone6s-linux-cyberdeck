# N71 session finalization: native shell UI, service recovery and balanced display

2026-11-16, physical iPhone 6s N71 / Samsung S8000, current batt2 RAM kernel. [Machine-readable observations](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.json).

## Delivered on the phone

A new static AArch64 framebuffer/EVDEV application now runs in the existing RAM session. It provides four views: Home, Terminal, System and Tools. Home reads battery state/current/temperature, native WLAN carrier, Bluetooth-controller presence, CPU utilization and available RAM. Presence/link labels deliberately do not imply HID profile support or independent WPA authentication.

Terminal opens a real local /bin/sh through a PTY. Its on-screen keyboard includes letters, digits, shift, a symbol layer, space, backspace, enter, Ctrl-C and Tab. Clear View clears the visible buffer, not a running job. This is a small ASCII TERM=dumb console with a rolling 48 × 24 character view, not a full VT emulator, history/scrollback browser or desktop terminal. It inherits the bench RAM environment's privileges.

System offers reversible display levels (35%, 50%, 74%) and an exit action. Tools accurately identifies the available shell/connectivity runtime and the uninstalled Kali subset; it does not offer fake launch buttons. SIGTERM/exit attempts to restore framebuffer contents and the prior virtual-console display mode. KD_GRAPHICS prevents the kernel virtual console from drawing text over the application; framebuffer readback was visually checked after this adjustment.

## Validation and exact limits

| Check | Result | Limit |
|---|---|---|
| Host build | Warning-clean static ARM64 build; host ASan/UBSan selftest passed | Build/host checks are not physical input proof |
| Native phone selftest | Simulated key hit dispatch typed a controlled echo command through a real phone PTY; expected output returned | Synthetic dispatch, not a person typing on glass |
| Device probe | Correct 750 × 1334 framebuffer, readable backup and matching pixel-coordinate touchscreen | Does not measure touch accuracy/latency |
| Live app | Process running and framebuffer content read back/reviewed | New UI has not received operator optical/manual-touch acceptance |
| Startup idempotence | Two consecutive calls retained all four existing daemon PIDs | Current session, not a reboot |
| Controlled recovery | BlueZ, private D-Bus, WPA and DHCP daemons stopped with identity guards and restored by the startup script | No driver unload or kernel reboot |
| Post-recovery networking | Fresh DHCP state/WPA_COMPLETED and a checked 4 MiB WLAN transfer | Short controlled test |
| Post-recovery Bluetooth | 65,536-byte encrypted Dell echo, correct peer, zero HCI transport errors | No HID/audio/GATT or reboot claim |

The new UI still needs a real person to open Terminal, type a harmless command, use backspace/symbols and return Home. Existing physical multitouch evidence establishes the input foundation but cannot substitute for this new application workflow.

## Battery and performance decisions

The CPU was already using apple-cpufreq with schedutil and a 300–1800 MHz range. These settings were preserved. Native Wi-Fi already reported power save on; it was preserved. The HCI parent's runtime-PM interface reported unsupported, so no unsupported forced suspend policy was applied.

Display brightness was reduced from 1505/2047 (about 74% of the register range) to 1023/2047 (about 50%). The original value is saved privately for explicit restoration. Register percentages are not measurements of luminance or battery-power savings.

The UI polls input/PTY with a bounded wait, samples telemetry every two seconds and redraws only when content changes, capped at ten redraws per second. In one 15-second current-session observation it used 8,832 KiB RSS and 0.31% of aggregate CPU capacity; overall system busy time was 0.96%. A controlled Bluetooth validation was also being performed, so this is not a rigorously isolated idle benchmark.

Battery temperature in that sample was 33.7 °C at 40%. The sampled net battery current was -13 mA, while other observations showed positive charging current. Do not infer autonomous battery life or sustained positive charge from a single snapshot. The existing guarded 300 mA input lease remains finite (3600 seconds); no permanent charger-limit change, overclock or full-charge qualification was introduced.

The balanced session's 4 MiB native WLAN transfer matched SHA-256 and the intended phone WLAN peer. Six Internet pings returned without loss, average 10.06 ms. This confirms short functional operation with power save and UI active; it is not a sustained throughput benchmark or a controlled before/after performance gain.

## Integrated RAM candidate prepared, not booted

A separate owner-private 25,066,924-byte candidate bundles the tested connectivity runtime, original private firmware/configuration, current Bluetooth bond state and the new shell UI. Its private runtime contains 55 regular files. m1n1/bootargs, both DTBs and the compressed kernel are unchanged; original CPIO entries are unchanged except init, plus the new pinned runtime/bootstrap files.

The private runtime manifest and full payload hashes were checked. Original USB recovery continues if integrated startup fails. The new hook extracts only a hash-pinned operator-built archive, starts connectivity, applies the display setting and schedules the UI after init handoff. The source hook itself is not proof of a successful new boot.

The private handoff command defaults to status, verifies the exact image hash/size and refuses sending while the known-good Linux USB gadget is present. Physical owner DFU/Pongo preparation and supervised USB transfer remain required. A 25 MB candidate's Pongo transfer is not yet qualified. No NAND access or in-place replacement of the recovery image occurred.

## Sources and next acceptance

- [Native application](../examples/cyberdeck-shell/) and [host regression tests](../tests/test_cyberdeck_native_shell.py).
- [Current-session connectivity startup](../scripts/n71_connectivity_autostart.sh), [display adjustment](../scripts/n71_balanced_display.sh), [new candidate boot hook](../scripts/n71_integrated_ram_startup.sh).
- [Product architecture](CYBERDECK_VISION_AND_ARCHITECTURE.md), [Kali plan](KALI_ARM64_INTEGRATION.md) and [open issues](ISSUE_STATUS_2026_11_16.md).

Next: manual UI typing acceptance, supervised integrated RAM boot and postflight, then authenticated recovery access and a measured Kali ARM64 subset. Keyboard/mouse testing remains deferred until hardware is available. Charging endurance, suspend/resume and long-run radio performance remain open.
