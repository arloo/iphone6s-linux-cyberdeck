# N71/S8000 external 5 V charging: input-limit cause and physical recovery — 2026-11-25

## Accepted scope

The real running N71/S8000 remained in the same Linux RAM boot and was connected directly to the owner's external adapter (5V, rated 30W overall). The Dell no longer enumerated its USB device. A temporary address-specific WiFi SSH listener, authenticated with the same previously pinned host key and authorized client key, provided control. No password or forwarding was enabled; the separate USB SSH service stayed unchanged.

A newly rebuilt exact-kernel snapshot module loaded and unloaded successfully and read only SN2400 registers 07/09/0d/10/1d. VBUS and the hardware-charging bit were asserted, but input register09 remained zero, decoding to **90mA** under the source/physically qualified scale. The battery gauge independently reported net discharge around -208mA. This establishes a live external-source input-limit problem, rather than inferring charger operation from its wattage or a charging icon.

The installed kernel's drivers/mux/sn2400.c implements only HDQ line ownership and regmap access. It does not register a complete charger power_supply or autonomously negotiate/adapt input current. The reference Orchard D111 charger includes such policy, but its board charge limits are not imported into N71. The owner's original charge-current/voltage/HDQ controls remain unmodified.

## External-source physical pilot and bounded continuation

The existing exact-hash input-only module was explicitly applied at 500mA for 30 seconds on this external source. It measured no-load VBUS 5.250V and loaded VBUS 5.100–5.125V. Excluding the initial gauge lag and expiry samples, net cell current was **+226 to +235mA**, with temperature around 30.5–30.6C. The native two-second monitor stayed healthy and automatic restoration to original input returned0. No 30W/PD negotiation, higher current or full-charge durability is claimed.

After that successful source-specific qualification, an explicitly started finite 500mA recovery lease retained the native guards/maximum3600-second rollback and added local 37.5C, cell3.6–4.1V and VBUS4.75–5.5V limits. Power presence is determined by the native status/ADC/fresh monitor, not USB data configuration. The UDC still reported configured after the Dell device disappeared, so that string is not accepted as power-source identity or charger-presence proof.

The recovery does not automatically renew or start storage. Its optional reserve-completion stop requires repeated agreement between reported SOC and Remaining/Full Charge, not SOC alone. The current input-only profile is a bounded recovery mechanism, **not an integrated autonomous full-charge driver**. A temperature/voltage/VBUS/monitor stop must not be bypassed by increasing its limits.

## Gauge qualification and storage boundary

Reported capacity jumped from30 to47 percent during the short30-second observation. At the measured +230mA, the physically added charge is only about2mAh; that percentage jump cannot be treated as real energy replenished. Later Remaining/Full Charge values were mutually consistent with the then-reported percentage, but the cause of the abrupt gauge transition remains unresolved. The common driver reads SOC directly; no guessed voltage-to-SOC conversion was introduced for this test.

Before the deferred block-bridge trial, independently recheck cell voltage, current, temperature, RC/FCC agreement, stable reserve and the native monitor/lease, as well as the unchanged binary and unused epoch. The S3E module remains unloaded: there was no block registration, NAND command, mount or persistent install. Do not repeat the earlier first-Read/capacity milestones as discovery.

[Sanitized acceptance](N71_S8000_EXTERNAL_CHARGER_ACCEPTANCE_2026_11_25.json), [preceding low-reserve gate](N71_S8000_RO_BLOCK_BOOT_POWER_GATE_2026_11_25.md), [planned block bridge](N71_S8000_RO_BLOCK_BRIDGE_TRIAL_2026_11_24.md).
