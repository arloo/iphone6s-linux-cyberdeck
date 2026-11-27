# N71/S8000 guarded 300 mA session support after the checkpoint trial — 27 November 2026

## Separate power follow-up

The matching APFS descriptor trial was already accepted and committed at598796f. S3E is closed and retained with one ref1 Live owner, all original DMA/HMB/DART/NVMMU/data/SGL/snapshot/CPU backing held and no probe/disk interface. This follow-up submits no new NAND command and never reloads, calls, resets or unloads the storage owner.

The initial full-battery500mA native lease had stopped at a4.225V guard and restored original input00/rc0. After the storage result, the exact accepted native binary SHA23e166ee1309dba0fbfa75d9a0bfd76e000e3e39dcc0cf0a5a5cecc65deafc7f was checked. Only its zero-reference charger module was normally removed/reinserted. Charge-current/voltage controls and native electrical/battery/thermal/VBUS/rollback guards were unchanged; only the supported input limit/finite lease parameters changed.

## Actual 30-second pilot

One300mA/30s activation succeeded at uptime1319.59s with VBUS5.025V. Fourteen subsequent monitor records stayed at4.900V with requested300mA. The scoped300mA activation had no MONITOR_STOP; an earlier500mA guard event in the same log belongs to the previous activation and is excluded. Normal30s expiry restored input00 with rc0 at1350.88s.

Ten middle-window samples averaged **+18.9mA**, with some negative samples; the final sample after rollback was83%, Good/Discharging,-307mA and32.9C. This establishes the finite pilot/rollback and a small positive sampled balance, not uniformly positive or autonomous charging.

## Finite session activation and measured margin

After the pilot had expired/restored normally, one explicit **300mA/7200s** lease was activated with the same binary and existing native guards. Eight fresh native monitor records passed at4.9V; the initial eight gauge samples averaged-37mA during/after the transition, ending Charging/+50mA. A later independent eight-sample window measured **83%, Good,33.0–33.1C, cell4.045–4.106V**, with five positive and three negative current samples, mean **+11.375mA**. Remaining Charge stayed at1,038,000uAh throughout that later window. The last gauge sample wasCharging/+13mA; native monitors remained fresh at4.9V/requested300mA.

Brightness was already1023/2047, the previously qualified balanced setting; readback confirmed it and no brightness change was applied. There was no CPU governor, network, UI or storage change. The margin under the measured bench workload is small: input300mA does not mean300mA net battery charge, and sustained charging/endurance are not qualified.

This is a live session override. The RAM image, default hashed500mA boot opt-in, kernel and storage/helper binaries are unchanged. Native guards may stop the lease before7200 seconds; there is no automatic renewal. Actual full two-hour duration/expiry is still untested. All original storage backing and the same ref1 owner remain held.

[Sanitized samples and activation evidence](N71_S8000_300MA_SESSION_SUPPORT_2026_11_27.json), [preceding storage acceptance](N71_S8000_APFS_CHECKPOINT_PAIR_SUCCESS_2026_11_27.md), [native two-hour source/limits](N71_S8000_TWO_HOUR_CHARGE_PROFILE_2026_11_26.md).
