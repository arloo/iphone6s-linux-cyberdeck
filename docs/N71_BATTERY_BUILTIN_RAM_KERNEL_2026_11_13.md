# N71 battery observation kernel — 13 November 2026

Status: ARM64 build, private RAM image verification, physical boot, battery telemetry and full PERST-held stage-8 postflight PASS. Charging is observed as net discharge in the tested Dell USB setup.

The owner observed shutdown after a Linux session, followed by an iOS battery indication changing from 44% to 2%. The owner subsequently reported 14%. These observations do not establish the cause of shutdown, charging failure, or a defective battery. No evidence establishes an Apple security restriction.

The previous configuration built the HDQ battery gauge and SN2400 HDQ line mux as modules. Their nodes already exist in the Samsung DTB. The new isolated build changes exactly:

| Symbol | Previous | Diagnostic build |
| --- | --- | --- |
| CONFIG_BATTERY_BQ27XXX_HDQ_UART | m | y |
| CONFIG_MUX_SN2400 | m | y |
| CONFIG_LOCALVERSION | empty | -n71-batt1 |

Release: `7.3.0-rc1-n71-batt1-g68aadac820d0-dirty`.

Linux Image SHA256: `e3203ca17c9d2592fda659311e67139c0bfbfa90cccb31d7c1a57464e1cf25d7`.

Private RAM image SHA256: `45999f495004794f6c9c7ff9babde6b5040419b400d56fd7ff395eb70d42771b`, size 13,199,997 bytes. The image contains private firmware and is not distributed.

The previous loader and both DTBs are byte-identical. Every existing initramfs entry and its content is preserved. Added files are the power_supply observation script, single-syscall module loader, matching native PMIC GPIO module, and matching PERST-held port1 module. Both new modules' vermagic matches the diagnostic kernel. Existing guard tooling for the previous kernel remains dormant and must not be used with the new release.

The earlier touch changes and wireless software support are retained. Port1 is not automatically activated at boot. The validated READY experiment remains a manually armed loadable module, with PERST held low, strict packed DART1 zero-state gate, and reverse cleanup. No enumeration or DMA isolation is claimed.

`tools/build-n71-battery-kernel.sh` builds from an existing matching owner-local tree and build directory into a new directory. `tools/n71-battery-status.sh` observes power_supply properties without writing charging controls. It reports an explicit UNKNOWN result if no supply registered.

The HDQ gauge driver reads the gauge. Its SN2400 mux provider temporarily writes the HDQ ownership control and returns ownership to the state observed at probe. This is not a charger-management driver: built-in gauge support does not prove that charging works. The first physical check must inspect probe logs, registered supplies, voltage, current, temperature, state of charge and charging status, then compare a second timestamped sample. Sysfs observations should precede further PCIe experiments.

Validation: kernel Image/modules build, exact three-symbol config diff, matched module vermagic, unchanged loader/DTBs/original CPIO entries, shell syntax, and git whitespace checks passed. Physical boot remains pending while the phone is in iOS charging. The prior stage-8 USB postflight remains incomplete.

## Pongo retry path

The owner supplied earlier successful runs through `scripts/pongo-once-without-mfi-reload.sh run`, followed by the pinned RAM-send helper. A later direct palera1n invocation remained at "Sending pongo image" before interruption. A read-only host check then found the Apple MFi fast-charge module loaded while the temporary runtime policy still existed. This identifies a difference worth controlling; it does not prove the cause of the failed attempt or battery discharge.

Use the existing wrapper for the next supervised Pongo attempt. Its `run` mode requires an administrative local terminal, verifies the pinned Pongo binary, prevents host MFi module auto-loading, and verifies module removal before launching palera1n. Its `restore` mode restores the host driver after testing. No host policy is changed by status checks.

`scripts/n71-battery-builtin-pongo-ram-smoke.sh send` replaces the earlier PMGR-only image sender for this diagnostic build. It pins the new image's hash and size, refuses sending over an existing Linux gadget, requires the Pongo gadget and a local administrative shell, and requires both exact upload acknowledgement and a new Linux USB gadget before reporting handoff success. A Pongo-tool exit status alone is insufficient. The helper has been installed in the owner workspace; no phone transfer has yet been performed.

Helper verification: shell syntax, byte-identical workspace/repository copies, successful local image-pin status check, and same-size corrupt-image rejection before USB handoff passed. Physical retry and battery observations are pending.

## Physical diagnostic boot and completed postflight

The new pinned RAM image booted as `7.3.0-rc1-n71-batt1-g68aadac820d0-dirty`, with Linux USB `05ac:4142`. The built-in SN2400 mux probed with HDQ control `0x00`, idle state 0; the BQ27540 UART driver established its HDQ link and registered `bq27540-0`.

