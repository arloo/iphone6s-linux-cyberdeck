# N71/S8000 SPI2 driver lifecycle — modular strategy

**2026-11-10. Status: code-reviewed and configured offline, not boot-tested.**

## Why prefer a module instead of the synthetic power helper?

The earlier `ttpwr_v1` SPI2 test module created a synthetic `struct device`, explicitly attached it to a generic power domain, and acquired a runtime PM reference. It did not provide a matching teardown. A separate private prototype with explicit release exposed a difficult module-exit failure mode: `pm_genpd_remove_device()` may fail when the power domain is prepared, but a module's exit path cannot simply cancel unload. This makes that prototype unsuitable for live use.

The locally patched S8000 kernel offers an alternative that uses the standard driver core, not a synthetic reference:

1. The N71 Device Tree declares `spi@20a088000` with `power-domains = <&ps_spi2>`; the phandle matches the actual PMGR provider node.
2. `drivers/base/platform.c::platform_probe` attaches the power domain using `PD_FLAG_ATTACH_POWER_ON | PD_FLAG_DETACH_POWER_OFF`.
3. `drivers/spi/spi-apple-s5l.c` uses devres-managed controller registration and `devm_clk_get_enabled`; when the driver unbinds, those resources have normal devres cleanup.
4. `drivers/base/dd.c::device_unbind_cleanup` calls `devres_release_all()` and then `dev_pm_domain_detach(dev, dev->power.detach_power_off)`.
5. Both driver Kconfig entries are `tristate`. A separate local kernel configuration therefore sets `CONFIG_SPI_APPLE_S5L=m` and `CONFIG_TOUCHSCREEN_APPLE_Z2=m`, leaving the N71 touch child disabled by default.

The original document described an offline-only hypothesis. A subsequent **physical guarded sysfs platform unbind/rebind test** on the host-only kernel confirmed the SPI2 generic domain transitioned `on → off-0 → on`, and its reference clock enable count `1 → 0 → 1` while the Z2 child remained disabled. See [live power-cycle validation](N71_SPI2_POWER_CYCLE_LIVE_VALIDATION.md). This does **not** guarantee safety while child devices or transfers are active.

## Experimental gates

- Preserve the known-good boot image; never replace it in place.
- Package the modular kernel as a distinct RAM-only recovery-test candidate.
- Boot with the N71 touch child **disabled**; do not embed private calibration or firmware into any public or CI build.
- Verify the kernel and USB gadget first. With no S5L driver module loaded, the physical SPI2 domain should be reported as off; if it is not, stop.
- Test the **SPI host module only**, without a touchscreen client, and measure the generic power-domain state before load, while bound, and after removing the module.
- On bind failure or incorrect post-unbind state, stop testing; do not enable analog rails or issue HBPP commands.
- Separately review the touch reference clock and Chestnut analog rail baseline and exact rollback. Only then is a bounded calibration experiment eligible.
- Never combine calibration NOP framing and alternate 16-bit SPI transfer into the same test.

## Evidence still missing

The modular kernel image and `.ko` artifacts must first compile successfully, then pass preflight checks. Device-specific USB, PMGR and GPIO rollback has **not** been tested with this kernel. The touchscreen has not emitted functional high-resolution multitouch coordinates.

**No hardware behavior is inferred merely from a kernel Kconfig option or source-code inspection.**

## Offline targeted compilation results

An isolated copy of the patched kernel build tree was configured with:

```text
CONFIG_SPI_APPLE_S5L=m
CONFIG_TOUCHSCREEN_APPLE_Z2=m
CONFIG_INPUT_TOUCHSCREEN=y
CONFIG_OF_OVERLAY=y
```

The full kernel build was intentionally terminated before completion, avoiding an unnecessary full-system recompile. A targeted `make` of `drivers/spi/spi-apple-s5l.ko` and `drivers/input/touchscreen/apple_z2.ko` then **succeeded**, using LLVM 21. No module or new kernel was loaded on the phone.

Both modules report **`7.3.0-rc1-g68aadac820d0`** in vermagic. The iPhone's proven live kernel reports **`7.3.0-rc1-g6831bc701a6c`**. Therefore, these artifacts are **not eligible for insertion into the current phone session**. A separate, matching modular kernel image remains to be built and validated if this strategy is selected for a later boot experiment.

The repository includes `tools/check_n71_module_abi.sh`. Offline checks accepted both modules for their own target release and rejected both against the running iPhone's release. This is a minimal preflight only: even matching vermagic does **not** establish safe SPI2 electrical behavior or a correct rollback.
