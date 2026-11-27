#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only admission for one bounded storage trial with an already-full battery.

Caller must separately attest board/boot/artifacts, unused epoch, direct USB and
native charger stop plus verified original-input rollback. The legacy four-read
protocol requires its native guard-stop; cq-wrap-17 also permits a separately
attested normal native-only module exit. Neither permits charger rearm. This function
never controls power or submits I/O. The current/duration figures are planning
assumptions, not measured peak-current limits or a qualified endurance claim.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

# Named protocols only: callers cannot lower a duration or energy margin.
# The legacy admission remains byte-for-byte equivalent in its measurements.
PLANS = {"four-read": (120,25), "cq-wrap-17": (300,10)}

def qualify(samples: list[dict], *, plan: str = "four-read") -> dict:
    if type(plan) is not str or plan not in PLANS:raise ValueError("unknown_storage_plan")
    planning_duration_s,required_windows=PLANS[plan]
    if not isinstance(samples,list) or len(samples)!=8:raise ValueError("eight_samples_required")
    integer_fields=('capacity','current_now','voltage_now','temp','charge_now','charge_full')
    for s in samples:
        if not isinstance(s,dict):raise ValueError("sample_schema")
        for k in integer_fields:
            if type(s.get(k)) is not int:raise ValueError("integer_measurement_required")
        t=s.get('uptime_s')
        if type(t) not in (int,float) or not math.isfinite(t) or t<0:raise ValueError("invalid_sample_time")
        if s.get('health')!='Good' or s.get('udc')!='configured':raise ValueError("health_or_USB")
        if s.get('status') not in ('Charging','Discharging','Full','Not charging'):raise ValueError("unknown_gauge_status")
        rc,fcc=s['charge_now'],s['charge_full']
        if not 50<=s['capacity']<=100 or rc<1000000 or fcc<rc:raise ValueError("insufficient_full_reserve")
        if 100*rc<50*fcc or abs(s['capacity']*fcc-100*rc)>2*fcc:raise ValueError("gauge_disagreement")
        if not 3600000<=s['voltage_now']<4100000:raise ValueError("cell_voltage")
        if not 100<=s['temp']<350:raise ValueError("battery_temperature")
        if abs(s['current_now'])>500000:raise ValueError("idle_current")
    times=[s['uptime_s'] for s in samples]
    if any(b-a<0.5 for a,b in zip(times,times[1:])) or not 10<=times[-1]-times[0]<=40:raise ValueError("sample_window")
    rc=[s['charge_now'] for s in samples];fcc=[s['charge_full'] for s in samples]
    if max(rc)-min(rc)>5000 or max(fcc)-min(fcc)>1000:raise ValueError("unstable_gauge")
    planning_current_uA=1000000
    planning_charge_uAh=(planning_current_uA*planning_duration_s+3599)//3600
    margin=min(rc)//planning_charge_uAh
    if margin<required_windows:raise ValueError("reserve_margin")
    return dict(trial_plan=plan,required_reserve_windows=required_windows,samples=8,window_s=round(times[-1]-times[0],3),minimum_percent=min(s['capacity'] for s in samples),
                minimum_RC_uAh=min(rc),minimum_RC_FCC_percent=round(min(100*s['charge_now']/s['charge_full'] for s in samples),3),
                maximum_temperature_tenths_C=max(s['temp'] for s in samples),minimum_cell_uV=min(s['voltage_now'] for s in samples),maximum_cell_uV=max(s['voltage_now'] for s in samples),
                maximum_measured_idle_discharge_uA=max(0,max(-s['current_now'] for s in samples)),
                planning_current_uA=planning_current_uA,planning_duration_s=planning_duration_s,planning_charge_uAh=planning_charge_uAh,
                minimum_reserve_windows=margin,charger_rearm_authorized=False,physical_endurance_qualified=False)

def main() -> int:
    if len(sys.argv)!=2:return 2
    try:result=qualify(json.loads(Path(sys.argv[1]).read_text()))
    except (OSError,ValueError,TypeError,KeyError):
        print('FULL_RESERVE_STORAGE_GATE_REFUSED');return 1
    print('FULL_RESERVE_STORAGE_GATE_PASS '+json.dumps(result,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
