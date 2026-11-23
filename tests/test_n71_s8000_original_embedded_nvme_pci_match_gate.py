# SPDX-License-Identifier: MIT
"""Fail-closed source requirements for N71 AppleEmbeddedNVMeController.

The exact owner-original kernelcache is checked separately; synthetic
instruction fixtures are not hardware or actual iOS runtime proof.
"""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import n71_s8000_original_embedded_nvme_pci_match_gate as M
import n71_s8000_original_ionvme_read_source_gate as READ


class N71EmbeddedPersonalityTests(unittest.TestCase):
    def test_each_constructor_vtable_instruction_is_guarded(self):
        self.assertEqual(len(M.PINNED_WORDS), 9)
        code = bytearray(READ.EXPECTED_TEXT_SIZE)
        for at, word in M.PINNED_WORDS.items():
            struct.pack_into('<I', code, at, word)
        M.verify_words(bytes(code))
        for at in M.PINNED_WORDS:
            with self.subTest(at=hex(at)):
                broken = bytearray(code)
                broken[at] ^= 1
                with self.assertRaises(ValueError):
                    M.verify_words(bytes(broken))
        with self.assertRaises(ValueError):
            M.verify_words(bytes(code[:0x31384]))
        with self.assertRaises(READ.RejectedOriginalNVMeSource):
            READ.verify_true_original_text(bytes(code))

    def test_original_personality_matches_real_endpoint_id_but_not_live_binding(self):
        self.assertEqual(M.EXPECTED_IOCLASS, 'AppleEmbeddedNVMeController')
        self.assertEqual(M.EXPECTED_VENDOR_DEVICE_MATCH, '0x2002106b')
        self.assertEqual(M.PHYSICAL_PCI_VENDOR_DEVICE, 0x2002106b)
        self.assertEqual(M.EXPECTED_PCI_CLASS_MATCH, '0x01800200&0xffffff00')
        expected, mask = M.EXPECTED_PCI_CLASS_MATCH.split('&')
        self.assertEqual(M.MODEL_CLASS_REVISION & int(mask,16), int(expected,16))
        self.assertEqual(M.EMBEDDED_PARENT_CTOR, 0x31158)
        self.assertEqual(M.VIRTUAL_METHOD_SLOT, 1440)
        self.assertEqual(M.EXPECTED_EMBEDDED_VMETHOD, 0x31384)

    def test_source_explicitly_disallows_nand_access_and_runtime_claims(self):
        source = (ROOT/'tools/n71_s8000_original_embedded_nvme_pci_match_gate.py').read_text()
        self.assertIn('IOS_RUNTIME_DRIVER_BINDING_PROVEN=NO',source)
        self.assertIn('FIRST_NAND_READ_AUTHORIZED=NO',source)
        self.assertNotIn('writel(',source)
        self.assertNotIn('dma_map_single(',source)

if __name__ == '__main__':
    unittest.main()
