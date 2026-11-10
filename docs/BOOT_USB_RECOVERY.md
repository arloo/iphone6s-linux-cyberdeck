# RAM-only boot: observed USB re-enumeration recovery

**Date:** November 10, 2026. **Target:** iPhone 6s N71/S8000. **Host:** Dell XPS with a palen1x Ventoy environment.

## Observed boot sequence

1. Boot the **previously prepared and SHA-256-verified** `CYBERDECK_A9_palen1x_embedded.iso`. The user confirmed that `sha256sum -c SHA256SUMS` passed for all embedded toolkit files.
2. The palen1x environment was running entirely in RAM. The USB stick was removed after verifying no filesystem dependency remained, freeing its port for the Lightning cable.
3. With the phone in iOS normal USB mode `05ac:12a8`, run `/opt/cyberdeck/01-pongo.sh` and enter DFU when requested (`05ac:1227`).
4. On this **single observed attempt**, the host displayed `checkm8 trigger stage` followed by `Checkmate?`, then stopped progressing.
5. Disconnecting/reconnecting the **Lightning connector at the phone** caused the host to report `Found download mode device` and `Sending pongo image`. The phone's display showed `pongoOS>`.
6. The host initially did not enumerate PongoOS after stopping the launcher. A second Lightning reconnect caused `05ac:4141` to appear.
7. `/opt/cyberdeck/02-linux.sh` then connected to PongoOS and reported `Uploaded 12339516 bytes`. The subsequent host `LIBUSB_ERROR_IO` coincided with the bootloader USB handoff. The **phone display independently confirmed** a HoolockLinux kernel boot and a BusyBox test ramdisk shell.
8. Returning the host to Kubuntu without rebooting the phone exposed the HoolockLinux USB gadget at `05ac:4142`, interface `172.16.42.2/24`, with successful ping and root shell over isolated USB at `172.16.42.1:23`.

## Interpretation and limits

- `Checkmate?` alone is **not** proof of exploitation or PongoOS success; the decisive evidence is the PongoOS prompt and subsequent `05ac:4141` USB enumeration.
- `LIBUSB_ERROR_IO` from the loader is **not, by itself, proof of failure** when the next stage has visibly started; verify the new USB identity and kernel shell.
- The physical Lightning replug method succeeded on this host and device once in the recorded session. It is **not a validated universal workaround**. Do not blindly unplug while another stage is transferring data.
- Both PongoOS and Linux were RAM-only. No persistent jailbreak, flash, NAND write or iOS restore was requested.
- The root Telnet shell is unencrypted: use only the direct, isolated USB gadget connection, not an untrusted network.

## Next validation

Capture a second independent boot attempt before calling the replug sequence reproducible. Do not reset a running Linux session solely to prove it.
