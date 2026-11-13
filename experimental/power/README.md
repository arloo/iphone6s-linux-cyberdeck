# N71 SN2400 charging investigation

Status: physical N71 before/during/after trial PASS. Increasing the input limit from 90 to 300 mA produces positive battery current; restoring 90 mA returns to discharge. A monitored session lease is active; automatic boot integration and full-charge durability remain pending.

The N71 diagnostic kernel reads the BQ27540 gauge correctly, but its existing SN2400 driver only handles HDQ ownership. Across a 60-sample Dell/wall-supply observation the gauge reported net discharge throughout. Native PCIe/WLAN remains pending; PCIe tests are paused for charging work.

A read-only snapshot through the existing SN2400 regmap on the physical N71 returned:

| Register | Raw value | Interpretation used |
| --- | --- | --- |
| 0x07 | 0xb9 | VBUS and hardware-charging bits asserted, per upstream driver |
| 0x09 | 0x00 | Input-current setting: 90 mA, per upstream scale |
| 0x0d | 0xff | Original charge-limit register; not modified |
| 0x10 | 0x04 | Original input-control state; not modified |
| 0x1d | 0x00 | Original HDQ idle state |

The charger can report hardware charging while the battery still loses charge: the battery gauge measures net battery current. These are different measurements. The observed 90 mA input setting is a specific candidate cause, not proof that changing it solves charging.

Register definitions and scaling are based on Paul Praschl's [Apple SN2400 charger driver](https://github.com/OrchardLinux/orchard/blob/8ea3182ac02f1c4da22dce8c082eb0df5f7083d3/kernel/patches/import/pauli1go/0077-power-supply-add-Apple-SN2400-charger.patch), originally targeting D111. An independent offline inspection of the owner's original N71 AppleSN2400Charger code also found the `90 + 10 * code` arithmetic. Proprietary binaries and disassembly stay private. This does not import D111 board current/voltage limits onto N71.

`n71-sn2400-input-trial.c` defaults unarmed and makes no hardware access in that mode. With explicit `armed=1`, it accepts only 300 mA or 500 mA input targets, requires exact N71/S8000 identity and the observed initial register pattern, checks the live gauge, measures VBUS through the SN2400 ADC, and changes only input register 0x09. The default target is 300 mA. ADC register 0x11 is written only to request a VBUS conversion; battery charge-current and voltage controls are not programmed.

The trial requests restoration of the original input setting after 30 seconds using a 2-second monitor cadence. It also restores on VBUS loss/droop, out-of-range battery measurements, input readback mismatch, and unload. Module data/device references are retained if an initialization-time write and its rollback both fail, so explicit cleanup remains possible. This experimental observation module is not a complete charger driver or a durable boot policy.

The armed trial requires capacity above 10%, temperature from 10 C to below 40 C, battery voltage from 3.3 to 4.2 V, and VBUS from 4.4 to 5.5 V. The first actual arm request was rejected at 9% before changing input register 0x09. The owner had requested stopping for recharge at 10%; physical validation must resume after recharge. No input-limit increase or positive-current result is claimed.

Validation: read-only snapshot load/unload passed on the real diagnostic kernel. The first trial candidate's unarmed load/unload passed. The revised source compiled for ARM64 with matching kernel vermagic; 20 cases execute the actual C source with fake kernel I/O and cover unarmed behavior, limits, identity, existing configuration, ADC errors, partial writes, failed rollback ownership, timed restore, droop/detach, temperature and unload. These software tests do not simulate analog hardware. Run them with:

```sh
python3 -m unittest discover -s tests -p test_n71_sn2400_input_trial.py -v
```

Build externally against the exactly matching owner-local kernel:

```sh
make -C "$KERNEL" O="$BUILD" M="$PWD/experimental/power" \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- modules
```

The existing private RAM image is unchanged. A pinned owner-local USB runner is staged for a before/during/after comparison following recharge. It defaults unarmed, uses the single-syscall module loader, and does not automatically retry a rejected arm request.

## Physical charging fix validation after recharge

The owner returned with Linux active and 56% battery. The initial trial rejected an idle ADC selector of `0x0a`; it made no input-limit change. The revised ADC helper accepts idle selectors only, saves the selector, performs the VBUS conversion, and restores the selector after each measurement. Active and unknown ADC control bits remain rejected.

The complete physical comparison on the same diagnostic kernel was:

| Phase | Input limit | Battery state/current | Other observation |
| --- | --- | --- | --- |
| Before | 90 mA | Discharging, -150 mA | 55%, 3.921 V, 31.0 C |
| During | 300 mA | Charging: +100, +107, +101, +112, +101 mA | Remaining charge 700 to 701 mAh; VBUS about 4.9 V |
| After automatic restore | 90 mA | Discharging, -142 mA | Restore readback and module removal returned 0; USB intact |

This demonstrates real net charging under Linux and the effect of the input limit on this N71. It does not prove that the earlier Wi-Fi experiments caused the 90 mA setting, or qualify every charger/cable and temperature condition.

A subsequent version adds read-only `lease_seconds=30..3600`, default 30, to support a monitored research session. A 3600-second lease at 300 mA was explicitly activated on the physical phone after the successful rollback test. It automatically restores the previous input setting on expiry, monitor failure or unload. This is a temporary RAM-session fix; it must be re-applied after reboot and is not an autonomous, full-charge driver. Battery voltage/temperature and VBUS bounds are unchanged.

The actual C source passes 23 fake-I/O scenarios, including the preserved idle ADC selector, unknown ADC control rejection, and excessive lease rejection. ARM64 module compilation and matching kernel ABI pass. No battery charge-voltage/current setpoints were altered.
