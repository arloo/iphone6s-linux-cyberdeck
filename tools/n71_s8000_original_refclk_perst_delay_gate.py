#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline N71 Apple PCIe REFCLK-to-PERST 100 microsecond proof.

Original privately retained N71 iOS15.8.8 Mach-O, Apple ADT and
owner iOS15.7.9 port1 IORegistry. Traces t-refclk-to-perst into
the +416 port field, through inherited S800x virtual port method,
the prelinked GOT import trampoline and exact original XNU _IODelay
symbol (NOT _IOSleep). Apple publicly documents IODelay in microseconds.

No live MMIO, DMA, devices, or per-device identifiers are used/exported.
"""
from __future__ import annotations
import argparse,importlib.util,plistlib,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load(alias,name):
    s=importlib.util.spec_from_file_location(alias,HERE/name)
    assert s and s.loader
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

SEQ=load("n71_delay_seq","n71_s8000_port1_inherited_sequence_gate.py")
ROOT=load("n71_delay_root","n71_s8000_root_resource_gate.py")
ADT=load("n71_delay_adt","n71_s8000_adt_window_gate.py")
F=416
TEXT_LEN=46924
SIG={
 0x4bc8:0x91068280, # port field address object+416
 0x4bd4:0xaa1303e1, # Apple provider
 0x4bd8:0x52800003, # zero default
 0x4bdc:0x94000253, # original property load helper +0x5528
 0x5528:0xa9bd57f6, # helper start
 0x553c:0xaa0103f6,
 0x5540:0xaa0003f3, # output buffer pointer -> X19
 0x5560:0x9400109d, # OSData property lookup
 0x5564:0xb40000c0,
 0x556c:0xf9406d08,
 0x5570:0xd63f0100,
 0x5574:0xb9400008, # load value as 32bit
 0x5578:0xb9000268, # store W8 into port field +416
}
class UnsafeDelay(ValueError):pass
def need(cond,reason):
    if not cond:raise UnsafeDelay(reason)
def u32(b,at):
    need(at>=0 and at%4==0 and at+4<=len(b),"Invalid original instruction")
    return struct.unpack_from("<I",b,at)[0]

def check_original_port_property_flow(code,vm,cstring,cstring_vm):
    need(len(code)==TEXT_LEN,"Original embedded PCIe executable length changed")
    for at,ins in SIG.items():
        need(u32(code,at)==ins,"Apple original REFCLK field dataflow changed")
    needle=b"t-refclk-to-perst\0"
    need(cstring.count(needle)==1,"Original source property missing or duplicated")
    adrp=u32(code,0x4bcc)
    add=u32(code,0x4bd0)
    need(adrp&0x9f00001f==0x90000002 and
         add&0xffc003ff==0x91000042 and
         (add>>22)&3==0,"Original Apple REFCLK key address changed")
    value=SEQ.CTOR.adrp_target(vm+0x4bcc,adrp,2)
    value+=(add>>10)&0xfff
    need(value==cstring_vm+cstring.find(needle),
         "Original property source is not t-refclk-to-perst")
    dest=SEQ.CTOR.bl_destination(vm+0x4bdc,u32(code,0x4bdc))
    need(dest==vm+0x5528,"Original property-to-field helper changed")
    return {"offset":F,"width":4}

def kernel_named_symbols(blob,names):
    need(32<len(blob)<=SEQ.KMAP.MAX_MACHO and
         struct.unpack_from("<I",blob,0)[0]==0xfeedfacf and
         struct.unpack_from("<I",blob,4)[0]==0x0100000c,
         "Not an original AArch64 Mach-O kernel symbol image")
    ncmd,cmdsize=struct.unpack_from("<2I",blob,16)
    need(8<=ncmd<=256 and 32+cmdsize<=len(blob),
         "Original Mach-O commands out of file")
    pos=32;matches=[]
    for _ in range(ncmd):
        need(pos+8<=32+cmdsize,"Original command header truncated")
        cmd,sz=struct.unpack_from("<2I",blob,pos)
        need(sz>=8 and pos+sz<=32+cmdsize,"Original command overflow")
        if cmd==2:
            need(sz>=24,"Original symbol command size wrong")
            matches.append(struct.unpack_from("<4I",blob,pos+8))
        pos+=sz
    need(pos==32+cmdsize and len(matches)==1,"Original kernel symtab ambiguous")
    off,count,stroff,strsz=matches[0]
    need(0<count<=500000 and 0<strsz<20000000 and
         off+16*count<=len(blob) and stroff+strsz<=len(blob),
         "Original symtab truncated")
    found={}
    for k in range(count):
        idx,typ,sect,desc,addr=struct.unpack_from("<IBBHQ",blob,off+16*k)
        if idx>=strsz or addr==0:continue
        end=blob.find(b"\0",stroff+idx,stroff+strsz)
        if end<0:continue
        name=bytes(blob[stroff+idx:end])
        if name not in names:continue
        need(name not in found and (typ&0x0e)==0x0e,
             "Original XNU symbol not unique section export")
        found[name]=addr
    need(set(found)==names,"Original XNU IODelay and IOSleep exports missing")
    return found

def check_original_callback(kernel,main,shared_nested,shared_vm,code):
    state=SEQ.analyze_method(code)
    need(state["fixed_callback_argument"]==100 and
         state["dynamic_callback_argument_field"]==F and
         state["two_calls_same_callback"],
         "Original shared port sequencing changed")
    # Original controller slot1984 waits on root bit4, retrying with
    # the SAME XNU IODelay import and a fixed 10-microsecond value.
    # No original caller-level finite poll bound is established.
    for at,ins in ((0x668,0x37200080),(0x66c,0x52800140),
                   (0x670,0x94001082),(0x674,0x17fffff8)):
        need(u32(code,at)==ins,
             "Original shared-root status polling delay changed")
    calls=[
        SEQ.CTOR.ctor_stub_callee(kernel,main,shared_nested,shared_vm+at,
                                  u32(code,at))
        for at in (0x1264,0x12d0,0x670)]
    symbols=kernel_named_symbols(kernel,{b"_IODelay",b"_IOSleep"})
    need(len(set(calls))==1 and calls[0]==symbols[b"_IODelay"] and
         calls[0]!=symbols[b"_IOSleep"],
         "Original Apple port/shared waits must use IODelay, not IOSleep")
    return True

def original_live_value(adt,ios_plist):
    text=ADT.audit_bytes(adt)
    need("S8000_ADT_METADATA_GATE_PASS" in text and
         "WLAN_IOMMU_TO_DART1_MAPPER=UNIQUE_RESOLVED" in text,
         "Original N71/S8000 identity not qualified")
    found=[]
    def visitor(path,props):
        if path==ADT.HOST+"/pci-bridge1":
            found.append(props.get("t-refclk-to-perst"))
    ADT.ADT.parse_node(adt,0,"",visitor=visitor,visit_all=True,
                       extra_props=frozenset({"t-refclk-to-perst"}))
    need(found==[struct.pack("<I",100)],
         "Original S8000 REFCLK/PERST scalar missing or changed")
    try:
        live=plistlib.loads(ios_plist)["IORegistry"]
    except (KeyError,ValueError,TypeError,plistlib.InvalidFileException) as e:
        raise UnsafeDelay("Original stock-iOS snapshot malformed") from e
    need(type(live) is dict and
         live.get("t-refclk-to-perst")==found[0] and
         live.get("IOPCIConfigured") is True and
         live.get("IOPCIResourced") is True,
         "Original live iOS port1 timing metadata changed")
    return 100

def verify(kernel,original_adt,ios_port1):
    value=original_live_value(original_adt,ios_port1)
    main,modules=ROOT.auditable_root_code(kernel)
    pre=main["__PRELINK_TEXT"];info=main["__PRELINK_INFO"]
    kexts=SEQ.KMAP.kext_metadata(kernel[
        info["offset"]:info["offset"]+info["filesize"]].rstrip(b"\0"))
    embedded=modules["embedded"];nested=embedded["nested"]
    sec=nested["__TEXT"]["sections"]["__cstring"]
    load=kexts["com.apple.driver.AppleEmbeddedPCIE"][0]
    at=pre["offset"]+load-pre["vm"]+sec["offset"]
    need(at+sec["size"]<=len(kernel),
         "Original embedded port literal section out of file")
    check_original_port_property_flow(
        embedded["code"],embedded["vm"],
        kernel[at:at+sec["size"]],sec["vm"])
    shared_code=SEQ.audited_shared_code(kernel)
    shva=kexts[SEQ.SHARED_ID][0]
    sh=SEQ.KMAP.macho_segments(kernel,
         pre["offset"]+shva-pre["vm"])
    vm=sh["__TEXT_EXEC"]["sections"]["__text"]["vm"]
    check_original_callback(kernel,main,sh,vm,shared_code)
    return value

def private_read(p,maximum):
    need(p.is_file() and not p.is_symlink(),
         "Private source unavailable or symlinked")
    n=p.stat().st_size
    need(8<n<=maximum,"Original private source length unsupported")
    return p.read_bytes()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("private_original_n71_macho",type=Path)
    ap.add_argument("private_original_n71_adt",type=Path)
    ap.add_argument("private_ios15_port1_plist",type=Path)
    a=ap.parse_args()
    try:
        duration=verify(private_read(a.private_original_n71_macho,
                                     SEQ.KMAP.MAX_MACHO),
                        private_read(a.private_original_n71_adt,ADT.ADT.MAX_FILE),
                        private_read(a.private_ios15_port1_plist,1048576))
    except Exception:
        print("N71_ORIGINAL_APPLE_REFCLK_TO_PERST_DELAY_FAIL_CLOSED",
              file=sys.stderr)
        return 1
    print("N71_ORIGINAL_APPLE_REFCLK_TO_PERST_MICROSECONDS_STATIC_PASS")
    print("ORIGINAL_XNU_PCIE_PORT_WAIT_KERNEL_SYMBOL=_IODelay")
    print("ORIGINAL_XNU_IOSleep_MILLISECOND_WAIT_USED=NO")
    print("ORIGINAL_APPLE_REFCLK_PROPERTY_TO_PORT_FIELD_416=VERIFIED")
    print("ORIGINAL_APPLE_PORT_FIELD_TO_IODelay_ARGUMENT=VERIFIED")
    print("ORIGINAL_IOS_REFCLK_TO_PERST_DELAY_MICROSECONDS",duration)
    print("ORIGINAL_PORT_SEQUENCE_FIXED_WAIT_MICROSECONDS",duration)
    print("ORIGINAL_ROOT_SHARED_BIT4_POLL_RETRY_IODelay_MICROSECONDS",10)
    print("ORIGINAL_SHARED_STATUS_POLL_FINITE_TIMEOUT_PROVEN=NO")
    print("IOS_REFCLK_AND_RESET_OPERATION_ELECTRICAL_SAFETY_PROVEN=NO")
    print("LINUX_PORT1_DART1_DMA_AND_WIFI_HARDWARE_AUTHORIZED=NO")
    print("PRIVATE_APPLE_KERNEL_AND_IOREGISTRY_EXPORTED=NO")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
