# N71/S8000 USB charging: verified boot-enumeration race and RAM-only mitigation (24 Nov 2026)

## Real phone evidence, before any modifications

During the first owner-attended Linux RAM boot after an iOS recharge to 100%, the Apple iPhone 6s N71/S8000 was visible as a Hoolock USB gadget (`05ac:4142`), and direct-USB SSH succeeded with the already pinned current-boot host key. The original SN2400 driver log shows:

- Uptime **2.177 s**: 300 mA **USB input limit** applied (not an assertion about net battery current); sampled VBUS **5.000 V**, 3,600-second automatic lease.
- Uptime **4.231 s**: monitored VBUS **4.875 V**, charge limit still programmed.
- Uptime **6.318 s**: `MONITOR_STOP rc=-34 VBUS_uV=0`, followed by `RESTORE reason=monitor-stop input=00 rc=0` at **6.319 s**.
- Uptime **28.052 s**: DWC2 gadget bound again; subsequently enumerated as high-speed and SSH worked.

The monitor correctly stopped/reverted on bad VBUS evidence. The trace does **not prove why VBUS was measured as zero** (actual USB disturbance or ADC transient): it does show that the original startup armed the charger **before the USB reconfiguration was finished**. A fresh observation then measured about **98–95% SOC**, 30.5–31.6°C, ~4.12–4.17 V, `Discharging`, negative net battery current, with the SN2400 module still resident but no longer changing its input register. No storage DMA module was present. The live module was **not rearmed** during this engineering change.

## Fail-closed startup correction

`scripts/n71_runtime_autostart.sh` now performs the already verified board/kernel/hash checks, waits for initial USB configuration, starts the PMIC GPIO and Bluetooth setup, then **returns promptly to `/init`**. It starts exactly one isolated detached charge worker (`nohup`/`setsid`), writing its diagnostics to a separate RAM-only log. If these launch tools are absent, charging is skipped rather than delaying the boot.

The charge worker requires all of the following before **one** 300 mA SN2400 module insertion:

1. The initial startup marker and the original on-device SHA-256 file manifest validate; a RAM-only atomic directory prevents duplicate worker attempts.
2. Kernel uptime **at least 45 seconds** plus **15 consecutive** `configured` samples of the same USB gadget, with counter reset on any USB loss. A maximum of 120 attempts prevents indefinite enumeration waiting.
3. Battery health `Good`, fuel gauge **35–98%**, temperature **10–37.4°C**, voltage **3.500–4.149 V**. When immediately following a 100% iOS charge, the worker waits for a valid battery window, at most **40 checks / ~20 minutes**; no charger registers are touched while the battery is over the conservative voltage/SOC limit.
4. USB remains configured and no `n71_s3e` or already loaded SN2400 diagnostic is present. The worker never retries or unloads/rearms any failed SN2400 lease.
5. The same original kernel module independently enforces battery, VBUS **4.4–5.5 V** / startup droop bound, the 2-second monitor cadence, and at most **3,600 seconds** before automatic input-register restoration.

This is an **input-current limit**, not evidence of sustained positive net battery current. A successful offline test of the script does not qualify continuous Linux charging. An operator must still verify the measured battery current, thermal margin and independent rollback during a new real boot. A failure or zero-VBUS reading must stop the trial and never be retried blindly.

## Host-only verification and private RAM payload

`tests/test_n71_runtime_autostart_usb_charge_gate.py` executes the new shell logic against an isolated mocked sysfs, stubbed shell commands and no device IO. Its 11 cases cover USB initial loss/re-enumeration, configured-state stability, a full/high-voltage battery, temperature/voltage/SOC health limits, duplicate module prevention, bad image hash manifest, missing PMIC initialization, a post-boot charge gate and nonblocking main startup. Shell syntax and Git diff are verified.

On the owner Dell, a **private, RAM-only** next-boot candidate was reconstructed from the prior authenticated ARLO image. The exact original kernel, both DTBs, bootloader, `/init`, private UI bundle and every other CPIO entry are preserved. Only `usr/bin/n71-runtime-autostart` and the matching line in `usr/lib/cyberdeck/n71-runtime.sha256` were changed; all nine original runtime-hash manifest records were rechecked. New candidate SHA-256: `4c69f432bbe78e8672c3395afc88cacf8d9bff1114acc435cff3dd3ba4224953`. A private attended-boot wrapper validates the new image size/hash and preserves DFU/Pongo and USB handoff guards.

**Security boundary:** the private RAM image contains owner-specific connection/SSH/Bluetooth state and MUST NOT be committed or publicly released. Only the general startup logic, tests and sanitized evidence belong in Git. **The candidate has not been physically booted**; no reboot, NAND read/write, storage DMA or new live SN2400 programming was performed to validate this mitigation. This work does not solve persistent long-term charging or give any independent DMA retirement proof.

## Physical acceptance for a future owner-attended boot

Keep the existing Linux session until the owner coordinates the next DFU. On that fresh boot, verify the detached charge worker's log, the uninterrupted USB connection, thermal/battery behavior, positive net battery current and automatic input-register rollback; stop if the old VBUS=0 event repeats. The first physical NAND NVM Read is independently blocked by the storage acceptance ledger until PRP/FlatDMA and DMA drain are qualified.
