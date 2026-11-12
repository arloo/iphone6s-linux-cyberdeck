"""Adversarial synthetic tests for owner-private N71 C5 RAM Linux overlay.

Uses fabricated CPIO newc records and fake firmware bytes only. It never
reads or distributes actual Apple firmware, touches iPhone or enables Wi-Fi.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

SRC=Path(__file__).resolve().parents[1]/"tools/n71_s8000_private_c5_ram_overlay_gate.py"
spec=importlib.util.spec_from_file_location("n71_c5_ram_overlay",SRC)
assert spec and spec.loader
G=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=G
spec.loader.exec_module(G)

def member(name:str,data:bytes=b"",mode=stat.S_IFREG|0o644,ino=100):
    name_b=name.encode()+b"\0"
    fields=[ino,mode,0,0,1,0,len(data),0,0,0,0,len(name_b),0]
    h=b"070701"+b"".join(f"{v:08x}".encode() for v in fields)
    head=h+name_b
    return head+b"\0"*(-len(head)%4)+data+b"\0"*(-len(data)%4)

def fixture():
    old={f"orig/file{i:02d}.txt":(stat.S_IFREG|0o644,("base_%02d"%i).encode())
         for i in range(21)}
    old["lib/firmware"]=(stat.S_IFDIR|0o755,b"")
    old["init"]=(stat.S_IFREG|0o755,b"#!/bin/sh\n")
    assert len(old)==23
    firmware={
        G.BR_PREFIX+".bin":b"original fake firmware 4350 "+b"A"*220,
        G.BR_PREFIX+".clm_blob":b"fake clm "*24,
        G.BR_PREFIX+".txcap_blob":b"fake txcap "*24,
    }
    for i in range(14):
        firmware[f"{G.BR_PREFIX}-BLMA-m-{i}.txt"]=b"fake stock variant" + bytes([i])*200
    assert len(firmware)==17
    trailer=member("TRAILER!!!",b"",mode=0,ino=0)+b"\0"*420
    oldraw=b"".join(member(k,d,m,i) for i,(k,(m,d)) in enumerate(old.items(),1))+trailer
    before=oldraw[:-len(trailer)]
    appended=member("lib/firmware/brcm",b"",stat.S_IFDIR|0o755,30000)
    appended+=b"".join(member("lib/firmware/brcm/"+k,v,stat.S_IFREG|0o644,i)
                       for i,(k,v) in enumerate(sorted(firmware.items()),30001))
    newraw=before+appended+trailer
    return oldraw,newraw,firmware

def check_fake(old,new,firmware):
    def decompose(blob):
        return (b"fake_loader_and_DT",b"fake_compiled_WIFI_kernel",
                old if blob==b"previous" else new)
    with patch.object(G,"sha",side_effect=lambda b:G.OLD_SHA if b==b"previous" else G.NEW_SHA):
        with patch.object(G,"decompose",side_effect=decompose):
            return G.validate(b"previous",b"candidate",firmware)

class TestPrivateC5FirmwareRAMOverlayGate(unittest.TestCase):
    def test_exact_synthetic_41_cpio_members_accept(self):
        a,b,f=fixture()
        self.assertTrue(check_fake(a,b,f))
    def test_old_has_exact_23_members(self):
        old,_,_=fixture()
        self.assertEqual(len(G.archive(old)[0]),23)
    def test_overlay_has_exact_41_members(self):
        _,new,_=fixture()
        self.assertEqual(len(G.archive(new)[0]),41)
    def test_trailer_relocated_without_loss(self):
        old,new,_=fixture()
        self.assertNotEqual(G.archive(old)[1],G.archive(new)[1])
        self.assertEqual(new[G.archive(new)[1]:],old[G.archive(old)[1]:])
    def test_original_members_byte_identical(self):
        old,new,_=fixture()
        oldmem=G.archive(old)[0]
        newmem=G.archive(new)[0]
        self.assertTrue(all(newmem[k]==v for k,v in oldmem.items()))
    def test_reject_modified_original_ram_cpio_member(self):
        old,new,fw=fixture()
        new=new.replace(b"base_00",b"bAse_00",1)
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_corrupted_original_cpio_header(self):
        old,new,fw=fixture()
        new=new.replace(b"070701",b"080701",1)
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_extra_firmware_directory_file(self):
        old,new,fw=fixture()
        fw["brcmfmac4350c2-pcie.apple,albarossa-BOGUS.txt"]=b"X"*200
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_wrong_firmware_variant_bytes(self):
        old,new,fw=fixture()
        key=G.BR_PREFIX+".bin"
        fw[key]=fw[key]+b"mutated"
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_missing_otp_profile(self):
        old,new,fw=fixture()
        fw.pop(f"{G.BR_PREFIX}-BLMA-m-4.txt")
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_altered_new_kernel_in_header(self):
        old,new,fw=fixture()
        def altered(blob):
            return (b"changed" if blob==b"candidate" else b"original",
                    b"kernel", old if blob==b"previous" else new)
        with patch.object(G,"sha",side_effect=lambda b:G.OLD_SHA if b==b"previous" else G.NEW_SHA):
            with patch.object(G,"decompose",side_effect=altered):
                with self.assertRaises(G.UnqualifiedOverlay):
                    G.validate(b"previous",b"candidate",fw)
    def test_reject_no_common_firmware_directory(self):
        old,new,fw=fixture()
        new=new.replace(b"lib/firmware/brcm\0",b"lib/firmware/WRONG\0",1)
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_unknown_private_binary(self):
        old,new,fw=fixture()
        fw.pop(G.BR_PREFIX+".bin")
        fw["brcmfmac4350c2-pcie.apple,albarossa-UNKNOWN.bin"]=b"X"*200
        with self.assertRaises(G.UnqualifiedOverlay):
            check_fake(old,new,fw)
    def test_reject_absolute_cpio_traversal_path(self):
        header=member("../secret",b"S"*128)
        with self.assertRaises(G.UnqualifiedOverlay):
            G.archive(header+member("TRAILER!!!",mode=0))
    def test_reject_duplicate_cpio_filename(self):
        entries=member("test",b"x")+member("test",b"y")+member("TRAILER!!!",mode=0)
        with self.assertRaises(G.UnqualifiedOverlay):
            G.archive(entries)
    def test_no_native_wifi_false_success_claim(self):
        s=SRC.read_text()
        self.assertIn("N71_NATIVE_PCIE_DART_DMA_AND_BRCM4350_WIFI_ENABLED=NO",s)
        self.assertIn("N71_NEW_PRIVATE_WLAN_FIRMWARE_IMAGE_HAS_NOT_BEEN_BOOTED=YES",s)
        for unsafe in ("palera1n","devmem","writel(","modprobe",
                       "flash_erase","ios-deploy","ssh root@"):
            self.assertNotIn(unsafe,s)

if __name__=="__main__":unittest.main()
