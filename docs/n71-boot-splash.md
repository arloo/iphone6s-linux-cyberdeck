# N71 S8000 Cyberdeck // arlo — RAM-only boot splash

The boot splash is **optional**, and the default remains the existing debug boot.
It does not change the iPhone NAND or Linux storage, nor is it a claim that PCIe,
DART, NVMe, native Wi-Fi, Bluetooth, touch, or charging have passed a test.

The approved full-color artwork is a **portrait** PNG. Build it on the operator's
Linux host with Pillow:

```sh
python3 scripts/n71_boot_splash_prepare.py /path/to/approved-artwork.png /path/to/private-splash-output
```

The output is a correctly letterboxed 750×1334 preview and a compressed
4,002,000-byte **BGRX** framebuffer blob. Keep generated `.bgrx.gz` private.
The generated manifest contains a digest for the compressed file.

To enable showcase mode in a *separately built, owner-controlled RAM initramfs*,
copy these verified outputs under `/usr/lib/cyberdeck/`:

- `splash.bgrx.gz`
- `splash.sha256`
- `boot-mode` (containing exactly `showcase`)

Install `scripts/n71_boot_splash_ram.sh` as executable
`/usr/bin/n71-boot-splash`. The integrated startup hook can invoke it
immediately before the existing UI handoff. The existing UI starts normally and
replaces the still image. If no asset is present, the script exits successfully.

To restore debug mode, delete `boot-mode` from the *next RAM image*, or set it
to `debug`. Do not hide kernel logs on experimental storage bring-up images:
`quiet` and `loglevel=3` are **separate opt-in boot arguments** for a later
showcase-only boot after serial/USB recovery has been proven.

For the approved illustration, lines such as `[OK] DART` are decorative.
They must not be interpreted as hardware readiness; a future live overlay
should render real subsystem states.

Never copy private identity keys, calibration, pairing data or device identifiers
into this public repository or a shared image.
