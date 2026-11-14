#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pack an owner-private single-board NVRAM, supplying a temporary local MAC.
Never prints calibration or MAC values. Output must stay outside this repo.
"""
import argparse,secrets,struct
from pathlib import Path

def pack_nvram(data,mac=None):
 if not data.isascii() or b"\0" in data:raise ValueError("Require ASCII text NVRAM")
 entries=[line.split(b"#",1)[0].strip() for line in data.splitlines()]
 entries=[line for line in entries if line]
 if not entries or any(b"=" not in x or b" " in x or b"\t" in x for x in entries):raise ValueError("Unsupported NVRAM syntax")
 if any(x.startswith((b"devpath",b"pcie/")) for x in entries):raise ValueError("Multi-device NVRAM unsupported")
 if not any(x.startswith(b"boardrev=") for x in entries):raise ValueError("Require explicit owner board revision")
 existing=[x for x in entries if x.startswith(b"macaddr=")]
 if len(existing)>1:raise ValueError("Duplicate MAC entry")
 if mac is not None:
  if len(mac)!=6 or mac[0]&3!=2:raise ValueError("Override must be local unicast MAC")
  entries=[x for x in entries if not x.startswith(b"macaddr=")]
 elif existing:
  mac=None
 else:mac=bytes([2])+secrets.token_bytes(5)
 if mac is not None:entries.append(b"macaddr="+":".join("%02x"%x for x in mac).encode())
 payload=b"\0".join(entries)+b"\0"
 length=(len(payload)+4)&~3
 if length>64000:raise ValueError("NVRAM too large")
 payload+=bytes(length-len(payload));words=length//4
 return payload+struct.pack("<I",((~words&65535)<<16)|words)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];out=a.output.resolve()
 if out==root or root in out.parents:raise ValueError("Private output must be outside public repo")
 packed=pack_nvram(a.source.read_bytes())
 with out.open("xb") as f:f.write(packed)
 out.chmod(0o600)
 print("N71_PRIVATE_NVRAM_PACKED bytes="+str(len(packed))+" MAC_PRESENT values_not_printed")
if __name__=="__main__":main()
