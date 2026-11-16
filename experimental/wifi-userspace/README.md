# Native WLAN userspace on the tested RAM kernel

Use the source URLs and SHA-256 pins in `source-pins.json`. The physically tested tools are static ARM64 iw6.9 and WPA supplicant/CLI2.11, linked against static libnl3.11.0 core and generic-netlink libraries. The build uses `aarch64-linux-gnu-gcc`; set `N71_ARM64_PREFIX` to the private libnl installation prefix before using `wpa_supplicant.config`. With pthreads disabled, libnl `lib/socket.c` also needs `<time.h>` **after** its internal core headers, to preserve GNU feature definitions.

Apply `wpa211-brcmfmac-offload-compat.patch` to the pinned Hostap source. It carries the documented Hostap compatibility revert for the current legacy kernel image. The successful encrypted data tests are independent of the supplicant's displayed status. Future kernel images should carry the upstream `brcmfmac` PORT_AUTHORIZED fix instead.

This minimal PSK-only build does not support `-f` log files or the `update_config` configuration option. Use `-B -P /tmp/n71-wpa-live.pid` for the managed daemon, without `-f`. Keep owner network configuration private, mode0600; no credentials or original Apple firmware belong in Git.

The managed kernel module is built with `tools/build_n71_native_iommu_runtime.py --managed-wlan-runtime` and the existing kernel/source/calibration arguments. It retains the real driver until its platform device is unbound. `scripts/n71_native_wlan_runtime_stop.sh` performs the matching stop on the phone; plain rmmod is deliberately blocked while the IOMMU still has consumers.

The original C5 TRX, CLM and TxCap files must be available privately under the standard `brcmfmac4350-pcie` firmware names, with the validated private NVRAM. DHCP must install its native default route and DNS; this initramfs initially lacked `/etc`, so create it before writing `/etc/resolv.conf`. Leave a DHCP daemon running for lease renewal. The current operating session is RAM-only; automatic recovery after reboot has not been tested.
