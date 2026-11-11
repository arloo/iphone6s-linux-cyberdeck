# N71/S8000 Z2 automated post-firmware initialization in RAM-only Linux

**2026-11-11. Status: off-device staging and mock tests PASS. Actual automatic-start physical validation PENDING.** The previous real hardware kernel #5 continues operating with validated two-finger multitouch; the new RAM-only payload has not been booted.

## Why this matters

The public RFC 0001-0010 kernel bring-up achieved real N71 iPhone 6s touchscreen input on Linux. The first accepted single-contact sequence and the later physical two-finger test demonstrated two simultaneously active tracking IDs in 273 SYN_REPORT frames. Until now, however, Z2 runtime initialization was executed manually after every boot through separate sysfs controls. The kernel uploaded private firmware, but the post-firmware wake and report setup were not automatic.

The next engineering milestone is repeatable initialization at cold boot without manually writing wake, D9, Type-1 9D/BF and AF sysfs attributes. This is separate from converting the experimental RFCs into a long-term upstream driver.

## Public autoinit implementation

The public shell script is scripts/n71_z2_autostart.sh. It is installed into a **private** initramfs as /usr/bin/n71_z2_autostart.sh and invoked ONCE after the standard init mounts proc/sys/dev and configures the USB network and mdev, but before entering the interactive shell:

    if [ -x /usr/bin/n71_z2_autostart.sh ]; then
        /bin/sh /usr/bin/n71_z2_autostart.sh > /run/n71_z2_autostart.log 2>&1 ||
            echo "N71 Z2 initialization incomplete; see /run/n71_z2_autostart.log"
    fi

The public file itself contains NO firmware, calibration, D9 private boundary tuple, device identifier, key or rootfs binary. Only the RAM-only private packager combines the public script with authorized original Apple firmware and per-device calibration.

The automation:
1. Verifies exact compatible apple,n71 and waits a maximum of eight seconds for the existing spi0.0 runtime_state sysfs node.
2. Verifies firmware booted and all controller one-shot controls initially unattempted.
3. Creates an ephemeral /run/n71_z2_auto_attempted marker BEFORE the first SPI write; any unexpected state aborts, and restart of the same script cannot silently re-run the commands.
4. Issues one EE wake; checks transport success.
5. Issues two E3/D9 report metadata queries, verifies each expected reply code, and requires the second query to report a 16-byte descriptor, status zero and checksum agreement.
6. Uses the physically validated Type-1 E7 D9 long report once, requiring E7 reply, checksum agreement and plausible geometry. The signed reversed Y axis is accepted by RFC 0010.
7. Issues one 9D/BF Type-1 setup and one AF enable, each checked for transport success, before logging only COMPLETE:PROTOCOL_READY. Real physical touch input must be confirmed separately.

Failure is **fail-closed**: the script stops without retries, reset, power cycling, flash access or GPIO manipulation. The RAM-boot shell is still available so the operator can inspect /run/n71_z2_autostart.log and use the previously proven RAM image. A completed script does not by itself prove touch functionality.

## Reproduction and privacy gates

The previously physically booted kernel #5 RAM payload was reconstructed bit-for-bit from a preserved m1n1 binary, unchanged bootargs, private N71 calibration DTB, disabled S8003 DTB, unchanged Image.gz and original firmware initramfs. The new image reuses the SAME kernel and changes ONLY the initramfs.

The new initramfs is produced by copying the original private ramroot, preserving files, executable permissions and symlinks, adding one public script in usr/bin, inserting the invocation in init, packing a newc CPIO with root:root header ownership and gzip compression. A private filesystem inventory check confirmed the only content changes are init and the new script; the firmware and the nested HoolockLinux extraction archive were identical. New RAM-only payload is stored under private-touch-live-test/z2-n71-autoinit-stage/ on the authorized workstation with file mode 0600; it is intentionally NOT included in the public repository.

The five mock protocol tests in tests/test_n71_z2_autostart.py simulate a valid full startup, an unexpected D9 length, invalid D9 geometry, wrong board compatible and an already-present one-shot marker. They do not interact with real hardware and cannot replace physical acceptance.

## Next supervised physical test

1. Preserve running kernel #5 and its known-good fallback until the operator can perform attended DFU/PongoOS RAM boot.
2. Load the new private auto-init payload once, and confirm HoolockLinux USB 05ac:4142.
3. Read /run/n71_z2_autostart.log; require COMPLETE:PROTOCOL_READY without an error line.
4. Read /sys/bus/spi/devices/spi0.0/runtime_state **without writing anything**; all manual gates must already show completed, including plausible geometry, Type-1 setup and AF.
5. Test the actual panel with a finger and two simultaneous fingers while recording bounded EVDEV event frames and IRQ increments. The test only PASSES if input works with ZERO manual sysfs commands after boot.
6. Perform supervised four-corner and edge accuracy tests, frame-cadence/latency checks and long no-touch stability observations.
7. On any error, STOP. Do not blindly retry commands or restore iOS; recover with the previous RAM-only payload via PongoOS under supervision.

## Scope

This automates the experimentally validated N71/S8000 touchscreen protocol after each RAM Linux boot. It does not boot Linux from NAND, install a persistent iOS replacement, enable the LCD or provide Wi-Fi/Bluetooth support. Those are separate project workstreams. The new image is a **staged experiment until real phone acceptance passes**.
