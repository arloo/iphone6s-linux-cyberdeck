# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('dfu_boot_gate',ROOT/'scripts/n71_recent_dfu_boot_gate.py');G=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(G)
IMAGE='1'*64

def fixture():
 return dict(candidate_image_sha256=IMAGE,power_observed_at_epoch=1000,old_Linux_disconnect_at_epoch=1020,DFU_enumeration_at_epoch=1023,identity_verified=True,board_verified=True,same_USB_port_verified=True,encrypted_finished_backup_verified=True,previous_epoch_attested=True,native_cleanup_before_transition=False,power=dict(capacity=82,charge_now=1025000,current_now=0,voltage_now=4090000,temp=337,health='Good',status='Not charging'))

class RecentDFUBootGateTests(unittest.TestCase):
 def test_realistic_already_entered_DFU_admits_boot_without_inventing_native_rollback(self):
  r=G.qualify(fixture(),now=1360,candidate_sha256=IMAGE)
  self.assertTrue(r['RAM_boot_only']);self.assertEqual(r['age_s'],360)
  self.assertFalse(r['native_rollback_inferred'] or r['NAND_IO_authorized'] or r['charger_rearm_authorized'])
 def test_each_identity_port_backup_and_epoch_witness_must_be_exactly_true(self):
  for k in ['identity_verified','board_verified','same_USB_port_verified','encrypted_finished_backup_verified','previous_epoch_attested']:
   for value in [None,False,1,'True']:
    s=fixture();s[k]=value
    with self.subTest(k=k,v=value),self.assertRaises(ValueError):G.qualify(s,now=1360,candidate_sha256=IMAGE)
 def test_stale_future_reordered_and_nonfinite_event_times_refuse(self):
  for now in [999,1022,1900.001,float('nan'),float('inf'),True]:
   with self.subTest(now=now),self.assertRaises(ValueError):G.qualify(fixture(),now=now,candidate_sha256=IMAGE)
  for k,v in [('power_observed_at_epoch',1021),('old_Linux_disconnect_at_epoch',1024),('DFU_enumeration_at_epoch',float('nan')),('power_observed_at_epoch',True)]:
   s=fixture();s[k]=v
   with self.subTest(k=k),self.assertRaises(ValueError):G.qualify(s,now=1360,candidate_sha256=IMAGE)
 def test_mismatched_candidate_missing_schema_and_measurement_types_refuse(self):
  with self.assertRaises(ValueError):G.qualify(fixture(),now=1360,candidate_sha256='2'*64)
  for digest in [None,True,'','1'*63,'g'*64]:
   with self.assertRaises(ValueError):G.qualify(fixture(),now=1360,candidate_sha256=digest)
  for s in [None,{},dict(fixture(),power=None)]:
   with self.assertRaises(ValueError):G.qualify(s,now=1360,candidate_sha256=IMAGE)
  for k in ['capacity','charge_now','current_now','voltage_now','temp']:
   s=fixture();s['power'][k]=True
   with self.subTest(k=k),self.assertRaises(ValueError):G.qualify(s,now=1360,candidate_sha256=IMAGE)
 def test_low_reserve_and_all_electrical_or_gauge_failure_classes_refuse(self):
  for k,v in [('capacity',49),('capacity',101),('charge_now',999999),('current_now',500001),('current_now',-500001),('voltage_now',3599999),('voltage_now',4200000),('temp',99),('temp',350),('health','Unknown'),('status','Unknown')]:
   s=fixture();s['power'][k]=v
   with self.subTest(k=k,v=v),self.assertRaises(ValueError):G.qualify(s,now=1360,candidate_sha256=IMAGE)
 def test_finite_time_and_reserve_boundaries_still_authorize_only_RAM_boot(self):
  s=fixture();s['power'].update(capacity=50,charge_now=1000000,current_now=-500000,voltage_now=3600000,temp=100)
  for now in [1023,1900]:
   r=G.qualify(s,now=now,candidate_sha256=IMAGE);self.assertTrue(r['RAM_boot_only']);self.assertFalse(r['NAND_IO_authorized'])
