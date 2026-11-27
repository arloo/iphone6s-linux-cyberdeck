# SPDX-License-Identifier: MIT
import copy
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('reserve_gate',ROOT/'scripts/n71_storage_full_reserve_gate.py');G=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(G)
def fixture():
    return [dict(uptime_s=100+2*i,capacity=94,current_now=-320000,voltage_now=4000000,temp=330,health='Good',charge_now=1050000-1000*(i//4),charge_full=1117000,status='Discharging',udc='configured') for i in range(8)]
class ReserveGateTests(unittest.TestCase):
    def test_full_battery_without_active_charger_has_explicit_conservative_energy_margin(self):
        r=G.qualify(fixture());self.assertEqual(r['samples'],8);self.assertEqual(r['planning_charge_uAh'],33334);self.assertEqual(r['minimum_reserve_windows'],1049000//33334)
        self.assertFalse(r['charger_rearm_authorized'] or r['physical_endurance_qualified'])
    def test_each_electrical_gauge_status_and_identity_measurement_failure_refuses(self):
        cases=[('capacity',89),('capacity',101),('capacity',98),('charge_now',999999),('charge_now',1118000),('charge_full',1200000),('current_now',-500001),('current_now',500001),('voltage_now',3599999),('voltage_now',4100000),('temp',99),('temp',350),('health','Unknown'),('status','Unknown'),('udc','not attached')]
        for k,v in cases:
            s=fixture();s[4][k]=v
            with self.subTest(k=k,v=v),self.assertRaises(ValueError):G.qualify(s)
    def test_missing_nonfinite_boolean_sparse_or_reordered_samples_refuse(self):
        for v in [None,[],fixture()[:7]]:
            with self.assertRaises(ValueError):G.qualify(v)
        for k,v in [('uptime_s',float('nan')),('uptime_s',float('inf')),('uptime_s',True),('uptime_s',105),('capacity',True),('charge_now','1050000')]:
            s=fixture();s[4][k]=v
            with self.subTest(k=k,v=v),self.assertRaises(ValueError):G.qualify(s)
        s=fixture();s[-1]['uptime_s']=200
        with self.assertRaises(ValueError):G.qualify(s)
        s=fixture();del s[3]['health']
        with self.assertRaises(ValueError):G.qualify(s)
    def test_gauge_drift_and_full_window_energy_units_are_independently_bounded(self):
        s=fixture();s[4]['charge_now']-=6000
        with self.assertRaises(ValueError):G.qualify(s)
        s=fixture();s[4]['charge_full']+=2000
        with self.assertRaises(ValueError):G.qualify(s)
        s=fixture()
        for q in s:q['capacity']=90;q['charge_now']=1000000;q['charge_full']=1111000;q['voltage_now']=3600000;q['temp']=100;q['current_now']=-500000
        r=G.qualify(s);self.assertGreaterEqual(r['minimum_reserve_windows'],25);self.assertLessEqual(r['planning_current_uA']*r['planning_duration_s']/3600,r['planning_charge_uAh'])

    def test_FCC_learning_between_windows_does_not_hide_the_same_large_absolute_reserve(self):
        first=fixture();second=fixture()
        for q in first:q['capacity']=97;q['charge_now']=1080000;q['charge_full']=1117000
        for q in second:q['capacity']=87;q['charge_now']=1096000;q['charge_full']=1261000
        self.assertGreaterEqual(G.qualify(first)['minimum_reserve_windows'],25)
        self.assertGreaterEqual(G.qualify(second)['minimum_reserve_windows'],25)
        for q in second:q['capacity']=49;q['charge_now']=1000000;q['charge_full']=2000000
        with self.assertRaises(ValueError):G.qualify(second)

    def test_seventeen_read_protocol_has_its_own_five_minute_energy_model(self):
        r=G.qualify(fixture(),plan="cq-wrap-17")
        self.assertEqual(r["trial_plan"],"cq-wrap-17")
        self.assertEqual(r["planning_duration_s"],300)
        self.assertEqual(r["planning_charge_uAh"],83334)
        self.assertEqual(r["required_reserve_windows"],10)
        self.assertEqual(r["minimum_reserve_windows"],1049000//83334)
        self.assertGreaterEqual(r["minimum_reserve_windows"],10)
        self.assertFalse(r["charger_rearm_authorized"] or r["physical_endurance_qualified"])

    def test_protocol_selection_cannot_shorten_or_invent_the_energy_model(self):
        for p in [None,True,17,"", "17", "cq-wrap", "four-read-1s", 0, []]:
            with self.subTest(plan=p),self.assertRaises(ValueError):G.qualify(fixture(),plan=p)
        r=G.qualify(fixture())
        self.assertEqual((r["planning_duration_s"],r["required_reserve_windows"]),(120,25))

    def test_wrap_protocol_retains_absolute_reserve_and_electrical_gauge_limits(self):
        for k,v in [("charge_now",999999),("capacity",49),("current_now",-500001),("voltage_now",4100000),("temp",350),("udc","not attached"),("health","Unknown")]:
            s=fixture();s[4][k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):G.qualify(s,plan="cq-wrap-17")
        s=fixture()
        for q in s:q.update(capacity=80,charge_now=1000000,charge_full=1250000)
        r=G.qualify(s,plan="cq-wrap-17")
        self.assertEqual(r["minimum_reserve_windows"],11)
