# N71 S8000 RAM charging supervisor — 18 November 2026

## Objective and hard limit

Keep the iPhone 6s cyberdeck USB input-current configuration available
throughout a healthy Linux session, without a periodic *user-facing stop
timer*. This must never be achieved by disabling the charger IC's
protection mechanisms, exceeding the host's declared USB budget, or
releasing current-limit control to an unmonitored permanent value.

The existing, physically tested SN2400 pilot uses a **300 mA USB-input
limit**, checks VBUS/status/cell voltage/temperature approximately every
two seconds and has a **3600-second automatic rollback**. This deadline
is a **fail-safe deadman**, not an arbitrary intended charge stop; it
must remain active in experimental builds.

The new `scripts/n71_charge_supervisor_ram.sh` is a **phone-side**
POSIX-shell supervisor. Unlike a Dell-hosted user service, it can operate
within the Linux RAM session after USB-gadget enumeration; it is
not a flash/NAND component or a full production charging driver.

## Qualified controls

Before acting the script verifies all of the following:

- Root, exact N71/S8000 board and current `n71-batt2` kernel family
- Byte-exact SHA-256 of the current 300 mA kernel module
- SN2400 module live with `armed=Y`, `input_ua=300000`,
  `lease_seconds=3600`, and configured USB gadget
- BQ27540: charge capacity at least 35%, temperature 10–38.9 °C,
  cell voltage at least 3.6 V **and strictly below 4.18 V**
- Presence of the latest `APPLIED input_uA=300000` event, a fresh
  (`<=15 s`) hardware VBUS monitor event, no subsequent
  `MONITOR_STOP`, `RESTORE` or `ROLLBACK_FAILED` event
- Lease is not expired, and the renewal operation is not at the
  end of the 3600-second deadline
- A local `flock` prevents concurrent renewal attempts

The main loop checks every 60 seconds and **requests renewal only when
the current lease reaches 2400 seconds**. On renewal it asks the kernel
to unload the existing module, checks `RESTORE reason=module-exit
input=00 rc=0`, rechecks voltage/temperature/USB, and inserts the
unchanged SHA-verified module via the existing RAM-only helper. The
new active monitor is checked after a short settling interval.

The 4.18 V pre-renewal boundary deliberately lies **below** the pilot
driver's 4.20 V guard. Neither value is claimed to be the actual rated
maximum of the unknown physically installed battery. Further
battery-specific validation is required before changing these limits.

## Actual phone tests

With the physical N71/S8000 at approximately 78% and in the same
RAM-booted session, the new supervisor passed a **read-only hardware
preflight**: original module SHA, board identity, USB link, SN2400
parameters, 2-second VBUS monitor and battery telemetry.

A **single attended physical renew** was then attempted. The kernel
reported:

```text
[1064.426501] n71-sn2400-trial: RESTORE reason=module-exit input=00 rc=0
[1064.550393] n71-sn2400-trial: APPLIED input_uA=300000 original_uA=90000
              VBUS_uV=5025000 automatic_restore_ms=3600000
[1066.642474] n71-sn2400-trial: MONITOR VBUS_uV=4900000
              status=b1 input_uA=300000
```

This **demonstrates one safe module rollover**, not sustained full-cycle
battery charging. The first supervisor version incorrectly treated the
previous RESTORE as a current lease failure because timestamp comparison
discarded subsecond precision; it correctly stopped supervising,
without undoing the newly applied current limit. The event parser now
defines each APPLIED event as a new epoch and clears older failure/
monitor events. Three host regression tests cover prior RESTORE,
current-cycle stop and new epoch without a fresh monitor. The revised
script subsequently passed the physical read-only check.

A brief BQ27540 `Not charging` observation was seen while SN2400
continued reporting VBUS, before returning to `Charging`. The script
accepts this status as a gauge state, **not** as proof of net charging;
cell-voltage/temperature and monitor checks remain mandatory.

## Operating status

- The revised supervisor script has been staged and checked in the
  **current phone's /run tmpfs** (not NAND)
- **A continuously running supervisor has not been enabled or verified**
  in this session; a remote execution attempt to create a resident
  process was blocked
- The previous Dell-hosted supervision service stays **disabled**
- The physical pilot's built-in **3600-second fail-safe still applies**
  unless a future verified supervisor successfully renews it
- A future boot image must be separately rebuilt and boot-tested before
  the supervisor can be considered available automatically at startup

Safety-first follow-up: verify a resident loop in a controlled attended
trial, prove at least one automatic renewal with live logs and sustained
gauge/VBUS observations, then integrate it into a **new private RAM image**
with an explicit debug fallback. Never treat this pilot as an approved
full-charge thermal/battery-management driver.
