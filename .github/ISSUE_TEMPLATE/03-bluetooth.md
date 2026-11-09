---
name: "Hardware: BCM4350C5 Bluetooth enablement"
about: "Resolve board-specific firmware and validate the detected HCI UART controller"
title: "[BT] Firmware and HCI bring-up for BCM4350C5 on N71"
labels: ["hardware", "bluetooth", "help wanted"]
assignees: []
---

## Observed baseline
The N71 Device Tree exposes `brcm,bcm4350-bt` on Apple serial1. The kernel already registers `/sys/class/bluetooth/hci0`.

A live iPhone 6s A9/S8000 boot returned:

```text
Bluetooth: hci0: BCM: chip id 110
Bluetooth: hci0: BCM: features 0x2f
Bluetooth: hci0: BCM4350C5
Bluetooth: hci0: BCM4350C5 (003.006.007) build 0000
Bluetooth: hci0: BCM: firmware Patch file not found, tried:
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM4350C5.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.apple,n71.hcd'
Bluetooth: hci0: BCM: 'brcm/BCM.hcd'
```

## Research questions
- What exact firmware build and module profile are appropriate for iPhone 6s N71?
- Is there a lawful procedure to extract the firmware from the user's own supported iOS restore image?
- Is there a need for extra NVRAM or calibration and a valid local controller address?
- Can the HCI controller reach operational state reliably after patchram load?

## Acceptance criteria
- [ ] Firmware provenance, revision and required format documented (no blob in repository).
- [ ] Driver loads the firmware without a missing-patch message.
- [ ] HCI information and enabled state validated.
- [ ] Discovery of a consenting test device succeeds.
- [ ] Controlled pairing, traffic and reconnection work.
- [ ] No false “Bluetooth working” claim based only on `hci0` existence.

## Collaboration rules
No copyrighted firmware or device-specific MAC, Bluetooth calibration or secrets in issues or commits.
