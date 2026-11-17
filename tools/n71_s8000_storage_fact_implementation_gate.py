#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the real N71/S8000 DART and NVMe MMU Fact implementations.

Private original kernelcache and Apple ADT inputs only. This verifies
source provenance and state-restoration side effects, never a live
Linux activation sequence. No device, MMIO, GPIO or NAND access.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import n71_original_dart_mapper_tcr_lane_gate as DART
import n71_s8000_storage_force_active_chain_gate as STORAGE

class RejectedSource(ValueError):
    pass

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RejectedSource(message)

# Minimal original instruction identities, not executable payloads.
FAMILY_WORDS = {
    0x254: 0xb0ffbbc1, 0x258: 0x913c7021,
    0x268: 0xb4000080, 0x26c: 0xb9494268,
    0x270: 0x32010108, 0x274: 0xb9094268,
    0x1c20: 0x528c6e89, 0x1c24: 0x72a8cc29,
    0x1c28: 0x6b09011f, 0x1c2c: 0x54000740,
    0x1d1c: 0xb4fffb36, 0x1d20: 0xb5fffb14,
    0x1d24: 0xb5fffaf5, 0x1d28: 0xb94002c8,
    0x1d2c: 0x7100011f, 0x1d30: 0x1a9f07e1,
    0x1d34: 0xf9400268, 0x1d38: 0xf9430108,
    0x1d3c: 0xaa1303e0, 0x1d40: 0xd63f0100,
}
S5L_WORDS = {
    0x1d94: 0xb9494008, 0x1d98: 0x36f802c8,
    0x1d9c: 0xaa0103f4, 0x1db0: 0x39254a74,
    0x1db8: 0xf9436908, 0x1dc0: 0xd63f0100,
    0x1dd4: 0x39254a74, 0x1ddc: 0xf9436901,
    0x1dec: 0xd61f0020,
    0x1cd4: 0xb9494268, 0x1cd8: 0x37f801c8,
    0x1d10: 0x39654a68, 0x1d14: 0x396a0269,
    0x1d18: 0x6b08013f, 0x1d1c: 0x54000180,
    0x1d20: 0x350000c8, 0x1d24: 0x52801a48,
    0x1d38: 0x52801a68, 0x1d40: 0xf8687928,
    0x39b8: 0xf9405a60, 0x39c0: 0xf942b508,
    0x39c4: 0x52800021, 0x39cc: 0xd63f0100,
    0x39d0: 0xf9405a60, 0x39d8: 0xf942b908,
    0x39dc: 0x52800021, 0x39e8: 0xd63f0100,
    0x39f4: 0xf9435508, 0x3a00: 0xd63f0100,
    0x3bbc: 0xb94ae668, 0x3bc0: 0xf9456a69,
    0x3bc4: 0xb9000d28, 0x3bc8: 0xb9400d28,
    0x3bd4: 0x7201c11f, 0x3bd8: 0x540006e1,
}
SHARED_WORDS = {
    0x2060: 0xf941e908, 0x2068: 0x52800001,
    0x206c: 0x52800002, 0x2070: 0xd63f0100,
    0x2074: 0xf9006a60, 0x2080: 0xf9403d08,
    0x2084: 0xd63f0100, 0x2088: 0xf9006e60,
    0x2df0: 0x528c6e89, 0x2df4: 0x72a8cc29,
    0x2df8: 0x6b09011f, 0x2dfc: 0x54fffb21,
    0x3730: 0xd0ffb4e1, 0x3734: 0x912fb821,
    0x38c4: 0xb4000161, 0x38d0: 0xb9400028,
    0x38d4: 0x7100011f, 0x38d8: 0x1a9f07e1,
    0x38dc: 0xf9401400, 0x38e0: 0x97ffff6b,
    0x3920: 0xf9400a60, 0x3930: 0xf9001660,
    0x3698: 0x39455408, 0x369c: 0x6b01011f,
    0x36a0: 0x540002c0, 0x36a8: 0x39055401,
    0x36ac: 0x34000261, 0x36b0: 0xf940ae68,
    0x36b4: 0xf9406e69, 0x36b8: 0xb9001128,
    0x36bc: 0xb940113f, 0x36c0: 0xd360fd08,
    0x36c4: 0xb9001528, 0x36c8: 0xb940153f,
    0x36cc: 0xf940b261, 0x36d4: 0x97fffc45,
    0x36d8: 0x3945a261, 0x36dc: 0xb9416e62,
    0x36e0: 0xb9417263, 0x36e4: 0xb9417664,
    0x36f4: 0x17fffc20,
    0x27f4: 0xf9406c08, 0x27f8: 0xb9000901,
    0x27fc: 0xb940091f, 0x2800: 0xd360fc29,
    0x2804: 0xb9000d09, 0x2808: 0xb9400d1f,
    0x280c: 0x52a00029, 0x2810: 0xb9000509,
    0x2814: 0xb940051f, 0x2818: 0xb9400509,
    0x281c: 0x3787ffe9,
    0x2784: 0x39455408, 0x2788: 0x340001a8,
    0x2790: 0x34000121, 0x2794: 0xb9002502,
    0x27a0: 0xb9002909, 0x27ac: 0xb9002d09,
    0x27b4: 0xb9002101,
}
S5L_METHODS = {
    1536: 0x1d84, 1744: 0x1cb4,
    1680: 0x3a7c, 1688: 0x3984, 1704: 0x3b68,
}

