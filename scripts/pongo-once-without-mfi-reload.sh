#!/usr/bin/env bash
# N71 Samsung S8000 iPhone6s: one controlled checkm8/Pongo transfer.
# Host-only temporary /run modprobe policy. No iOS NAND changes.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BIN="$ROOT/hoolock/bin"
POLICY="/run/modprobe.d/cyberdeck-pongo-no-apple-mfi.conf"
UDEV_RULE="/run/udev/rules.d/80-drivers.rules"
MODE="${1:-}"

print_help() {
    cat <<'HELP'
Usage (owner Dell, interactive terminal):
  bash scripts/pongo-once-without-mfi-reload.sh status
  bash scripts/pongo-once-without-mfi-reload.sh run
  bash scripts/pongo-once-without-mfi-reload.sh restore

run:
  - Temporarily blocks apple_mfi_fastcharge and the Apple boot-mode USB device
    modalias autoload path in /run; interface-driver events are unchanged.
  - Unloads this Dell host module, verifies that it is unloaded.
  - Executes the original palera1n --cli -p -k Pongo.bin command.
  - Operator puts iPhone 6s in DFU when requested.
  - Never flashes iOS NAND or boots experimental PCIe/DMA.
restore:
  - Removes ONLY the two recognized temporary /run policies and reloads udev.
  - Re-enables original Dell Apple fast-charge driver.
  - Rebooting Dell also removes both temporary /run policies.
HELP
}
if [[ "$MODE" == "status" ]]; then
    printf 'HOST_APPLE_MFI_MODULE=%s\n' "$(test -d /sys/module/apple_mfi_fastcharge && echo LOADED || echo UNLOADED)"
    printf 'CYBERDECK_RUNTIME_POLICY=%s\n' "$(test -f "$POLICY" && echo PRESENT || echo ABSENT)"
    printf 'CYBERDECK_RUNTIME_UDEV_RULE=%s\n' "$(test -f "$UDEV_RULE" && echo PRESENT || echo ABSENT)"
    for id in 05ac:12a8 05ac:1227 05ac:4141 05ac:4142; do
        lsusb -d "$id" || true
    done
    exit 0
fi
if [[ "$MODE" == "help" || "$MODE" == "--help" || "$MODE" == "-h" ]]; then
    print_help
    exit 0
fi
if [[ "$MODE" != "run" && "$MODE" != "restore" ]]; then
    print_help >&2; exit 2
fi
if [[ "$EUID" -ne 0 ]]; then
    echo "ADMINISTRATIVE_SHELL_REQUIRED" >&2; exit 2
fi
desired_policy=$'blacklist apple_mfi_fastcharge\ninstall apple_mfi_fastcharge /bin/false\n'
# Match USB DEVICE events only. Per-interface events still load CDC/NCM, etc.
# MODALIAS is read-only in this udev version. Temporarily prepend a narrow
# skip inside an otherwise identical copy of the vendor 80-drivers.rules.
VENDOR_DRIVER_RULES="/usr/lib/udev/rules.d/80-drivers.rules"
if [[ -e /etc/udev/rules.d/80-drivers.rules || -L /etc/udev/rules.d/80-drivers.rules ]]; then
    echo "CUSTOM_ETC_DRIVER_RULES_PRESENT; STOP" >&2; exit 2
fi
if [[ ! -f "$VENDOR_DRIVER_RULES" || -L "$VENDOR_DRIVER_RULES" ]] ||
   ! grep -Fxq 'LABEL="drivers_end"' "$VENDOR_DRIVER_RULES"; then
    echo "UNRECOGNIZED_VENDOR_DRIVER_RULES; STOP" >&2; exit 2
fi
udev_guard='ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="05ac", ATTR{idProduct}=="12a8|1227|1281|1338|4141|4142", GOTO="drivers_end"'
desired_udev_rule="$udev_guard"$'\n'"$(cat -- "$VENDOR_DRIVER_RULES")"$'\n'
check_managed_file() {
    local file="$1" expected="$2"
    if [[ -e "$file" || -L "$file" ]]; then
        if [[ -L "$file" || ! -f "$file" || "$(cat -- "$file")"$'\n' != "$expected" ]]; then
            echo "REFUSING_UNRECOGNIZED_RUNTIME_POLICY: $file" >&2
            exit 2
        fi
    fi
}
# Validate both before changing either, including on restore.
check_managed_file "$POLICY" "$desired_policy"
check_managed_file "$UDEV_RULE" "$desired_udev_rule"
if [[ "$MODE" == "restore" ]]; then
    rm -f -- "$UDEV_RULE" "$POLICY"
    udevadm control --reload
    udevadm settle --timeout=10
    echo "TEMPORARY_HOST_DRIVER_POLICIES_REMOVED"
    modprobe apple_mfi_fastcharge || {
        echo "DRIVER_RELOAD_FAILED; PC_REBOOT_RESTORES_DEFAULT_POLICY" >&2
        exit 1
    }
    echo "HOST_APPLE_MFI_DRIVER_RESTORED"
    exit 0
