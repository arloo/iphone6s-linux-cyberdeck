# N71/S8000 SPI2 — guarded platform unbind/rebind on physical iPhone 6s

**Date:** 2026-11-10
**Result:** **PASS — power domain ON → OFF → ON; reference clock enabled → disabled → enabled; SPI master recovered.**
**Scope:** Linux platform driver lifecycle only. No Z2 protocol, SPI payload transfers or touch calibration.

## Starting state

The experimental `01-spi2-host-only` RAM boot had already reached a BusyBox root shell on the real N71 (Apple A9 S8000). The same device remained reachable from Kubuntu over the USB gadget network at `172.16.42.1` and presented USB ID `05ac:4142`.

- Driver `apple-s5l-spi` successfully bound to the sole SPI2 platform device `20a088000.spi`.
- SPI host `spi0` existed, with a 48 MHz reference clock.
- The SPI2 generic power domain reported `on`; `spi_ref/clk_enable_count` reported `1`.
- `/sys/kernel/debug/pm_genpd/spi2/devices` contained exactly one consumer: `20a088000.spi`.
- `/proc/device-tree/soc/spi@20a088000/touchscreen@0/status` reported `disabled`.
- `/sys/bus/spi/devices` was empty; no Z2 driver, transfers, or child input were present.

## Controlled procedure

A temporary shell script was written to the **phone's RAM-only `/tmp`**, syntax-checked with BusyBox `sh -n`, and required all preconditions above to pass. The script:

1. Read the initial generic power-domain state and SPI reference-clock enable count.
2. Launched an independent 5-second watchdog to re-bind the platform device through `/sys/bus/platform/drivers/apple-s5l-spi/bind` if it remained unbound. The watchdog redirected standard input/output and recorded its status in `/tmp`.
3. Issued **one** controlled sysfs `unbind` of `20a088000.spi`.
4. Read the state and reference-clock enable count while unbound.
5. Allowed the watchdog to rebind the controller, then confirmed the driver symlink and `spi0` reappeared, with the domain and clock restored.

No attempt was made to change the touchscreen Device Tree status, power its external analog rails, modify SPI pinmux manually, transfer data, or write iOS storage.

## Direct measurements

| State | Generic SPI2 domain | `spi_ref` enable count | Driver / controller |
| --- | --- | --- | --- |
| Initial, bound | `on` | `1` | Driver bound, `spi0` present |
| Immediately after unbind | `off-0` | `0` | Driver absent |
| After watchdog rebind | `on` | `1` | Driver bound again, `spi0` present |

The iPhone shell printed:

```text
BASELINE: PM=on CLK=1 SPI0=present
AFTER_UNBIND: PM=off-0 CLK=0
AFTER_UNBIND_DRIVER_ABSENT
AFTER_WATCHDOG: PM=on CLK=1
DRIVER_REBOUND_PASS
WATCHDOG: PM=on
```

The post-cycle kernel log included a new `apple-s5l-spi ... S5L SPI controller, ref clock 48000000 Hz` probe at uptime approximately 1,198.8 seconds. After the cycle, the Z2 child remained disabled and the SPI master remained present. No Oops, panic or SPI timeout was observed during this short test.

## Interpretation and correction to the original modular plan

The S5L host driver is **built into this kernel**, so it cannot be removed using `rmmod`. However, a built-in Linux platform driver still exposes driver-core **sysfs unbind/rebind**. That mechanism is sufficient to test this driver's controller-registration and generic power-domain *binding lifecycle* without rebuilding the kernel as a module.

The previous plan's statement that a modular kernel was strictly required for a bind/unbind experiment was therefore too broad. A modular build would only be needed for specifically testing module unload/reload behavior, or for replacing driver code without rebuilding the kernel.

**What remains unproven:** reliable repeated cycling under load, full touch analog-rail control, electrical SPI signaling, Z2 identity and firmware protocol, calibration ACK, touch input reporting, and Wi-Fi. Runtime PM was reported `unsupported`; this test relied on full platform driver detach/attach, **not runtime suspend/resume**.

## Next touch experiment gates

1. Capture any available read-only N71/S8000 SPI2 pinmux and touch external-power dependencies from the private board data without publishing raw firmware, provisioning blobs or unique device identifiers.
2. Design an isolated Z2 presence/protocol probe with carefully bounded transactions, a strict timeout, and a documented rollback. No analog-rail power modifications without explicit preflight.
3. Keep the RAM-only PongoOS recovery path and the verified SPI2-OFF image available for each subsequent real-device experiment.
4. Test BLE and PCIe Wi-Fi separately; current binding-lifecycle measurements do not validate either subsystem.
