#!/usr/bin/env python3
"""Read-only, host-side N71/S8000 status monitor over pinned USB SSH.

Prints *only* whitelisted coarse telemetry. No remote writes, root device
commands, secrets, Bluetooth addresses, private file names or implicit key
trust. Linux Mint can display this through an separately authorized Dell
remote shell; no inbound server is started here.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

DEFAULT_CONFIG = (Path.home() / "Documenti/cyberdeck-a9-linux/private-touch-live-test"
                  / "n71-ssh-20261116/client-config-PRIVATE.json")
SAFE_KEYS = ("kernel", "capacity", "status", "cell_uV", "current_uA",
             "temp_tenths", "usb", "wlan", "wifi_ip",
             "bluetooth", "nvme_module", "nand_reset", "ui",
             "charge_supervisor", "ram_available_kb")
PROBE = r"""set -eu
printf 'kernel=';uname -r
b=/sys/class/power_supply/bq27540-0
for field in capacity status voltage_now current_now temp; do
 case "$field" in voltage_now) key=cell_uV;;current_now) key=current_uA;;temp) key=temp_tenths;;*)key=$field;;esac
 printf '%s=' "$key";cat "$b/$field"
done
printf 'usb=';cat /sys/class/udc/20c100000.usbdev/state
printf 'wlan=';cat /sys/class/net/wlan0/carrier
printf 'wifi_ip=';ip -4 addr show dev wlan0 | awk '/inet / {split($2,a,"/");print a[1];exit}'
printf 'bluetooth=';if [ -e /sys/class/bluetooth/hci0 ];then echo present;else echo absent;fi
printf 'nvme_module=';if grep -q '^n71_s3e_p0_asserted_reset_rootstart ' /proc/modules;then echo loaded;else echo absent;fi
printf 'nand_reset=';if grep 'gpio-160' /sys/kernel/debug/gpio | grep -q 'out lo';then echo asserted_low;else echo not_asserted_low;fi
printf 'ui=';if pidof n71-cyberdeck-shell >/dev/null;then echo running;else echo absent;fi
printf 'charge_supervisor='
if [ -r /run/n71-charge-supervisor.pid ] && kill -0 "$(cat /run/n71-charge-supervisor.pid)" 2>/dev/null;then echo running;else echo inactive;fi
printf 'ram_available_kb=';awk '/^MemAvailable:/ {print $2;exit}' /proc/meminfo
"""

def load_config(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private SSH config absent or symlink")
    st = path.stat(follow_symlinks=False)
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
        raise ValueError("Private SSH config ownership/permissions invalid")
    cfg = json.loads(path.read_text())
    pin = Path(cfg["known_hosts"])
    key = Path(cfg["identity_file"])
    for f in (pin, key):
        if f.is_symlink() or not f.is_file():
            raise ValueError("SSH key or host pin unavailable")
        st = f.stat(follow_symlinks=False)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
            raise ValueError("SSH key or host pin permissions invalid")
    args = list(cfg["ssh_common_args"])
    for item in ("StrictHostKeyChecking=yes", "IdentitiesOnly=yes",
                 "BatchMode=yes", "UserKnownHostsFile=" + str(pin)):
        if item not in args:
            raise ValueError("Fail-closed SSH option missing: " + item.split("=")[0])
    if cfg["target"] != "root@172.16.42.1":
        raise ValueError("Unexpected USB endpoint")
    return [x for x in args if x != "-n"] + ["-i", str(key), cfg["target"], "sh", "-s"]


def parse_status(output: str):
    parsed = {}
    for raw in output.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key not in SAFE_KEYS or key in parsed or len(value) > 95:
            continue
        if not re.fullmatch(r"[A-Za-z0-9._/+:-]+(?: [A-Za-z0-9._/+:-]+)*", value):
            continue
        parsed[key] = value
    if set(parsed) != set(SAFE_KEYS):
        raise ValueError("Missing or malformed status fields; no partial telemetry accepted")
    if not re.fullmatch(r"7\.3\.0-rc1-n71-batt2-[A-Za-z0-9-]+", parsed["kernel"]):
        raise ValueError("Unexpected kernel release")
    for f in ("capacity", "cell_uV", "current_uA", "temp_tenths", "ram_available_kb"):
        int(parsed[f])
    return parsed


def poll(ssh):
    r = subprocess.run(ssh, input=PROBE, text=True, capture_output=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError("Pinned USB SSH failed; never disable host-key validation")
    return parse_status(r.stdout)


def show(v):
    cap = int(v["capacity"])
    milliamp = int(v["current_uA"]) / 1000
    temp = int(v["temp_tenths"]) / 10
    print("CYBERDECK // ARLO   " + datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"))
    print(f"Linux: up | USB: {v['usb']} | WLAN: {'up' if v['wlan']=='1' else 'down'} | IP: {v['wifi_ip']}")
    print(f"Battery: {cap}% | {temp:.1f} °C | {milliamp:+.0f} mA net | gauge: {v['status']}")
    print(f"Bluetooth: {v['bluetooth']} | UI: {v['ui']} | Charge guard: {v['charge_supervisor']}")
    print(f"NVMe module: {v['nvme_module']} | NAND reset: {v['nand_reset']} | RAM free: {int(v['ram_available_kb'])//1024} MiB")
    print("This is diagnostic monitoring, NOT a NAND storage or charging guarantee.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=3)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    a = parser.parse_args()
    if a.once == a.watch or not 2 <= a.interval <= 60:
        parser.error("select --once or --watch; --interval must be 2..60 seconds")
    ssh = load_config(a.config)
    while True:
        if a.watch and sys.stdout.isatty():
            print("\033[2J\033[H", end="")
        try:
            show(poll(ssh))
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
            print("DEVICE UNAVAILABLE / RE-PIN REQUIRED: " + type(e).__name__)
            if a.once:
                return 2
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
