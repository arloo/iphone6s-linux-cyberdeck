#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only complete N71/S8000 Apple ADT census of DART1 mapper references.

Walks EVERY original Apple Device Tree node, including multi-cell iommu-parent
arrays, rejecting missing/ambiguous phandles and cross-port consumers. Reuses
the independent strict N71/S8000 topology gate. All original/private ADT data
stay local; emits only aggregate counts, never identifiers, node paths,
unknown properties, firmware, OTP, device-specific values or raw ADT.

A unique declared IOMMU consumer does NOT establish physical exclusive DMA,
an actual DART1 stream ID, a safe IOVA range, controller side effects,
or permission to reset, probe, map or access DART MMIO.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location(
    "n71_census_adt", HERE/"n71_s8000_adt_window_gate.py")
assert SPEC and SPEC.loader
BASE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

MAX_REFS_PER_NODE=32
MAX_TOTAL_REFS=4096

class InvalidMapperCensus(ValueError):
    pass

def must(ok:bool,description:str)->None:
    if not ok:raise InvalidMapperCensus(description)

def census_nodes(nodes:list[tuple[str,dict[str,bytes]]])->dict[str,int]:
    # Node properties are private and never included in outputs.
    ids:dict[int,str]={}
    references:list[tuple[str,int]]=[]
    mapper_id=None
    for path,props in nodes:
        if "AAPL,phandle" in props:
            raw=props["AAPL,phandle"]
            must(len(raw)==4,"Malformed Apple global phandle")
            ident=struct.unpack("<I",raw)[0]
            must(ident!=0 and ident not in ids,
                 "Duplicate/invalid global Apple phandle")
            ids[ident]=path
            if path==BASE.MAPPER:
                mapper_id=ident
        if "iommu-parent" in props:
            raw=props["iommu-parent"]
            must(len(raw)>0 and len(raw)%4==0 and
                 len(raw)//4<=MAX_REFS_PER_NODE,
                 "Invalid IOMMU parent cell vector")
            for (ident,) in struct.iter_unpack("<I",raw):
                must(ident!=0,"Zero IOMMU parent reference")
                references.append((path,ident))
                must(len(references)<=MAX_TOTAL_REFS,"Too many IOMMU references")

    must(mapper_id is not None,"Verified WLAN DART1 mapper absent")
    must(all(ident in ids for _,ident in references),
         "Unresolved IOMMU parent cell")
    # Fail closed on another mapper/child under DART1, even if no
    # iommu-parent points to that child in this particular snapshot.
    children=[path for path,_ in nodes
              if path.startswith(BASE.DART_PATHS[1]+"/")]
    must(children==[BASE.MAPPER],
         "Unreviewed additional DART1 child mapper")
    # A direct reference to DART1 controller (not the mapper) also
    # invalidates the assumption of a single DECLARED DMA consumer.
    must(not any(ids[ident]==BASE.DART_PATHS[1]
                 for _,ident in references),
         "Unreviewed direct consumer of DART1 controller")
    uses=[path for path,ident in references if ident==mapper_id]
    must(uses==[BASE.WLAN],
         "Unrecognized or multiple DART1 mapper consumers")
    must(len(references)>=1,
         "No original IOMMU reference found")
    return {
      "iommu_parent_properties":sum(
          1 for _,props in nodes if "iommu-parent" in props),
      "iommu_parent_cells":len(references),
      "dart1_mapper_declared_consumers":len(uses),
      "dart1_child_nodes":len(children),
      "dart1_direct_controller_consumers":0,
      "global_unique_phandles":len(ids),
    }

def audit_bytes(adt:bytes)->dict[str,int]:
    must(8<len(adt)<=BASE.ADT.MAX_FILE,
         "Private original ADT size rejected")
    # This separate pre-existing audit also verifies real N71/S8000
    # silicon, actual BCM4350 port1 / mapper path, DART1 page/VM size,
    # all PCIe and DART windows, 178 phandle uniqueness in original data.
    strict=BASE.audit_bytes(adt)
    must("S8000_ADT_METADATA_GATE_PASS" in strict and
         "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in strict,
         "Original S8000 ADT full hardware topology unqualified")
    nodes:list[tuple[str,dict[str,bytes]]]=[]
    try:
        result=BASE.ADT.parse_node(
            adt,0,"",visitor=lambda path,props: nodes.append((path,props)),
            visit_all=True)
    except (BASE.ADT.InvalidADT,UnicodeError,struct.error) as exc:
        raise InvalidMapperCensus("Original Apple ADT traversal rejected") from exc
    must(result<=len(adt),"Original ADT traversal overrun")
    return census_nodes(nodes)

def private_file(path:Path)->bytes:
    must(path.is_file() and not path.is_symlink(),
         "Original private Apple ADT file absent or symlink")
    size=path.stat().st_size
    must(8<size<=BASE.ADT.MAX_FILE,"Private Apple ADT file size invalid")
    return path.read_bytes()

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_original_n71_apple_adt",type=Path)
    args=parser.parse_args()
    try:
        counts=audit_bytes(private_file(args.private_original_n71_apple_adt))
    except Exception:
        # Input paths, original unknown node strings, IDs and binary data
        # must never be echoed even if a malformed private file is supplied.
        print("N71_DART1_DECLARED_CONSUMER_CENSUS_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_S8000_DART1_ORIGINAL_ADT_DECLARED_CONSUMERS_PASS")
    print("IOMMU_PARENT_PROPERTY_COUNT",counts["iommu_parent_properties"])
    print("IOMMU_PARENT_REFERENCE_CELL_COUNT",counts["iommu_parent_cells"])
    print("DART1_MAPPER_DECLARED_CONSUMERS",counts["dart1_mapper_declared_consumers"])
    print("DART1_CHILD_MAPPER_COUNT",counts["dart1_child_nodes"])
    print("DART1_DIRECT_CONTROLLER_REFERENCES",counts["dart1_direct_controller_consumers"])
    print("DART1_ONLY_DECLARED_CONSUMER=WLAN")
    print("DART1_PHYSICAL_STREAM_ID_PROVEN=NO")
    print("DART1_ACTUAL_EXCLUSIVE_DMA_OWNERSHIP_PROVEN=NO")
    print("DART1_IOVA_DMA_FAULT_ISOLATION_PROVEN=NO")
    print("DART1_HARDWARE_INITIALIZATION_AUTHORIZED=NO")
    print("PRIVATE_APPLE_ADT_OR_DEVICE_VALUES_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
