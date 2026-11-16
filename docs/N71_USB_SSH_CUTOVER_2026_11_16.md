# N71 USB SSH recovery: current-session acceptance (2026-11-16)

A private, RAM-local Dropbear 2026.94 instance has been tested on physical N71/S8000 Linux. The server binds only to the USB gadget address `172.16.42.1:22`, uses a unique private Ed25519 host key and an operator-provisioned authorized public key, and does not offer password or keyboard-interactive authentication. The Dell pins the server's host key through an already trusted USB-local channel.

The positive public-key login and a new authenticated command after Telnet cutover succeeded. A wrong client key, unsupported password authentication and a deliberately wrong pinned host key were rejected. TCP port 23 was closed. The private operator command helper now uses authenticated SSH with no fallback to Telnet. Authentication transcripts, private keys and device identities remain private.

**Qualification boundary:** these are physical results from one active RAM session, not a fresh boot. The optional USB-only SSH bootstrap in `scripts/n71_integrated_ram_startup.sh` is an unbooted integration candidate. It waits for the expected USB IPv4 address and cannot block the original USB recovery if it fails. No WAN listening or gadget-to-WLAN bridge is authorized.

See `results/2026-11-16-s8000-ssh-access.json`. Pending gates: fresh-boot service activation, host-key continuity, normal-user/least-privilege operation and clean key rotation.
