# N71/S8000 — live Linux baseline before further Z2 experiments

**Date:** 2026-11-10. **Device:** iPhone 6s, Samsung A9/S8000 (N71). **Mode:** native HoolockLinux, tethered, loaded entirely in RAM.

## Read-only observations from the actual phone

| Check | Observed | Meaning |
| --- | --- | --- |
| USB identity | `05ac:4142` | HoolockLinux gadget still enumerated |
| USB gadget | phone `172.16.42.1`, host `172.16.42.2` | Ping 2/2 successful; remote shell available |
| Kernel | `7.3.0-rc1-g6831bc701a6c` AArch64 | Matches previously built diagnostic modules |
| Loaded module set | `gpio_apple_pmic` only | No out-of-tree Z2 or SPI module left bound |
| Linux input | `gpio-keys`, event0 | No touchscreen input device exists |
| Linux SPI bus | no SPI devices listed | SPI2 overlay/controller not active |
| SPI2 generic power domain | `/sys/kernel/debug/pm_genpd/spi2/current_state: off-0` | Domain is currently off according to kernel PM |
| UART Bluetooth | `hci0` exists | HCI interface remains present |
| I2C bus | kernel adapters `i2c-0` and `i2c-1` exist | Does not imply userspace I2C read access |
| Userspace I2C | no `/dev/i2c-*` | Direct analog rail readout needs a separately reviewed method |
| PMIC regmap debugfs | `0-0074` exists, limited exposed registers | Did not expose the earlier touch LDO control register `0x319` here |

These checks came from `lsusb`, `ip`, `ping`, `uname`, `/proc/modules`, `/proc/bus/input/devices`, and relevant **read-only sysfs/debugfs** entries. They do not include a fresh PMGR `0x20e078000` value or a fresh Chestnut analog `0x05` readback. The earlier values (`0x800002ee` and `0x0f`) are **historical evidence only**. Never present them as measurements from the current boot.

**No kernel module was inserted, no SPI transfers were issued, and no device memory, PMIC settings or iPhone flash was written during this baseline check.**

## Experimental SPI2 power-domain lifecycle issue

The original proof-of-concept `ttpwr_v1` creates a synthetic device, attaches it to `spi2` generic PM domain and acquires a runtime reference without a matching teardown. Consequently it cannot be assumed reversible even though it previously worked.

An independent local prototype with explicit `pm_runtime_put_sync`, `pm_runtime_disable`, `pm_genpd_remove_device`, and `device_unregister` compiles against the exact kernel using LLVM 21. It remains **unloaded** and **not certified for live use**: the kernel's `pm_genpd_remove_device` can return `-EAGAIN` when a domain is prepared, and this teardown failure path needs a rigorous lifetime review before testing. A syntactically successful module build is not a guarantee of safe hardware rollback.

## Next justified steps

1. Review the SPI2 attachment/removal lifetime with the actual kernel PM core and establish reliable failure-path handling.
2. Establish a non-writing, device-authorized read of the *current* Chestnut analog rail and reference clock before any regulator change.
3. Validate USB shell, backup boot path and immutable recovery assets before enabling SPI2.
4. Test the **existing** 1,038-byte calibration frame first with sanitized 8-bit SPI transport metadata. Only if the baseline supports it, try the documented NOP-prefixed 1,040-byte variant as a **separate** experiment.
5. The NOP prefix is a source-level hypothesis: two private original Apple preconstructed **firmware** packets use NOP+DATA framing, but calibration is a different phase. Neither NOP nor alternate word size is a proven fix.

**Current go/no-go for touch hardware transfer: NO-GO** until the readback and teardown questions are resolved. The phone's native Linux/Bluetooth session remains valuable and should not be rebooted for speculation.
