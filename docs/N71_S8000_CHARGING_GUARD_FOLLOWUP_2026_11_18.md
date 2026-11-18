# N71/S8000 charging: guarded 500 mA input and upper-voltage stop (18 Nov 2026)

## Physical results

On the USB-connected N71/S8000 RAM Linux session the Dell USB descriptor
reported **MaxPower 500 mA**. Reusing the previously owner-tested,
readback-verified SN2400 module with *only* the USB input-current limit
changed from the stock 90 mA baseline to 500 mA yielded an observed
**+269 mA net battery current** at approximately 75% state of charge.
VBUS remained approximately 4.75 V; temperature was 35.2 C.

A private Dell user service was experimentally enabled to verify the
hardware module every 60 s and renew its 3,600-second charge-input lease
before expiration. It *did not* remove the kernel driver's two-second
battery / VBUS monitor or the automatic rollback failsafe.

This did **not** prove uninterrupted charging. Subsequently the hardware
monitor observed a BQ27540 reported cell voltage of **4,201,000 uV**,
slightly beyond the experimental **4,200,000 uV** upper bound, and
correctly took its fail-closed path:

```text
BATTERY_GUARD capacity=77 temp_tenths=353 voltage_uV=4201000
MONITOR_STOP rc=-34 VBUS_uV=0 phase=battery
RESTORE reason=monitor-stop input=00 rc=0
```

The Dell supervision process then stopped because it no longer received
current valid monitor events, preserving the conservative state.
The failure was the **voltage guard**, **not** expiry of the one-hour
lease. The gauge then reported net discharge, despite USB still being
connected.

## Remaining work and safety

The module's 4.200 V threshold is a research safety assumption, **not**
a verified maximum for the battery physically installed in this phone.
Many iPhone 6s-compatible replacement packs report a higher rated maximum,
but that is not proof of the identity or safety limits of this specific
device battery. Before any adjusted bound, independently qualify the
pack rating, the SN2400 native charge regulation setpoint and the gauge
accuracy on the actual phone.

Do **not** remove the battery temperature / VBUS monitor, silently
disable upper voltage protection, exceed the declared USB 500 mA input
budget, or extend the charge-current / charge-voltage setpoints. Preserve
the automatic fail-safe rollback even with a continuous host-side
renewal scheme. If qualified, implement continuous operation as
periodic guarded *renewal*, not as indefinite unmonitored register state.

The owner may safely return to iOS for stock charging. The current
research session holds the NVMe module in quarantine; never force unload
it to address charger state. Fully restart the phone before a further
NVMe physical trial.

Source: the locally retained N71 bounded SN2400 kernel module and
physical event log. No personal device identifiers are published.
