# CYBERDECK // ARLO: physically verified quiet splash (2026-11-18)

## First physical boot verification

The owner-approved portrait 750×1334 splash was integrated into an
*isolated private RAM-only* N71/S8000 Linux image. The retained kernel,
both DTBs, original recovery tooling, touch/WLAN/Bluetooth UI and the
original debug RAM image were preserved. The alternate showcase boot
header adds only `quiet loglevel=3`, not a kernel rebuild.

The new image was SHA-256 pinned before transfer. Its SHA-256 is
`fd6468087c5bd92878149bf794a60dc03dacd6f55c73b997df895da8e32cb646`
and size is 27,361,435 bytes. Generated runtime PNG data and private
device files are not committed to the public repository.

At approximately 14:50 local time, the physical phone enumerated as
PongoOS `05ac:4141`, then RAM Linux `05ac:4142`. The live phone's
USB-pinned SSH session returned:

```text
/proc/cmdline: console=tty0 hl_rd=shell apple_z2.hbpp_cal_nop=1 quiet loglevel=3
/run/n71-boot-splash.log: N71_SPLASH_DISPLAYED_RAM_ONLY
/run/n71-splash.log: /usr/lib/cyberdeck/splash.bgrx.gz: OK
/run/n71-integrated-startup-PRIVATE.log: N71_INTEGRATED_SERVICES_READY_UI_SCHEDULED
/sys/class/graphics/fb0/virtual_size: 750,1334
/sys/class/graphics/fb0/bits_per_pixel: 32
/sys/class/graphics/fb0/stride: 3000
```

The touch-first native UI process was running, Wi-Fi carrier was up
and Bluetooth `hci0` was present. The framebuffer splash completed
successfully. These readbacks are software/USB-SSH confirmation; they
do not replace the operator's separate visual acceptance of the
rendered boot sequence. Early m1n1 messages are not necessarily hidden.

## Recovery and transport

Several earlier host-side checkm8/DFU transfers failed with USB errors
`-110` and `-71`, even though the DFU stage and checkra1n
handshake had been reached. The operator's Dell host had both
`apple_mfi_fastcharge` autoload and `fwupd` observing DFU transitions.
A narrow temporary udev rule was revised to include DFU USB interface
modalias events; the owner-attended wrapper also briefly stopped and
runtime-masked the host `fwupd.service` while transferring Pongo,
restoring its original state upon ordinary script exit.

The successful transition followed these mitigations, but the logs
do **not** prove that either service was the sole root cause: USB
transport instability may have contributed. There were still failed
attempts beforehand. Do not claim full reproducibility from one
successful transfer.

No NAND filesystem operations or storage-probing module were loaded
for this visual demonstration. Linux remains RAM-only. Its debug
counterpart and previously tested image are preserved for recovery.

## Battery caution

On this fresh image the existing monitored charger module reported
`input_uA=300000`, VBUS approximately 4.875–4.900 V, 78% state
of charge and net-positive current at several samples (including
+33 mA). The module's **3,600-second fail-safe lease still exists**;
no continuous charging claim or removal of cell-voltage/temperature
protections is made. Earlier testing observed cutoff at a BQ27540
reading of 4.201 V, so the previous unattended Dell renew service
was deliberately disabled pending hardware safety qualification.

This boot does **not** demonstrate persistent Linux storage. The
64 GB NVMe Identify result was obtained in the preceding, separately
quarantined hardware session, not in this showcase boot.