fi

for file in "$BIN/palera1n" "$BIN/Pongo.bin"; do
    [[ -s "$file" && ! -L "$file" ]] || {
        echo "LOCAL_VERIFIED_TOOL_MISSING" >&2; exit 2;
    }
done
if [[ -e "$POLICY" || -L "$POLICY" ]]; then
    if [[ ! -f "$POLICY" || -L "$POLICY" ||
          "$(cat "$POLICY")"$'\n' != "$desired_policy" ]]; then
        echo "UNRECOGNIZED_EXISTING_POLICY; STOP" >&2
        exit 2
    fi
    echo "EXISTING_IDENTICAL_RUNTIME_POLICY_REUSED"
fi
EXPECTED_PONGO_SHA256="1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575"
PONGO_SHA256="$(sha256sum "$BIN/Pongo.bin" | cut -d' ' -f1)"
[[ "$PONGO_SHA256" == "$EXPECTED_PONGO_SHA256" ]] || {
    echo "PONGO_BINARY_HASH_MISMATCH; ABORTING" >&2; exit 2
}
install -d -m 0755 /run/modprobe.d
if [[ ! -e "$POLICY" ]]; then
    (umask 022; printf '%s' "$desired_policy" > "$POLICY")
    chmod 0644 "$POLICY"
fi
install -d -m 0755 /run/udev/rules.d
if [[ ! -e "$UDEV_RULE" ]]; then
    (umask 022; printf '%s' "$desired_udev_rule" > "$UDEV_RULE")
    chmod 0644 "$UDEV_RULE"
fi
udevadm verify "$UDEV_RULE" || {
    echo "HOST_RUNTIME_UDEV_RULE_INVALID; STOP" >&2; exit 2
}
udevadm control --reload || {
    echo "HOST_UDEV_RELOAD_FAILED; STOP" >&2; exit 2
}
# Drain events already queued with the old autoload policy before unloading.
udevadm settle --timeout=10 || {
    echo "HOST_UDEV_QUEUE_DID_NOT_SETTLE; STOP" >&2; exit 2
}
if [[ -e /sys/module/apple_mfi_fastcharge ]]; then
    modprobe -r apple_mfi_fastcharge || {
        echo "HOST_MODULE_UNLOAD_FAILED; see restore command" >&2; exit 2
    }
fi
if [[ -e /sys/module/apple_mfi_fastcharge ]]; then
    echo "HOST_MODULE_STILL_LOADED; STOP; see restore command" >&2
    exit 2
fi
# Do not pipe grep -q under pipefail: it exits early and makes
# modprobe's SIGPIPE exit 141 look like a policy failure.
if ! grep -Fxq 'install apple_mfi_fastcharge /bin/false' <(modprobe --showconfig); then
    echo "HOST_RUNTIME_POLICY_NOT_EFFECTIVE; STOP" >&2
    exit 2
fi
echo "N71_PONGO_TEMP_HOST_UDEV_BOOT_MODALIAS_BLOCKED"
echo "N71_PONGO_TEMP_HOST_APPLE_MFI_AUTORELOAD_DISABLED"
echo "N71_PONGO_BINARY_SHA256_VERIFIED"
echo "N71_PONGO_PLEASE_ENTER_DFU_WHEN_PALERA1N_PROMPTS"
echo "N71_PONGO_THIS_DOES_NOT_FLASH_PHONE_NAND"
echo "N71_PONGO_RESTORE_DRIVER_AFTER_TEST_WITH_THIS_SCRIPT_RESTORE"
export PALERA1N_BYPASS_PASSCODE_CHECK=1
set +e
"$BIN/palera1n" --cli -p -k "$BIN/Pongo.bin"
palera_rc=$?
set -e
echo "N71_PALERA1N_EXIT_CODE=$palera_rc"
if lsusb -d 05ac:4141 | grep -q '05ac:4141'; then
    echo "N71_PONGO_LIVE_USB_GADGET_05ac_4141_CONFIRMED"
else
    echo "N71_PONGO_TRANSFER_EXITED_BUT_NO_4141; CHECK_DEVICE" >&2
    exit 1
fi
