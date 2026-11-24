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

## Physical follow-up: delayed startup passed, charging still unqualified

The owner-attended new RAM boot was verified over direct USB SSH. The running startup SHA-256 matched the latest committed startup (538680df3dd663b022adea2a8291bbbccff5bee9c677bc6ab06d42678f35ade7). PMIC GPIO and HCI initialization succeeded; the detached worker reported stable USB and a valid battery window (93% SOC, 30.9 C, 4.142 V). The charger applied 300 mA at 59.596 s with a baseline 5.025 V. At 61.631 s it reported MONITOR_STOP rc=-34 VBUS_uV=0 and immediately restored input=00 rc=0. No USB disconnect/re-enumeration was logged at that failure time on either host or phone. Subsequent battery readings were negative, around 92% SOC.

**Correction to interpretation:** the running module remained the older binary SHA-256 06b497deb2baf3724fe3d03f72870df2910d40b27afd71e176df52f2358aafea, lacking the diagnostic phase field. Its logged zero is ambiguous: a preceding battery guard failure can leave the VBUS variable zero without any ADC conversion. The successful delayed startup disproves early arming as a sufficient explanation, but does not establish an ADC malfunction. Prior physical evidence in N71_S8000_CHARGING_GUARD_FOLLOWUP_2026_11_18.md demonstrated precisely this log signature for an upper-voltage battery guard (4.201 V), with phase=battery.

The existing phase-aware batt2 diagnostic build and its later 120 mA-support revision were identified offline by matching kernel vermagic and log-format strings. Neither was loaded or rearmed in this session. Two additional host-only C harness cases verify that upper battery voltage causes rollback without any ADC read, whereas a real zero conversion also causes rollback but performs the ADC read. All 26 simulated cases pass. No threshold, lease, hardware register or storage state was changed. A future physical diagnostic requires the phase-aware module and independently observed electrical conditions; a repeated fault must remain fail-closed.


## Physical follow-up: phase-aware module boot and small positive charge balance

A further owner-attended N71/S8000 RAM boot physically loaded the staged
phase-aware charger module. The on-phone module file SHA-256 is
b559145fd3c1c30ba3aea008544ffb2fcf7aa737b69773f53f1512b1d197eec7;
startup still matches
538680df3dd663b022adea2a8291bbbccff5bee9c677bc6ab06d42678f35ade7.
The candidate image SHA-256 is
44ca99abd83ba5ddbcf81bda0fdf7c0c5b5d69991b31ea8f75d875d240f588fa.
Only the SN2400 module and its runtime-hash manifest entry changed from the
previous USB-stable candidate. Kernel, DTBs, bootloader, splash, startup,
battery safeguards and finite lease were preserved.

At uptime 59.599 s the module applied the existing 300 mA input profile,
with 5.025 V baseline VBUS and the unchanged 3600-second lease.
Real monitor events continued through uptime 467.463 s at 4.875 V VBUS,
without MONITOR_STOP, BATTERY_GUARD, RESTORE or ROLLBACK_FAILED in this boot.

A subsequent read-only 25-sample BQ27540 observation spanning 125.19 s
recorded 53% capacity throughout, 31.5-31.6 C, all health=Good and all
USB=configured. Net battery current ranged from -54 to +96 mA; its
arithmetic sample mean was +38.72 mA (19 positive, 3 zero, 3 negative).
Reported remaining charge increased from 688 to 689 mAh. This is a small
positive idle-session balance with intermittent discharge, not continuous
positive current or a qualified charging margin for storage activity.
The later snapshot showed 53%, 31.7 C and zero net current.

The previously failed boot had different cell voltage/SOC and lacked
phase diagnostics; this new successful monitor does not retrospectively
prove its rollback cause. No fault was forced. No 500 mA profile,
brightness change, S3E module or NAND operation was performed.
The 500 mA source attestation remains pending. Storage remains blocked
until power margin is physically qualified under the intended workload.

Sanitized physical evidence:
[phase-aware boot and battery observations](../results/2026-11-24-n71-sn2400-phase-boot.json).
