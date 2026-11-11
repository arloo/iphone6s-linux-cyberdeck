#!/bin/sh
# N71/S8000 Z2 post-firmware runtime initialization.
# Public logic only; private calibration and firmware live in the initramfs.
# No persistence, no automatic retries and no device resets.
set -u

Z2_DIR=/sys/bus/spi/devices/spi0.0
BOARD_FILE=/proc/device-tree/compatible
MARKER=/run/n71_z2_auto_attempted
TAG="[n71-z2-auto]"

log() { printf '%s %s\n' "$TAG" "$1"; }
fail() { log "FAIL:$1"; exit 1; }

# Exact board allowlist, not "any Apple Z2 touchscreen".
if [ ! -r "$BOARD_FILE" ]; then
    log "SKIP:no_board"
    exit 0
fi
if ! tr '\000' '\n' < "$BOARD_FILE" | grep -qx apple,n71; then
    log "SKIP:not_N71"
    exit 0
fi

# Wait for sysfs probe only. No controller command is retried.
tries=0
while [ ! -r "$Z2_DIR/runtime_state" ] && [ "$tries" -lt 8 ]; do
    tries=$((tries + 1))
    sleep 1
done
[ -r "$Z2_DIR/runtime_state" ] || fail "no_runtime_state"
[ ! -e "$MARKER" ] || fail "already_attempted"

state=""
read_state() {
    state="$(cat "$Z2_DIR/runtime_state" 2>/dev/null)" || fail "state_read"
    [ -n "$state" ] || fail "state_empty"
}
expect_tokens() {
    for token in "$@"; do
        case " $state " in
            *" $token "*) ;;
            *) fail "unexpected_protocol_state" ;;
        esac
    done
}
write_once() {
    control="$1"
    requested="$2"
    [ -w "$Z2_DIR/$control" ] || fail "control_not_writable"
    printf '%s' "$requested" > "$Z2_DIR/$control" || fail "spi_error"
}

read_state
expect_tokens "booted=1" "wake_attempted=0" "d9_attempts=0" \
    "d9_fetch_attempted=0" "type1_attempted=0" "af_attempted=0"

# Arm the failure-safe marker BEFORE sending any state-changing command.
: > "$MARKER" || fail "marker_write"
log "START"

write_once runtime_wake 1
read_state
expect_tokens "wake_attempted=1" "wake_rc=0"
log "WAKE_OK"

write_once runtime_d9 1
read_state
expect_tokens "d9_attempts=1" "d9_rc=0" "d9_reply=0xe1" "d9_checksum_ok=1"
log "D9_FIRST_OK"

write_once runtime_d9 1
read_state
expect_tokens "d9_attempts=2" "d9_rc=0" "d9_reply=0xe3" \
    "d9_status=0" "d9_size=16" "d9_checksum_ok=1"
log "D9_SECOND_OK"

# Type-1 was established on the real N71 in supervised testing.
write_once runtime_d9_fetch 1
read_state
expect_tokens "d9_fetch_attempted=1" "d9_fetch_mode=1" \
    "d9_fetch_rc=0" "d9_fetch_first=0xe7" \
    "d9_fetch_checksum_ok=1" "d9_geometry_plausible=1"
log "D9_SURFACE_OK"

write_once runtime_type1_setup 1
read_state
expect_tokens "type1_attempted=1" "type1_rc=0"
log "TYPE1_SETUP_OK"

write_once runtime_af 1
read_state
expect_tokens "af_attempted=1" "af_rc=0" "af_reply=0xe1" "af_checksum_ok=1"
log "COMPLETE:PROTOCOL_READY"
exit 0
