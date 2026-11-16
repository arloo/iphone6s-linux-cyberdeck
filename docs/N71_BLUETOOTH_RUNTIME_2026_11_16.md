# N71 Bluetooth physical validation — 2026-11-16

The existing BCM UART HCI transport and genuine device firmware were used unchanged. A private D-Bus and BlueZ runtime was staged in RAM; no host packages were installed and the phone was not rebooted.

Verified on the N71 Samsung S8000:

- LE discovery saw 12 devices.
- Classic inquiry discovered the controlled Dell peer.
- BlueZ reported Paired and Bonded.
- A controlled L2CAP echo at PSM 0x1001 exchanged 256 packets of 256 bytes with exact payload checks, totaling 65,536 bytes.
- Both endpoints required BT_SECURITY_MEDIUM; the server reported level 2 and verified the expected peer.
- The controlled Dell test passed twice in the same RAM session, each with a 65,536-byte verified echo. No daemon restart or reboot occurred between the trials.
- HCI transport errors remained zero. Native Wi-Fi stayed WPA_COMPLETED and Internet traffic succeeded during the Bluetooth test.
- Temporary Dell discoverability was restored after the test. Addresses, device scan logs and pairing keys remain private.

This proves discovery, pairing, bonding and encrypted data transport in the current RAM session. HID input, A2DP audio, suspend/resume and automatic restoration after reboot remain unqualified. Encryption at level 2 does not establish MITM-authenticated pairing.

## Echo client

Build with an AArch64 cross compiler and isolated BlueZ headers:

```sh
make build/n71-bt-l2cap-echo-aarch64 BLUEZ_HEADERS=/path/to/isolated/include
```

Run on the phone with a mode-0600 private file containing only the controlled peer address. The peer must expose an encrypted SOCK_SEQPACKET L2CAP echo listener at PSM 0x1001. The client prints aggregate verification only, never an address. It requests encryption before connecting and rejects a socket below BT_SECURITY_MEDIUM.

## Validated userspace

The RAM runtime used Ubuntu ARM64 BlueZ 5.85-4ubuntu0.4 and D-Bus 1.16.2-2ubuntu4, downloaded through isolated APT with signed Ubuntu archive metadata. Six programs and 23 shared libraries were selected after checking the ELF architecture and dependency closure. An explicit AArch64 loader and private library directory avoid changing the ramdisk global loader configuration.

Client headers came from bluez-5.87.tar.xz, SHA256 26bdcf2cebd7310c6f598850606b037ef0c515fe6608ebc54d22c50c4c32b35f. Full package and runtime hash manifests are retained with the private deployment checkpoint. The running daemon is 5.85, not 5.87.

The private bus uses an owner-only Unix directory and EXTERNAL authentication. BlueZ state contains private bond keys and must never be committed. A successful bond in this RAM session does not imply persistence across a reboot.

The daemon logged a rejected optional privacy-setting request; Bluetooth address privacy has not been qualified.

## Current-session recovery follow-up

A later third controlled trial followed an identity-guarded restart of the private BlueZ/D-Bus services. Paired/Bonded state and the encrypted 65,536-byte Dell echo passed again with zero transport errors and native Wi-Fi intact. This qualifies daemon restart/bond reload in RAM, not a new kernel boot. See [session finalization](N71_SESSION_FINALIZATION_UI_POWER_2026_11_16.md).
