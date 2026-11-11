# N71 Wi-Fi: signed regulatory PKCS#7 symbol — verified offline ARM64 export

**Date:** 2026-11-11. **Device target:** iPhone 6s Samsung A9/S8000 N71. **Host-only compiler verification; no phone connection, no kernel boot or NAND modification.**

## Root cause of the earlier cfg80211 modpost failure

The last proven display/Z2 touch/USB Linux boot was built without `CONFIG_SYSTEM_DATA_VERIFICATION`. Its actual exported-kernel-symbol list does not include `verify_pkcs7_signature`. However, the isolated BCM4350 Wi-Fi candidate includes `CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y` and the compiled `cfg80211.o` references that symbol. Attempting to link cfg80211 against the old kernel correctly failed in `modpost`.

In the original pinned Linux source, `certs/system_keyring.c` exports `verify_pkcs7_signature` only under `CONFIG_SYSTEM_DATA_VERIFICATION`. Disabling signed-regulatory-database enforcement or fabricating the kernel symbol would not be an acceptable fix.

## Actual new verified build

From the separate offline Wi-Fi kernel build tree on the Dell, using the original Linux AArch64 cross toolchain:

```bash
make -s -j2 -C /private/linux-source \
  O=/private/isolated-wifi-kernel-build \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  certs/system_keyring.o
```

The actual `certs/system_keyring.o` is ELF64 AArch64 relocatable and exposes both `verify_pkcs7_signature` and `__export_symbol_verify_pkcs7_signature`. The original known-good `Module.symvers` does not contain the export. The separately compiled Wi-Fi candidate `cfg80211.o` still imports the symbol. Thus the missing symbol's implementation and export metadata have been compiled for the candidate kernel, without touching the original image.

The isolated Wi-Fi candidate enables `CONFIG_SYSTEM_DATA_VERIFICATION=y`, `CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y`, `CONFIG_CFG80211_USE_KERNEL_REGDB_KEYS=y`, `CONFIG_ASYMMETRIC_KEY_TYPE=y`, and `CONFIG_PKCS7_MESSAGE_PARSER=y`.

Public `tools/n71_wifi_pkcs7_compat_gate.py` compares both private kernel configurations and the original `vmlinux` export map, checks that both new objects are genuine AArch64 relocatable ELFs, and confirms the reference/export relationship. It explicitly reports `NEW_VMLINUX_LINKED_OR_BOOTED=NO`. Twelve synthetic fail-closed tests in `tests/test_n71_wifi_pkcs7_compat_gate.py` reject removal of signing enforcement, missing trusted keys, absent exported symbol/reference and changes to the original kernel.

### Reproduce without phone hardware

```bash
python3 tools/n71_wifi_pkcs7_compat_gate.py \
  /private/known-good/.config \
  /private/isolated-wifi/.config \
  /private/known-good/Module.symvers \
  /private/isolated-wifi/certs/system_keyring.o \
  /private/isolated-wifi/net/wireless/cfg80211.o
```

## What remains blocked

This result closes the symbol mismatch at source-object level only. No replacement `vmlinux`, complete `cfg80211`/`brcmfmac` modules, final ABI checks, signed regulatory database trust test, or RAM boot were produced. In parallel, the experimental S5L8960x DART packed-TCR fix passes real C testing and ARM64 cross-compilation, but whole-instance DART resets in probe/remove/resume still prohibit hardware activation until physical SID, IOVA and DMA-fault isolation are independently qualified.

Native S8000 PCIe port 1 is not enumerated and onboard BCM4350 radio association remains NOT ACHIEVED. The proven Linux LCD/touch/USB RAM image and recovery path remain unchanged.
