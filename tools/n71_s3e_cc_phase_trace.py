#!/usr/bin/env python3
"""Classify optional N71/S8000 CC INTMS/PERST *read-only* snapshots.

No hardware control, no DMA safety proof. Missing/malformed/duplicate
measurements never become a successful phase conclusion.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re

STEPS=("enable","shutdown","disable")
EDGES=("before","after")
ORDER=tuple((step,edge) for step in STEPS for edge in EDGES)
LINE=re.compile(
    r"ADMIN_CC_INTMS_RO phase=(enable|shutdown|disable) "
    r"edge=(before|after) intms_bit0=([01]) perst_high=([01]) "
    r"no_dma_release=YES(?:\s|$)"
)

def interpret(text: str) -> tuple[str,str,list[str]]:
    """(stage, observation, phase list) with no MMIO or sensitive data."""
    if "N71_ONE_SHOT_START" in text:
        text=text.rsplit("N71_ONE_SHOT_START",1)[-1]
    samples={}
    for raw in text.splitlines():
        if "ADMIN_CC_INTMS_RO" not in raw:
            continue
        match=LINE.search(raw)
        if match is None:
            return "MALFORMED","none",[]
        phase,edge,mask,high=match.groups()
        key=(phase,edge)
        if key in samples:
            return "DUPLICATE","none",[]
        samples[key]=(int(mask),int(high))
    if tuple(samples)!=ORDER:
        return "INCOMPLETE","none",[
            phase+"."+edge for phase,edge in ORDER if (phase,edge) not in samples
        ]
    if any(not high for _,high in samples.values()):
        return "PERST_UNEXPECTED","none",[]
    masks=[samples[k][0] for k in ORDER]
    transitions=[]
    for i in range(1,len(masks)):
        if masks[i-1] and not masks[i]:
            transitions.append("after_"+ORDER[i-1][0]+"_"+ORDER[i-1][1]
                               +"_before_"+ORDER[i][0]+"_"+ORDER[i][1])
    if masks[-1]:
        return "MASK_RETAINED","no_1_to_0_transition",[]
    if transitions:
        return "MASK_CLEARED",";".join(transitions),[]
    return "MASK_ZERO_ALL_PHASES","none",[]

def read_log(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>512*1024:
        raise ValueError("Refuse missing, symlinked, or oversized S3E log")
    return path.read_text(encoding="utf-8",errors="replace")

def main():
    parser=argparse.ArgumentParser(description="Read-only CC INTMS phase analysis")
    parser.add_argument("log",type=Path)
    args=parser.parse_args()
    status,detail,missing=interpret(read_log(args.log))
    print("CC_INTMS_TRACE="+status)
    print("CC_INTMS_OBSERVATION="+detail)
    print("MISSING_PHASES="+(",".join(missing) if missing else "none"))
    print("DMA_QUARANTINE=REQUIRED")
    print("NAND_BLOCK_ACCESS=NOT_PROVEN")

if __name__=="__main__":
    main()
