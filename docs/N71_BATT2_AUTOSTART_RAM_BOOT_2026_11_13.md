# N71 batt2 charging/Bluetooth autostart RAM boot

Status: physical RAM boot and runtime autostart accepted on N71/S8000.

Release: `7.3.0-rc1-n71-batt2-g68aadac820d0-dirty`.

Kernel Image SHA256: `048a57c71aa7f41fb59011079f56fdc69325a82d8eafe256ee376cba656122da`.

Private RAM payload: 13703936 bytes; SHA256 `acd50a55e0e44169b5bf66dd3222122715527801abbf17a0e4393595e6b299d9`. No proprietary payload is distributed.

The only Kconfig change from the physically tested batt1 build is LOCALVERSION to `-n71-batt2`. The loader and both DTBs are byte-identical to the earlier pinned PMGR-phandle RAM image. All its original initramfs entries are retained byte-for-byte except the init data/size, which adds one startup-script invocation after the established touch initialization. The 17 original Wi-Fi firmware files are unchanged.

Ten added files provide matched PMIC GPIO, monitored charging and stage-9 PERST-held modules; the single-syscall loader; redacted HCI inspection; battery observation; the private board-matched USI Bluetooth HCD; the autostart script and its hash manifest. The dormant older guard tool from the historical base is retained but remains incompatible with the new kernel and must not be used.

`scripts/n71_runtime_autostart.sh` verifies exact board family, batt2 kernel and bundled file hashes. It waits for USB configuration, makes one PMIC GPIO module load and one guarded 300 mA charging activation with a 3600-second lease, waits for the previously validated Bluetooth firmware build 0825, and requests HCI up. Failures leave the USB shell available and are logged in `/run/n71_runtime_autostart.log`. Boot startup does not load the PCIe module or activate a PCIe domain. Existing charger voltage, temperature, initial-state and ADC guards remain effective; autostart success must be verified on the real phone.

The physical boot passed: matching batt2 kernel, startup PMIC GPIO and charging module loads succeeded, Bluetooth build 0825 was UP/RUNNING with zero RX/TX errors, USB and touch remained present. Battery rose from 55% to 57% during this session; the stage-11 postflight measured +44 mA, 4.026 V and 30.3 C. Charging remains a guarded one-hour lease, not a full-charge qualification. Stages 9 through 14 subsequently passed their hardware checks; see the PERST-held report. No enumeration, DMA isolation or native Wi-Fi success is claimed.

On the owner Dell, with the iPhone in DFU:

```sh
cd ~/Documenti/cyberdeck-a9-linux
sudo bash scripts/pongo-once-without-mfi-reload.sh run
# After Pongo is confirmed as USB 05ac:4141:
sudo bash scripts/n71-batt2-pongo-ram-smoke.sh send
```

Use the new sender: earlier senders pin older RAM images. The helper verifies hash/size, exact upload acknowledgement and Linux USB reenumeration. The first live checks are kernel identity, startup log, battery current, HCI counters, touch initialization and all PCIe domains OFF; only then run the staged DART snapshot.

Validation: ARM64 kernel and three matching modules built; configuration delta checked; loader/DTBs preserved; original CPIO-entry preservation checked; init insertion bounded to one call; all added CPIO data/modes and module vermagic checked; shell syntax and wrong-kernel skip passed. Physical USB transfer, boot, startup log and subsequent USB/Bluetooth/touch/PMGR postflights passed.


Session stop: stages15/16/18 completed bounded controller/reset tests, but link status bit0 remained clear; stage17 rejected its register readback. Stage19 is compiled only and untested, with private calibration retained locally. See the port1 report's stop checkpoint before resuming.
