# N71/S8000 charge-source ceilings and opt-in 500 mA research profile

Date: 2026-11-19. Device: iPhone 6s N71, Samsung S8000.
Scope: documented source electrical limits, real device proof, and an
**offline-staged** Linux charging-policy improvement. No physical Linux
charge-profile switching was performed during this review.

## Current iOS emergency baseline

On the Dell's USB 2.0 host port, the genuine iPhone enumerated as
`05ac:12a8`, `iPhone8,1`, with device configuration
`bMaxPower=500mA`. The Linux host's `apple_mfi_fastcharge` device
showed `charge_type=Trickle`. This is a host driver software
setting, **not an independent USB ammeter**. iOS reported
`BatteryIsCharging=true` and `ExternalConnected=true`.
The state-of-charge reading briefly fell to 3%, then recovered
to 6% while iOS was left running. Low-battery Linux/DFU/NVMe trials
were correctly suspended.

The 500 mA *device descriptor* expresses the current declared for
the current USB configuration. **It does not prove an actual 500 mA
draw**, nor prove a 1.5/2.0 A high-current host source. Do not
switch the host's MFi `charge_type` to Fast when the supply
capability has not been independently established: Linux's generic
MFi driver uses a 2500 mA value for that selection, which is not
a measured safe maximum for this phone or port.

## Proven S8000 SN2400 Linux input-current steps

The native N71/S8000 SN2400 research module programs **only the
input-current limit** register 0x09. The measured and source-correlated
scale is `90 mA + 10 mA * code`. Charge-voltage, cell-current
regulation and pack voltage thresholds are **not modified**.

| Linux charge input profile | Observed on actual N71 | Limit |
| --- | --- | --- |
| Baseline 90 mA | Net discharge observed under load | Insufficient for useful Cyberdeck |
| 300 mA | Positive cell current during selected tests | Already used in standard RAM boot; later sessions showed 0/negative net current |
| 500 mA | On 2026-11-17, a 30-second monitored trial averaged **+265 mA cell current**, at about 35.5°C and VBUS 4.775–4.80 V | Was reverted, and a finite 500 mA / 3600-second lease was also physically tested |

The **500 mA profile has already been physically demonstrated**
on the same board, but this is not proof of sustained charging at
all levels of cell voltage. A later experimental lease stopped on
the existing 4.200 V research upper-voltage guard after a 4.201 V
readback, correctly restoring the baseline. This cell cutoff is
a conservative prototype bound, not a qualified maximum rating for
the actual possibly-replaced battery pack.

Important: **500 mA is not the proven absolute charging ceiling
of the iPhone 6s**. It is the maximum *tested* Linux setting compatible
with this specific Dell USB port's current 500 mA descriptor. A
better power source may permit more input, but the board charger,
cable protocol, battery pack identity, thermistor accuracy, and
power-budget qualification are open.

## Source topology and limits

- Dell USB 2.0 standard downstream port: 500 mA configured USB 2.0
  envelope, **2.5 W at 5 V** (not measured cell charging power).
  No greater current should be requested without independent source
  classification and a supported charging-port negotiation.
- Standalone reputable 5 V / 1 A adapter: **5 W available** for iOS
  stock charging; no USB data path to Dell.
- Apple-compatible 5 V / 2–2.4 A 10–12 W adapter: **power-source
  capacity**, not a promise the 6s will draw that many amps.
  The phone determines its usable current.
- An independently verified, compatible **BC1.2 charging downstream
  port (CDP)** can provide USB communication plus charging, with a
  standard port ceiling **up to 1.5 A**. Neither the present Dell
  port nor our S8000/Lightning negotiation has been qualified as CDP.
- Do **not** use improvised USB Y-cables or electrically parallel two
  unrelated sources to feed VBUS while retaining data. Use a
  certified power/data charging hub or suitable source.

