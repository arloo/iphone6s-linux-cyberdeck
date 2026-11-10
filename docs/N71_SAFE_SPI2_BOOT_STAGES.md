# Safe, staged SPI2 bring-up for Samsung A9 / N71

**November 10, 2026.** This is a build-and-validation protocol, **not a successful phone boot or functioning touch driver**.

## Why the strategy changed

The earlier private `ttpwr_v1` SPI2 proof-of-concept attached a synthetic device to the generic PM domain and acquired a runtime PM reference without a matching teardown. A later local module prototype attempted to release that reference, but kernel `pm_genpd_remove_device()` can fail (e.g., while the domain is prepared), and module unload cannot safely abandon an attached device. **That experimental helper has not been cleared for use on a live phone.**

Fortunately, the separately patched N71 kernel tree already has a native Device Tree relationship:

```dts
spi2: spi@20a088000 {
    compatible = "apple,s8000-spi", "apple,s5l-spi";
    power-domains = <&ps_spi2>;
    status = "disabled"; /* SoC base; the N71 board DTS overrides this */
};
```

The board selects SPI2 `status = "okay"`, but the `apple,n71-multitouch` child remains **disabled by default**. Structural validation showed the SPI2 `power-domains` phandle resolves exactly to the `ps_spi2` PMGR node. This is not evidence that power-domain release will succeed under every runtime condition.

## Two local, offline-packaged RAM boot candidates

| Candidate | SPI2 controller status | N71 touch child | What it can prove if booted later |
| --- | --- | --- | --- |
| 00 — `spi2-off` | `disabled` | `disabled` | Whether the separately patched kernel boots without initializing the SPI2 bus |
| 01 — `spi2-host-only` | `okay` | `disabled` | Whether native S8000 SPI host and its generic PM domain can initialize without running touch firmware |

Both were **packaged offline only** using the existing m1n1 + kernel + DTBs + RAM test rootfs concatenation. The known-good HoolockLinux payload SHA-256 was verified before and after packaging; it was **not overwritten**. The two staged DTBs differ semantically by only one `status` property on SPI2. Both retain the N71 touchscreen disabled. The TSMC iPhone6s Device Tree was carried unchanged; no cross-foundry equivalence is implied.

The existing patched kernel configuration compiles the SPI and Z2 drivers as built-ins; the touch node is nevertheless disabled by the DTB. Separately, an **isolated modular configuration** was created with `CONFIG_SPI_APPLE_S5L=m` and `CONFIG_TOUCHSCREEN_APPLE_Z2=m` so the two drivers could later be brought up independently with explicit driver lifecycle checks. A targeted build of these two `.ko` modules **completed offline**, but the full modular kernel build was stopped and **there is no matching new boot-tested modular Image.gz**. The targeted modules report kernel release `7.3.0-rc1-g68aadac820d0`, while the running phone reports `7.3.0-rc1-g6831bc701a6c`. The modules **must not be inserted into the current phone kernel**. Use `tools/check_n71_module_abi.sh` for the basic release-string preflight; it is necessary, not sufficient, for compatibility.

## Mandatory preflight tool

Run against a *compiled* `s8000-n71.dtb`:

```sh
tools/check_n71_boot_dtb.sh path/to/s8000-n71.dtb off
tools/check_n71_boot_dtb.sh path/to/s8000-n71.dtb host-only
```

The tool requires `fdtget` (from `dtc`) and checks: N71/S8000 compatibility, expected SPI2 status, **disabled** touch child, matching SPI2 `power-domains` and PMGR phandle, and a compatible S5L SPI host. A deliberately altered fixture with touch `status = "okay"` was rejected in offline testing. The script **does not flash, patch or boot the phone**.

## Live validation order — only after further review

1. Keep the existing proven RAM-only image separately immutable, with a documented normal-iOS recovery path.
2. If a future boot test is approved, boot the conservative candidate first; confirm kernel, USB gadget and Bluetooth remain alive.
3. Only then test host-only candidate, verifying SPI2 driver, clock and generic-PM state. With the touch child disabled, **no calibration should be attempted**.
4. Evaluate modular driver lifecycle separately. Only an explicitly measured ability to return to the original idle power-domain state can qualify a subsequent touch test.
5. Acquire verified *current* analog-rail and touch-clock baseline readings before any regulator or clock changes. Older saved values are not substitutes.
6. Baseline 1,038-byte DATA framing must be measured before considering the 1,040-byte NOP-prefixed hypothesis. No speculative vendor-command fuzzing or storage writes.

**Current device remains on the known-good HoolockLinux USB session. Neither staged image has been booted, and no experimental module or GPIO/power change was made during staging.**
