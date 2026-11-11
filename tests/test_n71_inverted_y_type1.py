"""Synthetic signed Y and N71 Type-1 report setup checks."""
import unittest
from pathlib import Path
PATCH=(Path(__file__).resolve().parents[1] /
       "patches/0010-n71-inverted-y-metrics-type1-report-setup-rfc.patch")

def accepted(l,r,t,b):
    x=abs(r-l)
    y=abs(b-t)
    return 512<=x<=20000 and 512<=y<=20000 and abs(x*1334-y*750)*10<=y*750

def normalized(raw,start,end,m):
    return max(0,min(m,(raw-start)*m//(end-start)))

def frame(report,bytes_):
    buf=bytearray(16)
    buf[:3]=bytes((0xe4,report,len(bytes_)))
    buf[3:3+len(bytes_)]=bytes_
    buf[-2:]=sum(buf[:14]).to_bytes(2,'little')
    return bytes(buf)

class N71Type1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch=PATCH.read_text()
        cls.added="\n".join(x[1:] for x in cls.patch.splitlines()
                            if x.startswith("+") and not x.startswith("+++"))

    def test_reverse_y(self):
        self.assertTrue(accepted(0,750,1334,0))
        self.assertTrue(accepted(750,0,0,1334))
        self.assertTrue(accepted(-3,747,1331,-3))

    def test_reject_bad_geometry(self):
        for vals in ((0,500,0,8000),(0,20001,0,35000),
                     (0,100,0,100),(0,800,0,800),(0,750,0,0)):
            with self.subTest(vals=vals):
                self.assertFalse(accepted(*vals))

    def test_axis_mapping(self):
        self.assertEqual(normalized(1334,1334,0,1333),0)
        self.assertEqual(normalized(0,1334,0,1333),1333)
        self.assertEqual(normalized(750,0,750,749),749)

    def test_reports(self):
        c=frame(0x9d,bytes((1,0,0,0,0,0,0,0)))
        self.assertEqual(c[:4],bytes.fromhex("e49d0801"))
        self.assertEqual(c[-2:],sum(c[:14]).to_bytes(2,'little'))
        d=frame(0xbf,bytes.fromhex("9d810900"))
        self.assertEqual(d[:7],bytes.fromhex("e4bf049d810900"))
        self.assertEqual(d[-2:],sum(d[:14]).to_bytes(2,'little'))

    def test_guards_in_kernel_source_patch(self):
        required=("static DEVICE_ATTR_WO(runtime_type1_setup)",
                  "z2->n71_type1_attempted = true;",
                  "z2->n71_d9_fetch_mode != 1",
                  "n71_d9_y_reversed = dy < 0",
                  "aspect_delta * 10 <= ay * 750",
                  "clamp(px, 0, mx)", "clamp(py, 0, my)",
                  "!z2->n71_type1_attempted || z2->n71_type1_rc")
        for x in required:
            with self.subTest(x=x):
                self.assertIn(x,self.added)

    def test_privacy_and_no_retries(self):
        for bad in ("while (","for (;;)","gpiod_set_value(",
                    "regulator_enable(","request_firmware(","print_hex_dump(",
                    "%*ph","left=-248","right=5594","top=10159",
                    "bottom=-238","@gmail","ECID:"):
            self.assertNotIn(bad,self.added)

if __name__=="__main__":
    unittest.main()
