#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sanitized aggregate analysis of existing N71/S8000 S3E dmesg snapshots.

Never reaches a device. Never prints raw lines, paths, IDs, addresses,
timestamps or SHA hashes. Deduplication uses a boot-relative *event
signature*, NOT proof that two samples came from different physical boots.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

LINE = re.compile(
    r"^\[\s*(?P<at>\d+\.\d+)\]\s+n71-s3e-p0:\s+"
    r"(?P<tag>ADMIN_POST_STOP_DMA_SNAPSHOT|ADMIN_SHUTDOWN_TRACE|"
    r"ADMIN_IDENTIFY_ONCE)\s+(?P<fields>.*)$"
)
KV = re.compile(r"([A-Za-z_][A-Za-z_0-9]*)=([A-Za-z0-9_.+\-]+)")


def parse_one(text: str) -> list[dict]:
    """Return observations with private details confined to local memory."""
    shutdown = identify = None
    output = []
    for line in text.splitlines():
        match = LINE.match(line.strip())
        if not match:
            continue
        fields = dict(KV.findall(match["fields"]))
        stamp = match["at"]
        tag = match["tag"]
        if tag == "ADMIN_SHUTDOWN_TRACE":
            shutdown = (stamp, fields)
        elif tag == "ADMIN_IDENTIFY_ONCE":
            identify = (stamp, fields)
        else:
            sig = (
                stamp,
                fields.get("nvmmu_fifo", "?"),
                fields.get("dart_fault", "?"),
                shutdown[0] if shutdown else "?",
                identify[0] if identify else "?",
            )
            output.append({
                "sig": sig,
                "snap": fields,
                "shutdown": shutdown[1] if shutdown else {},
                "identify": identify[1] if identify else {},
            })
    return output


def aggregate(logs: list[str]) -> dict:
    raw = [v for content in logs for v in parse_one(content)]
    seen: set[tuple] = set()
    unique = []
    for sample in raw:
        if sample["sig"] in seen:
            continue
        seen.add(sample["sig"])
        unique.append(sample)
    fifo = Counter()
    dart = Counter()
    successful_shutdown = 0
    quarantined = 0
    owned_queues = 0
    exact_fields = 0
    for rec in unique:
        s, sh, ide = rec["snap"], rec["shutdown"], rec["identify"]
        f = s.get("nvmmu_fifo", "")
        d = s.get("dart_fault", "")
        if re.fullmatch(r"[0-9a-fA-F]{8}", f):
            fifo[f.lower()] += 1
        if re.fullmatch(r"[0-9a-fA-F]{8}", d):
            dart[d.lower()] += 1
        if (
            sh.get("rc") == "0"
            and sh.get("disable_rc") == "0"
            and sh.get("inner_rc") == "0"
            and sh.get("master_off") == "1"
            and s.get("hmb_descriptor_zero") == "1"
        ):
            successful_shutdown += 1
        if (
            ide.get("rc") == "-3"
            and s.get("no_dma_release_attempted") == "YES"
            and s.get("quarantine_unchanged") == "YES"
        ):
            quarantined += 1
        if s.get("queues_owned_io_va") == "1" and s.get("dart_queues_mapped") == "1":
            owned_queues += 1
        if all(k in s for k in (
            "nvmmu_fifo", "dart_fault", "hmb_descriptor_zero",
            "queues_owned_io_va", "dart_queues_mapped", "quarantine_unchanged"
        )):
            exact_fields += 1

    # Records can overlap across saved copies. Do not infer boot count.
    return {
        "files_examined": len(logs),
        "snapshots_found": len(raw),
        "unique_event_signatures": len(unique),
        "deduplicated_copies": len(raw) - len(unique),
        "complete_snapshot_fields": exact_fields,
        "shutdown_consistent_snapshots": successful_shutdown,
        "explicitly_quarantined_snapshots": quarantined,
        "queue_mapping_retained_snapshots": owned_queues,
        "raw_nvmmu_fifo_histogram": dict(sorted(fifo.items())),
        "raw_dart_fault_histogram": dict(sorted(dart.items())),
        "independent_boot_count_proven": False,
        "fifo_bitfield_semantics_proven": False,
        "hardware_dma_quiescence_proven": False,
        "dma_release_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path, nargs="+", help="Private dmesg files, processed locally")
    args = parser.parse_args()
    try:
        texts = [path.read_text(encoding="utf-8", errors="replace") for path in args.logs]
    except OSError:
        print("ERROR: an input log could not be read", flush=True)
        return 2
    result = aggregate(texts)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["snapshots_found"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