def word(code: bytes, at: int) -> int:
    require(at >= 0 and at % 4 == 0 and at + 4 <= len(code),
            "Original instruction outside executable bounds")
    return struct.unpack_from("<I", code, at)[0]

def check_words(code: bytes, expected: dict[int, int]) -> None:
    for at, value in expected.items():
        require(word(code, at) == value,
                "Original Fact implementation changed")

def vptr(module: dict, at: int) -> int:
    return DART.G.adrp_add_str_vptr(
        module["vm"] + at, *(word(module["code"], at + i) for i in (0, 4, 8)))

def check_literal(kernel: bytes, main: dict, module: dict,
                  at: int, expected: bytes) -> None:
    code = module["code"]
    va = DART.G.adrp_target(module["vm"] + at, word(code, at), 1)
    add = word(code, at + 4)
    require(add & 0xffc003ff == 0x91000021,
            "Original callback class/property literal changed")
    va += (add >> 10) & 0xfff
    pre = main["__PRELINK_TEXT"]
    require(pre["vm"] <= va and
            va + len(expected) <= pre["vm"] + pre["filesize"],
            "Original literal is outside prelinked text")
    off = pre["offset"] + va - pre["vm"]
    require(kernel[off:off + len(expected)] == expected,
            "Original callback class/property identity changed")

def check_poll(code: bytes) -> None:
    # The complete original polling block contains exactly LDR + TBNZ.
    # An unchanged bit16 loops back without a counter/deadline in this block.
    branch = word(code, 0x281c)
    require(word(code, 0x2818) == 0xb9400509 and branch == 0x3787ffe9,
            "Original NVMe MMU invalidate loop changed")
    displacement = (branch >> 5) & 0x3fff
    if displacement & 0x2000:
        displacement -= 0x4000
    require(0x281c + displacement * 4 == 0x2818,
            "Original invalidate branch no longer loops to its read")

def audit(kernel: bytes, adt: bytes) -> None:
    STORAGE.audit(kernel, adt)
    DART.verify_original_code(kernel)
    main, modules = DART.extract_original_modules(kernel)
    family, s5l = modules[DART.FAMILY], modules[DART.S5L]
    _, port, _ = STORAGE.FANOUT.original_port_vtable(kernel)
    shared = port["shared"]
    check_words(family["code"], FAMILY_WORDS)
    check_words(s5l["code"], S5L_WORDS)
    check_words(shared["code"], SHARED_WORDS)
    check_literal(kernel, main, family, 0x254, b"manual-availability\0")
    check_literal(kernel, main, shared, 0x3730,
                  b"AppleNVMeMMUActivateFunction\0")
    nodes = STORAGE.ADT.parse_adt(adt)
    require(nodes[STORAGE.ADT.ROOT + "dart-apcie0"].get(
        "manual-availability") == struct.pack("<I", 1),
        "Original storage DART manual-availability property changed")
    require(nodes[STORAGE.ADT.ROOT + "nvme-mmu0"].get("reg") ==
            struct.pack("<QQQQ", 0x601004000, 0x4000, 0x601000000, 0x4000),
            "Original NVMe MMU resource mapping changed")
    dart_vp = vptr(s5l, 0x44)
    for slot, relative in S5L_METHODS.items():
        require(DART.G.read_data_pointer(kernel, main, dart_vp + slot) ==
                s5l["vm"] + relative,
                "Actual constructed DART Fact virtual route changed")
    nv_vp = vptr(shared, 0x376c)
    require(nv_vp == vptr(shared, 0x2e24),
            "Fact factory and actual activation-function vtables differ")
    require(DART.G.read_data_pointer(kernel, main, nv_vp + 128) ==
            shared["vm"] + 0x38c4,
            "Actual NVMe MMU callback virtual target changed")
    check_poll(shared["code"])

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_kernelcache", type=Path)
    parser.add_argument("original_apple_adt", type=Path)
    args = parser.parse_args()
    try:
        require(20_000_000 < args.original_kernelcache.stat().st_size < 150_000_000
                and 1000 < args.original_apple_adt.stat().st_size < 200_000,
                "Original input sizes unsupported")
        audit(args.original_kernelcache.read_bytes(),
              args.original_apple_adt.read_bytes())
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        print("N71_DART_NVMMU_FACT_IMPLEMENTATION_SOURCE_GATE=REJECTED")
        return 1
    print("N71_DART_NVMMU_FACT_IMPLEMENTATION_SOURCE_GATE=PASS")
    print("DART_FACT_MANUAL_AVAILABILITY_AND_VSLOT1536_ROUTE=VERIFIED")
    print("DART_ACTIVE_PATH_PROVIDER_OPERATIONS_AND_REGISTER_RESTORE=VERIFIED")
    print("NVMMU_FACT_REAL_CALLBACK_TO_STATE_RESTORE=VERIFIED")
    print("NVMMU_FIRST_ORIGINAL_MMIO_RESOURCE=0x601004000")
    print("NVMMU_ADDRESS_RESTORE_OFFSETS=0x10,0x14,0x08,0x0c")
    print("NVMMU_INACTIVE_BRANCH_REVERSES_REGISTER_WRITES=NO")
    print("NVMMU_INVALIDATE_REGISTER_0x04_BIT16_POLL_HAS_NO_LOCAL_DEADLINE=YES")
    print("LINUX_PORT0_ENABLE_AND_DMA_ISOLATION_QUALIFIED=NO")
    print("PHYSICAL_HARDWARE_OR_NAND_ACCESSED=NO")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
