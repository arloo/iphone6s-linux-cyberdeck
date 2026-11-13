#!/usr/bin/env bash
# N71 Samsung S8000 iPhone6s: one controlled checkm8/Pongo transfer.
# Host-only temporary /run modprobe policy. No iOS NAND changes.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BIN="$ROOT/hoolock/bin"
POLICY="/run/modprobe.d/cyberdeck-pongo-no-apple-mfi.conf"
MODE="${1:-}"

print_help() {
    cat <<'HELP'
Usage (owner Dell, interactive terminal):
  bash scripts/pongo-once-without-mfi-reload.sh status
  bash scripts/pongo-once-without-mfi-reload.sh run
  bash scripts/pongo-once-without-mfi-reload.sh restore

run:
  - Temporarily blocks apple_mfi_fastcharge auto-loading in /run.
  - Unloads this Dell host module, verifies that it is unloaded.
  - Executes the original palera1n --cli -p -k Pongo.bin command.
  - Operator puts iPhone 6s in DFU when requested.
  - Never flashes iOS NAND or boots experimental PCIe/DMA.
restore:
  - Removes ONLY this specific temporary /run policy.
  - Re-enables original Dell Apple fast-charge driver.
  - Rebooting Dell also removes this temporary /run policy.
HELP
}
if [[ "$MODE" == "status" ]]; then
    printf 'HOST_APPLE_MFI_MODULE=%s\n' "$(test -d /sys/module/apple_mfi_fastcharge && echo LOADED || echo UNLOADED)"
    printf 'CYBERDECK_RUNTIME_POLICY=%s\n' "$(test -f "$POLICY" && echo PRESENT || echo ABSENT)"
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
if [[ "$MODE" == "restore" ]]; then
    if [[ -e "$POLICY" ]]; then
        if [[ ! -f "$POLICY" || "$(cat "$POLICY")"$'\n' != "$desired_policy" ]]; then
            echo "REFUSING_TO_REMOVE_AN_UNRECOGNIZED_MODPROBE_POLICY" >&2
            exit 2
        fi
        rm -- "$POLICY"
        echo "TEMPORARY_HOST_DRIVER_POLICY_REMOVED"
    fi
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
echo "N71_PONGO_TEMP_HOST_APPLE_MFI_AUTORELOAD_DISABLED"
echo "N71_PONGO_BINARY_SHA256_VERIFIED"
echo "N71_PONGO_PLEASE_ENTER_DFU_WHEN_PALERA1N_PROMPTS"
echo "N71_PONGO_THIS_DOES_NOT_FLASH_PHONE_NAND"
echo "N71_PONGO_RESTORE_DRIVER_AFTER_TEST_WITH_THIS_SCRIPT_RESTORE"
export PALERA1N_BYPASS_PASSCODE_CHECK=1
"$BIN/palera1n" --cli -p -k "$BIN/Pongo.bin"
if lsusb -d 05ac:4141 | grep -q '05ac:4141'; then
    echo "N71_PONGO_LIVE_USB_GADGET_05ac_4141_CONFIRMED"
else
    echo "N71_PONGO_TRANSFER_EXITED_BUT_NO_4141; CHECK_DEVICE"
fi
