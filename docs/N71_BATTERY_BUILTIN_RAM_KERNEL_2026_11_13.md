# N71 battery observation kernel — 13 November 2026

Status: ARM64 build and private RAM image verification PASS; physical boot and battery readings PENDING.

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