References:
- Apple: https://support.apple.com/it-it/120548
- USB BC1.2 categories: https://www.iteh.eu/catalog/standards/clc/ba1c693a-5d15-4e84-975f-875a1bf69527/en-62680-3-2013
- Linux MFi driver: https://github.com/torvalds/linux/blob/master/drivers/usb/misc/apple-mfi-fastcharge.c
- Actual historical measurements: [17 November 500mA trial](N71_S8000_SN2400_500MA_AND_PCIE_LOCAL0210_2026_11_17.md)
- Guard-voltage stop: [18 November stop](N71_S8000_CHARGING_GUARD_FOLLOWUP_2026_11_18.md)

## Implemented now: offline, not physically deployed

New shell script `scripts/n71_charge_supervisor_500ma_ram.sh` is
a **separate operator-attended** counterpart of the proven
`n71_charge_supervisor_ram.sh`. Existing 300 mA startup and daemon
remain unchanged. No new code was installed onto the iPhone.

The 500 mA supervisor requires a mode-0600 root-owned RAM-only
`/run/n71-owner-verified-500ma-source` marker containing
`N71_500MA_USB_SOURCE_OWNER_VERIFIED`. The owner shall authorize
this marker **only after** independently checking the intended
USB power source and cable, not merely by reading
`bMaxPower=500mA`. This prevents accidental auto-arm after reboot.

The phone-local script further requires:
- Real N71/S8000, matching `batt2` kernel and SHA-pinned 500-capable
  SN2400 kernel module, already explicitly armed at 500 mA;
- Valid USB gadget connection and healthy 2-second SN2400 VBUS
  telemetry and current-limit readback;
- Battery >=35%, 10–38.9°C, 3.6 V to **less than 4.180 V** at
  the supervising stage;
- Maximum 3600-second lease; renewal at >=2400 seconds, never
  near its expiration; an exclusive lock against concurrent
  supervisor processes;
- A verified return to the original input register before any
  re-arm, with automatic fail-closed handling on monitor stop,
  voltage/VBUS deviation, missing metrics or disconnection.

The kernel module itself also has a stricter **above-10% minimum**
and conservative hard-fail battery-temperature/voltage safeguards;
the operator-controlled rollout additionally requires **>=50%** to
start any new Linux experiment. Do not bypass either threshold.

On a future **fresh USB-attached Linux boot**, after the >=50%
battery preflight and a verified 500 mA source:
1. Qualify eight independent gauge samples and identify the exact
   running kernel and SHA-pinned charger module. Save baseline VBUS,
   real cell-current direction and temperature.
2. Stop the 300 mA supervisor, unload only the independently verified
   SN2400 charging pilot after successful restoration to stock
   input-current setting. **Never unload the quarantined S3E NVMe
   module to manipulate charging**.
3. Arm an unchanged, previously tested 500 mA SN2400 module using
   its explicit `input_ua=500000` and finite lease, ensure readback
   and monitor confirmation, then use the 500 mA supervisor.
4. Monitor cell net current, VBUS droop and temperature over a
   fixed attended interval. Revert on any violated limit.
5. Keep the existing 300 mA RAM boot as a verified fallback.
   Consider a faster source only after independent electrical
   and Apple Lightning/BC1.2 negotiation qualification.

**At the time of writing the phone is still in iOS, charging at
a single-digit percentage. No new charge controls have been
written and no DFU/Linux/NVMe boot requested.**

## 2026-11-23 actual N71 Linux SN2400 3600-second deadman expiry

A **read-only, directly observed physical test** on the currently running N71/S8000 Linux kernel (`7.3.0-rc1-n71-batt2`), with the USB gadget configured and S3E absent, qualified the already-live original 300 mA / 3600-second input-current lease. At 27% state of charge, the original module still reported 300 mA, 4.875–4.900 V VBUS, and normal periodic monitor events through uptime 3601 seconds. No charger register writes, module reloads, brightness adjustments or source changes were performed for this observation.

