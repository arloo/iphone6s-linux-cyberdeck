# N71/S8000 Wi-Fi kernel baseline compatibility gate

Date: 2026-11-11. OFFLINE ONLY. The iPhone was not contacted. Dell host still cannot enumerate the N71 gadget after the USB disconnect recorded at 19:13:45 CET.

## Real original configuration comparison

The working Linux framebuffer/Z2 touchscreen/USB CDC-NCM kernel and a separate private out-of-tree Wi-Fi kernel configuration were compared with tools/n71_wifi_kernel_baseline_gate.py.

The original N71 kernel has 1,323 enabled configuration symbols. All 1,323 were preserved without changing y/m values in the new Wi-Fi candidate. Only two original disabled menu roots switched to y: CONFIG_WIRELESS and CONFIG_WLAN. New symbols include CONFIG_CFG80211=m, CONFIG_BRCMUTIL=m, CONFIG_BRCMFMAC=m and CONFIG_BRCMFMAC_PCIE=y.

The gate also requires unchanged INPUT_EVDEV, TOUCHSCREEN_APPLE_Z2, DRM, DRM_SIMPLEDRM, USB_GADGET, USB_CONFIGFS, USB_CONFIGFS_NCM and APPLE_DART settings. It rejects accidentally enabling the nonfunctional S8000 research PCIe guard, wrong USB/SDIO Broadcom buses or an unrelated PCIe host.

Actual sanitized output:

    N71_KNOWN_GOOD_LINUX_CORE_CONFIG_PRESERVED_PASS
    PRESERVED_ENABLED_BASELINE_SYMBOLS 1323
    ORIGINAL_SYMBOL_CHANGES 2
    BRCMFMAC_PCIE_AND_CFG80211_CONFIGURED_OFFLINE=YES
    S8000_PCIE_HOST_AND_NATIVE_WIFI_OPERATIONAL=NO

15 synthetic tests in tests/test_n71_wifi_kernel_baseline_gate.py exercise removal of known-good touchscreen/USB/display, incorrect DART or radio options, unrelated PCIe controllers, malformed duplicate Linux Kconfig names, changed module-unload behavior and missing input files. No private kernel config or Apple firmware is distributed.

## Reproduce locally

    python3 tools/n71_wifi_kernel_baseline_gate.py /private/known-good/.config /private/offline-wifi/.config

This is a configuration-preservation check, not hardware qualification. A complete replacement kernel image still requires linkage, a safe RAM-only boot path and USB recovery; on-device PCIe/DART and Wi-Fi association are unverified. The current RAM kernel has CONFIG_MODULE_UNLOAD=n and must not be used for unremovable experimental driver probes.

The original BCM4350 firmware C2/C5 is separately stored outside Git. The S8000 host provider memory-resource ordering and port1-only clock/reset/PHY/MSI and DART1 stream fault isolation still must be proven before the native BCM4350 can enumerate. USB network forwarding does not count as radio connectivity.