| Approximate uptime | State of charge | Gauge status | Current | Voltage | Temperature | Remaining charge |
| --- | --- | --- | --- | --- | --- | --- |
| 58 s | 20% | Discharging | -150 mA | 3.739 V | 34.1 C | 246 mAh |
| 150 s | 19% | Discharging | -154 mA | 3.713 V | 33.6 C | 242 mAh |
| 359 s postflight | 19% | Discharging | -231 mA | 3.671 V | 32.2 C | 233 mAh |

These observations establish net battery discharge during the tested USB-connected Linux session. They do not identify the charger failure mechanism or explain the earlier iOS percentage jump. Gauge telemetry is working; sustained charging remains unverified. The included SN2400 driver controls HDQ ownership only, not charging setpoints.

Matching PMIC GPIO support and the privately verified USI Bluetooth patchram restored HCI firmware build 0825. HCI was UP/RUNNING with cmd_tx=524, evt_rx=524, err_rx=0 and err_tx=0 before and after the port1 test. No pairing or new RF scan was attempted.

Both an unarmed module load/unload and a single armed stage-8 test completed on the diagnostic kernel. The matching module SHA256 is `9d62a4089e7146668c8e9b94a07c4666a80d384e47ae8722d23289710dd9aa94`. Port1 READY held for 25 samples over 250 ms; packed DART1 TCR read `0x00000000`. PERST stayed low throughout activation. Cleanup restored PERST raw `0x00072200`, WLAN GPIO10 low, original COMMON controls, and protected port controls. Module removal returned 0; the temporary node and module were absent afterward. All seven PCIe domains were OFF, no PCI endpoint enumerated, USB and touch input registration remained present, and HCI retained zero errors. Touch initialization reported Type-1 setup and AF completion; no new physical-coordinate acceptance test was performed in this boot.

This completes a new full postflight; it does not retroactively complete the previous battery-interrupted cycle or prove DART DMA isolation. PERST release, physical enumeration and native Wi-Fi remain pending.

`tools/n71-battery-log.sh` provides a finite, timestamped gauge log for a supervised comparison between Dell USB and a wall supply while keeping this same Linux boot. It does not write charging controls, refuses overwriting an existing log, samples at most 60 times at intervals of at most 10 seconds, and stops if state of charge drops below 15% or temperature reaches 45 C. It is transferred into RAM after boot; the pinned image itself is unchanged. A physical supply comparison has not yet been performed.

## Wall-supply comparison in the same Linux boot

The owner moved the running phone from Dell USB to a wall charger and back. Linux remained on the same diagnostic boot; the USB controller logged its next host enumeration at uptime 1134.5 s. The finite RAM logger completed all 60 samples over 600.15 seconds (uptime 609.43 through 1209.58 s). The owner-reported wall-supply interval is included; exact unplug and wall-attachment timestamps and charger specifications were not independently recorded.

| Measurement | Recorded result |
| --- | --- |
| State of charge | 18% to 16% |
| Remaining charge | 221 to 194 mAh |
| Status | Discharging in 60/60 samples |
| Current | -319 to -150 mA; median -159 mA |
| Positive-current samples | 0/60 |
| Reading after return to Dell | 16%, -160 mA, 3.594 V, 30.5 C |

The phone showed net discharge throughout the observed test, including the owner-reported wall-charger phase. Battery telemetry remains operational. This result does not distinguish absent charger input, input insufficient to cover the load, charger configuration/watchdog behavior, or other hardware causes; it does not establish that every Linux setup is unable to charge. The next extended hardware session requires recharging in iOS or an independently verified source of sustained net charge. No charger setpoints, flash storage, PCIe reset release or DART writes were attempted in this comparison.

The complete non-identifying TSV and summary are retained privately in the owner workspace. USB access recovered and HCI remained UP/RUNNING with zero RX/TX errors on return to Dell. The diagnostic kernel, private RAM image and module source are unchanged.

## Input-limit restriction located; charging trial pending recharge

Charging work now takes priority over further PCIe tests. A physical read-only SN2400 snapshot read `07=b9`, `09=00`, `0d=ff`, `10=04`, `1d=00`. The zero input setting corresponds to 90 mA in the upstream SN2400 driver; original N71 Apple driver arithmetic independently corroborates the scale. A new default-inert [input-limit trial module](../experimental/power/README.md) is built for the current diagnostic kernel, with 300 mA default and timed rollback. The actual arm request was refused at 9% before changing the input limit. Battery recharge is required before physical current validation; a working charging fix is not yet claimed.
