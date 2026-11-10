# N71 SPI2-OFF: first boot test handoff

**Created:** 2026-11-10. **Status:** ISO generated and verified offline; **NOT booted on phone**.

## Distinct ISO and boot assets

- Filename: `CYBERDECK_A9_SPI2_OFF_TEST.iso` (59 MiB, 60,882,944 bytes).
- SHA-256: `23f37f2bb163f10fff51b7ed7579090364910a799200d9a4446677e7d61d9356`.
- Embedded `/opt/cyberdeck/m1n1-linux.bin`: experimental `00-spi2-off` RAM-only payload, SHA-256 `0c93711939a7d847c9ef323e16205bda0160253cc4021f4bdcc4b5821f94cc93`.
- Embedded `/opt/cyberdeck/m1n1-linux-known-good.bin`: previous RAM-only payload, SHA-256 `220e086184d0cfdec1f04f3ea038e4c439378c8add6610727357fd2d4503c032`.
- Existing previously booted `CYBERDECK_A9_palen1x_embedded.iso` remains unchanged.
- ISO was generated from previously verified upstream palen1x `v3.0.0-beta.2`, keeping original UEFI/BIOS El Torito boot entries.
- Extracted ISO `/boot/initramfs.xz` was byte-identical to the build's compressed initramfs and passed `xz -t`. All eight embedded toolkit files passed `sha256sum -c SHA256SUMS`.
- **Neither the experimental ISO nor its payload has been booted**; verified file integrity is not boot validation.

## Why ordinary remote kexec is NOT available

The phone's active known-good kernel `7.3.0-rc1-g6831bc701a6c` does not expose `/sys/kernel/kexec_loaded` and shows no `spin-table park` range in `/proc/iomem`. The upstream fast-reload script explicitly refuses such a running kernel. Do **not** attempt a kexec transfer or reboot remotely; use the already demonstrated, manually attended DFU -> PongoOS -> RAM Linux procedure.

## Safe transfer to Ventoy

The experimental ISO currently resides on the Dell internal filesystem, **not on the USB stick**. The Dell has only the Lightning cable connected (no Ventoy USB disk in `lsblk`). A local script `palen1x/copy-spi2-off-iso-to-ventoy.sh` was written and syntax-checked. It refuses to run unless precisely one existing **SanDisk USB partition labelled Ventoy** is found, verifies the source hash, refuses to overwrite an existing ISO, verifies the destination and unmounts the filesystem. It deliberately does not repartition, format or overwrite an existing ISO. Tested with no Ventoy connected: failed safely without writing.

To stage, the human operator must disconnect the iPhone Lightning cable from the Dell, insert the existing SanDisk Ventoy stick, and run that script on Kubuntu. The USB Linux shell will disconnect during the cable swap, but the **running phone's RAM Linux can continue on battery** until it is restarted. Confirm the script reports integrity and unmount success before rebooting the Dell.

## Device-attended first boot validation (future step)

1. With the new ISO copied, boot Dell via F12 -> existing Ventoy -> `CYBERDECK_A9_SPI2_OFF_TEST.iso` in Normal mode.
2. At the palen1x root shell, run `cd /opt/cyberdeck && sha256sum -c SHA256SUMS`. All eight lines must be `OK`.
3. Enter Recovery/DFU using the already documented manual USB steps, then run `./01-pongo.sh`; use prior bounded USB re-enumeration recovery only if the same conditions recur. Do **not** restore or erase iOS.
4. Confirm PongoOS via `05ac:4141` and `pongoOS>` screen. Only then run `./02-linux.sh` for the experimental SPI2-OFF kernel. If choosing to send the original known-good kernel instead, use **`./03-known-good.sh`** while PongoOS is connected.
5. A new Linux boot is only successful once it shows a shell, reconnects via USB gadget, and permits read-only verification of kernel release, `gpio-keys`, SPI2 power state, and the Bluetooth UART; the PHY/radio Bluetooth firmware may need reloading from private RAM assets. USB gadget ID alone is insufficient.
6. If no new shell appears, stop and use a **person-at-device** DFU recovery with the known-good payload. Do not repeat an unstable loader blindly.
7. Only after conservative boot succeeds should `01-spi2-host-only` be tested. Its ISO has **not** been built or deployed.

**Do not claim the touchscreen works:** the N71 HBPP calibration ACK remains unconfirmed, and the experimental image keeps the Z2 child disabled.
