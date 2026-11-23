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

## Repeat regression diagnosed — 2026-11-23 (Dell Kubuntu host)

A fresh host reboot left the iPhone running stock iOS. Two attended palera1n beta 3.0.0 attempts entered **real N71/S8000 DFU (`05ac:1227`)**, and the USB descriptor subsequently showed the pwned-DFU checkm8 marker on both attempts. Nevertheless, **no PongoOS `05ac:4141` gadget was observed**, and the device ultimately returned to stock iOS (`05ac:12a8`). No Linux image or storage experiment was started.

Direct comparison against the successful **2026-11-20 14:10–14:11** host-kernel record is decisive:

| Stage | Successful 2026-11-20 boot | Failed 2026-11-23 attempts |
| --- | --- | --- |
| N71 DFU `05ac:1227` | Yes | Yes |
| USB control-transfer timeouts `-110` / protocol errors `-71` | Yes | Yes |
| `usbfs` interface-claim warnings | Yes | Yes |
| Apple MFi kernel driver unloaded before attempt | Yes | Yes |
| PongoOS `05ac:4141` | **Yes** | **No** |
| HoolockLinux `05ac:4142` | **Yes** | **No** |

The `-110/-71` messages are **not independently diagnostic of failure**: the same messages occurred in the successful checkm8 run. The active host kernel and xHCI path matched the prior run, and the scheduled `fwupd-refresh` failure also occurred during the successful boot. The observed regression is bounded to the **pwned-DFU → PongoOS USB re-enumeration/handoff** stage. Neither bad firmware nor a defective physical cable is proven.

**Attended next attempt:** use the exact SHA-verified, previously successful RAM-only boot command. After an explicit *checkm8/Checkmate* indication, if progress stops **before** Pongo image upload, perform the already physically validated **one-time Lightning disconnect/reconnect at the phone** and look for a real `05ac:4141` enumeration. If the Pongo prompt is visible but its USB gadget is missing, a second re-enumeration was needed in the 2026-11-10 physical record. The upstream A9(X) palera1n guidance also allows stopping and re-running the tool if stuck midway in PongoOS. **Do not** unplug during an active Pongo/Linux image transfer, do not flash NAND, do not reset arbitrary USB ports, and do not equate the checkm8 marker with boot completion. If no Pongo gadget appears, stop and preserve diagnostic evidence instead of blind automatic retries.

This diagnosis is based on sanitized host-kernel USB transition states. Original USB serials, ECID, private logs and firmware remain excluded from public Git.

## Narrow Dell USB root-port recovery (2026-11-23)

The owner repeated the physical DFU/checkm8 operation, but the iPhone still did not transition to PongoOS. The Dell's real USB topology showed the iPhone on **USB2 root hub, bus 001 port 1** (`1-1`), separate from the Bluetooth, fingerprint reader, and webcam on other ports. While no Pongo/DFU transfer was running, Linux exposed a writable **per-port** sysfs control at `usb1/1-0:1.0/usb1-port1/disable`, initially `0` (enabled). The target briefly reported `not attached`, then re-enumerated as normal iOS without intervention. A host inspection verified no current `palera1n` or `pongoterm` process.

The owner-facing helper `scripts/n71-host-usb-port1-recover.sh` provides a **dry-run `--check`** and a **root-only `--reset`** that toggles *only that port* for a bounded two-second interval and always attempts reenable on interruption. It refuses unknown USB devices, active Pongo/Linux, concurrent DFU/boot applications, unexpected port/peer topology or a port already disabled. This **logical port disable/re-enable is not guaranteed to remove physical VBUS power**; it is a narrower USB enumeration reset, not an xHCI controller reset or a Lightning reconnection. It never flashes, changes firmware, touches storage or operates on NAND.

**Status:** shell syntax and read-only physical-port preflight passed on the Dell; root-privileged `--reset` has **not** been executed by the assistant. Run it in an attended local owner terminal only when no USB transfer is active, then inspect the reported USB identity before attempting DFU and palera1n once. Do not run it after a Pongo or Linux session has started. If Pongo still fails, preserve the next diagnostic transition and consider a different direct physical USB port/cable before changing kernel or exploit binaries.

## Next validation

Capture a second independent boot attempt before calling the replug sequence reproducible. Do not reset a running Linux session solely to prove it.
