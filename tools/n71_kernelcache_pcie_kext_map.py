#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline, metadata-only map of A9 PCIe KEXT code ranges in a local Mach-O.

Reads a user-supplied, already decompressed arm64 prelinked kernelcache.
Does not write files, export code/disassembly, or access physical hardware.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

TARGETS = {
    "com.apple.iokit.IOPCIFamily",
    "com.apple.driver.AppleEmbeddedPCIE",
    "com.apple.driver.AppleS800xPCIe",
    "com.apple.driver.AppleS8000PCIe",
}
MACH64 = 0xFEEDFACF
ARM64_CPU = 0x0100000C
LC_SEGMENT_64 = 0x19
MAX_MACHO = 150_000_000
MAX_PRELINK_XML = 20_000_000


class BadKernelcache(ValueError):
    pass


def require(ok: bool, problem: str) -> None:
    if not ok:
        raise BadKernelcache(problem)


def macho_segments(buf: bytes, at: int) -> dict[str, dict]:
    require(0 <= at <= len(buf)-32, "Mach-O header exceeds buffer")
    magic, cpu, subtype, filetype, ncmd, szcmd, flags, reserved = (
        struct.unpack_from("<8I", buf, at))
    require(magic == MACH64 and cpu == ARM64_CPU, "Not a 64-bit arm64 Mach-O")
    require(1 <= ncmd < 250 and 0 < szcmd < 200_000, "Unsafe Mach-O load command count")
    require(at+32+szcmd <= len(buf), "Mach-O load commands out of bounds")
    pos = at + 32
    end = pos + szcmd
    segments = {}
    for i in range(ncmd):
        require(pos+8<=end, "Truncated Mach-O load command")
        cmd,size=struct.unpack_from("<2I",buf,pos)
        require(size>=8 and pos+size<=end, "Invalid Mach-O command size")
        if cmd==LC_SEGMENT_64:
            require(size>=72, "Truncated segment command")
            _,_,rawname,va,vms,fo,fs,maxprot,initprot,nsecs,fl = (
                struct.unpack_from("<II16sQQQQiiII",buf,pos))
            name=rawname.split(bytes([0]),1)[0].decode("ascii")
            require(name and name not in segments,"Duplicate or nameless segment")
            require(nsecs<120 and 72+nsecs*80<=size,"Invalid section count")
            sections={}
            for k in range(nsecs):
                offset=pos+72+k*80
                rawsec,rawseg,sva,ssz,fileoff,*tail=(
                    struct.unpack_from("<16s16sQQIIIIIIII",buf,offset))
                sec=rawsec.split(bytes([0]),1)[0].decode("ascii")
                require(sec not in sections,"Duplicate section")
                sections[sec]={"vm":sva,"size":ssz,"offset":fileoff}
            segments[name]={"vm":va,"vmsize":vms,
                            "offset":fo,"filesize":fs,"sections":sections}
        pos+=size
    require(pos==end,"Mach-O load command table misalignment")
    return segments


def pairs(d: ET.Element) -> dict[str, ET.Element]:
    elements=list(d)
    found={}
    for i in range(len(elements)-1):
        if elements[i].tag=="key":
            key=elements[i].text or ""
            if key in found:
                raise BadKernelcache("Duplicate prelink metadata key")
            found[key]=elements[i+1]
    return found


def kext_metadata(xml: bytes) -> dict[str, tuple[int,int]]:
    require(0<len(xml)<=MAX_PRELINK_XML,"Bad prelink metadata length")
    require(xml.startswith(b"<dict>"),"Unsupported prelink XML root")
    try:
        root=ET.fromstring(b'<plist version="1.0">'+xml+b"</plist>")
    except ET.ParseError as exc:
        raise BadKernelcache("Invalid prelink XML") from exc
    output={}
    for d in root.iter("dict"):
        entries=pairs(d)
        ident=entries.get("CFBundleIdentifier")
        if ident is None or ident.tag!="string" or ident.text not in TARGETS:
            continue
        if "_PrelinkExecutableLoadAddr" not in entries:
            continue
        name=ident.text
        require(name not in output,"Duplicate matching KEXT")
        load=entries.get("_PrelinkExecutableLoadAddr")
        size=entries.get("_PrelinkExecutableSize")
        require(load is not None and size is not None,
                "Missing prelinked executable extent")
        try:
            va=int(load.text or "",0)
            sz=int(size.text or "",0)
        except (ValueError,TypeError) as exc:
            raise BadKernelcache("Unreadable prelink executable extent") from exc
        require(va>0 and 0<sz<10_000_000,"Implausible prelinked extent")
        output[name]=(va,sz)
    require(set(output)==TARGETS,"Missing A9 PCIe driver family metadata")
    return output


def map_pcie_kexts(buf: bytes) -> list[tuple[str,int,int]]:
    require(1000<=len(buf)<=MAX_MACHO,"Unexpected Mach-O byte count")
    main=macho_segments(buf,0)
    for needed in ("__PRELINK_TEXT","__PRELINK_INFO","__PLK_TEXT_EXEC"):
        require(needed in main,"Missing prelinked kernel segment")
    prelink=main["__PRELINK_TEXT"]
    info=main["__PRELINK_INFO"]
    execseg=main["__PLK_TEXT_EXEC"]
    require(info["offset"]+info["filesize"]<=len(buf),"Prelink info out of file")
    start=info["offset"]
    xml=buf[start:start+info["filesize"]].rstrip(bytes([0]))
    modules=kext_metadata(xml)
    result=[]
    for name in sorted(TARGETS):
        load,size=modules[name]
        require(load>=prelink["vm"],"KEXT header before PRELINK_TEXT")
        delta=load-prelink["vm"]
        require(delta+size<=prelink["filesize"],
                "KEXT Mach-O header not contained within PRELINK_TEXT")
        off=prelink["offset"]+delta
        kext=macho_segments(buf,off)
        require(kext.get("__TEXT",{}).get("vm")==load,
                "KEXT load address does not match Mach-O TEXT")
        require(kext["__TEXT"]["filesize"]==size,
                "KEXT header size does not match prelink metadata")
        code=kext.get("__TEXT_EXEC")
        require(code is not None,"KEXT has no executable segment")
        section=code["sections"].get("__text")
        require(section is not None,"KEXT has no native text section")
        text_va=section["vm"]
        text_len=section["size"]
        require(text_va>=execseg["vm"] and text_len>0 and text_len%4==0,
                "KEXT text outside executable segment or unaligned")
        delta=text_va-execseg["vm"]
        require(delta+text_len<=execseg["filesize"],
                "KEXT executable bytes outside kernelcache")
        code_start=execseg["offset"]+delta
        require(code_start+text_len<=len(buf),"KEXT file range truncated")
        # No content from this location is returned or written to disk.
        result.append((name,text_va,text_len))
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decompressed_private_macho",type=Path)
    args=parser.parse_args()
    try:
        require(0<args.decompressed_private_macho.stat().st_size<=MAX_MACHO,
                "Input size rejected")
        results=map_pcie_kexts(args.decompressed_private_macho.read_bytes())
    except (OSError,BadKernelcache,UnicodeError,struct.error) as exc:
        print("FAIL_CLOSED:",str(exc))
        return 1
    print("A9_PCIE_KEXT_METADATA_PASS: private ARM64 Mach-O, four prelinked modules.")
    for name,vm,size in results:
        print(name,"text_bytes="+str(size))
    print("HARDWARE_BLOCKED: metadata only; no code export, MMIO, DMA or PCIe activity")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