At **kernel uptime 3603.36 s**, the native module logged:

```text
n71-sn2400-trial: RESTORE reason=lease-expired input=00 rc=0
```

This validates successful return of the input-current **register code** to its original zero-coded baseline (90 mA nominal), not an independent electrical-current measurement. Subsequent real BQ27540 samples at 3605–3636 seconds reported **net negative cell currents ranging from -140 mA to -245 mA**, and remaining charge fell from **347 to 345 mAh**. This is strong evidence that the stock 90 mA input limit is insufficient to sustain the present Linux workload on this host; it does not establish how much current is actually drawn over USB.

**Operational restriction:** At 27% battery the existing owner-only supervisor's **minimum 35%** renewal threshold is not satisfied. No 300/500 mA lease was force-renewed. Do not bypass the supervisor or replace a finite lease with an infinite timer; recharge by a separately qualified iOS/charging path before high-power S3E work. The phone remained in Linux and S3E stayed unloaded at the end of the observation. The owner retains exclusive brightness control. Historical iOS status statements above refer only to November 19 and are not the current live state.

## 2026-11-23 owner-attended Linux low-SOC recovery (separate bounded 300mA policy)

The owner explicitly chose to **preserve the current Linux RAM boot instead of rebooting to iOS** and specified **38 °C** as the maximum operating temperature. The earlier 300 mA lease had correctly expired after 3600 seconds; at subsequent uptime the 23% battery was losing approximately 229 mA net with the SN2400 original 90 mA input setting. Leaving the phone idle in that configuration was depleting the battery. This operation makes a narrow, **explicitly disclosed 20–34% recovery-policy exception** to the normal supervisor's >=35% entry requirement; it does **not** modify the normal supervisor or the signed-off SN2400 kernel module.

The new owner-only `scripts/n71_charge_low_soc_recovery_once.sh` defaults to **`--check` (read-only)**. `--run` requires root, matching N71/S8000 board/kernel, SHA-pinned original charger module, configured USB gadget, external host-side verification of the currently configured 500 mA USB envelope, healthy battery, 20–34% indicated capacity, **battery voltage 3.50–4.15 V**, temperature **under 37.5 °C**, no S3E storage module, and exact `RESTORE reason=lease-expired input=00 rc=0` proof from the old lease. An exclusive lock prevents racing the standard supervisor. It unloads only the **expired SN2400** module, then reloads the same pinned binary at **300 mA for 600 seconds**; the kernel's independent 2-second VBUS/temperature/voltage monitor and timer-based rollback remain active. A second foreground watchdog polls battery every 2 seconds, aborts if any limit fails, and unloads the charger module no later than 540 seconds. At successful unload, `RESTORE reason=module-exit input=00 rc=0` is required. The watchdog stops before the user's 38 °C limit, with a margin for sampling latency; it is not an absolute physical-temperature guarantee.

Synthetic tests replace **all** `/sys`, `/proc`, `/usr`, and `/run` paths with temporary simulated fixtures; they verify no-write preflight, source refusal, wrong voltage/temperature/SOC, missing USB, failed rollback, S3E conflict, and a complete shortened run with module unload and baseline restoration. No synthetic test operates the physical phone. In a separate **actual-device run**, the host-side read-only preflight passed at 23%, ~31.6 °C and 3.596 V; arming returned `FINIT_MODULE_ONCE rc=0 errno=0` and the new SN2400 module's parameters confirmed **300 mA / 600 s**. Early real monitor samples reported VBUS 4.825–4.850 V, ~31.6 °C and approximately +76–88 mA net battery current; no storage module was loaded. The gauge percentage **jumped abruptly from 23 to 33–34%**, much faster than a 300 mA USB source can actually replenish a cell, so this is treated as **likely fuel-gauge re-estimation**, never proof of an equivalent physical charge increase.

