# N71/S8000 SN2400 USB-stable charge startup (2026-11-24)

## Evidence and scope

The existing physically booted batt2 RAM image loaded the optional SN2400 input-current trial at approximately 2.17 s, then its independent hardware monitor observed VBUS=0 at approximately 6.32 s and restored its original 90 mA setting. DWC2 gadget reconfiguration was observed around 28 s. USB-SSH recovered, but battery readings confirmed continued discharge.

The startup update does not fix battery charging on the currently running phone: this image has not been booted physically. Its only purpose is to qualify a safer subsequent RAM-only boot candidate without enabling S3E/NAND storage.

## Safer startup sequence

1. Validate N71/S8000 kernel, device-tree family, bundled SHA-256 manifest and initial USB enumeration.
2. Initialize PMIC GPIO and Bluetooth independently. An unsuccessful PMIC step stops the charger sequence.
3. Start a detached charge-monitor worker, allowing init to continue to the Cyberdeck interface without waiting up to 20 minutes.
4. The one-shot worker validates hashes again, permits no duplicate worker, waits until boot uptime >=45 s and requires 15 consecutive configured UDC samples. Any instability resets the count.
5. Re-check battery telemetry and refuse energizing the trial outside 35–98% SOC, 10.0–37.4 C, 3.50–4.149999 V, or health=Good. At high SOC/voltage it waits for a valid window for no more than 20 minutes; USB loss or invalid data stops it.
6. Only then permit a single 300 mA SN2400 input-current trial with a maximum 3,600-second lease. This is an input-current limit, not guaranteed net battery-charge current. Existing module VBUS and temperature monitors and rollback remain unchanged.

## Verification

A host-only path-isolated unittest harness covers 11 scenarios including safe arming, full battery rejection, unconfigured USB, early uptime, USB glitch resetting stability, invalid PMIC, hash failure, duplicate trial module, unsafe temperature/voltage/capacity/health, and non-blocking main startup. No test modifies PMIC, UDC, power-supply registers, NAND, or USB on a live phone.

A private 2026-11-24 RAM-only candidate was repacked preserving kernel, DTBs, m1n1 header/splash, and all CPIO entries except the startup script and its SHA-256 manifest. The image contains existing private runtime/credentials and MUST NOT be committed to Git. Hardware boot remains to be performed in a later controlled session.

## Physical validation criteria (not yet performed)

Verify the worker launches without blocking the UI, USB stays configured through the 45+15-second stability gate, live SN2400 monitor reads genuine VBUS, battery current becomes consistently positive rather than continuing to discharge, health/temperature/voltage stay within conservative limits, and automatic rollback works after a fault or lease expiration. Never infer charging from an attached cable alone. No S3E/NAND operation until power is stable.
