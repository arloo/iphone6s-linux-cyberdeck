# SPDX-License-Identifier: MIT
"""CPU-only admission for an already observed Linux-to-DFU boot transition.

The caller authenticates device identity, USB event chronology, backup and the
private candidate-bound telemetry record. This admits RAM boot only. It cannot
qualify new NAND I/O, charger rearm or native rollback that did not occur.
"""
import math,re

def qualify(record, *, now, candidate_sha256):
    if type(candidate_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}",candidate_sha256):raise ValueError("candidate_digest")
    if not isinstance(record,dict):raise ValueError("record_schema")
    if type(now) not in (int,float) or not math.isfinite(now):raise ValueError("clock")
    if record.get("candidate_image_sha256")!=candidate_sha256:raise ValueError("candidate_mismatch")
    for k in ("identity_verified","board_verified","same_USB_port_verified","encrypted_finished_backup_verified","previous_epoch_attested"):
        if record.get(k) is not True:raise ValueError("missing_identity_or_transition_witness")
    times=[]
    for k in ("power_observed_at_epoch","old_Linux_disconnect_at_epoch","DFU_enumeration_at_epoch"):
        v=record.get(k)
        if type(v) not in (int,float) or not math.isfinite(v):raise ValueError("event_time")
        times.append(v)
    if not times[0]<=times[1]<=times[2]<=now or not 0<=now-times[0]<=900:raise ValueError("stale_or_reordered_transition")
    p=record.get("power")
    if not isinstance(p,dict):raise ValueError("power_schema")
    for k in ("capacity","current_now","voltage_now","temp","charge_now"):
        if type(p.get(k)) is not int:raise ValueError("integer_measurement_required")
    if p.get("health")!="Good" or p.get("status") not in ("Charging","Discharging","Full","Not charging"):raise ValueError("gauge_state")
    if not 50<=p["capacity"]<=100 or p["charge_now"]<1000000:raise ValueError("reserve")
    if not 3600000<=p["voltage_now"]<4200000 or not 100<=p["temp"]<350 or abs(p["current_now"])>500000:raise ValueError("electrical_limits")
    return dict(RAM_boot_only=True,age_s=round(now-times[0],3),minimum_RC_uAh=p["charge_now"],native_rollback_inferred=False,NAND_IO_authorized=False,charger_rearm_authorized=False)