**Observed end of the first run:** The recovery watchdog automatically stopped when the gauge crossed the 20–34% indicated window, after about **108 s**, and recorded both `N71_RECOVERY_MODULE_REMOVED` and `N71_RECOVERY_BASELINE_RESTORED=PASS`. The reading subsequently fell from **35% to 34%** with the input set back to baseline; the live test therefore reinforces the warning that the sudden gauge percentage rise was not a physically credible charge accumulation.

To bridge the noisy 34/35% handoff safely without relaxing the regular >=35% supervisor, two **separate finite, owner-attended** scripts were built and synthetically tested: `scripts/n71_charge_low_soc_bridge_38c_once.sh` requires an unloaded prior charger, authenticated `RESTORE reason=module-exit input=00 rc=0`, battery **20–36%**, temperature **under 37.5 °C**, and 300 mA / 600 s input lease with 2-second watchdog and mandatory cleanup at 540 s; `scripts/n71_charge_standard_38c_once.sh` is for a stable **35% or higher**, 300 mA / 3600 s lease, with the same temperature, voltage and teardown safeguards and a 3540 s supervised observation. Neither touches the standard supervisor or kernel charger policy. Simulated tests cover successful staged start/restore and refusals under invalid battery, temperature, voltage, USB and previous-baseline conditions.

**Second real bridge initial result:** At **34%**, 31.9–32.0 °C and 3.628 V before module load, a second 300 mA / 600 s finite lease was accepted and its monitor reported VBUS approximately 4.825 V, 31.9 °C and about +88 mA net cell current. That is an **initial armed-state observation**, not a claim that this second timed session has completed. An unstable fuel gauge can still force an early fail-closed stop. The owner controls the display brightness; neither script changes it.

**Boundary:** Neither recovery nor standard 38 °C-limited charging permits 500 mA input, indefinite renewal, higher battery charge-current/charge-voltage regulation, or DMA/NVMe/NAND experiments. The real hardware can always respond differently from the synthetic fixtures; any source disconnect, thermal excursion, unusual battery value, missing monitor or failed baseline restoration is a stop condition.

## 2026-11-23 second 300mA finite bridge completed and returned to baseline

The owner-attended second Linux low-SOC bridge at an indicated 34% battery completed its entire **540-second** foreground observation and returned the SN2400 charger module to its baseline input register with both `N71_RECOVERY_MODULE_REMOVED` and `N71_RECOVERY_BASELINE_RESTORED=PASS`. The external operator's temperature ceiling remained 38 °C; final gauge temperature was **32.2 °C** and the last positive net current sample was approximately **+92 mA**. USB stayed configured and S3E stayed unloaded. **No indefinite charging lease or NAND operation** was started.

A later, separate read-only check at iPhone uptime 8466 seconds confirmed the SN2400 module was **not loaded**, the battery showed **34%** and **433 mAh**, temperature **32.3 °C**, and net current approximately **-220 mA** after the fallback to the original 90 mA nominal input code. The fuel-gauge percentage remained unstable around the 34/35% threshold, so a switch to the standard >=35% policy is not yet qualified. Future charging should use a new explicit preflight and bounded profile; do not leave Linux on the baseline current for extended periods, and do not misinterpret this bridge as having reached 50% or enabling high-power storage experiments.

## 2026-11-26 explicit two-hour candidate and measured lower-reserve recovery

The existing one-hour native module separately qualified500mA at15% with mean+292.25mA, stable33.2C and normal30s rollback, while the already-closed S3E prefix owner remained held. The new research RAM image explicitly selects a finite7200s profile with unchanged native electrical/thermal/rollback guards; ordinary no-opt-in startup retains its earlier300mA/3600s admission. The new two-hour binary is now booted with exact500mA/7200s activation and positive-current samples; physical two-hour expiry is not yet accepted. [Detailed evidence, default/opt-in boundaries and pending hardware acceptance](N71_S8000_TWO_HOUR_CHARGE_PROFILE_2026_11_26.md).
