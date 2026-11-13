#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify actual S8000 port-instance local MMIO, avoiding another class's fields."""
from pathlib import Path
import argparse
import struct
import n71_s8000_original_port1_local_fanout_gate as F
import n71_ios_iodevicememory_order_gate as MEM
# Source signatures only; original images remain private.
EMBEDDED={0x51a8:0xb9421288,0x51ac:0xb940aa81,0x51bc:0xf9405280,
 0x51c0:0xf9400008,0x51c4:0xf943a508,0x51c8:0xd63f0100,
 0x51cc:0xaa0003e1,0x51d0:0xf94002a8,0x51d4:0xf941e908,
 0x51d8:0xaa1503e0,0x51dc:0x52800002,0x51e0:0xd63f0100,
 0x51e4:0xf9006680,0x51ec:0xf9400008,0x51f0:0xf9403d08,
 0x51f4:0xd63f0100,0x51f8:0xf9006a80,0x51fc:0xf9406680,
 0x5204:0xf9006e80}
SHARED={0xd0:0x52800020,0xd4:0x331f7820,0xd8:0xd65f03c0,
 0x15b4:0xf943e908,0x15b8:0x52801001,0x15c0:0x121f7808,
 0x15c4:0x2a130102,0x15cc:0xf943ed03,0x15d4:0x52801001,
 0x1468:0xf943e908,0x1470:0x52801101,0x1478:0x12000000,
 0x1aec:0xf9406a88,0x1af0:0xb8734913,
 0x1bc8:0xf9406a88,0x1bcc:0xb8334915}
def check_words(code, expected):
 for off,word in expected.items():
  if off+4>len(code) or struct.unpack_from('<I',code,off)[0]!=word:
   raise ValueError('Unrecognized original port-instance dataflow')
def audit(original, adt, root):
 main,ports,roots=F.original_port_vtable(original)
 F.verify_vtable_fanout(original,main,ports,roots)
 ptr=lambda mods,slot:F.CTOR.read_data_pointer(original,main,mods['a9']['vptr']+slot)
 if ptr(ports,104)!=ports['embedded']['vm']+0x4918:raise ValueError('Port initializer changed')
 if ptr(roots,1864)!=roots['shared']['vm']+0xd0:raise ValueError('Root port-resource selector changed')
 if ptr(ports,1784)!=ports['shared']['vm']+0x159c:raise ValueError('Port control accessor changed')
 if ptr(ports,1496)!=ports['shared']['vm']+0x1444:raise ValueError('Port status accessor changed')
 F.check_words(ports['shared']['code'])
 check_words(ports['embedded']['code'],EMBEDDED)
 check_words(ports['shared']['code'],SHARED)
 resources=MEM.compare_private_inputs(root,adt)
 if resources[3]!=(0x602000000,0x4000):raise ValueError('Port1 aperture mismatch')
 return True
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('original_macho','original_adt','original_root_plist'):p.add_argument(name,type=Path)
 a=p.parse_args()
 try:audit(a.original_macho.read_bytes(),a.original_adt.read_bytes(),a.original_root_plist.read_bytes())
 except (OSError,ValueError,KeyError,IndexError):print('N71_PORT_LOCAL_MMIO_SOURCE_REJECTED');return 2
 print('N71_PORT_INSTANCE_LOCAL_MMIO_SOURCE_PASS')
 print('PORT_OBJECT_MAP200_VIRTUAL208_PHYSICAL216_FROM_ROOT_SLOT1864')
 print('PORT1_RESOURCE_INDEX=3 BASE=0x602000000 SIZE=0x4000')
 print('ORIGINAL_PORT_CONTROL_0X80_BIT0_AND_STATUS_0X88_BIT0_SOURCE_PASS')
 print('PHYSICAL_LINK_OR_REQUESTER_SID_PROVEN=NO')
 return 0
if __name__=='__main__':raise SystemExit(main())
